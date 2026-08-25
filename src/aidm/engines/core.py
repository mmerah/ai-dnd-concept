import dataclasses
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.tools import ObjectJsonSchema, ToolDefinition, ToolFuncEither
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.content.io import SavedGame, engine_text
from aidm.content.model import CreatedCharacter
from aidm.state.creation import AnyStep, Picks
from aidm.state.entities import (
    PLAYER_ID,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Mutable,
    Slug,
)
from aidm.state.facts import (
    Fact,
    MechanicEvent,
    explained_fact,
    labeled,
    player_events,
)
from aidm.state.model import Game, WorldState, draft_refusal
from aidm.state.play import OptionId, PendingDecision

type EntityRenderer = Callable[[Entity], str]


@dataclass(slots=True)
class TurnRecord:
    facts: list[Fact] = field(default_factory=list)
    events: list[MechanicEvent] = field(default_factory=list)
    on_event: Callable[[MechanicEvent], None] | None = None

    def landed(self, facts: tuple[Fact, ...], events: tuple[MechanicEvent, ...]) -> None:
        self.facts.extend(facts)
        self.events.extend(events)
        if self.on_event is not None:
            for event in events:
                self.on_event(event)


@dataclass(frozen=True, slots=True)
class DirectorContext:
    """Director tools resolve against the turn's draft, never committed state."""

    engine: "Engine"
    draft: Game
    rng: Random
    log: TurnRecord
    # The run began with a re-suspended decision: it develops what the answer caused, no more.
    suspended_at_start: bool = False
    answered: PendingDecision | None = None


class CharacterCreation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine(ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of state."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    mechanics_type: type[Mutable]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.mechanics_type
        self.director_instructions: str = engine_text(self.engine_dir / "director.md")
        # An engine's own mechanics reach the Director as tools; core's world vocabulary is shared.
        self.director_toolsets: tuple[AbstractToolset[DirectorContext], ...] = ()
        self.advancement: Advancement | None = None
        self.creation: CharacterCreation | None = None

    @abstractmethod
    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        """Refuses authored character rules this engine cannot play."""

    @abstractmethod
    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> Mutable: ...

    def restored(self, saved: SavedGame) -> Game:
        state = saved.game(self.mechanics_type.model_validate(saved.mechanics))
        if state.pending is not None:
            self.check_pending(state.pending)
        return state

    @abstractmethod
    def validate(self, state: Game) -> None:
        """Refuses a state this engine cannot play, rather than repairing one."""

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:  # noqa: B027
        """Whatever this engine must give an entity created during play; a hook, not abstract."""

    def resume(
        self, draft: Game, pending: PendingDecision, option_id: OptionId, rng: Random
    ) -> tuple[Fact, ...]:
        """Applies a closed answer through the tools' own resolvers; may set `pending` again."""
        del draft, option_id, rng
        raise ValueError(f"the {self.id!r} engine resumes no {pending.kind!r} decision")

    def check_pending(self, pending: PendingDecision) -> None:
        """Refuses a decision whose kind this engine does not play or whose payload is invalid."""
        raise ValueError(f"the {self.id!r} engine cannot play a {pending.kind!r} decision")

    def renderer(self, state: Game) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    @abstractmethod
    def describe(self, state: Game, entity: Entity) -> str: ...

    @abstractmethod
    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def adjust(
    entity: Entity, key: str, counter: Counter, amount: int, why: str, icon: str = "casino"
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [counter_fact(entity, key, counter, landed, why, icon)]


def spend(
    entity: Entity, key: str, counter: Counter, amount: int, icon: str = "casino"
) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(entity, key, counter, -amount, f"spent {key}", icon)]


def counter_fact(
    entity: Entity, key: str, counter: Counter, delta: int, why: str, icon: str = "casino"
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    title = moved if entity.id == PLAYER_ID else f"{entity.name}: {moved}"
    trace = f"{labeled(entity)} {key} {delta:+d} -> {pool(counter)}"
    return explained_fact(
        entity, "counter_changed", trace, why, event=MechanicEvent(title=title, icon=icon)
    )


NOTHING_CHANGED = "- (nothing changed)"
RULES_WAIT = "the rules now wait on the player's decision"

# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play = Callable[[Game, Random], tuple[Fact, ...]]


def apply_to_draft(engine: Engine, draft: Game, play: Play, rng: Random) -> tuple[Fact, ...]:
    """Every mutation runs this sequence, so seeding cannot be forgotten by a caller."""
    before = draft.pending
    landed = play(draft, rng)
    if before is not None and draft.pending is not before:
        raise ValueError("the rules already wait on a decision; they take one at a time")
    if draft.pending is not None:
        engine.check_pending(draft.pending)
    _seed_created(engine, draft, landed, rng)
    engine.validate(draft)
    return landed


def transact(engine: Engine, draft: Game, play: Play, rng: Random) -> tuple[Game, tuple[Fact, ...]]:
    """A draft mutated and committed whole, for a change that stands on its own outside a turn."""
    before = draft.pending
    landed = apply_to_draft(engine, draft, play, rng)
    if draft.pending is not before:
        raise ValueError("a change outside a turn cannot open a decision for the player")
    return draft.committed(), landed


def apply_tool_call(ctx: RunContext[DirectorContext], play: Play) -> str:
    """Refused against a throwaway copy, applied to the turn's draft, answered with what changed."""
    deps = ctx.deps
    if refused := draft_refusal(
        deps.draft, lambda copy: apply_to_draft(deps.engine, copy, play, Random(0))
    ):
        raise ModelRetry(refused)
    already_pending = len(deps.draft.world.pending_notes)
    decided_before = deps.draft.pending
    landed = apply_to_draft(deps.engine, deps.draft, play, deps.rng)
    deps.log.landed(landed, player_events(landed))
    lines = [f"- {fact.trace}" for fact in landed]
    lines.extend(f"- {note}" for note in deps.draft.world.pending_notes[already_pending:])
    lines.extend(_reached(deps.draft, landed))
    if decided_before is None and deps.draft.pending is not None:
        lines.append(f"- {RULES_WAIT}")
    return "\n".join(lines) or NOTHING_CHANGED


def sequential_toolset(
    tools: list[ToolFuncEither[DirectorContext, ...]],
) -> FunctionToolset[DirectorContext]:
    """One tool at a time: two calls in one answer would interleave on the same draft."""
    return FunctionToolset(
        tools=tools, sequential=True, require_parameter_descriptions=True, max_retries=2
    )


def with_enum(tool: ToolDefinition, fields: Sequence[str], values: Sequence[str]) -> ToolDefinition:
    schema = tool.parameters_json_schema
    # Copied, never mutated: a prepare function is handed the same definition on every step.
    properties: dict[str, ObjectJsonSchema] = dict(schema["properties"])
    for name in fields:
        properties[name] = {**properties[name], "enum": list(values)}
    return dataclasses.replace(tool, parameters_json_schema={**schema, "properties": properties})


def _seed_created(engine: Engine, draft: Game, facts: Sequence[Fact], rng: Random) -> None:
    for fact in facts:
        if fact.kind == "entity_created" and fact.entity_id is not None:
            engine.seed(draft, draft.world.require(fact.entity_id), rng)


def _reached(draft: Game, facts: Sequence[Fact]) -> list[str]:
    # The prompt was rendered before the discovery, so the instruction authored for it arrives here.
    lines: list[str] = []
    for fact in facts:
        if fact.kind != "entity_discovered" or fact.entity_id is None:
            continue
        detail = draft.world.require(fact.entity_id).detail
        if detail is not None and detail.when_reached:
            lines.append(f"- {detail.when_reached}")
    return lines


class AdvancementOffer(Frozen):
    """One change advancement holds open for one subject, already resolved out of content."""

    subject_id: EntityId
    prompt: str
    text: str = ""


class ProposalBase(Frozen):
    """What the advisor writes, in the engine's own vocabulary."""


class Advancement(ABC):
    """One advance per boundary the fiction closed, per party member."""

    proposal_type: ClassVar[type[ProposalBase]]
    ledger_key: ClassVar[Slug]
    occasion: ClassVar[str]
    offer_text: ClassVar[str]
    spent_why: ClassVar[str]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / "advancement.md")

    def offers(self, state: Game) -> tuple[AdvancementOffer, ...]:
        earned = self.earned(state)
        return tuple(
            AdvancementOffer(
                subject_id=subject_id,
                prompt=f"{state.world.require(subject_id).name} {self.occasion}.",
                text=self.offer_text,
            )
            for subject_id in (PLAYER_ID, *state.world.party)
            if earned > self.ledger(state, subject_id).current
        )

    def resolve(
        self, draft: Game, offer: AdvancementOffer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        granted = self.grant(draft, offer.subject_id, proposal, rng)
        ledger = self.ledger(draft, offer.subject_id)
        ledger.current += 1
        subject = draft.world.require(offer.subject_id)
        return (*granted, counter_fact(subject, self.ledger_key, ledger, 1, self.spent_why))

    def advance_refusal(
        self, state: Game, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        return draft_refusal(
            state,
            lambda draft: self.resolve(draft, offer, proposal, Random(0)),
            "the sheet this leaves",
        )

    @abstractmethod
    def ledger(self, state: Game, subject_id: EntityId) -> Counter: ...

    @abstractmethod
    def earned(self, state: Game) -> int:
        """How many boundaries the fiction has closed: what an advance is owed against."""

    @abstractmethod
    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        """Writes what the proposal buys; moving the ledger itself belongs to the base."""
