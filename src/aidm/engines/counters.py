from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, model_validator

from aidm.state.base import Counter, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact, explained_fact


class Pools(Protocol):
    def counters(self) -> dict[Slug, Counter]: ...


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


def move_pool(sheet: Pools | None, entity: Entity, effect: CounterChange) -> list[Fact]:
    counter = None if sheet is None else sheet.counters().get(effect.counter)
    if counter is None:
        known = ", ".join(sorted(sheet.counters())) if sheet else "(none)"
        raise ValueError(f"{entity.name} has no pool {effect.counter!r}. Their pools are: {known}")
    if effect.mode == "adjust":
        return adjust(entity, effect.counter, counter, effect.amount, "")
    return spend(entity, effect.counter, counter, effect.amount, "")
