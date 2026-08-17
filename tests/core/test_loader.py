from pathlib import Path
from random import Random

from aidm.engines.loader import Engine
from aidm.engines.sheets import SheetBase, SheetMechanics
from aidm.state.base import Counter, EngineId, Entity, Frozen, Slug
from aidm.state.plan import Resolution
from aidm.state.world import GameState


class NoSheet(SheetBase):
    def counters(self) -> dict[Slug, Counter]:
        return {}


def _engine(tmp_path: Path) -> Engine[NoSheet]:
    """Only the procedure: no packs, no examples, and no advancement file, because an
    engine played from the fiction alone must load without content ceremony."""
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")

    class BareEngine(Engine[NoSheet]):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        engine_dir = tmp_path
        actions = {}
        sheet_type = NoSheet
        mechanics_type = SheetMechanics[NoSheet]

        def new_sheet(self, draft: GameState, rng: Random) -> NoSheet:
            del draft, rng
            return NoSheet()

        def describe(self, state: GameState, entity: Entity) -> str:
            del state, entity
            return ""

        def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
            del draft, roll, rng
            return Resolution()

    return BareEngine()


def test_an_engine_without_content_loads_and_advertises_no_tool(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert engine.director_toolsets == ()
    assert engine.advancement is None
    assert engine.creation is None
    # The world half of the brief is core's, so every engine teaches it whatever else it owns.
    assert "Test procedure." in engine.director_instructions
    assert "## Effects" in engine.director_instructions
