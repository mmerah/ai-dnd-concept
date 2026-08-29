import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import ClassVar, Protocol

from pydantic import BaseModel, Field, JsonValue, ValidationError

from aidm.content.io import ENCODING
from aidm.content.model import Character
from aidm.state.creation import AnyStep, CreationOption, CreationStep, Picks, picked
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
)
from aidm.state.facts import (
    Fact,
    MechanicEvent,
    entity_fact,
    player_events,
    told_traces,
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
    return entity_fact(
        entity, "counter_changed", f"{trace} ({why})", event=MechanicEvent(title=title, icon=icon)
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
    chapters: int = 0


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
    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> Character:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


def load_packs[P: BaseModel](directories: Sequence[Path], model: type[P]) -> dict[str, P]:
    """Later directories win; a broken file raises rather than being skipped."""
    packs: dict[str, P] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            packs[path.stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
    if "srd" not in packs:
        raise ValueError(f"no srd content pack was found for {model.__module__}")
    return packs


def find_entry[T: CreationOption](entries: Sequence[T], chosen: str) -> T:
    return next(entry for entry in entries if entry.id == chosen)


class NamedPack(Protocol):
    name: str


class PackCreation[P: NamedPack](CharacterCreation):
    def __init__(self, packs: Mapping[str, P]) -> None:
        self.packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        options = tuple(
            CreationOption(id=one, label=one_pack.name) for one, one_pack in self.packs.items()
        )
        first = CreationStep(id="pack", prompt="Choose a character table set", options=options)
        pack = self.packs.get(chosen[0]) if (chosen := picked(picks, "pack")) else None
        return (first,) if pack is None else (first, *self.steps_for(pack, picks))

    @abstractmethod
    def steps_for(self, pack: P, picks: Picks) -> tuple[AnyStep, ...]: ...


class Decision(Frozen):
    """A decision's own fields are the `PendingDecision.payload` a save carries."""

    kind: ClassVar[Slug]

    def pending(
        self, prompt: str, options: tuple[DecisionOption, ...] = (), *, allows_text: bool = True
    ) -> PendingDecision:
        return PendingDecision(
            kind=self.kind,
            prompt=prompt,
            options=options,
            payload=self.model_dump(mode="json"),
            allows_text=allows_text,
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
    state: Game, sheet_type: type[S], ledger: Callable[[S], int]
) -> tuple[str, ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen payload the open decision holds.
    if state.pending is not None:
        return ()
    notes: list[str] = []
    for subject_id in (state.player_id, *state.world.party):
        subject = state.world.require(subject_id)
        sheet = sheet_type.model_validate(subject.rules)
        if sheet.chapters > ledger(sheet):
            notes.append(
                f"{subject.name} has an advance owed; call advance only when the player asks "
                "for it."
            )
    return tuple(notes)


# Declaring a director tool.


class NoArgs(Frozen):
    pass


@dataclass(frozen=True, slots=True)
class DirectorTool:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[Game, Mapping[str, JsonValue], Random], tuple[Fact, ...]]
    # Core world tools may still run in a turn that opened suspended; engine mechanics may not.
    during_suspension: bool = False


def director_tool[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    resolve: Callable[[Game, A, Random], Sequence[Fact]],
    *,
    during_suspension: bool = False,
) -> DirectorTool:
    """Validation lives here, so both harnesses reject the same arguments the same way."""
    if bare := [key for key, one in args.model_fields.items() if not one.description]:
        raise ValueError(f"{name} parameters the model reads carry no description: {bare}")

    def call(draft: Game, raw: Mapping[str, JsonValue], rng: Random) -> tuple[Fact, ...]:
        return tuple(resolve(draft, args.model_validate(raw), rng))

    return DirectorTool(name, description, args, call, during_suspension)


def complete_chapter[S: SheetBase](draft: Game, ending: str, sheet_type: type[S]) -> list[Fact]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    for member_id in (draft.player_id, *draft.world.party):
        member = draft.world.require(member_id)
        # A companion nobody wrote rules for has no sheet, and a chapter writes them none.
        if not member.rules:
            continue
        with rules(member, sheet_type) as sheet:
            sheet.chapters += 1
    return [
        Fact(
            kind="chapter_completed",
            trace=ending,
            told=True,
            event=MechanicEvent(title=ending, icon="auto_stories"),
        )
    ]


def chapter_tool[S: SheetBase](description: str, ending: str, sheet_type: type[S]) -> DirectorTool:
    """Every engine closes a chapter the same way; only what it calls one differs."""
    return director_tool(
        "complete_chapter",
        description,
        NoArgs,
        lambda draft, _args, _rng: complete_chapter(draft, ending, sheet_type),
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


def describe_by(
    rules_types: Mapping[Kind, type[EntityRules]],
) -> Callable[[Game, Entity], str]:
    """One entity's mechanics as a prompt reads them; the player's own panel is `sheet_rows`."""

    def describe(state: Game, entity: Entity) -> str:
        del state
        # An actor the scenario gave no rules is a threat the Director narrates, not a sheet.
        if entity.kind == "actor" and not entity.rules:
            return ""
        return describe_rows(rules_types[entity.kind].model_validate(entity.rules).rows(), ())

    return describe


@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    id: EngineId
    badge: tuple[str, str]
    director_instructions: str
    # Every entity's rules are parsed through the model its kind maps to; `validate` is the gate.
    rules_types: Mapping[Kind, type[EntityRules]]
    packs: Mapping[str, BaseModel]
    # The complete list: each engine spreads `CORE_TOOLS` itself, so core stays import-free.
    director_tools: tuple[DirectorTool, ...]
    creation: CharacterCreation
    describe: Callable[[Game, Entity], str]
    # What only this engine's rules can refuse, once every entity's own rules have parsed.
    checks: Callable[[Game], None] = lambda state: None
    decisions: tuple[type[Decision], ...] = ()
    player_actions: tuple[PlayerAction, ...] = ()
    authoring_instructions: str = ""
    owed_notes: Callable[[Game], tuple[str, ...]] = lambda state: ()

    def validate(self, state: Game) -> None:
        """Refuses a state this engine cannot play, rather than repairing one."""
        if missing := sorted(set(state.packs) - set(self.packs)):
            raise ValueError(f"the game names packs not installed for {self.id!r}: {missing}")
        for entity in state.world.entities:
            try:
                _ = self.rules_types[entity.kind].model_validate(entity.rules)
            except ValidationError as broken:
                first = broken.errors()[0]
                place = ".".join(str(part) for part in ("rules", entity.id, *first["loc"]))
                raise ValueError(f"{place}: {first['msg']}") from broken
        self.checks(state)

    def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""
        return self.rules_types["actor"].model_validate(state.player.rules).rows()

    def notes(self, state: Game) -> tuple[str, ...]:
        return (*state.world.pending_notes, *self.owed_notes(state))

    def check_overlay(self, overlay: dict[str, JsonValue]) -> None:
        """The character file this engine plays by, refused where it is read rather than in play."""
        _ = self.rules_types["actor"].model_validate(overlay)

    def authoring_context(self, pack_ids: tuple[Slug, ...]) -> str:
        # Defaults restate rules the guidance already carries; dropping them halves the prompt.
        packs = {
            pack_id: self.packs[pack_id].model_dump(mode="json", exclude_defaults=True)
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
        told = Line(text="\n".join(told_traces(facts)) or "Nothing changed.")
        draft.record(offer.label, (told,), player_events(facts))
        return facts

    return transact(engine, state.draft(), play, rng)
