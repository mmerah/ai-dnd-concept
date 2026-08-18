from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue, TypeAdapter, ValidationError
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import Binding, CreatedCharacter
from aidm.content.store import engine_text
from aidm.state.apply import apply_effect
from aidm.state.base import EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.creation import AnyStep, Picks
from aidm.state.effects import is_world_op
from aidm.state.facts import Fact
from aidm.state.plan import DirectorBeat, Resolution, RuleCall, check_draft
from aidm.state.world import GameState

from .advancement import Advancement
from .sheets import SheetBase, SheetMechanics, actor_sheets, check_sheets
from .vocabulary import (
    EFFECTS_CARD,
    ROLLS_CARD,
    WORLD_CALLS,
    TypedBeat,
    card,
    effect_adapter,
    translate,
    translate_effect,
)

ENGINE_MODULES: tuple[str, ...] = (
    "aidm.engines.loner3e.rules",
    "aidm.engines.twentyfourxx.rules",
)
ENGINE = "ENGINE"
WORKED_PLANS = (
    "One plan per turn, each opening its own beat; every beat of a turn is the same shape. Most "
    "beats need few or no effects, and an empty `effects` is a normal answer. But a beat whose "
    "fiction starts or ends a lasting state — a condition taking hold or passing — must write that "
    "trait change: nothing records it otherwise."
)

type EntityRenderer = Callable[[Entity], str]


class Creation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine[S: SheetBase](ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of the
    state core keeps but cannot read. Mechanics are one sheet per actor, and this engine resolves
    its own rolls. What content it needs is its own to load."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    # What a beat's `roll` may name: this engine's own vocabulary, by the name a call gives it.
    actions: ClassVar[Mapping[Slug, type[Frozen]]]
    # What an `effects` entry may name beyond the world ops: this engine's own effects, by name.
    effects: ClassVar[Mapping[Slug, type[Frozen]]] = {}
    sheet_type: type[S]
    mechanics_type: type[SheetMechanics[S]]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.sheet_type, self.mechanics_type, self.actions
        self._effects: TypeAdapter[Frozen] = effect_adapter(self.effects)
        parts = (
            engine_text(self.engine_dir / "director.md"),
            card("Rolls", ROLLS_CARD, self.actions),
            card("Effects", EFFECTS_CARD, {**WORLD_CALLS, **self.effects}),
            self._worked_plans(),
        )
        self.director_instructions: str = "\n\n".join(part for part in parts if part)
        # An engine with content advertises its own lookups; one without teaches the model no tool.
        self.director_toolsets: tuple[AbstractToolset[object], ...] = ()
        # An engine with no growth mechanic plugs in none; the app offers only what it finds.
        self.advancement: Advancement | None = None
        # An engine that creates characters replaces this; the app offers only what it finds.
        self.creation: Creation | None = None

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        for rules in payloads:
            _ = self.sheet_type.model_validate(rules)

    def binding(self) -> Binding:
        return Binding(
            engine=self.id, parse_effect=self.parse_effect, check_overlay=self.check_overlay
        )

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        sheets = actor_sheets(state, rules, self.sheet_type, self.id)
        state.set_mechanics(self.mechanics_type(sheets=sheets))

    def validate(self, state: GameState) -> None:
        check_sheets(state, state.mechanics_as(self.mechanics_type).sheets, self.id)
        self.check_mechanics(state)

    def check_mechanics(self, state: GameState) -> None:  # noqa: B027 (a hook, not abstract)
        """Whatever this engine tracks beyond one sheet per actor."""

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        mechanics = draft.mechanics_as(self.mechanics_type)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        mechanics.sheets[entity.id] = self.new_sheet(draft, rng)

    @abstractmethod
    def new_sheet(self, draft: GameState, rng: Random) -> S: ...

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return translate_effect(RuleCall.model_validate(effect), self._effects)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return self.apply(draft, translate_effect(RuleCall.model_validate(effect), self._effects))

    def apply(self, draft: GameState, effect: Frozen) -> list[Fact]:
        """An engine with its own effects overrides this, falling through to super() for world
        ops."""
        if not is_world_op(effect):
            raise TypeError(f"{type(effect).__name__} is no effect this engine applies")
        return apply_effect(draft, effect)

    def renderer(self, state: GameState) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    @abstractmethod
    def describe(self, state: GameState, entity: Entity) -> str: ...

    @abstractmethod
    def sheet_view(self, state: GameState) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""

    @abstractmethod
    def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
        """Rolls one translated call and mutates the draft."""

    def check_beat(self, state: GameState, beat: DirectorBeat) -> str | None:
        """Returns the refusal instead of raising: a raising output validator kills the turn
        instead of retrying it."""
        try:
            typed = translate(beat, self.actions, self._effects)
        except ValidationError as broken:
            return _named(broken)
        except ValueError as refused:
            return str(refused)
        return check_draft(state, lambda draft: self._play(draft, typed, Random(0)))

    def resolve_beat(self, draft: GameState, beat: DirectorBeat, rng: Random) -> Resolution:
        return self._play(draft, translate(beat, self.actions, self._effects), rng)

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

    def _worked_plans(self) -> str:
        path = self.engine_dir / "examples.json"
        if not path.is_file():
            return ""
        plans = TypeAdapter(list[DirectorBeat]).validate_json(engine_text(path))
        blocks: list[str] = []
        for number, plan in enumerate(plans, start=1):
            _ = translate(plan, self.actions, self._effects)
            blocks.append(f"Example {number}:\n\n```json\n{plan.model_dump_json(indent=2)}\n```")
        return "\n\n".join(["## Worked plans", WORKED_PLANS, *blocks]) if blocks else ""


def _named(broken: ValidationError) -> str:
    """`check_draft` renders the message alone; a translation fault needs the field it names."""
    first = broken.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}" if where else first["msg"]


def engines() -> tuple[type[Engine[SheetBase]], ...]:
    """Imported by name, because a static import would put core back inside the engine packages."""
    found = tuple(_engine_class(module) for module in ENGINE_MODULES)
    if len({engine.id for engine in found}) != len(found):
        raise ValueError(f"engine ids collide: {[engine.id for engine in found]}")
    return found


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in engines())


def engine_class(engine_id: EngineId) -> type[Engine[SheetBase]]:
    found = next((engine for engine in engines() if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def _engine_class(module: str) -> type[Engine[SheetBase]]:
    declared = getattr(import_module(module), ENGINE, None)
    if not (isinstance(declared, type) and issubclass(declared, Engine)):
        raise ValueError(f"engine module {module!r} declares no {ENGINE}")
    # issubclass narrows only to the unparameterized generic; the sheet type is checked at
    # construction by check_overlay/begin, not statically knowable from a dynamic import.
    return declared  # pyright: ignore[reportUnknownVariableType]
