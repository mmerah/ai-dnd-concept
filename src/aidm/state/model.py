import re
from collections import Counter as Tally
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Annotated, Literal, NewType, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, or an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Mutable(BaseModel):
    """State a resolution mutates in place; commit revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")


Kind = Literal["actor", "location", "item"]


def kind_word(kind: Kind) -> str:
    """Prompts and traces say 'npc', because 'actor' reads as the player too."""
    return "npc" if kind == "actor" else kind


ThreadStatus = Literal["active", "resolved", "dormant"]
EngineId = NewType("EngineId", str)
EntityId = NewType("EntityId", str)
SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SLUG_MAX = 64
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)]

PLAYER_ID = EntityId("player")


def content_id(value: str) -> Slug:
    """Narrow a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    return EntityId(_unused(base, taken, "_"))


def text_slug(text: str, taken: Iterable[str]) -> Slug:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return _unused(_capped(words, SLUG_MAX), taken, "-", SLUG_MAX)


def _unused(base: str, taken: Iterable[str], join: str, limit: int | None = None) -> str:
    used, candidate, number = set(taken), base, 2
    while candidate in used:
        suffix = f"{join}{number}"
        room = base if limit is None else _capped(base, limit - len(suffix))
        candidate, number = f"{room}{suffix}", number + 1
    return candidate


def _capped(words: str, limit: int) -> str:
    return words[:limit].rstrip("-") or "entry"


def duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(name for name, count in Tally(ids).items() if count > 1)


def require_unique(what: str, ids: Iterable[str]) -> None:
    if found := duplicates(ids):
        raise ValueError(f"duplicate {what}: {found}")


class Counter(Mutable):
    current: int
    maximum: int | None = None  # None is unbounded: wealth, experience

    @model_validator(mode="after")
    def _within_bounds(self) -> Self:
        if self.current < 0:
            raise ValueError(f"{self.current} is below zero")
        if self.maximum is not None and self.current > self.maximum:
            raise ValueError(f"{self.current} is above maximum {self.maximum}")
        return self

    def clamped(self, value: int) -> int:
        bounded = max(value, 0)
        return bounded if self.maximum is None else min(bounded, self.maximum)


class EntityDetail(Frozen):
    description: str
    when_reached: str


class Trait(Frozen):
    """A lasting fictional quality interpreted by engines, not core."""

    id: Slug
    name: str
    text: str = ""


class Exit(Mutable):
    """A way out of one location, in one direction: an author writes both ends."""

    to: EntityId
    known: bool = False
    locked: bool = False


class Entity(Mutable):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False
    # Which kinds may hold which is one rule, in `world.check_placement`.
    parent_id: EntityId | None = None
    traits: list[Trait] = Field(default_factory=list)
    exits: list[Exit] = Field(default_factory=list)

    def trait(self, trait_id: str) -> Trait | None:
        return next((held for held in self.traits if held.id == trait_id), None)

    def exit_to(self, to_id: EntityId) -> Exit | None:
        return next((way for way in self.exits if way.to == to_id), None)

    @model_validator(mode="after")
    def _traits_are_unambiguous(self) -> Self:
        require_unique(f"trait ids on {self.id!r}", (held.id for held in self.traits))
        return self

    @model_validator(mode="after")
    def _exits_are_unambiguous(self) -> Self:
        require_unique(f"exits of {self.id!r}", (way.to for way in self.exits))
        if any(way.to == self.id for way in self.exits):
            raise ValueError(f"location {self.id!r} has an exit to itself")
        return self


NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Chip(Frozen):
    """A small player-facing card a fact earns, phrased where its own values were in scope."""

    title: str
    icon: str = "casino"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)
    chip: Chip | None = None


def labeled(entity: Entity) -> str:
    """A trace names an entity by kind, name, and exact id, so the Director can reuse the id."""
    word = "player" if entity.id == PLAYER_ID else kind_word(entity.kind)
    return f"the {word} {entity.name}[{entity.id}]"


def entity_fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    *,
    narrate: bool = True,
    chip: Chip | None = None,
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        kind=kind,
        trace=trace,
        narrator=trace if narrate and entity.known else None,
        data={"entity_id": entity.id, **data},
        chip=chip,
    )


def explained_fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    why: str,
    *,
    narrate: bool = True,
) -> Fact:
    """The `why` is what the advancement panel shows the player before they confirm."""
    rendered = f"{trace} ({why})" if why else trace
    return entity_fact(entity, kind, rendered, data, narrate=narrate)


def narrator_lines(facts: Sequence[Fact]) -> tuple[str, ...]:
    return tuple(told for fact in facts if (told := fact.narrator) is not None)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    return "\n".join(f"- {told}" for told in narrator_lines(facts)) or NOTHING_MECHANICAL


class Line(Frozen):
    speaker_id: EntityId | None = Field(
        default=None,
        description="Exact id of who speaks this line, or null when it is narration, not speech.",
    )
    text: str = Field(min_length=1, description="One spoken line, or a passage of narration.")


def narration_text(lines: Sequence[Line]) -> str:
    return "\n".join(line.text for line in lines)


class Narration(Frozen):
    """The Narrator's answer: the one role that writes prose now says who speaks each line."""

    lines: tuple[Line, ...] = Field(
        description="The narration in order: 2-4 sentences in all, split by who says them."
    )

    @property
    def text(self) -> str:
        return narration_text(self.lines)


class EventBadge(Frozen):
    label: str
    value: str


class DiceEvent(Frozen):
    label: str
    faces: tuple[int, ...]
    rolled: tuple[int, ...]
    kept: int

    @model_validator(mode="after")
    def _rolled_matches_faces(self) -> Self:
        if len(self.rolled) != len(self.faces):
            raise ValueError("one rolled value per face")
        for die, face in zip(self.rolled, self.faces, strict=True):
            if not 1 <= die <= face:
                raise ValueError(f"a d{face} cannot show {die}")
        if self.kept not in self.rolled:
            raise ValueError("the kept die must be among those rolled")
        return self


class MechanicEvent(Frozen):
    """Player-facing: no field for model-authored free text, so a canon leak has no channel."""

    tool: str
    title: str
    badges: tuple[EventBadge, ...] = ()
    dice: tuple[DiceEvent, ...] = ()
    outcome: str = ""
    effects: tuple[str, ...] = ()
    icon: str = "casino"


# Laxer than `Slug`: 24XX's defence options are carried-item entity ids, which allow underscores.
OptionId = Annotated[str, Field(pattern=r"^[a-z0-9_-]+$", max_length=64)]


class Option(Frozen):
    id: OptionId
    label: str = Field(min_length=1)
    detail: str = ""


class PendingDecision(Frozen):
    """One decision the game waits on; None at `Game.pending` means the composer is the only way."""

    kind: Slug
    # A prose-less segment replays into model history from this alone, so it can never be empty.
    prompt: str = Field(min_length=1)
    options: tuple[Option, ...]
    free_text: bool = True
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def _is_answerable(self) -> Self:
        require_unique("option ids", (option.id for option in self.options))
        if not self.options and not self.free_text:
            raise ValueError(f"the {self.kind!r} decision offers no way to answer it")
        return self


class Answer(Frozen):
    """What the player submits: a chosen option or written text, never both."""

    option_id: OptionId | None = None
    text: str = ""

    @model_validator(mode="after")
    def _answers_one_way(self) -> Self:
        if (self.option_id is None) == (not self.text):
            raise ValueError("an answer is either a chosen option or written text")
        return self


class Exchange(Frozen):
    prompt: str
    lines: tuple[Line, ...]
    events: tuple[MechanicEvent, ...] = ()
    # The suspending decision's prompt: the pause has to survive after `Game.pending` clears.
    decision: str = ""

    @property
    def narration(self) -> str:
        return narration_text(self.lines)


class StepTrace(Frozen):
    name: str
    prompt: str
    output: dict[str, JsonValue] | str


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    prompt: str
    narration: str
    steps: tuple[StepTrace, ...] = ()


class Applied(TraceEntryBase):
    """One advancement change: the same transaction as a turn, without a prompt or a narration."""

    subject_id: EntityId


class Extended(TraceEntryBase):
    """Canon a background authoring run appended."""


type TraceEntry = Turn | Applied | Extended


_HOLDERS: Mapping[Kind, tuple[Kind, ...]] = {
    "actor": ("location",),
    "item": ("actor", "location"),
    "location": (),
}


def check_placement(entity: Entity, holder: Entity | None) -> None:
    allowed = _HOLDERS[entity.kind]
    if not allowed:
        if entity.parent_id is not None:
            raise ValueError(f"{entity.kind} {entity.id!r} cannot be inside anything")
        return
    if holder is None:
        raise ValueError(f"{entity.kind} {entity.id!r} is not in a valid {' or '.join(allowed)}")
    if holder.kind not in allowed:
        raise ValueError(f"{entity.kind} {entity.id!r} is in a {holder.kind}, which cannot hold it")


class Thread(Mutable):
    """A storyline the scenario tracks: a quest, an investigation, or a countdown."""

    id: Slug
    title: str
    status: ThreadStatus = "active"
    stage: Slug | None = None
    note: str = ""
    clock: Counter | None = None

    @model_validator(mode="after")
    def _a_clock_fills(self) -> Self:
        if self.clock is not None and self.clock.maximum is None:
            raise ValueError(f"thread {self.id!r} has a clock with no maximum to fill")
        return self


class AdvanceThread(Frozen):
    thread_id: Slug = Field(description="Exact id of one thread in ACTIVE THREADS.")
    status: ThreadStatus | None = Field(
        default=None, description="Where the thread now stands, or null to leave it as it is."
    )
    stage: Slug | None = Field(
        default=None,
        description="Stable slug for the point it has reached, or null to leave it as it is.",
    )
    tick: int = Field(
        default=0,
        description="How many segments this fills on the thread's clock, when it has one.",
    )
    note: str | None = Field(
        default=None,
        description="Replace the thread's private bookkeeping note with what its new state means "
        "for play, or null to keep it.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.tick < 0:
            raise ValueError("a tick fills a clock; it never runs one backwards")
        if self.status is None and self.stage is None and not self.tick:
            raise ValueError("advance-thread moves a thread's status, its stage, or its clock")
        return self


class WorldState(Mutable):
    """The whole persistent fiction; `Game` holds the played game around it."""

    entities: list[Entity] = Field(default_factory=list)
    threads: list[Thread] = Field(default_factory=list)
    party: list[EntityId] = Field(default_factory=list)
    pending_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent_fiction(self) -> Self:
        require_unique("entity ids", (entity.id for entity in self.entities))
        require_unique("thread ids", (thread.id for thread in self.threads))
        for entity in self.entities:
            # `find`, not `require`: a dangling id is a topology fault, not a lookup failure.
            holder = None if entity.parent_id is None else self.find(entity.parent_id)
            check_placement(entity, holder)
            self._check_exits(entity)
        self._check_party()
        return self

    def _check_exits(self, entity: Entity) -> None:
        """Reject known exits that would expose an unknown destination."""
        if entity.exits and entity.kind != "location":
            raise ValueError(f"{entity.kind} {entity.id!r} cannot have exits")
        for way in entity.exits:
            far = self.require_kind(way.to, "location")
            if way.known and not (entity.known and far.known):
                raise ValueError(
                    f"the known way from {entity.id!r} to {way.to!r} names a place the player "
                    "has not met"
                )

    def _check_party(self) -> None:
        require_unique("party members", self.party)
        if PLAYER_ID in self.party:
            raise ValueError("the player cannot travel with themselves")
        for member_id in self.party:
            member = self.require_kind(member_id, "actor")
            if not member.known:
                raise ValueError(f"{member_id!r} travels with the player without being met")

    def of_kind(self, kind: Kind) -> Iterator[Entity]:
        return (entity for entity in self.entities if entity.kind == kind)

    def all_ids(self) -> set[EntityId]:
        return {entity.id for entity in self.entities}

    def find(self, entity_id: EntityId) -> Entity | None:
        return next((entity for entity in self.entities if entity.id == entity_id), None)

    def thread(self, thread_id: Slug) -> Thread | None:
        return next((thread for thread in self.threads if thread.id == thread_id), None)

    def require(self, entity_id: EntityId) -> Entity:
        entity = self.find(entity_id)
        if entity is None:
            raise ValueError(f"unknown entity id {entity_id!r}. Use only ids you were shown.")
        return entity

    def require_kind(self, entity_id: EntityId, kind: Kind) -> Entity:
        entity = self.require(entity_id)
        if entity.kind != kind:
            raise ValueError(
                f"{entity_id!r} is a {entity.kind}, not a {kind}. "
                "Use an id of the kind this field asks for."
            )
        return entity

    def children(self, entity_id: EntityId, kind: Kind | None = None) -> tuple[Entity, ...]:
        held = self.entities if kind is None else self.of_kind(kind)
        return tuple(entity for entity in held if entity.parent_id == entity_id)

    def location_of(self, entity: Entity) -> EntityId | None:
        """Walk holders up to the enclosing place; a location is inside none, so it has none."""
        current = entity
        while current.parent_id is not None:
            current = self.require(current.parent_id)
        return None if current.id == entity.id else current.id


def check_player_playable(world: WorldState) -> None:
    if not world.require_kind(PLAYER_ID, "actor").known:
        raise ValueError("the player entity must be known")


def frontier(world: WorldState) -> int:
    """Unknown locations a known location leads to: doors the player can still find."""
    known = {entity.id for entity in world.entities if entity.known}
    return len(
        {
            way.to
            for entity in world.entities
            if entity.id in known
            for way in entity.exits
            if not world.require(way.to).known
        }
    )


class ScenarioMeta(Frozen):
    title: str
    premise: str


@dataclass(slots=True)
class Game:
    """The game as it is played; `SavedGame` is the boundary that validates one."""

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState
    # Opaque to core: the engine that wrote it is the only reader and the only validator.
    mechanics: Mutable
    history: tuple[Exchange, ...] = ()
    turn: int = 0
    pending: PendingDecision | None = None

    @property
    def player(self) -> Entity:
        return self.world.require_kind(PLAYER_ID, "actor")

    @property
    def player_location(self) -> EntityId:
        location = self.player.parent_id
        if location is None:
            raise ValueError("the player is not in a location")
        return location

    def is_here(self, entity: Entity) -> bool:
        return self.world.location_of(entity) == self.player_location

    def draft(self) -> Self:
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return deepcopy(self)

    def committed(self) -> Self:
        """One validation per transaction, over the whole copy rather than per field change."""
        landed = replace(
            self,
            world=_revalidated(self.world),
            mechanics=_revalidated(self.mechanics),
        )
        check_player_playable(landed.world)
        return landed

    def add(self, entity: Entity) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the entry."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities.append(entity)
        summary = f"new {kind_word(entity.kind)}: {entity.name}[{entity.id}]"
        return entity_fact(
            entity, "entity_created", summary, {"kind": entity.kind, "name": entity.name}
        )

    def reveal(self, entity: Entity) -> list[Fact]:
        """Leave chips to the containing action or the standalone reveal resolver."""
        if entity.known:
            return []
        entity.known = True
        summary = f"learned of {labeled(entity)}"
        return [entity_fact(entity, "entity_discovered", summary, {"name": entity.name})]

    def move(self, entity: Entity, destination: Entity) -> Fact:
        entity.parent_id = destination.id
        trace, chip = _move_summary(entity, destination)
        return entity_fact(
            entity,
            "entity_moved",
            trace,
            {
                "entity_name": entity.name,
                "entity_kind": entity.kind,
                "to_id": destination.id,
                "to_name": destination.name,
                "to_kind": destination.kind,
            },
            chip=chip,
        )


def check_draft(
    state: Game, act: Callable[[Game], object], what: str = "the state this leaves"
) -> str | None:
    draft = state.draft()
    try:
        _ = act(draft)
        _ = draft.committed()
    except ValidationError as broken:
        return f"{what} is invalid: {broken.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None


def _revalidated[M: Mutable](model: M) -> M:
    """Dumping runs no validator, so the dump is validated back: that is the commit gate."""
    return type(model).model_validate(model.model_dump(round_trip=True))


def _move_summary(entity: Entity, destination: Entity) -> tuple[str, Chip]:
    """Trace (ids, for the Director) and chip (plain names, for the player), from one branch."""
    icon = "directions_walk"
    if entity.kind == "actor":
        return (
            f"{labeled(entity)} moved to {labeled(destination)}",
            Chip(title=f"{entity.name} moved to {destination.name}", icon=icon),
        )
    if destination.id == PLAYER_ID:
        return (
            f"{labeled(destination)} took {labeled(entity)}",
            Chip(title=f"Took {entity.name}", icon="back_hand"),
        )
    if destination.kind == "actor":
        # The giver is always the player: an item only ever moves to an actor by being handed over.
        return (
            f"the player gave {labeled(entity)} to {labeled(destination)}",
            Chip(title=f"Gave {entity.name} to {destination.name}", icon=icon),
        )
    return (
        f"the player left {labeled(entity)} at {labeled(destination)}",
        Chip(title=f"Left {entity.name} at {destination.name}", icon=icon),
    )


# Engine option ids may contain repeated hyphens, unlike `Slug`.
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]

type Picks = Mapping[Slug, tuple[str, ...]]


class CreationOption(Frozen):
    id: ContentSlug
    label: str
    detail: str = ""


class CreationStep(Frozen):
    id: Slug
    prompt: str
    options: tuple[CreationOption, ...] = Field(min_length=1)
    choose: int = 1
    repeats: bool = False

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        # A repeatable step may ask for more picks than it offers options: they stack.
        distinct = self.choose <= len(self.options) or self.repeats
        if self.choose < 1 or not distinct:
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


class TextStep(Frozen):
    """A creation question the player answers in their own words."""

    id: Slug
    prompt: str
    hint: str = ""
    count: int = 1
    max_length: int = 100


type AnyStep = CreationStep | TextStep


def picked(picks: Picks, step_id: Slug) -> tuple[str, ...]:
    return picks.get(step_id, ())


def check_picks(steps: Sequence[AnyStep], picks: Picks) -> None:
    """One legality rule for the page and for `create`, so neither can drift."""
    known = {step.id for step in steps}
    if unknown := sorted(set(picks) - known):
        raise ValueError(f"no creation step is called {unknown}")
    for step in steps:
        answers = picked(picks, step.id)
        if isinstance(step, TextStep):
            _check_written(step, answers)
        else:
            _check_chosen(step, answers)


def _check_chosen(step: CreationStep, chosen: tuple[str, ...]) -> None:
    # Blank repeat slots are missing picks, not invalid offered options.
    named = tuple(pick for pick in chosen if pick)
    if not step.repeats and len(set(named)) != len(named):
        raise ValueError(f"{step.id!r} repeats a pick")
    if len(named) != step.choose:
        raise ValueError(f"{step.id!r} takes exactly {step.choose} picks, not {len(named)}")
    legal = {option.id for option in step.options}
    if outside := sorted(set(named) - legal):
        raise ValueError(f"{step.id!r} offers no {outside}")


def _check_written(step: TextStep, answers: tuple[str, ...]) -> None:
    if len(answers) != step.count:
        raise ValueError(f"{step.id!r} takes exactly {step.count} answers, not {len(answers)}")
    for answer in answers:
        if not answer.strip():
            raise ValueError(f"{step.id!r} takes an answer in words")
        if len(answer) > step.max_length:
            raise ValueError(f"{step.id!r} takes at most {step.max_length} characters")
