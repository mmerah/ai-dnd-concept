"""Probes name state the way a sheet spells it — `pool: "slot-1"`, `tag: "advancement-ready"`,
`key: "armor-class"` — and resolve it against the entity's `Sheet`."""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import Annotated, Literal

from pydantic import Field, JsonValue

from aidm.engines.dnd5e.advance import level_ref
from aidm.engines.loader import Engine
from aidm.state.base import PLAYER_ID, EntityId, Frozen
from aidm.state.facts import Fact
from aidm.state.packs import Content, Record, is_int_fact
from aidm.state.sheet import Counter, Sheet, SheetTag
from aidm.state.world import GameState

HP = "hp"
MAX_HP = "max-hp"
LEVEL = "level"
SLOT_PREFIX = "slot-"
LONG_REST = "long-rest"
CONTESTED_KIND = "dice_rolled"


class Place(Frozen):
    probe: Literal["place"] = "place"
    entity: EntityId
    location: EntityId


class Reveal(Frozen):
    probe: Literal["reveal"] = "reveal"
    entity: EntityId


class SetPool(Frozen):
    probe: Literal["set_pool"] = "set_pool"
    entity: EntityId = PLAYER_ID
    pool: str
    remaining: int = Field(ge=0)


class SetNumber(Frozen):
    probe: Literal["set_number"] = "set_number"
    entity: EntityId = PLAYER_ID
    key: str
    value: int


class SetLevel(Frozen):
    probe: Literal["set_level"] = "set_level"
    value: int = Field(ge=1)


class AddTag(Frozen):
    probe: Literal["add_tag"] = "add_tag"
    entity: EntityId = PLAYER_ID
    tag: str
    text: str = ""


class SetNote(Frozen):
    probe: Literal["set_note"] = "set_note"
    entity: EntityId = PLAYER_ID
    key: str
    text: str = Field(min_length=1)


type SetupStep = Annotated[
    Place | Reveal | SetPool | SetNumber | SetLevel | AddTag | SetNote, Field(discriminator="probe")
]


class PoolDelta(Frozen):
    probe: Literal["pool_delta"] = "pool_delta"
    entity: EntityId = PLAYER_ID
    pool: str = HP
    min: int
    max: int


class PoolValue(Frozen):
    probe: Literal["pool_value"] = "pool_value"
    entity: EntityId = PLAYER_ID
    pool: str = HP
    min: int
    max: int


class HasTag(Frozen):
    probe: Literal["has_tag"] = "has_tag"
    entity: EntityId = PLAYER_ID
    tag: str
    present: bool = True


class AttackRollHappened(Frozen):
    probe: Literal["attack_roll_happened"] = "attack_roll_happened"
    min: int = Field(default=1, ge=0)
    # An upper bound turns "something was rolled" into "exactly this much was rolled".
    max: int | None = Field(default=None, ge=0)


class BranchAddsTag(Frozen):
    """Asserts the plan itself, not the die: the seeds make some runs' d20 a guaranteed miss, so a
    state check gated on the success branch firing would measure the roll, never the Director."""

    probe: Literal["branch_adds_tag"] = "branch_adds_tag"
    outcome: str = "success"
    entity: EntityId
    tag: str


class RollTarget(Frozen):
    """Bounds every target number rolled against: a chosen DC, or a target's armour class."""

    probe: Literal["roll_target"] = "roll_target"
    min: int
    max: int


class NumberValue(Frozen):
    probe: Literal["number_value"] = "number_value"
    entity: EntityId = PLAYER_ID
    key: str
    min: int
    max: int


class HasRef(Frozen):
    probe: Literal["has_ref"] = "has_ref"
    entity: EntityId = PLAYER_ID
    ref: str
    present: bool = True


class NoteValue(Frozen):
    probe: Literal["note_value"] = "note_value"
    entity: EntityId = PLAYER_ID
    key: str
    contains: str = Field(min_length=1)


class RolledWithMode(Frozen):
    """Reads the plan through the die it produced: an advantage attack rolls twice and keeps one."""

    probe: Literal["rolled_with_mode"] = "rolled_with_mode"
    mode: Literal["normal", "advantage", "disadvantage"]


class Created(Frozen):
    """How many entities the turn added, which is the worldkeeper's whole output."""

    probe: Literal["created"] = "created"
    min: int = Field(default=0, ge=0)
    max: int = Field(ge=0)


class AtLocation(Frozen):
    probe: Literal["at_location"] = "at_location"
    entity: EntityId = PLAYER_ID
    location: EntityId


class HookFired(Frozen):
    """Passes when any named hook fired: one fiction can reach a thread by more than one hook."""

    probe: Literal["hook_fired"] = "hook_fired"
    hooks: tuple[str, ...] = Field(min_length=1)


class ThreadAt(Frozen):
    probe: Literal["thread_at"] = "thread_at"
    thread: str
    stage: str


class NoStateChange(Frozen):
    probe: Literal["no_state_change"] = "no_state_change"


type CheckStep = Annotated[
    PoolDelta
    | PoolValue
    | HasTag
    | NumberValue
    | HasRef
    | NoteValue
    | RolledWithMode
    | Created
    | AttackRollHappened
    | BranchAddsTag
    | RollTarget
    | AtLocation
    | HookFired
    | ThreadAt
    | NoStateChange,
    Field(discriminator="probe"),
]


@dataclass(slots=True)
class Setup:
    engine: Engine
    state: GameState
    rng: Random


@dataclass(frozen=True, slots=True)
class Outcome:
    before: GameState
    after: GameState
    facts: tuple[Fact, ...]
    plan: JsonValue = None


def apply_setup(setup: Setup, steps: Sequence[SetupStep]) -> GameState:
    """Commit once at the end, so a setup that breaks an invariant fails before the model runs."""
    for step in steps:
        _apply(setup, step)
    committed = setup.state.committed()
    setup.engine.validate_state(committed)
    return committed


def check(outcome: Outcome, step: CheckStep) -> str | None:
    """The reason the check failed, or None when it held."""
    match step:
        case PoolDelta():
            before = _pool(outcome.before, step.entity, step.pool)
            after = _pool(outcome.after, step.entity, step.pool)
            return _within(after - before, step.min, step.max, f"{step.entity} {step.pool} delta")
        case PoolValue():
            value = _pool(outcome.after, step.entity, step.pool)
            return _within(value, step.min, step.max, f"{step.entity} {step.pool}")
        case HasTag():
            held = step.tag in _tags(outcome.after, step.entity)
            if held == step.present:
                return None
            return f"{step.entity} tag {step.tag!r} is {'absent' if step.present else 'present'}"
        case NumberValue():
            held = _sheet(outcome.after, step.entity).numbers
            if step.key not in held:
                return f"{step.entity} has no number {step.key!r}; it has {sorted(held)}"
            return _within(held[step.key], step.min, step.max, f"{step.entity} {step.key}")
        case HasRef():
            refs = {str(ref) for ref in _sheet(outcome.after, step.entity).refs}
            if (step.ref in refs) == step.present:
                return None
            return f"{step.entity} ref {step.ref!r} is {'absent' if step.present else 'present'}"
        case NoteValue():
            held = _sheet(outcome.after, step.entity).notes.get(step.key, "")
            if step.contains.casefold() in held.casefold():
                return None
            return f"{step.entity} note {step.key!r} is {held!r}, wanted {step.contains!r} in it"
        case RolledWithMode():
            modes = [
                str(fact.data.get("mode")) for fact in outcome.facts if fact.kind == CONTESTED_KIND
            ]
            if step.mode in modes:
                return None
            return f"nothing was rolled with {step.mode}; the modes rolled were {sorted(modes)}"
        case Created():
            added = len(outcome.after.world.all_ids() - outcome.before.world.all_ids())
            return _within(added, step.min, step.max, "entities created")
        case BranchAddsTag():
            if _branch_adds_tag(outcome.plan, step):
                return None
            return (
                f"the plan's {step.outcome!r} branch does not add tag {step.tag!r} to {step.entity}"
            )
        case AttackRollHappened():
            rolled = len(_contested(outcome.facts))
            if step.max is None:
                if rolled >= step.min:
                    return None
                return f"{rolled} rolls against a target number, wanted at least {step.min}"
            return _within(rolled, step.min, step.max, "rolls against a target number")
        case RollTarget():
            return _targets_within(outcome.facts, step)
        case AtLocation():
            where = outcome.after.world.location_of(outcome.after.world.require(step.entity))
            if where == step.location:
                return None
            return f"{step.entity} is at {where!r}, wanted {step.location!r}"
        case HookFired():
            if set(step.hooks) & set(outcome.after.fired_hooks):
                return None
            return f"none of {step.hooks} fired; those that did: {outcome.after.fired_hooks}"
        case ThreadAt():
            thread = outcome.after.threads.get(step.thread)
            if thread is None:
                held = sorted(outcome.after.threads)
                return f"no thread {step.thread!r}; the threads are {held}"
            if thread.stage == step.stage:
                return None
            return f"thread {step.thread} is at {thread.stage!r}, wanted {step.stage!r}"
        case NoStateChange():
            if outcome.before.world == outcome.after.world:
                return None
            return "the world changed, and this turn should have changed nothing"


def _apply(setup: Setup, step: SetupStep) -> None:
    state = setup.state
    match step:
        case Place():
            entity = state.world.require(step.entity)
            state.move(entity, state.world.require_kind(step.location, "location"))
        case Reveal():
            state.reveal(state.world.require(step.entity))
        case SetPool():
            _write_pool(_sheet(state, step.entity), step.entity, step.pool, step.remaining)
        case SetNumber():
            _write_number(_sheet(state, step.entity), step.entity, step.key, step.value)
        case SetLevel():
            _level_up_to(setup.engine.content, state, step.value)
        case AddTag():
            # Mirrors the runtime `tag-change` effect, so the rendered scene matches real play.
            name = step.tag.replace("-", " ").title()
            _sheet(state, step.entity).tags.append(SheetTag(id=step.tag, name=name, text=step.text))
        case SetNote():
            _sheet(state, step.entity).notes[step.key] = step.text


def _sheet(state: GameState, entity_id: EntityId) -> Sheet:
    return state.world.record(entity_id, "actor").rules


def _counter(sheet: Sheet, entity_id: EntityId, pool: str) -> Counter:
    found = sheet.counters.get(pool)
    if found is None:
        held = sorted(sheet.counters)
        raise ValueError(f"{entity_id!r} holds no {pool!r} counter; it has {held}")
    return found


def _pool(state: GameState, entity_id: EntityId, pool: str) -> int:
    return _counter(_sheet(state, entity_id), entity_id, pool).current


def _write_pool(sheet: Sheet, entity_id: EntityId, pool: str, remaining: int) -> None:
    counter = _counter(sheet, entity_id, pool)
    if counter.maximum is not None and remaining > counter.maximum:
        raise ValueError(f"{entity_id!r} {pool} holds at most {counter.maximum}, not {remaining}")
    counter.current = remaining


def _write_number(sheet: Sheet, entity_id: EntityId, key: str, value: int) -> None:
    """`max-hp` is a counter's bound rather than a number, and the only key spelled that way."""
    if key == MAX_HP:
        counter = _counter(sheet, entity_id, HP)
        counter.maximum = value
        counter.current = min(counter.current, value)
        return
    if key not in sheet.numbers:
        raise ValueError(f"{entity_id!r} has no number {key!r}; it has {sorted(sheet.numbers)}")
    sheet.numbers[key] = value


def _tags(state: GameState, entity_id: EntityId) -> frozenset[str]:
    return frozenset(tag.id for tag in _sheet(state, entity_id).tags)


def _level_up_to(content: Content, state: GameState, level: int) -> None:
    """Characters are authored at level 1, so a scenario that wants a higher one applies the
    class's own level rows: what they raise is exactly what the advisor would raise."""
    sheet = _sheet(state, PLAYER_ID)
    for step in range(sheet.numbers[LEVEL] + 1, level + 1):
        _apply_level(sheet, content.require(level_ref(sheet, step), Record))


def _apply_level(sheet: Sheet, record: Record) -> None:
    for key, value in record.facts.items():
        if not is_int_fact(value):
            continue
        if key.startswith(SLOT_PREFIX):
            slot = sheet.counters.setdefault(key, Counter(current=0, maximum=0, recharge=LONG_REST))
            slot.maximum, slot.current = value, value
        elif key in sheet.numbers:
            sheet.numbers[key] = value


def _branch_adds_tag(plan: JsonValue, step: BranchAddsTag) -> bool:
    if not isinstance(plan, dict):
        return False
    branches = plan.get("branches")
    if not isinstance(branches, list):
        return False
    return any(
        isinstance(branch, dict)
        and branch.get("outcome") == step.outcome
        and isinstance(effects := branch.get("effects"), list)
        and any(
            isinstance(effect, dict)
            and effect.get("op") == "tag-change"
            and effect.get("mode") == "add"
            and effect.get("entity_id") == step.entity
            and effect.get("tag_id") == step.tag
            for effect in effects
        )
        for branch in branches
    )


def _contested(facts: Sequence[Fact]) -> tuple[Fact, ...]:
    return tuple(fact for fact in facts if _target_of(fact) is not None)


def _targets_within(facts: Sequence[Fact], step: RollTarget) -> str | None:
    rolled = _contested(facts)
    if not rolled:
        return "nothing was rolled against a target number"
    for fact in rolled:
        target = _target_of(fact)
        if target is None:
            continue
        if fault := _within(target, step.min, step.max, f"target number of {fact.trace!r}"):
            return fault
    return None


def _target_of(fact: Fact) -> int | None:
    """A `roll` given no `vs` was rolled against nothing, so it is not a contested roll."""
    if fact.kind != CONTESTED_KIND:
        return None
    target = fact.data.get("vs")
    return None if target is None else _as_int(target, "target number")


def _as_int(value: JsonValue, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} recorded {value!r}, which is not a whole number")
    return value


def _within(value: int, low: int, high: int, what: str) -> str | None:
    if low <= value <= high:
        return None
    return f"{what} was {value}, wanted {low}..{high}"
