from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue, TypeAdapter

from aidm.engines.loader import WORLD_EXAMPLES, Engine, EntityRenderer, engine_text
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.effects import WorldEffect, effect_key, effect_keys
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase
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
        plan_type = TurnPlanBase
        rules_type = NoRules
        engine_dir = tmp_path

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


def test_the_shared_examples_teach_every_world_effect() -> None:
    """Adding an op is a union member, an apply case, and one worked example here."""
    entries = TypeAdapter(list[WorldEffect]).validate_json(engine_text(WORLD_EXAMPLES))
    assert {effect_key(entry) for entry in entries} == effect_keys(WorldEffect.__value__)
