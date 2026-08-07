import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from aidm.content.authored import AuthoredEntity, AuthoredWorld
from aidm.engines.loader import Engine, EnginePlugin, load_engine
from aidm.state.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId, Slug
from aidm.state.packs import (
    ContentRef,
    Manifest,
    Pack,
    pack_format,
    read_pack,
    validate_pack,
    write_pack,
)
from aidm.state.packs import Record as PackRecord
from aidm.state.sheet import Counter, Sheet
from aidm.state.world import GameState, Record, ScenarioMeta, WorldState


class Monster(PackRecord):
    """A test engine's record class: the loader must read any engine's shape polymorphically."""

    hp: int
    armor_class: int
    attacks: str

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {"armor-class": self.armor_class, "hp": self.hp}

    def noted(self) -> Mapping[Slug, str]:
        return {"attacks": self.attacks}


PACK = Pack(
    manifest=Manifest(
        id="testpack",
        name="Test Pack",
        version="1.0.0",
        edition="test",
        provides={"monsters": 1},
    ),
    records={
        "monsters": {
            "giant-rat": Monster(
                index="giant-rat",
                name="Giant Rat",
                text="Keen smell, pack tactics.",
                hp=7,
                armor_class=12,
                attacks="Bite +4 to hit, 1d4+2 piercing",
            )
        }
    },
)

SPEC: dict[str, object] = {
    "templates": {
        "actor": {
            "numbers": {"armor-class": 10},
            "counters": {"hp": {"current": 1, "maximum": 1, "recharge": "long-rest"}},
        },
    },
    "collections": {"monsters": {}},
}


def _engine_dir(tmp_path: Path) -> Path:
    (tmp_path / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")
    (tmp_path / "advancement.md").write_text("Test growth.\n", encoding="utf-8")
    (tmp_path / "examples.json").write_text("[]\n", encoding="utf-8")
    write_pack(tmp_path / "packs" / "testpack", PACK)
    return tmp_path


def _engine(tmp_path: Path) -> Engine:
    """A pack loader test needs no procedure, so this engine resolves nothing."""
    plugin = EnginePlugin(
        id=EngineId("test"),
        badge=("TEST", "grey-6"),
        engine_dir=_engine_dir(tmp_path),
        actions=(),
        action_doc="",
        offered=lambda engine, state: None,
        check_delta=lambda state, delta: None,
        record_types={"monsters": Monster},
    )
    return load_engine(plugin)


def _minimal_state(engine: Engine, player_sheet: Sheet) -> GameState:
    vault = Entity(id=EntityId("vault"), kind="location", name="Vault", brief="", known=True)
    player = Entity(
        id=PLAYER_ID, kind="actor", name="Kael", brief="", known=True, parent_id=vault.id
    )
    world = WorldState(
        records={
            vault.id: Record(entity=vault, rules=Sheet(kind="location")),
            PLAYER_ID: Record(entity=player, rules=player_sheet),
        }
    )
    return GameState(
        save_version=SAVE_VERSION,
        scenario_id="vault",
        character_id="kael",
        scenario=ScenarioMeta(title="T", premise="P"),
        engine=engine.id,
        world=world,
    )


def test_default_rules_gives_a_grown_actor_the_templates_canonical_keys(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    actor = Entity(id=EntityId("goblin"), kind="actor", name="Goblin", brief="", known=True)

    sheet = engine.default_rules(actor)

    assert sheet.counters["hp"] == Counter(current=1, maximum=1, recharge="long-rest")
    assert sheet.numbers["armor-class"] == 10


def test_an_authored_ref_backs_the_sheet_with_numbers_and_renders_its_notes(tmp_path: Path) -> None:
    """Record numbers land on the sheet; notes and tags stay on the record and render by the ref."""
    engine = _engine(tmp_path)
    goblin = Entity(id=EntityId("goblin"), kind="actor", name="Goblin", brief="", known=True)
    authored = AuthoredWorld(
        entities={
            goblin.id: AuthoredEntity(
                entity=goblin,
                rules={
                    "refs": [{"pack": "testpack", "collection": "monsters", "index": "giant-rat"}]
                },
            )
        }
    )

    world = engine.initial_world(authored, {})

    sheet = world.record(goblin.id).rules
    assert sheet.counters["hp"] == Counter(current=7, maximum=7, recharge="long-rest")
    assert sheet.numbers["armor-class"] == 12
    assert sheet.notes == {}
    rendered = engine.entity_state(goblin, sheet)
    assert "- Giant Rat [testpack/monsters/giant-rat] — attacks=Bite +4 to hit" in rendered


def test_validate_state_rejects_a_sheet_missing_a_canonical_key(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    state = _minimal_state(engine, Sheet(kind="actor"))

    with pytest.raises(ValueError, match="canonical keys"):
        engine.validate_state(state)


def test_validate_state_rejects_a_sheet_naming_an_unresolved_ref(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    broken = ContentRef(pack="testpack", collection="monsters", index="missing-monster")
    sheet = Sheet(
        kind="actor",
        numbers={"armor-class": 10},
        counters={"hp": Counter(current=1, maximum=1, recharge="long-rest")},
        refs=(broken,),
    )
    state = _minimal_state(engine, sheet)

    with pytest.raises(ValueError, match="missing content"):
        engine.validate_state(state)


async def _read_content(toolset: AbstractToolset[object], ref: str) -> str:
    """Tools take a `RunContext`; a test builds one instead of running an agent."""
    ctx = RunContext[object](deps=object(), model=TestModel(), usage=RunUsage())
    tools = await toolset.get_tools(ctx)
    rendered = await toolset.call_tool("read_content", {"ref": ref}, ctx, tools["read_content"])
    assert isinstance(rendered, str)
    return rendered


async def test_read_content_renders_the_record_and_refuses_a_bad_ref(tmp_path: Path) -> None:
    toolset = _engine(tmp_path).director_toolset

    rendered = await _read_content(toolset, "testpack/monsters/giant-rat")
    assert rendered.startswith("Giant Rat [testpack/monsters/giant-rat]")
    assert "numbers: armor-class 12, hp 7" in rendered
    assert "Keen smell, pack tactics." in rendered
    with pytest.raises(ModelRetry, match="pack/collection/index"):
        _ = await _read_content(toolset, "malformed")
    with pytest.raises(ModelRetry, match="missing content"):
        _ = await _read_content(toolset, "testpack/monsters/absent")


def test_validate_pack_refuses_a_record_missing_a_required_fact() -> None:
    fmt = pack_format({"monsters": {"challenge": "int"}}, {"monsters": Monster})

    with pytest.raises(ValueError, match="required int fact 'challenge'"):
        validate_pack(PACK, fmt)


def test_a_pack_round_trips_byte_for_byte(tmp_path: Path) -> None:
    pack_dir = _engine_dir(tmp_path) / "packs" / "testpack"
    fmt = pack_format({"monsters": {}}, {"monsters": Monster})

    pack = read_pack(pack_dir, fmt)
    other_dir = tmp_path / "roundtrip"
    write_pack(other_dir, pack)

    for name in ("manifest.json", "monsters.json"):
        assert (other_dir / name).read_bytes() == (pack_dir / name).read_bytes()
