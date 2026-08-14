from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.facts import Fact
from aidm.state.plan import DirectorBeat, Resolution
from aidm.state.world import GameState


def _engine(tmp_path: Path) -> Engine:
    """Only the procedure: no spec, no packs, no examples, and no advancement file, because an
    engine played from the fiction alone must load without content ceremony."""
    (tmp_path / "director.md").write_text("Test procedure.\n", encoding="utf-8")

    class NoRules(Frozen):
        pass

    class BareEngine(Engine):
        id = EngineId("test")
        badge = ("TEST", "grey-6")
        engine_dir = tmp_path
        actions = {}

        def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
            for rules in payloads:
                _ = NoRules.model_validate(rules)

        def begin(
            self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]
        ) -> None: ...

        def validate(self, state: GameState) -> None: ...

        def seed(self, draft: GameState, entity: Entity, rng: Random) -> None: ...

        def parse_effect(self, effect: JsonValue) -> Frozen:
            raise ValueError(f"this engine applies no effects, unlike {effect!r}")

        def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
            raise ValueError(f"this engine applies no effects, unlike {effect!r}")

        def renderer(self, state: GameState) -> EntityRenderer:
            return lambda entity: ""

        def check_beat(self, state: GameState, beat: DirectorBeat) -> str | None:
            return None

        def resolve_beat(self, draft: GameState, beat: DirectorBeat, rng: Random) -> Resolution:
            return Resolution()

    return BareEngine()


def test_an_engine_without_content_loads_and_advertises_no_tool(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert engine.director_toolsets == ()
    assert engine.subsystems == ()
    # The world half of the brief is core's, so every engine teaches it whatever else it owns.
    assert "Test procedure." in engine.director_instructions
    assert "## Effects" in engine.director_instructions
