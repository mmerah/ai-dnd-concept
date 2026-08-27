import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import ClassVar, Self

from pydantic import BaseModel, Field, JsonValue, ValidationError, model_validator

from aidm.content.io import SavedGame, engine_text
from aidm.content.model import CreatedCharacter, Scenario
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.creation import AnyStep, Picks
from aidm.state.entities import (
    DEAD,
    PLAYER_ID,
    CheckedEntityId,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Frozen,
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
    player_events,
    trace_lines,
)
from aidm.state.model import Game, WorldState, draft_refusal
from aidm.state.play import DecisionOption, PendingDecision

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


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


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
    """What the advisor writes, in the engine's own vocabulary."""


class AdvancementOffer(Frozen):
    """One change advancement holds open for one subject, already resolved out of content."""

    subject_id: CheckedEntityId
    prompt: str
    text: str = ""


class Advancement(ABC):
    """One advance per boundary the fiction closed, per party member."""

    proposal_type: ClassVar[type[ProposalBase]]
    ledger_key: ClassVar[Slug]
    occasion: ClassVar[str]
    offer_text: ClassVar[str]
    spent_why: ClassVar[str]

    def __init__(self, engine_dir: Path) -> None:
        self.instructions = engine_text(engine_dir / "advancement.md")

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

    def offers(self, state: Game) -> tuple[AdvancementOffer, ...]:
        earned = self.earned(state)
        return tuple(
            AdvancementOffer(
                subject_id=subject_id,
                prompt=f"{state.world.require(subject_id).name} {self.occasion}.",
                text=self.offer_text,
            )
            for subject_id in (state.player_id, *state.world.party)
            if earned > self.ledger(state, subject_id).current
        )

    def resolve(
        self, draft: Game, offer: AdvancementOffer, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        granted = self.grant(draft, offer.subject_id, proposal, rng)
        ledger = self.ledger(draft, offer.subject_id)
        ledger.current += 1
        subject = draft.world.require(offer.subject_id)
        return (
            *granted,
            counter_fact(draft, subject, self.ledger_key, ledger, 1, self.spent_why),
        )

    def advance_refusal(
        self, state: Game, offer: AdvancementOffer, proposal: ProposalBase
    ) -> str | None:
        return draft_refusal(
            state,
            lambda draft: self.resolve(draft, offer, proposal, Random(0)),
            "the sheet this leaves",
        )


class Engine(ABC):
    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    decisions: ClassVar[tuple[type[Decision], ...]] = ()
    authoring_instructions: ClassVar[str] = ""
    mechanics_type: type[Mutable]
    # The schema an authored pack is held to; None where an engine plays no content packs at all.
    pack_type: ClassVar[type[BaseModel] | None] = None
    advancement: Advancement
    creation: CharacterCreation

    def __init__(self, sources: PackSources = SHIPPED_PACKS) -> None:
        del sources
        _ = self.mechanics_type
        self.director_instructions: str = engine_text(self.engine_dir / "director.md")
        self.director_commands: tuple[Command, ...] = ()

    @abstractmethod
    def overlay_rows(self, rules: dict[str, JsonValue]) -> tuple[tuple[str, str], ...]:
        """Authored character rules as rows; raises ValueError on rules this engine cannot play."""

    @abstractmethod
    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> Mutable: ...

    @abstractmethod
    def validate(self, state: Game) -> None:
        """Refuses a state this engine cannot play, rather than repairing one."""

    @abstractmethod
    def describe(self, state: Game, entity: Entity) -> str:
        """One actor's mechanics as a prompt reads them; the player's own panel is `sheet_rows`."""

    @abstractmethod
    def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""

    def settle(self, draft: Game) -> tuple[Fact, ...]:
        """Consequences a command's landing forces; idempotent, since a turn settles after each."""
        del draft
        return ()

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:  # noqa: B027
        """Whatever this engine must give an entity created during play; a hook, not abstract."""

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = self.overlay_rows(rules)

    @property
    def pack_ids(self) -> tuple[Slug, ...]:
        return tuple(self.pack_models())

    def pack_models(self) -> Mapping[str, BaseModel]:
        return {}

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

    def restored(self, saved: SavedGame) -> Game:
        state = saved.game(self.mechanics_type.model_validate(saved.mechanics))
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

    def renderer(self, state: Game) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    def _decision(self, pending: PendingDecision) -> Decision:
        # Core's death hand-over is prepended, so no engine declares it and none can shadow it.
        found = next(
            (one for one in (Succession, *self.decisions) if one.kind == pending.kind), None
        )
        if found is None:
            raise ValueError(f"the {self.id!r} engine cannot play a {pending.kind!r} decision")
        return found.model_validate(pending.payload)


# Sheets: an engine that keeps one per actor writes almost none of the above itself.


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""

    packs: tuple[Slug, ...] = ("srd",)

    @model_validator(mode="after")
    def _packs_include_srd(self) -> Self:
        require_unique("sheet pack ids", self.packs)
        if "srd" not in self.packs:
            raise ValueError("sheet packs must include 'srd'")
        return self

    @abstractmethod
    def rows(self) -> tuple[tuple[str, str], ...]:
        """Every view of this sheet: labels head the player's panel, and a prompt lowers them."""


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


class SheetAdvancement(Advancement):
    def earned(self, state: Game) -> int:
        return SheetMechanics.of_game(state).completed.current


class SheetEngine[S: SheetBase](Engine):
    sheet_type: type[S]
    # Narrows a class attribute the base only ever reads; `Engine` itself is not generic.
    mechanics_type: type[SheetMechanics[S]]  # pyright: ignore[reportIncompatibleVariableOverride]

    def overlay_rows(self, rules: dict[str, JsonValue]) -> tuple[tuple[str, str], ...]:
        return self.sheet_type.model_validate(rules).rows()

    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> SheetMechanics[S]:
        # Validated as one map so a bad overlay is refused at `sheets.<entity id>.<field>`.
        return self.mechanics_type.model_validate(
            {
                "sheets": {
                    entity.id: player_rules if entity.id == PLAYER_ID else entity.rules
                    for entity in world.entities
                    if entity.id == PLAYER_ID or self.uses_sheet(entity)
                }
            }
        )

    def uses_sheet(self, entity: Entity) -> bool:
        return bool(entity.rules)

    def check_scenario(self, scenario: Scenario) -> None:
        super().check_scenario(scenario)
        for entity in scenario.world.entities:
            if not entity.rules:
                continue
            try:
                sheet = self.sheet_type.model_validate(entity.rules)
            except ValidationError as broken:
                first = broken.errors()[0]
                place = ".".join(str(part) for part in ("sheets", entity.id, *first["loc"]))
                raise ValueError(f"{place}: {first['msg']}") from broken
            if missing := sorted(set(sheet.packs) - set(scenario.packs)):
                raise ValueError(
                    f"{entity.id!r} uses packs the scenario does not select: {missing}"
                )
            self.check_sheet(entity, sheet)

    def check_sheet(self, entity: Entity, sheet: S) -> None:
        del entity, sheet

    def validate(self, state: Game) -> None:
        sheets = self.mechanics_type.of_game(state).sheets
        if state.player_id not in sheets:
            raise ValueError(f"the {self.id} mechanics name no player")
        required = {entity.id for entity in state.world.entities if self.uses_sheet(entity)}
        if missing := sorted(required - set(sheets)):
            raise ValueError(f"entities have no character sheet to play by: {missing}")
        if gone := sorted(set(sheets) - state.world.all_ids()):
            raise ValueError(f"mechanics name actors the world does not hold: {gone}")
        installed = set(self.pack_ids)
        if missing_packs := sorted(
            {pack for sheet in sheets.values() for pack in sheet.packs if pack not in installed}
        ):
            raise ValueError(f"sheets use packs that are not installed: {missing_packs}")

    def meanings(self, sheet: S) -> tuple[tuple[str, str], ...]:
        del sheet
        return ()

    def describe(self, state: Game, entity: Entity) -> str:
        sheet = self.mechanics_type.of_game(state).sheets.get(entity.id)
        if sheet is None:
            return ""
        meanings = self.meanings(sheet)
        lines: list[str] = []
        for label, value in sheet.rows():
            if not value:
                continue
            lines.append(f"{label.lower()}: {value}")
            listed = value.split(", ")
            lines.extend(f"- {tag}: {detail}" for tag, detail in meanings if tag in listed)
        return "\n".join(lines)

    def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
        return self.mechanics_type.of_game(state).sheets[state.player_id].rows()

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng
        mechanics = self.mechanics_type.of_game(draft)
        if not self.uses_sheet(entity) or entity.id in mechanics.sheets:
            return
        # The sheet lands first: the ledger this brings level is a counter on it.
        mechanics.sheets[entity.id] = self.sheet_type.model_validate(entity.rules)
        # A newcomer starts level with the party: what closed before they joined is not owed.
        self.advancement.ledger(draft, entity.id).current = mechanics.completed.current


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
    """Every mutation runs this sequence, so seeding cannot be forgotten by a caller."""
    before = draft.pending
    landed = play(draft, rng)
    decided = draft.pending
    landed = (*landed, *engine.settle(draft))
    if draft.pending is not decided:
        raise ValueError("settle applies consequences; it cannot open a decision")
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


def complete_chapter(draft: Game, ending: str) -> list[Fact]:
    SheetMechanics.of_game(draft).completed.current += 1
    return [
        Fact(
            kind="chapter_completed",
            trace=ending,
            told=True,
            event=MechanicEvent(title=ending, icon="auto_stories"),
        )
    ]


def chapter_command(description: str, ending: str) -> Command:
    """Every engine closes a chapter the same way; only what it calls one differs."""
    return command(
        "complete_chapter",
        description,
        NoArgs,
        lambda deps, _args: apply_action(deps, lambda draft: complete_chapter(draft, ending)),
    )


def run_command(found: Command, deps: DirectorContext, raw: Mapping[str, JsonValue]) -> str:
    """The one gate: a decision on the table blocks everything but developing its answer."""
    pending = deps.draft.pending
    if pending is not None and not (found.during_suspension and deps.suspended_at_start):
        raise ValueError(
            f"the rules are waiting on the player: {pending.prompt}\n"
            "Put that to the player, then start the next turn with their answer."
        )
    return found.call(deps, raw)
