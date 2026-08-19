from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue, TypeAdapter
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import CreatedCharacter, EngineBinding
from aidm.content.store import engine_text
from aidm.state.apply_effects import apply_effect
from aidm.state.base import EngineId, Entity, EntityId, Frozen
from aidm.state.beat import Resolution, check_draft
from aidm.state.creation import AnyStep, Picks
from aidm.state.effects import is_world_op
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .advancement import Advancement
from .sheets import SheetBase, SheetMechanics, actor_sheets, check_sheets

WORKED_PLANS = (
    "One plan per turn, each opening its own beat; every beat of a turn is the same shape. Most "
    "beats need few or no effects, and an empty `effects` is a normal answer. But a beat whose "
    "fiction starts or ends a lasting state — a condition taking hold or passing — must write that "
    "trait change: nothing records it otherwise."
)
SETTLE_REFUSAL = (
    "this is the turn's last beat: leave `roll` null and write only what the dice already settled."
)

type EntityRenderer = Callable[[Entity], str]


class CharacterCreation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine[S: SheetBase](ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of state."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    # What the Director answers under this engine: its own typed beat model.
    beat_type: ClassVar[type[Frozen]]
    sheet_type: type[S]
    mechanics_type: type[SheetMechanics[S]]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.sheet_type, self.mechanics_type, self.beat_type
        parts = (engine_text(self.engine_dir / "director.md"), self._worked_plans())
        self.director_instructions: str = "\n\n".join(part for part in parts if part)
        # An engine with content advertises its own lookups; one without teaches the model no tool.
        self.director_toolsets: tuple[AbstractToolset[object], ...] = ()
        # An engine with no growth mechanic plugs in none; the app offers only what it finds.
        self.advancement: Advancement | None = None
        # An engine that creates characters replaces this; the app offers only what it finds.
        self.creation: CharacterCreation | None = None

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        for rules in payloads:
            _ = self.sheet_type.model_validate(rules)

    def binding(self) -> EngineBinding:
        return EngineBinding(engine=self.id, check_overlay=self.check_overlay)

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

    def apply(self, draft: GameState, effect: Frozen) -> list[Fact]:
        """An engine with its own effects overrides this, falling through here for world ops."""
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

    @abstractmethod
    def unpack_beat(self, beat: Frozen) -> tuple[Frozen | None, tuple[Frozen, ...]]:
        """This engine's own beat, split into the roll it puts to the dice and what it causes."""

    def check_beat(self, state: GameState, beat: Frozen, settle: bool) -> str | None:
        """Returns the refusal instead of raising: raising would kill the turn, not retry it."""
        roll, effects = self.unpack_beat(beat)
        if settle and roll is not None:
            return SETTLE_REFUSAL
        return check_draft(state, lambda draft: self._play(draft, roll, effects, Random(0)))

    def resolve_beat(self, draft: GameState, beat: Frozen, rng: Random) -> Resolution:
        roll, effects = self.unpack_beat(beat)
        return self._play(draft, roll, effects, rng)

    def _play(
        self, draft: GameState, roll: Frozen | None, effects: tuple[Frozen, ...], rng: Random
    ) -> Resolution:
        """The order the beat runs: the roll first, then what it causes."""
        settled = None if roll is None else self.resolve_roll(draft, roll, rng)
        caused = [fact for effect in effects for fact in self.apply(draft, effect)]
        if settled is None:
            return Resolution(facts=tuple(caused), followup="none")
        return Resolution(
            facts=(*settled.facts, *caused),
            followup=settled.followup,
        )

    def _worked_plans(self) -> str:
        path = self.engine_dir / "examples.json"
        if not path.is_file():
            return ""
        entries = TypeAdapter(list[JsonValue]).validate_json(engine_text(path))
        blocks: list[str] = []
        for number, entry in enumerate(entries, start=1):
            # Authored examples pass through the same gate as the wire, so prose can't drift.
            plan = self.beat_type.model_validate(entry)
            blocks.append(f"Example {number}:\n\n```json\n{plan.model_dump_json(indent=2)}\n```")
        return "\n\n".join(["## Worked plans", WORKED_PLANS, *blocks]) if blocks else ""
