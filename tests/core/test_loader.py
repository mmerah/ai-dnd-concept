from collections.abc import Mapping
from pathlib import Path
from random import Random

from aidm.content.authored import Rules
from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import EngineId, EntityId
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState


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
    assert engine.subsystems == ()
    # The world half of the brief is core's, so every engine teaches it whatever else it owns.
    assert "Test procedure." in engine.director_instructions
    assert "## World effects" in engine.director_instructions
