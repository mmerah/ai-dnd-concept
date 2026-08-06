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
from aidm.state.packs import Content, LenientRecord
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


type SetupStep = Annotated[
    Place | Reveal | SetPool | SetNumber | SetLevel | AddTag, Field(discriminator="probe")
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


class RollTarget(Frozen):
    """Bounds every target number rolled against: a chosen DC, or a target's armour class."""

    probe: Literal["roll_target"] = "roll_target"
    min: int
    max: int


class NoStateChange(Frozen):
    probe: Literal["no_state_change"] = "no_state_change"


type CheckStep = Annotated[
    PoolDelta | PoolValue | HasTag | AttackRollHappened | RollTarget | NoStateChange,
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
        case AttackRollHappened():
            rolled = len(_contested(outcome.facts))
            if step.max is None:
                if rolled >= step.min:
                    return None
                return f"{rolled} rolls against a target number, wanted at least {step.min}"
            return _within(rolled, step.min, step.max, "rolls against a target number")
        case RollTarget():
            return _targets_within(outcome.facts, step)
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
            _sheet(state, step.entity).tags.append(SheetTag(id=step.tag, name=step.tag))


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
        _apply_level(sheet, content.require(level_ref(sheet, step), LenientRecord))


def _apply_level(sheet: Sheet, record: LenientRecord) -> None:
    for key, value in record.numbers.items():
        if key.startswith(SLOT_PREFIX):
            slot = sheet.counters.setdefault(key, Counter(current=0, maximum=0, recharge=LONG_REST))
            slot.maximum, slot.current = value, value
        elif key in sheet.numbers:
            sheet.numbers[key] = value


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
