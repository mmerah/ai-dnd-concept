"""Probes name state the way a sheet spells it — `pool: "hp"`, `tag: "advancement-ready"` — and
resolve it against the entity's own engine mechanics."""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.engines.counters import Counter
from aidm.engines.loader import Engine
from aidm.engines.story import mechanics as story
from aidm.state.base import PLAYER_ID, EngineId, EntityId, Frozen, ThreadStatus, Trait
from aidm.state.facts import Fact
from aidm.state.world import GameState

STORY = EngineId("story")

HP = "hp"
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


class AddTag(Frozen):
    probe: Literal["add_tag"] = "add_tag"
    entity: EntityId = PLAYER_ID
    tag: str
    text: str = ""


type SetupStep = Annotated[Place | Reveal | SetPool | AddTag, Field(discriminator="probe")]


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


class ContestedRollHappened(Frozen):
    probe: Literal["contested_roll_happened"] = "contested_roll_happened"
    min: int = Field(default=1, ge=0)
    # An upper bound turns "something was rolled" into "exactly this much was rolled".
    max: int | None = Field(default=None, ge=0)


class BranchAddsTag(Frozen):
    """Asserts the plan itself, not the die: the seeds make some runs' roll a guaranteed miss, so a
    state check gated on the success branch firing would measure the roll, never the Director."""

    probe: Literal["branch_adds_tag"] = "branch_adds_tag"
    outcome: str = "success"
    entity: EntityId
    tag: str


class RollTarget(Frozen):
    """Bounds every target number rolled against."""

    probe: Literal["roll_target"] = "roll_target"
    min: int
    max: int


class NumberValue(Frozen):
    probe: Literal["number_value"] = "number_value"
    entity: EntityId = PLAYER_ID
    key: str
    min: int
    max: int


class RolledWithMode(Frozen):
    """Reads the plan through the die it produced: an advantage roll rolls twice and keeps one."""

    probe: Literal["rolled_with_mode"] = "rolled_with_mode"
    mode: Literal["normal", "advantage", "disadvantage"]


class Created(Frozen):
    """How many entities the turn added, which is the worldkeeper's whole output."""

    probe: Literal["created"] = "created"
    min: int = Field(default=0, ge=0)
    max: int = Field(ge=0)


class Remembered(Frozen):
    probe: Literal["remembered"] = "remembered"
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
    stage: str | None = None
    status: ThreadStatus | None = None

    @model_validator(mode="after")
    def _reads_something(self) -> Self:
        if self.stage is None and self.status is None:
            raise ValueError("thread_at reads a thread's stage, its status, or both")
        return self


class NoStateChange(Frozen):
    probe: Literal["no_state_change"] = "no_state_change"


type CheckStep = Annotated[
    PoolDelta
    | PoolValue
    | HasTag
    | NumberValue
    | RolledWithMode
    | Created
    | Remembered
    | ContestedRollHappened
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
    setup.engine.commit(setup.state)
    return setup.state.committed()


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
            held = step.tag in _traits(outcome.after, step.entity)
            if held == step.present:
                return None
            return f"{step.entity} tag {step.tag!r} is {'absent' if step.present else 'present'}"
        case NumberValue():
            held = _numbers(outcome.after, step.entity)
            if step.key not in held:
                return f"{step.entity} has no number {step.key!r}; it has {sorted(held)}"
            return _within(held[step.key], step.min, step.max, f"{step.entity} {step.key}")
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
        case Remembered():
            kept = len(set(outcome.after.world.memories) - set(outcome.before.world.memories))
            return _within(kept, step.min, step.max, "memories kept")
        case BranchAddsTag():
            if _branch_adds_tag(outcome.plan, step):
                return None
            return (
                f"the plan's {step.outcome!r} branch does not add tag {step.tag!r} to {step.entity}"
            )
        case ContestedRollHappened():
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
            if set(step.hooks) & set(outcome.after.world.fired_hooks):
                return None
            return f"none of {step.hooks} fired; those that did: {outcome.after.world.fired_hooks}"
        case ThreadAt():
            thread = outcome.after.world.threads.get(step.thread)
            if thread is None:
                held = sorted(outcome.after.world.threads)
                return f"no thread {step.thread!r}; the threads are {held}"
            if step.stage is not None and thread.stage != step.stage:
                return f"thread {step.thread} is at {thread.stage!r}, wanted {step.stage!r}"
            if step.status is not None and thread.status != step.status:
                return f"thread {step.thread} is {thread.status!r}, wanted {step.status!r}"
            return None
        case NoStateChange():
            # Mechanics sit outside `world`, so both halves of the state have to hold still.
            unchanged = (
                outcome.before.world == outcome.after.world
                and outcome.before.mechanics == outcome.after.mechanics
            )
            if unchanged:
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
            _write_pool(state, step.entity, step.pool, step.remaining)
        case AddTag():
            # Mirrors the runtime `trait-change` effect, so the rendered scene matches real play.
            entity = state.world.require(step.entity)
            name = step.tag.replace("-", " ").title()
            entity.traits.append(Trait(id=step.tag, name=name, text=step.text))


def _counter_for(
    state: GameState, entity_id: EntityId, pool: str
) -> tuple[story.Mechanics, Counter]:
    if state.engine != STORY:
        raise ValueError(f"probes support story, not {state.engine!r}")
    mechanics = story.read(state)
    counter = mechanics.actors[entity_id].counters().get(pool)
    if counter is None:
        known = ", ".join(sorted(mechanics.actors[entity_id].counters())) or "(none)"
        raise ValueError(f"{entity_id!r} holds no {pool!r} counter; it has {known}")
    return mechanics, counter


def _pool(state: GameState, entity_id: EntityId, pool: str) -> int:
    return _counter_for(state, entity_id, pool)[1].current


def _write_pool(state: GameState, entity_id: EntityId, pool: str, remaining: int) -> None:
    mechanics, counter = _counter_for(state, entity_id, pool)
    if counter.maximum is not None and remaining > counter.maximum:
        raise ValueError(f"{entity_id!r} {pool} holds at most {counter.maximum}, not {remaining}")
    counter.current = remaining
    story.write(state, mechanics)


def _numbers(state: GameState, entity_id: EntityId) -> dict[str, int]:
    if state.engine != STORY:
        raise ValueError(f"probes support story, not {state.engine!r}")
    approaches = story.read(state).actors[entity_id].approaches()
    return {str(name): value for name, value in approaches.items()}


def _traits(state: GameState, entity_id: EntityId) -> frozenset[str]:
    return frozenset(trait.id for trait in state.world.require(entity_id).traits)


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
            and effect.get("op") == "trait-change"
            and effect.get("mode") == "add"
            and effect.get("entity_id") == step.entity
            and effect.get("trait_id") == step.tag
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
