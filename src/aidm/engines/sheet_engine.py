from abc import abstractmethod
from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random
from typing import cast

from pydantic import JsonValue, TypeAdapter

from aidm.state.apply import apply_effect, reveal_target
from aidm.state.base import Entity, EntityId, Frozen, Slug
from aidm.state.effects import WorldOp
from aidm.state.facts import Fact
from aidm.state.plan import (
    Branched,
    Resolution,
    Resolver,
    TurnPlanBase,
    check_branched,
    resolve_branched,
)
from aidm.state.world import GameState

from .actions import Action
from .counters import CounterChange, move_pool
from .loader import Engine, EntityRenderer
from .sheets import SheetBase, SheetMechanics, actor_sheets, check_sheets

type EngineEffect = WorldOp | CounterChange


class SheetEngine[S: SheetBase, A: Action](Engine):
    """An engine whose mechanics are one sheet per actor, whose plan's action resolves itself."""

    sheet_type: type[S]
    mechanics_type: type[SheetMechanics[S]]
    effects: TypeAdapter[EngineEffect]
    # Narrowed so a plan carrying the wrong action is a type error; never reassigned.
    plan_type: type[Branched[EngineEffect, A]]  # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.sheet_type, self.mechanics_type, self.effects

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        for rules in payloads:
            _ = self.sheet_type.model_validate(rules)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        sheets = actor_sheets(state, rules, self.sheet_type, self.id)
        state.set_mechanics(self.mechanics_type(sheets=sheets))

    def validate(self, state: GameState) -> None:
        check_sheets(state, state.mechanics_as(self.mechanics_type).sheets, self.id)
        self.check_mechanics(state)

    def check_mechanics(self, state: GameState) -> None:
        """Whatever this engine tracks beyond one sheet per actor."""

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        mechanics = draft.mechanics_as(self.mechanics_type)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        mechanics.sheets[entity.id] = self.new_sheet(draft, rng)

    @abstractmethod
    def new_sheet(self, draft: GameState, rng: Random) -> S: ...

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return self.effects.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return self.apply(draft, self.effects.validate_python(effect))

    def apply(self, draft: GameState, effect: EngineEffect) -> list[Fact]:
        if not isinstance(effect, CounterChange):
            return apply_effect(draft, effect)
        entity, seen = reveal_target(draft, effect.entity_id)
        sheets = draft.mechanics_as(self.mechanics_type).sheets
        return [*seen, *move_pool(sheets.get(entity.id), entity, effect)]

    def renderer(self, state: GameState) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    @abstractmethod
    def describe(self, state: GameState, entity: Entity) -> str: ...

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        typed = self._typed(plan)
        if typed is None:
            return f"this engine answers with a {self.plan_type.__name__}"
        action = typed.action
        labels = frozenset[Slug]() if action is None else action.outcomes
        return check_branched(state, typed, labels, self.apply, self._resolver(action))

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> Resolution:
        typed = self._typed(plan)
        if typed is None:
            raise ValueError(f"a {type(plan).__name__} is no {self.plan_type.__name__}")
        return resolve_branched(draft, typed, self.apply, self._resolver(typed.action), rng)

    def _resolver(self, action: A | None) -> Resolver | None:
        if action is None:
            return None
        return lambda draft, rng: action.resolve(self, draft, rng)

    def _typed(self, plan: TurnPlanBase) -> Branched[EngineEffect, A] | None:
        # `isinstance` narrows to the bare class, dropping the arguments the declaration pins.
        if not isinstance(plan, self.plan_type):
            return None
        return cast("Branched[EngineEffect, A]", plan)
