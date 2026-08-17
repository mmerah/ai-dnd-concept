from aidm.state.base import Counter, Entity, Slug
from aidm.state.facts import Fact, explained_fact


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


def spend(entity: Entity, key: str, counter: Counter, amount: int) -> list[Fact]:
    if counter.current < amount:
        raise ValueError(
            f"{entity.name} holds {counter.current} {key}, so {amount} cannot be spent."
        )
    counter.current -= amount
    return [counter_fact(entity, key, counter, -amount, f"spent {key}")]


def counter_fact(entity: Entity, key: str, counter: Counter, delta: int, why: str) -> Fact:
    data = {"counter": key, "delta": delta, "current": counter.current, "maximum": counter.maximum}
    trace = f"{entity.name} {key} {delta:+d} -> {pool(counter)}"
    return explained_fact(entity, "counter_changed", trace, data, why)


def render_counters(counters: dict[Slug, Counter]) -> str:
    return ", ".join(f"{key} {pool(counters[key])}" for key in sorted(counters))
