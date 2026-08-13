from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.state.base import Entity, EntityId, Frozen, Mutable, Slug
from aidm.state.facts import Fact, explained_fact
from aidm.state.world import GameState


def write_mechanics(state: GameState, mechanics: Mutable) -> None:
    # Dumping runs no validator, so the dump is validated back: that is the commit gate.
    payload = mechanics.model_dump(mode="json")
    _ = type(mechanics).model_validate(payload)
    state.mechanics = payload


def read_mechanics[M: Mutable](state: GameState, model: type[M]) -> M:
    return model.model_validate(state.mechanics)


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


class CounterChange(Frozen):
    """Move a counter: `adjust` shifts it by a delta, clamped to the counter's own bounds;
    `spend` pays a cost from it and refuses when the pool cannot cover it."""

    op: Literal["counter-change"] = "counter-change"
    mode: Literal["adjust", "spend"] = Field(
        description="`adjust` moves the pool, `spend` pays from it and can refuse."
    )
    entity_id: Annotated[
        EntityId,
        Field(
            description="Exact id of the entity affected; an actor must be here with the player."
        ),
    ]
    counter: Annotated[
        Slug,
        Field(description="Exact key of one of that entity's counters, as its state spells it."),
    ]
    amount: int = Field(
        description="For `adjust`, how much the pool moves: negative to reduce. For `spend`, how "
        "much of the pool is paid, always positive."
    )
    why: str = Field(
        default="",
        description="One short sentence saying what causes this change, for the player.",
    )

    @model_validator(mode="after")
    def _spend_pays(self) -> Self:
        """A negative spend would refill the pool it claims to pay from."""
        if self.mode == "spend" and self.amount < 1:
            raise ValueError("spend pays a positive amount; use adjust to raise a pool")
        return self


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


def spend(entity: Entity, key: str, counter: Counter, amount: int, why: str) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(entity, key, counter, -amount, why or f"spent {key}")]


def counter_fact(entity: Entity, key: str, counter: Counter, delta: int, why: str) -> Fact:
    data = {"counter": key, "delta": delta, "current": counter.current, "maximum": counter.maximum}
    trace = f"{entity.name} {key} {delta:+d} -> {pool(counter)}"
    return explained_fact(entity, "counter_changed", trace, data, why)


def render_counters(counters: dict[Slug, Counter]) -> str:
    return ", ".join(f"{key} {pool(counters[key])}" for key in sorted(counters))
