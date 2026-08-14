from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random
from typing import get_args

from pydantic import JsonValue, TypeAdapter

from aidm.engines.loader import WORLD_EXAMPLES, Engine, EntityRenderer, engine_text
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.effects import WorldEffect
from aidm.state.facts import Fact
from aidm.state.plan import Resolution, TurnPlanBase
from aidm.state.world import GameState


def _effect_key(effect: Frozen) -> str:
    """An op, or an op and the mode it is in: what one worked example teaches."""
    dumped = effect.model_dump()
    mode = dumped.get("mode")
    return f"{dumped['op']}/{mode}" if mode else str(dumped["op"])


def _effect_keys(union: object) -> frozenset[str]:
    """Every key an effect union can produce, so a worked example can be demanded per mode."""
    members, _ = get_args(union)
    # A `type X = ...` alias is a TypeAliasType; get_args does not resolve it on its own.
    keys: set[str] = set()
    for member in get_args(getattr(members, "__value__", members)):
        op = member.model_fields["op"].default
        mode = member.model_fields.get("mode")
        if mode is None:
            keys.add(op)
        else:
            keys.update(f"{op}/{value}" for value in get_args(mode.annotation))
    return frozenset(keys)


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
        beat_type = TurnPlanBase
        engine_dir = tmp_path

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

        def check_beat(self, state: GameState, beat: Frozen) -> str | None:
            return None

        def resolve_beat(self, draft: GameState, beat: Frozen, rng: Random) -> Resolution:
            return Resolution()

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
    assert {_effect_key(entry) for entry in entries} == _effect_keys(WorldEffect.__value__)
