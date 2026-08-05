import json
from pathlib import Path

import pytest

from aidm.core.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId
from aidm.core.content import AuthoredEntity, AuthoredWorld
from aidm.core.engine import AdvancementOffer, Engine
from aidm.core.enginepack import load_engine
from aidm.core.packs import (
    Content,
    ContentRef,
    LenientRecord,
    Manifest,
    Pack,
    lenient_format,
    read_pack,
    write_pack,
)
from aidm.core.sheet import Counter, Sheet, SheetDelta
from aidm.core.world import GameState, Record, ScenarioMeta, WorldState

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
            "giant-rat": LenientRecord(
                index="giant-rat",
                name="Giant Rat",
                text="Bite +4, 1d4 piercing.",
                numbers={"hp": 7, "armor-class": 12},
            )
        }
    },
)

SPEC = {
    "templates": {
        "actor": {
            "numbers": {"armor-class": 10},
            "counters": {"hp": {"current": 1, "maximum": 1, "recharge": "long-rest"}},
        },
    },
    "recharge": {"long-rest": ["long-rest"]},
    "collections": ["monsters"],
}


def _offered(state: GameState[Sheet], content: Content) -> AdvancementOffer | None:
    return None


def _check(state: GameState[Sheet], offer: AdvancementOffer, delta: SheetDelta) -> str | None:
    return None


def _engine_dir(tmp_path: Path) -> Path:
    (tmp_path / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")
    (tmp_path / "advancement.md").write_text("Test growth.\n", encoding="utf-8")
    write_pack(tmp_path / "packs" / "testpack", PACK)
    return tmp_path


def _engine(tmp_path: Path) -> Engine[Sheet]:
    return load_engine(_engine_dir(tmp_path), EngineId("test"), offered=_offered, check=_check)


def _minimal_state(engine: Engine[Sheet], player_sheet: Sheet) -> GameState[Sheet]:
    vault = Entity(id=EntityId("vault"), kind="location", name="Vault", brief="", known=True)
    player = Entity(
        id=PLAYER_ID, kind="actor", name="Kael", brief="", known=True, parent_id=vault.id
    )
    world = WorldState[Sheet](
        records={
            vault.id: Record(entity=vault, rules=Sheet(kind="location")),
            PLAYER_ID: Record(entity=player, rules=player_sheet),
        }
    )
    return GameState[Sheet](
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


def test_an_authored_ref_backs_the_sheet_with_the_records_numbers(tmp_path: Path) -> None:
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


def test_lenient_format_round_trips_a_pack_byte_for_byte(tmp_path: Path) -> None:
    pack_dir = _engine_dir(tmp_path) / "packs" / "testpack"
    fmt = lenient_format(("monsters",))

    pack = read_pack(pack_dir, fmt)
    other_dir = tmp_path / "roundtrip"
    write_pack(other_dir, pack)

    for name in ("manifest.json", "monsters.json"):
        assert (other_dir / name).read_bytes() == (pack_dir / name).read_bytes()
