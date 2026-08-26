from pathlib import Path

import pytest
from pydantic import JsonValue

from aidm.engines.core import Engine, command
from aidm.state.entities import EngineId, Entity, Frozen, Mutable
from aidm.state.model import Game, WorldState


class BareMechanics(Mutable): ...


def _engine(tmp_path: Path) -> Engine:
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")

    class BareEngine(Engine):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        engine_dir = tmp_path
        mechanics_type = BareMechanics

        def overlay_rows(self, rules: dict[str, JsonValue]) -> tuple[tuple[str, str], ...]:
            del rules
            return ()

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

        def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
            del state
            return ()

    return BareEngine()


def test_an_engine_without_content_loads_and_advertises_no_command(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert engine.director_commands == ()
    assert engine.director_instructions == "Test procedure.\n"


def test_a_command_parameter_the_model_cannot_read_is_refused() -> None:
    class Undescribed(Frozen):
        entity_id: str

    with pytest.raises(ValueError, match="carry no description"):
        _ = command("touch", "Touch a thing.", Undescribed, lambda _deps, _args: "")
