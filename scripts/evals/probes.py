"""Probes name state in post-refactor terms and resolve them against the shape this checkout has.

A scenario says `pool: "slot-1"` or `tag: "advancement-ready"`; today those land on `StatBlock` and
`Progression`, after phase 3 they are `Sheet` keys. Only this module changes with them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from random import Random
from typing import Annotated, Literal

from pydantic import Field, JsonValue

from aidm.core.base import PLAYER_ID, EntityId, Frozen
from aidm.core.facts import Fact
from aidm.core.packs import load
from aidm.core.registry import AnyEngine
from aidm.core.world import EngineRules, GameState
from aidm.engines.dnd5e.access import read_actor
from aidm.engines.dnd5e.advancement import (
    Dnd5eAdvancement,
    Dnd5eAdvancementDecisions,
    dump_decision,
)
from aidm.engines.dnd5e.content.pack_ruleset import compile_ruleset
from aidm.engines.dnd5e.content.registry import PACK_FORMAT
from aidm.engines.dnd5e.content.vocabulary import CONDITION_NAMES, ConditionName
from aidm.engines.dnd5e.engine import SHIPPED_PACK
from aidm.engines.dnd5e.progression import offer
from aidm.engines.dnd5e.ruleset import Ruleset
from aidm.engines.dnd5e.state import Dnd5eActorState, Progression, ResourceState
from aidm.engines.dnd5e.values import ABILITIES, Attributes

HP = "hp"
MAX_HP = "max-hp"
ARMOR_CLASS = "armor-class"
SLOT_PREFIX = "slot-"
ADVANCEMENT_READY = "advancement-ready"
# Every d20 compared against a target number: an attack against AC, a check or save against a DC.
CONTESTED_KINDS = ("attack_rolled", "dc_rolled")
TARGET_FIELDS = ("ac", "dc")
# Keyed by plain str so a scenario's tag can be looked up without widening the literal away.
CONDITIONS: dict[str, ConditionName] = {name: name for name in CONDITION_NAMES}


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
    """The state a scenario's setup steps build, before the director sees it."""

    engine: AnyEngine
    state: GameState[EngineRules]
    rng: Random


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one turn produced, in the terms checks are written against."""

    before: GameState[EngineRules]
    after: GameState[EngineRules]
    facts: tuple[Fact, ...]


def apply_setup(setup: Setup, steps: Sequence[SetupStep]) -> GameState[EngineRules]:
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
            _write_pool(_actor(state, step.entity), step.entity, step.pool, step.remaining)
        case SetNumber():
            _write_number(_actor(state, step.entity), step.key, step.value)
        case SetLevel():
            _level_up_to(setup, step.value)
        case AddTag():
            _write_tag(_actor(state, step.entity), step.tag)


def _actor(state: GameState[EngineRules], entity_id: EntityId) -> Dnd5eActorState:
    rules = state.world.record(entity_id, "actor").rules
    if not isinstance(rules, Dnd5eActorState):
        raise ValueError(f"{entity_id!r} carries {type(rules).__name__}, which no probe reads yet")
    return rules


def _progression(actor: Dnd5eActorState, entity_id: EntityId) -> Progression:
    if actor.progression is None:
        raise ValueError(f"{entity_id!r} has no progression, so it holds no slots and no level")
    return actor.progression


def _resource(actor: Dnd5eActorState, entity_id: EntityId, pool: str) -> ResourceState:
    """A slot level, or the use pool of the one owned feature whose index is `pool`."""
    progression = _progression(actor, entity_id)
    if pool.startswith(SLOT_PREFIX):
        level = _slot_level(pool)
        found = progression.spell_slots.get(level)
        if found is None:
            held = sorted(progression.spell_slots)
            raise ValueError(f"{entity_id!r} holds no {pool} slots; it has levels {held}")
        return found
    matched = [
        state for key, state in progression.feature_resources.items() if key.endswith(f"/{pool}")
    ]
    if len(matched) != 1:
        held = sorted(progression.feature_resources)
        raise ValueError(f"{entity_id!r} has no single feature pool {pool!r}; it has {held}")
    return matched[0]


def _slot_level(pool: str) -> int:
    digits = pool.removeprefix(SLOT_PREFIX)
    if not digits.isdigit():
        raise ValueError(f"pool {pool!r} names no slot level")
    return int(digits)


def _pool(state: GameState[EngineRules], entity_id: EntityId, pool: str) -> int:
    actor = _actor(state, entity_id)
    if pool == HP:
        return actor.stats.hp
    return _resource(actor, entity_id, pool).remaining


def _write_pool(actor: Dnd5eActorState, entity_id: EntityId, pool: str, remaining: int) -> None:
    if pool == HP:
        actor.stats.hp = remaining
        return
    resource = _resource(actor, entity_id, pool)
    if remaining > resource.maximum:
        raise ValueError(f"{entity_id!r} {pool} holds at most {resource.maximum}, not {remaining}")
    resource.remaining = remaining


def _write_number(actor: Dnd5eActorState, key: str, value: int) -> None:
    if key == ARMOR_CLASS:
        actor.stats.ac = value
        return
    if key == MAX_HP:
        actor.stats.max_hp = value
        actor.stats.hp = min(actor.stats.hp, value)
        return
    if key in ABILITIES:
        raised = {**actor.stats.attributes.model_dump(), key: value}
        actor.stats.attributes = Attributes.model_validate(raised)
        return
    raise ValueError(f"no 5e number is named {key!r}: use {ARMOR_CLASS}, {MAX_HP}, or an ability")


def _write_tag(actor: Dnd5eActorState, tag: str) -> None:
    condition = CONDITIONS.get(tag)
    if condition is None:
        raise ValueError(f"no 5e condition is named {tag!r}: {sorted(CONDITIONS)}")
    actor.stats.apply_condition(condition, active=True)


def _tags(state: GameState[EngineRules], entity_id: EntityId) -> frozenset[str]:
    """Conditions today, plus the level-up flag phase 3 turns into a real tag."""
    actor = _actor(state, entity_id)
    held: set[str] = set(actor.stats.conditions)
    if actor.progression is not None and actor.progression.level_up_available:
        held.add(ADVANCEMENT_READY)
    return frozenset(held)


def _level_up_to(setup: Setup, level: int) -> None:
    """Typed 5e starts every character at level 1, so a higher level has to be played out."""
    advancement = Dnd5eAdvancement(_shipped_ruleset())
    while (reached := _progression(_actor(setup.state, PLAYER_ID), PLAYER_ID).level) < level:
        offer(read_actor(setup.state, PLAYER_ID))
        committed = setup.state.committed()
        decisions = {
            choice.id: tuple(option.key for option in choice.options[: choice.choose])
            for choice in advancement.preview(committed).choices
        }
        decision = dump_decision(Dnd5eAdvancementDecisions(decisions=decisions))
        setup.state = setup.engine.advance(decision, committed, setup.rng).state
        if _progression(_actor(setup.state, PLAYER_ID), PLAYER_ID).level == reached:
            raise ValueError(f"level {reached} did not advance, so level {level} is unreachable")


@cache
def _shipped_ruleset() -> Ruleset:
    """The probe's own copy: `Engine` exposes no advancement preview to pick level choices from."""
    return compile_ruleset(load((SHIPPED_PACK,), PACK_FORMAT))


def _contested(facts: Sequence[Fact]) -> tuple[Fact, ...]:
    return tuple(fact for fact in facts if fact.kind in CONTESTED_KINDS)


def _targets_within(facts: Sequence[Fact], step: RollTarget) -> str | None:
    rolled = _contested(facts)
    if not rolled:
        return "nothing was rolled against a target number"
    for fact in rolled:
        target = _target_of(fact)
        if fault := _within(target, step.min, step.max, f"target number of {fact.trace!r}"):
            return fault
    return None


def _target_of(fact: Fact) -> int:
    for name in TARGET_FIELDS:
        found = fact.data.get(name)
        if found is not None:
            return _as_int(found, name)
    raise ValueError(f"{fact.kind!r} records no target number: {sorted(fact.data)}")


def _as_int(value: JsonValue, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} recorded {value!r}, which is not a whole number")
    return value


def _within(value: int, low: int, high: int, what: str) -> str | None:
    if low <= value <= high:
        return None
    return f"{what} was {value}, wanted {low}..{high}"
