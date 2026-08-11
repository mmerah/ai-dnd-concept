import json
from collections.abc import Mapping
from pathlib import Path
from random import Random

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from aidm.content.authored import Rules
from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import EngineId, EntityId
from aidm.state.facts import Fact
from aidm.state.packs import Manifest, Pack, read_pack, validate_pack, write_pack
from aidm.state.packs import Record as PackRecord
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState

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
            "giant-rat": PackRecord(
                index="giant-rat",
                name="Giant Rat",
                text="Keen smell, pack tactics.",
                facts={
                    "armor-class": 12,
                    "hp": 7,
                    "attacks": "Bite +4 to hit, 1d4+2 piercing",
                },
            )
        }
    },
)
SPEC: dict[str, object] = {"collections": {"monsters": {}}}


def _engine_dir(tmp_path: Path) -> Path:
    """Only the spec and the procedure: no examples and no advancement file, because an engine
    that offers neither must still load."""
    (tmp_path / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")
    write_pack(tmp_path / "packs" / "testpack", PACK)
    return tmp_path


def _engine(tmp_path: Path) -> Engine:
    """A pack loader test needs no procedure, so this engine resolves nothing."""

    class PackEngine(Engine):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        plan_type = TurnPlanBase
        engine_dir = _engine_dir(tmp_path)

        def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None: ...

        def commit(self, state: GameState) -> None: ...

        def renderer(self, state: GameState) -> EntityRenderer:
            return lambda entity: ""

        def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
            return None

        def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
            return []

    return PackEngine()


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
    # Semicolons, because a value carries commas of its own.
    assert "facts: armor-class=12; attacks=Bite +4 to hit, 1d4+2 piercing; hp=7" in rendered
    assert "Keen smell, pack tactics." in rendered
    with pytest.raises(ModelRetry, match="pack/collection/index"):
        _ = await _read_content(toolset, "malformed")
    with pytest.raises(ModelRetry, match="missing content"):
        _ = await _read_content(toolset, "testpack/monsters/absent")


def test_validate_pack_refuses_a_record_missing_a_required_fact() -> None:
    with pytest.raises(ValueError, match="required int fact 'challenge'"):
        validate_pack(PACK, {"monsters": {"challenge": "int"}})


def test_a_pack_round_trips_byte_for_byte(tmp_path: Path) -> None:
    pack_dir = _engine_dir(tmp_path) / "packs" / "testpack"

    pack = read_pack(pack_dir, {"monsters": {}})
    other_dir = tmp_path / "roundtrip"
    write_pack(other_dir, pack)

    for name in ("manifest.json", "monsters.json"):
        assert (other_dir / name).read_bytes() == (pack_dir / name).read_bytes()
