from abc import abstractmethod
from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue, ValidationError

from aidm.state.apply import apply_effect, reveal_target
from aidm.state.base import Entity, EntityId, Frozen
from aidm.state.facts import Fact
from aidm.state.plan import DirectorBeat, Resolution, check_draft
from aidm.state.world import GameState

from .counters import CounterChange, move_pool
from .loader import Engine, EntityRenderer
from .sheets import SheetBase, SheetMechanics, actor_sheets, check_sheets
from .vocabulary import EFFECTS, EngineEffect, TypedBeat, translate


class SheetEngine[S: SheetBase](Engine):
    """An engine whose mechanics are one sheet per actor, and whose rolls it resolves itself."""

    sheet_type: type[S]
    mechanics_type: type[SheetMechanics[S]]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.sheet_type, self.mechanics_type, self.actions
        super().__init__(extra_packs)

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
        return EFFECTS.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return self.apply(draft, EFFECTS.validate_python(effect))

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

    @abstractmethod
    def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
        """Rolls one translated call and mutates the draft."""

    def check_beat(self, state: GameState, beat: DirectorBeat) -> str | None:
        try:
            typed = translate(beat, self.actions)
        except ValidationError as broken:
            return _named(broken)
        except ValueError as refused:
            return str(refused)
        return check_draft(state, lambda draft: self._play(draft, typed, Random(0)))

    def resolve_beat(self, draft: GameState, beat: DirectorBeat, rng: Random) -> Resolution:
        return self._play(draft, translate(beat, self.actions), rng)

    def _play(self, draft: GameState, beat: TypedBeat, rng: Random) -> Resolution:
        """The order the beat runs: the roll first, then what it causes."""
        settled = None if beat.roll is None else self.resolve_roll(draft, beat.roll, rng)
        caused = [fact for effect in beat.effects for fact in self.apply(draft, effect)]
        if settled is None:
            return Resolution(facts=tuple(caused), followup="none")
        return Resolution(
            facts=(*settled.facts, *caused),
            outcome=settled.outcome,
            followup=settled.followup,
        )


def _named(broken: ValidationError) -> str:
    """`check_draft` renders the message alone; a translation fault needs the field it names."""
    first = broken.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}" if where else first["msg"]
