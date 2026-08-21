from pathlib import Path

from pydantic import JsonValue

from aidm.engines.engine import Engine
from aidm.state.model import EngineId, Entity, Game, Mutable, WorldState


class BareMechanics(Mutable): ...


def _engine(tmp_path: Path) -> Engine:
    """Only the procedure: no packs, no examples, no advancement file, and no sheet concept at
    all, because an engine played from the fiction alone must load without content ceremony."""
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")

    class BareEngine(Engine):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        engine_dir = tmp_path
        mechanics_type = BareMechanics

        def check_overlay(self, rules: dict[str, JsonValue]) -> None:
            del rules

        def opening_mechanics(
            self, world: WorldState, player_rules: dict[str, JsonValue]
        ) -> BareMechanics:
            del world, player_rules
            return BareMechanics()

        def validate(self, state: Game) -> None:
            del state

        def describe(self, state: Game, entity: Entity) -> str:
            del state, entity
            return ""

        def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
            del state
            return ()

    return BareEngine()


def test_an_engine_without_content_loads_and_advertises_no_tool(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert engine.director_toolsets == ()
    assert engine.advancement is None
    assert engine.creation is None
    assert engine.director_instructions == "Test procedure.\n"
