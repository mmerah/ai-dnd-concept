import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import ClassVar, Self

from pydantic import BaseModel, Field, JsonValue, ValidationError, model_validator

from aidm.content.io import engine_text
from aidm.content.model import CreatedCharacter, Scenario
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.creation import AnyStep, Picks
from aidm.state.entities import (
    DEAD,
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    Kind,
    Mutable,
    Slug,
    require_unique,
)
from aidm.state.facts import (
    NOTHING_CHANGED,
    Fact,
    MechanicEvent,
    entity_fact,
    explained_fact,
    narrator_lines,
    player_events,
    trace_lines,
)
from aidm.state.model import Game, draft_refusal
from aidm.state.play import DecisionOption, Line, PendingDecision

type EntityRenderer = Callable[[Entity], str]


# The small vocabulary an engine's rules are written with.


def pool(counter: Counter) -> str:
    if counter.maximum is None:
        return str(counter.current)
    return f"{counter.current}/{counter.maximum}"


def counter_fact(
    state: Game,
    entity: Entity,
    key: str,
    counter: Counter,
    delta: int,
    why: str,
    icon: str = "casino",
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    title = moved if entity.id == state.player_id else f"{entity.name}: {moved}"
    trace = f"{state.label(entity)} {key} {delta:+d} -> {pool(counter)}"
    return explained_fact(
        entity, "counter_changed", trace, why, event=MechanicEvent(title=title, icon=icon)
    )


def adjust(
    state: Game,
    entity: Entity,
    key: str,
    counter: Counter,
    amount: int,
    why: str,
    icon: str = "casino",
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [counter_fact(state, entity, key, counter, landed, why, icon)]


def spend(
    state: Game, entity: Entity, key: str, counter: Counter, amount: int, icon: str = "casino"
) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(state, entity, key, counter, -amount, f"spent {key}", icon)]


# An entity's own rules: authored as JSON, parsed by the engine that reads them.


class EntityRules(Mutable, ABC):
    """One entity's mechanics, whatever this engine's rules make of them."""

    @abstractmethod
    def rows(self) -> tuple[tuple[str, str], ...]:
        """Every view of them: labels head the player's panel, and a prompt lowers them."""


class NoRules(EntityRules):
    """A kind this engine gives no mechanics; `extra="forbid"` refuses any rules authored on it."""

    def rows(self) -> tuple[tuple[str, str], ...]:
        return ()


class SheetBase(EntityRules, ABC):
    packs: tuple[Slug, ...] = ("srd",)
    chapters: Counter = Counter(current=0)

    @model_validator(mode="after")
    def _packs_include_srd(self) -> Self:
        require_unique("sheet pack ids", self.packs)
        if "srd" not in self.packs:
            raise ValueError("sheet packs must include 'srd'")
        return self


@contextmanager
def rules[M: EntityRules](entity: Entity, model: type[M]) -> Generator[M]:
    """Parsed on entry, written back on exit; the one way an engine changes `entity.rules`."""
    # Where authored rules are what makes an entity playable, one without them has no sheet.
    if issubclass(model, SheetBase) and not entity.rules:
        raise ValueError(f"{entity.name} has no character sheet")
    parsed = model.model_validate(entity.rules)
    yield parsed
    entity.rules = parsed.model_dump(mode="json")


def describe_rows(rows: tuple[tuple[str, str], ...], meanings: tuple[tuple[str, str], ...]) -> str:
    lines: list[str] = []
    for label, value in rows:
        if not value:
            continue
        lines.append(f"{label.lower()}: {value}")
        listed = value.split(", ")
        lines.extend(f"- {tag}: {detail}" for tag, detail in meanings if tag in listed)
    return "\n".join(lines)


# The contract: what a new engine supplies.


class CharacterCreation(ABC):
    rolls: ClassVar[bool] = False

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks, rng: Random) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Decision(Frozen):
    """A decision's own fields are the `PendingDecision.payload` a save carries."""

    kind: ClassVar[Slug]

    def pending(self, prompt: str, options: tuple[DecisionOption, ...] = ()) -> PendingDecision:
        return PendingDecision(
            kind=self.kind, prompt=prompt, options=options, payload=self.model_dump(mode="json")
        )

    def resolve(self, draft: Game, option_id: Slug, rng: Random) -> tuple[Fact, ...]:
        del draft, rng
        raise ValueError(f"a {self.kind!r} decision resolves no option {option_id!r}")


class ProposalBase(Frozen):
    subject_id: CheckedEntityId = Field(description="Exact id of the party member who advances.")


ADVANCE_TOOL = "Spend one advance a party member has earned, when the player asks for it. "


def party_member(draft: Game, subject_id: EntityId) -> Entity:
    """An advance is a party member's own: nobody else's sheet is the engine's to grow."""
    subject = draft.world.require(subject_id)
    if subject_id not in (draft.player_id, *draft.world.party):
        raise ValueError(f"{subject.name} is not in the party")
    return subject


def advances_owed[S: SheetBase](
    state: Game, sheet_type: type[S], ledger: Callable[[S], Counter]
) -> tuple[str, ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen payload the open decision holds.
    if state.pending is not None:
        return ()
    notes: list[str] = []
    for subject_id in (state.player_id, *state.world.party):
        subject = state.world.require(subject_id)
        sheet = sheet_type.model_validate(subject.rules)
        if sheet.chapters.current > ledger(sheet).current:
            notes.append(
                f"{subject.name} has an advance owed; call advance only when the player asks "
                "for it."
            )
    return tuple(notes)


class Engine(ABC):
    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    decisions: ClassVar[tuple[type[Decision], ...]] = ()
    authoring_instructions: ClassVar[str] = ""
    # Every entity's rules are parsed through the model its kind maps to; `validate` is the gate.
    rules_types: ClassVar[Mapping[Kind, type[EntityRules]]]
    pack_type: ClassVar[type[BaseModel]]
    creation: CharacterCreation

    def __init__(self, sources: PackSources = SHIPPED_PACKS) -> None:
        # Subclasses load `sources` themselves so their packs keep their own type.
        del sources
        _ = self.rules_types, self.pack_type
        self.director_instructions: str = engine_text(self.engine_dir / "director.md")
        self.director_commands: tuple[Command, ...] = ()
        self.player_actions: tuple[PlayerAction, ...] = ()

    def validate(self, state: Game) -> None:
        """Refuses a state this engine cannot play, rather than repairing one."""
        installed = set(self.pack_ids)
        for entity in state.world.entities:
            try:
                parsed = self.rules_types[entity.kind].model_validate(entity.rules)
            except ValidationError as broken:
                first = broken.errors()[0]
                place = ".".join(str(part) for part in ("rules", entity.id, *first["loc"]))
                raise ValueError(f"{place}: {first['msg']}") from broken
            if isinstance(parsed, SheetBase) and (missing := sorted(set(parsed.packs) - installed)):
                raise ValueError(f"{entity.id!r} uses packs that are not installed: {missing}")

    def describe(self, entity: Entity) -> str:
        """One entity's mechanics as a prompt reads them; the player's own panel is `sheet_rows`."""
        # An actor the scenario gave no rules is a threat the Director narrates, not a sheet.
        if entity.kind == "actor" and not entity.rules:
            return ""
        return describe_rows(self.rules_types[entity.kind].model_validate(entity.rules).rows(), ())

    def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""
        return self.rules_types["actor"].model_validate(state.player.rules).rows()

    def notes(self, state: Game) -> tuple[str, ...]:
        return (*state.world.pending_notes, *self.owed_notes(state))

    def owed_notes(self, state: Game) -> tuple[str, ...]:
        """Advances the party has earned; an engine without advancement owes none."""
        del state
        return ()

    def check_overlay(self, overlay: dict[str, JsonValue]) -> None:
        """The character file this engine plays by, refused where it is read rather than in play."""
        _ = self.rules_types["actor"].model_validate(overlay)

    @property
    def pack_ids(self) -> tuple[Slug, ...]:
        return tuple(self.pack_models())

    @abstractmethod
    def pack_models(self) -> Mapping[str, BaseModel]:
        """Every installed pack by id; the schema each was validated against is `pack_type`."""

    def check_scenario(self, scenario: Scenario) -> None:
        if missing := sorted(set(scenario.packs) - set(self.pack_models())):
            raise ValueError(f"scenario names packs not installed for {self.id!r}: {missing}")

    def authoring_context(self, pack_ids: tuple[Slug, ...]) -> str:
        installed = self.pack_models()
        # Defaults restate rules the guidance already carries; dropping them halves the prompt.
        packs = {
            pack_id: installed[pack_id].model_dump(mode="json", exclude_defaults=True)
            for pack_id in pack_ids
        }
        return f"{self.authoring_instructions}\n\nSELECTED PACK CONTENT\n{json.dumps(packs)}"

    def restored(self, raw: str) -> Game:
        state = Game.model_validate_json(raw)
        if state.engine != self.id:
            raise ValueError(f"the save plays {state.engine!r}, not {self.id!r}")
        if state.pending is not None:
            self.check_pending(state.pending)
        self.validate(state)
        return state

    def resume(
        self, draft: Game, pending: PendingDecision, option_id: Slug, rng: Random
    ) -> tuple[Fact, ...]:
        """Applies a closed answer through the tools' own resolvers; may set `pending` again."""
        return self._decision(pending).resolve(draft, option_id, rng)

    def check_pending(self, pending: PendingDecision) -> None:
        """Refuses a decision whose kind this engine does not play or whose payload is invalid."""
        _ = self._decision(pending)

    def _decision(self, pending: PendingDecision) -> Decision:
        # Core's death hand-over is prepended, so no engine declares it and none can shadow it.
        found = next(
            (one for one in (Succession, *self.decisions) if one.kind == pending.kind), None
        )
        if found is None:
            raise ValueError(f"the {self.id!r} engine cannot play a {pending.kind!r} decision")
        return found.model_validate(pending.payload)


# Applying a change to the turn's draft.


@dataclass(slots=True)
class TurnRecord:
    facts: list[Fact] = field(default_factory=list)
    events: list[MechanicEvent] = field(default_factory=list)
    on_event: Callable[[MechanicEvent], None] | None = None

    def landed(
        self, draft: Game, facts: tuple[Fact, ...], events: tuple[MechanicEvent, ...]
    ) -> None:
        self.facts.extend(facts)
        self.events.extend(events)
        # On the draft too: a harness that commits per tool call reaches the page only through it.
        draft.turn_events = tuple(self.events)
        if self.on_event is not None:
            for event in events:
                self.on_event(event)


@dataclass(frozen=True, slots=True)
class DirectorContext:
    """Director tools resolve against the turn's draft, never committed state."""

    engine: Engine
    draft: Game
    rng: Random
    log: TurnRecord
    # The run began with a re-suspended decision: it develops what the answer caused, no more.
    suspended_at_start: bool = False
    answered: PendingDecision | None = None


RULES_WAIT = "the rules now wait on the player's decision"


# The rng is a parameter so a trial run against a throwaway copy cannot consume the turn's dice.
type Play = Callable[[Game, Random], tuple[Fact, ...]]


def apply_to_draft(engine: Engine, draft: Game, play: Play, rng: Random) -> tuple[Fact, ...]:
    """Every mutation runs this sequence, so no caller can skip the engine's own gate."""
    before = draft.pending
    landed = play(draft, rng)
    if before is not None and draft.pending is not before:
        raise ValueError("the rules already wait on a decision; they take one at a time")
    if draft.pending is not None:
        engine.check_pending(draft.pending)
    engine.validate(draft)
    return landed


def transact(engine: Engine, draft: Game, play: Play, rng: Random) -> tuple[Game, tuple[Fact, ...]]:
    """A draft mutated and committed whole, for a change that stands on its own outside a turn."""
    before = draft.pending
    landed = apply_to_draft(engine, draft, play, rng)
    if draft.pending is not before:
        raise ValueError("a change outside a turn cannot open a decision for the player")
    return draft.committed(), landed


def apply_play(deps: DirectorContext, play: Play) -> str:
    """Refused against a throwaway copy, applied to the turn's draft, answered with what changed."""
    if refused := draft_refusal(
        deps.draft, lambda copy: apply_to_draft(deps.engine, copy, play, Random(0))
    ):
        raise ValueError(refused)
    already_pending = len(deps.draft.world.pending_notes)
    decided_before = deps.draft.pending
    landed = apply_to_draft(deps.engine, deps.draft, play, deps.rng)
    deps.log.landed(deps.draft, landed, player_events(landed))
    lines = trace_lines(landed)
    lines.extend(f"- {note}" for note in deps.draft.world.pending_notes[already_pending:])
    lines.extend(_reached(deps.draft, landed))
    if decided_before is None and deps.draft.pending is not None:
        lines.append(f"- {RULES_WAIT}")
    return "\n".join(lines) or NOTHING_CHANGED


def apply_action(deps: DirectorContext, act: Callable[[Game], Sequence[Fact]]) -> str:
    """`aidm.state.actions` never rolls, so the turn's dice stay with the resolvers that do."""
    return apply_play(deps, lambda draft, _rng: tuple(act(draft)))


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


# The played character's death: core-owned, so every engine hands the story on the same way.


class Succession(Decision):
    """A dead player character hands the game to a companion; every engine plays this one."""

    kind: ClassVar[Slug] = "succession"

    def resolve(self, draft: Game, option_id: Slug, rng: Random) -> tuple[Fact, ...]:
        del rng
        return take_over(draft, EntityId(option_id))


def take_over(draft: Game, successor_id: EntityId) -> tuple[Fact, ...]:
    """Only the played id moves: sheets, items and history keep pointing where they point."""
    successor = draft.world.require_kind(successor_id, "actor")
    if successor_id not in draft.world.party:
        raise ValueError(f"{successor.name} does not travel with the player")
    if successor.trait(DEAD) is not None:
        raise ValueError(f"{successor.name} is dead and carries nothing on")
    draft.world.party.remove(successor_id)
    draft.player_id = successor_id
    return (
        entity_fact(
            successor,
            "player_succeeded",
            f"{draft.label(successor)} is the played character from here on",
            event=MechanicEvent(title=f"You play on as {successor.name}", icon="switch_account"),
        ),
    )


def succession_decision(engine: Engine, state: Game) -> PendingDecision | None:
    """None where nobody can carry the story on: the game ends with the played character."""
    options: list[DecisionOption] = []
    for member_id in state.world.party:
        if _takeover_refusal(engine, state, member_id) is not None:
            continue
        member = state.world.require(member_id)
        options.append(
            DecisionOption(id=member_id, label=f"Play on as {member.name}", detail=member.brief)
        )
    if not options:
        return None
    return Succession().pending(
        f"{state.player.name} is dead. Who carries the story on?", tuple(options)
    )


def _takeover_refusal(engine: Engine, state: Game, successor_id: EntityId) -> str | None:
    """Eligible means the swap leaves a game this engine can play, so there is no second rule."""
    return draft_refusal(
        state,
        lambda draft: apply_to_draft(
            engine, draft, lambda copy, _rng: take_over(copy, successor_id), Random(0)
        ),
    )


# Declaring a director command.


class NoArgs(Frozen):
    pass


@dataclass(frozen=True, slots=True)
class Command:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[DirectorContext, Mapping[str, JsonValue]], str]
    # Core world commands may still run in a turn that opened suspended; engine mechanics may not.
    during_suspension: bool = False


def command[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    run: Callable[[DirectorContext, A], str],
    *,
    during_suspension: bool = False,
) -> Command:
    """Validation lives here, so both harnesses reject the same arguments the same way."""
    if bare := [key for key, one in args.model_fields.items() if not one.description]:
        raise ValueError(f"{name} parameters the model reads carry no description: {bare}")

    def call(deps: DirectorContext, raw: Mapping[str, JsonValue]) -> str:
        return run(deps, args.model_validate(raw))

    return Command(name, description, args, call, during_suspension)


def rule[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    resolve: Callable[[Game, A, Random], Sequence[Fact]],
    *,
    during_suspension: bool = False,
) -> Command:
    """A command whose resolver rolls; the turn's own dice reach it, never a trial run's."""
    return command(
        name,
        description,
        args,
        lambda deps, one: apply_play(deps, lambda draft, rng: tuple(resolve(draft, one, rng))),
        during_suspension=during_suspension,
    )


def action[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    act: Callable[[Game, A], Sequence[Fact]],
    *,
    during_suspension: bool = False,
) -> Command:
    """A command that changes state without rolling."""
    return command(
        name,
        description,
        args,
        lambda deps, one: apply_action(deps, lambda draft: act(draft, one)),
        during_suspension=during_suspension,
    )


def run_command(found: Command, deps: DirectorContext, raw: Mapping[str, JsonValue]) -> str:
    """The one gate: a decision on the table blocks everything but developing its answer."""
    pending = deps.draft.pending
    if pending is not None and not (found.during_suspension and deps.suspended_at_start):
        # A plain answer, not a refusal: a retry prompt would tell the model to try again.
        return (
            f"the rules are waiting on the player: {pending.prompt}\n"
            "Put that to the player, then start the next turn with their answer."
        )
    return found.call(deps, raw)


def complete_chapter[S: SheetBase](draft: Game, ending: str, sheet_type: type[S]) -> list[Fact]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    for member_id in (draft.player_id, *draft.world.party):
        member = draft.world.require(member_id)
        # A companion nobody wrote rules for has no sheet, and a chapter writes them none.
        if not member.rules:
            continue
        with rules(member, sheet_type) as sheet:
            sheet.chapters.current += 1
    return [
        Fact(
            kind="chapter_completed",
            trace=ending,
            told=True,
            event=MechanicEvent(title=ending, icon="auto_stories"),
        )
    ]


def chapter_command[S: SheetBase](description: str, ending: str, sheet_type: type[S]) -> Command:
    """Every engine closes a chapter the same way; only what it calls one differs."""
    return command(
        "complete_chapter",
        description,
        NoArgs,
        lambda deps, _args: apply_action(
            deps, lambda draft: complete_chapter(draft, ending, sheet_type)
        ),
    )


# A player's own move between turns: no Director judgement, so no turn.


@dataclass(frozen=True, slots=True)
class Offer:
    label: str
    args: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class PlayerAction:
    name: Slug
    description: str
    apply: Callable[[Game, Mapping[str, JsonValue]], Sequence[Fact]]
    offers: Callable[[Game], Sequence[Offer]]


def player_action[A: BaseModel](
    name: Slug,
    description: str,
    args: type[A],
    act: Callable[[Game, A], Sequence[Fact]],
    offers: Callable[[Game], Sequence[tuple[str, A]]],
) -> PlayerAction:
    """Erases `A`: one engine tuple holds actions of different arg types. `offers` lists what the
    player can do right now, so a UI needs no form and no judgement."""
    return PlayerAction(
        name,
        description,
        lambda draft, raw: act(draft, args.model_validate(raw)),
        lambda state: tuple(
            Offer(label, one.model_dump(mode="json")) for label, one in offers(state)
        ),
    )


def offered(engine: Engine, state: Game) -> tuple[tuple[PlayerAction, Offer], ...]:
    return tuple((one, offer) for one in engine.player_actions for offer in one.offers(state))


def play_action(
    engine: Engine, state: Game, name: Slug, raw: Mapping[str, JsonValue], rng: Random
) -> tuple[Game, tuple[Fact, ...]]:
    """The exchange it records is how the chat, the journal and the next Director prompt see it."""
    if state.pending is not None:
        raise ValueError(f"the rules wait on the player's answer first: {state.pending.prompt}")
    match = next(
        (
            (one, offer)
            for one, offer in offered(engine, state)
            if one.name == name and offer.args == dict(raw)
        ),
        None,
    )
    if match is None:
        raise ValueError(f"{name!r} with {json.dumps(dict(raw))} is not offered right now")
    found, offer = match

    def play(draft: Game, _rng: Random) -> tuple[Fact, ...]:
        facts = tuple(found.apply(draft, raw))
        # Only told facts reach the player: an untold trace may name hidden canon.
        told = Line(text="\n".join(narrator_lines(facts)) or "Nothing changed.")
        draft.record(offer.label, (told,), player_events(facts))
        return facts

    return transact(engine, state.draft(), play, rng)
