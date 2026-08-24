import dataclasses
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from re import fullmatch
from typing import ClassVar, Literal, Protocol, Self

from pydantic import BaseModel, Field, JsonValue
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.tools import ObjectJsonSchema, ToolDefinition, ToolFuncEither
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.content.io import ENCODING, SavedGame, engine_text
from aidm.content.model import CreatedCharacter
from aidm.state.creation import AnyStep, CreationOption, CreationStep, Picks
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
from aidm.state.facts import Chip, Fact, explained_fact, labeled
from aidm.state.model import Game, WorldState, draft_refusal
from aidm.state.play import DiceEvent, MechanicEvent, OptionId, PendingDecision, StepTrace

type EntityRenderer = Callable[[Entity], str]


@dataclass(frozen=True, slots=True)
class EventCause:
    """What produced a batch of facts: a director tool call, or an answered decision's kind."""

    origin: Literal["tool", "decision"]
    name: str


@dataclass(slots=True)
class TurnLog:
    facts: list[Fact] = field(default_factory=list)
    steps: list[StepTrace] = field(default_factory=list)
    events: list[MechanicEvent] = field(default_factory=list)
    on_event: Callable[[MechanicEvent], None] | None = None

    def landed(self, facts: tuple[Fact, ...], events: tuple[MechanicEvent, ...]) -> None:
        self.facts.extend(facts)
        self.events.extend(events)
        if self.on_event is not None:
            for event in events:
                self.on_event(event)


@dataclass(frozen=True, slots=True)
class PlanContext:
    """Director tools resolve against the turn's draft, never committed state."""

    engine: "Engine"
    state: Game
    rng: Random
    log: TurnLog
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
        self.director_toolsets: tuple[AbstractToolset[PlanContext], ...] = ()
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

    def player_events(
        self, cause: EventCause, facts: tuple[Fact, ...]
    ) -> tuple[MechanicEvent, ...]:
        """Keep chip visibility at the narrator gate so unrevealed entities cannot bypass it."""
        return tuple(
            MechanicEvent(source=cause.name, title=fact.chip.title, icon=fact.chip.icon)
            for fact in facts
            if fact.chip is not None and fact.narrator is not None
        )


def dice_event(label: str, fact: Fact) -> DiceEvent:
    """A `dice_rolled` fact's own data, typed: the whitelisted exception to the narrator gate."""
    kept = fact.data["kept"]
    if not isinstance(kept, int):
        raise ValueError(f"a dice_rolled fact carries a non-int kept value: {kept!r}")
    return DiceEvent(
        label=label, faces=_ints(fact.data["faces"]), rolled=_ints(fact.data["rolled"]), kept=kept
    )


def counter_effect(fact: Fact) -> str:
    """Built from a `counter_changed` fact's data, prefixed by owner unless it is the player."""
    if fact.narrator is None:
        raise ValueError("a counter_changed fact with no narrator text cannot become an effect")
    key, delta, current, maximum = (
        fact.data["counter"],
        fact.data["delta"],
        fact.data["current"],
        fact.data["maximum"],
    )
    if not isinstance(delta, int) or not isinstance(current, int):
        raise ValueError(f"a counter_changed fact carries non-int values: {fact.data!r}")
    if maximum is not None and not isinstance(maximum, int):
        raise ValueError(f"a counter_changed fact carries a non-int maximum: {maximum!r}")
    entity_id = fact.data["entity_id"]
    if not isinstance(entity_id, str):
        raise ValueError(f"a counter_changed fact carries a non-str entity id: {entity_id!r}")
    pool_text = str(current) if maximum is None else f"{current}/{maximum}"
    line = f"{str(key).capitalize()} {delta:+d} -> {pool_text}"
    return line if entity_id == PLAYER_ID else f"{fact.data['entity_name']}: {line}"


def dice_by_role(facts: Sequence[Fact], role: str) -> Fact | None:
    return next(
        (fact for fact in facts if fact.kind == "dice_rolled" and fact.data.get("role") == role),
        None,
    )


def require_dice_role(facts: Sequence[Fact], role: str) -> Fact:
    """The same lookup for a role a resolver call always rolls, so a miss is a bug, not a case."""
    found = dice_by_role(facts, role)
    if found is None:
        raise ValueError(f"no dice_rolled fact carries role {role!r}")
    return found


def _ints(value: JsonValue) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"expected a list of dice, got {value!r}")
    ints: list[int] = []
    for item in value:
        if not isinstance(item, int):
            raise ValueError(f"expected dice values to be ints, got {value!r}")
        ints.append(item)
    return tuple(ints)


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def adjust(entity: Entity, key: str, counter: Counter, amount: int, why: str) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [counter_fact(entity, key, counter, landed, why)]


def spend(entity: Entity, key: str, counter: Counter, amount: int) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(entity, key, counter, -amount, f"spent {key}")]


def counter_fact(entity: Entity, key: str, counter: Counter, delta: int, why: str) -> Fact:
    data = {
        "counter": key,
        "delta": delta,
        "current": counter.current,
        "maximum": counter.maximum,
        "entity_name": entity.name,
    }
    trace = f"{labeled(entity)} {key} {delta:+d} -> {pool(counter)}"
    return explained_fact(entity, "counter_changed", trace, data, why)


def chipped(facts: list[Fact], icon: str) -> list[Fact]:
    """Chips a counter fact only where the narrator will read it, keeping the gate centralized."""
    return [
        f
        if f.narrator is None
        else f.model_copy(update={"chip": Chip(title=counter_effect(f), icon=icon)})
        for f in facts
    ]


def render_counters(counters: dict[Slug, Counter]) -> str:
    return ", ".join(f"{key} {pool(counters[key])}" for key in sorted(counters))


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""


class SheetMechanics[S: SheetBase](Mutable):
    sheets: dict[EntityId, S] = Field(default_factory=dict)
    # How many chapters the fiction has closed, game-wide: what advancement is owed against.
    completed: Counter = Counter(current=0)

    @classmethod
    def of_game(cls, state: Game) -> Self:
        mechanics = state.mechanics
        if not isinstance(mechanics, cls):
            # Both engines name their model `Mechanics`, so only the module tells them apart.
            raise ValueError(
                f"the state carries {type(mechanics).__module__} mechanics, not {cls.__module__}"
            )
        return mechanics


def actor_sheets[S: Mutable](
    world: WorldState, player_rules: dict[str, JsonValue], sheet: type[S]
) -> dict[EntityId, S]:
    return {
        entity.id: sheet.model_validate(player_rules if entity.id == PLAYER_ID else {})
        for entity in world.of_kind("actor")
    }


def check_sheets(world: WorldState, sheets: Mapping[EntityId, object], engine: EngineId) -> None:
    if PLAYER_ID not in sheets:
        raise ValueError(f"the {engine} mechanics name no player")
    actors = {entity.id for entity in world.of_kind("actor")}
    if missing := sorted(actors - set(sheets)):
        raise ValueError(f"actors carry no character sheet: {missing}")
    if gone := sorted(set(sheets) - world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


def complete_chapter(draft: Game, ending: str) -> list[Fact]:
    SheetMechanics.of_game(draft).completed.current += 1
    chip = Chip(title=ending, icon="auto_stories")
    return [
        Fact(
            kind="chapter_completed",
            trace=ending,
            narrator=ending,
            data={"ending": ending},
            chip=chip,
        )
    ]


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


def act(ctx: RunContext[PlanContext], play: Play) -> str:
    """Refused against a throwaway copy, applied to the turn's draft, answered with what changed."""
    deps = ctx.deps
    if refused := draft_refusal(
        deps.state, lambda copy: apply_to_draft(deps.engine, copy, play, Random(0))
    ):
        raise ModelRetry(refused)
    already_pending = len(deps.state.world.pending_notes)
    decided_before = deps.state.pending
    landed = apply_to_draft(deps.engine, deps.state, play, deps.rng)
    cause = EventCause("tool", ctx.tool_name or "")
    deps.log.landed(landed, deps.engine.player_events(cause, landed))
    lines = [f"- {fact.trace}" for fact in landed]
    lines.extend(f"- {note}" for note in deps.state.world.pending_notes[already_pending:])
    lines.extend(_reached(deps.state, landed))
    if decided_before is None and deps.state.pending is not None:
        lines.append(f"- {RULES_WAIT}")
    return "\n".join(lines) or NOTHING_CHANGED


def sequential_toolset(
    tools: list[ToolFuncEither[PlanContext, ...]],
) -> FunctionToolset[PlanContext]:
    """One tool at a time: two calls in one answer would interleave on the same draft."""
    return FunctionToolset(
        tools=tools, sequential=True, require_parameter_descriptions=True, max_retries=2
    )


def with_enum(
    tool: ToolDefinition, fields: Sequence[str], values: Sequence[str], inside: str | None = None
) -> ToolDefinition:
    """Use `inside` when multiple tool arguments nest model fields under `$defs`."""
    schema = tool.parameters_json_schema
    if inside is None:
        return dataclasses.replace(tool, parameters_json_schema=_enumerated(schema, fields, values))
    defs = {**schema["$defs"], inside: _enumerated(schema["$defs"][inside], fields, values)}
    return dataclasses.replace(tool, parameters_json_schema={**schema, "$defs": defs})


def _enumerated(
    schema: ObjectJsonSchema, fields: Sequence[str], values: Sequence[str]
) -> ObjectJsonSchema:
    # Copied, never mutated: a prepare function is handed the same definition on every step.
    properties: dict[str, ObjectJsonSchema] = dict(schema["properties"])
    for name in fields:
        properties[name] = {**properties[name], "enum": list(values)}
    return {**schema, "properties": properties}


def _seed_created(engine: Engine, draft: Game, facts: Sequence[Fact], rng: Random) -> None:
    for fact in facts:
        created = fact.data.get("entity_id") if fact.kind == "entity_created" else None
        if isinstance(created, str):
            engine.seed(draft, draft.world.require(EntityId(created)), rng)


def _reached(draft: Game, facts: Sequence[Fact]) -> list[str]:
    # The prompt was rendered before the discovery, so the instruction authored for it arrives here.
    lines: list[str] = []
    for fact in facts:
        found = fact.data.get("entity_id") if fact.kind == "entity_discovered" else None
        if not isinstance(found, str):
            continue
        detail = draft.world.require(EntityId(found)).detail
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

    id: ClassVar[Slug] = "advancement"
    proposal_type: ClassVar[type[ProposalBase]]
    ledger_key: ClassVar[Slug]
    occasion: ClassVar[str]
    offer_text: ClassVar[str]
    spent_why: ClassVar[str]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / f"{self.id}.md")

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


LOGGER = logging.getLogger(__name__)


class PackName(Protocol):
    name: str


def pack_step(packs: Mapping[str, PackName]) -> CreationStep:
    return CreationStep(
        id="pack",
        prompt="Choose a table set",
        options=tuple(
            CreationOption(id=pack_id, label=pack.name) for pack_id, pack in packs.items()
        ),
    )


def pack_paths(shipped: Path, extra: Path | None) -> dict[str, Path]:
    """User packs merge over shipped ones by file stem, so one can replace a shipped table set."""
    paths = {path.stem: path for path in sorted(shipped.glob("*.json"))}
    if extra is not None and extra.is_dir():
        paths.update({path.stem: path for path in sorted(extra.glob("*.json"))})
    return paths


def load_packs[P: BaseModel](paths: Mapping[str, Path], model: type[P]) -> dict[str, P]:
    """A broken user pack is skipped with a log line: it must not block the way to the launcher."""
    packs: dict[str, P] = {}
    for stem, path in paths.items():
        if fullmatch(r"[a-z0-9-]+", stem) is None:
            LOGGER.warning("skipping content pack %s: its name is not a slug", path)
            continue
        try:
            packs[stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
        except (OSError, ValueError) as broken:
            LOGGER.warning("skipping content pack %s: %s", path, broken)
    if not packs:
        raise ValueError("no usable content pack was found")
    return packs
