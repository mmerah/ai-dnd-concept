from collections.abc import Mapping
from pathlib import Path
from random import Random

import pytest

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


def _engine(tmp_path: Path) -> Engine:
    """Only the procedure: no spec, no packs, no examples, and no advancement file, because an
    engine played from the fiction alone must load without content ceremony."""
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")

    class BareEngine(Engine):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        plan_type = TurnPlanBase
        engine_dir = tmp_path

        def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None: ...

        def commit(self, state: GameState) -> None: ...

        def renderer(self, state: GameState) -> EntityRenderer:
            return lambda entity: ""

        def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
            return None

        def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
            return []

    return BareEngine()


def test_an_engine_without_content_loads_and_advertises_no_tool(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert engine.director_toolsets == ()
    assert engine.advancement is None
    # The world half of the brief is core's, so every engine teaches it whatever else it owns.
    assert "Test procedure." in engine.director_instructions
    assert "## World effects" in engine.director_instructions


def test_validate_pack_refuses_a_record_missing_a_required_fact() -> None:
    with pytest.raises(ValueError, match="required int fact 'challenge'"):
        validate_pack(PACK, {"monsters": {"challenge": "int"}})


def test_a_pack_round_trips_byte_for_byte(tmp_path: Path) -> None:
    pack_dir = tmp_path / "packs" / "testpack"
    write_pack(pack_dir, PACK)

    pack = read_pack(pack_dir, {"monsters": {}})
    other_dir = tmp_path / "roundtrip"
    write_pack(other_dir, pack)

    for name in ("manifest.json", "monsters.json"):
        assert (other_dir / name).read_bytes() == (pack_dir / name).read_bytes()
