from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from aidm.state.apply import fire_hooks
from aidm.state.base import EntityId
from aidm.state.facts import Fact
from aidm.state.plan import Flow, Resolution
from aidm.state.world import GameState

from .loader import Engine


@dataclass(frozen=True, slots=True)
class Transacted:
    """One committed state change: the facts resolved, and the facts hooks fired in reaction."""

    state: GameState
    resolved: tuple[Fact, ...]
    fired: tuple[Fact, ...]
    flow: Flow = "continue"

    @property
    def facts(self) -> tuple[Fact, ...]:
        return (*self.resolved, *self.fired)


def transact(
    engine: Engine,
    draft: GameState,
    resolve: Callable[[GameState], Resolution],
    rng: Random,
) -> Transacted:
    """Every mutation runs this sequence, so hooks and seeding cannot be forgotten by a caller."""
    resolution = resolve(draft)
    fired = fire_hooks(draft, resolution.facts, engine.apply_effect)
    _seed_created(engine, draft, [*resolution.facts, *fired], rng)
    engine.validate(draft)
    return Transacted(
        state=draft.committed(),
        resolved=resolution.facts,
        fired=tuple(fired),
        flow=resolution.flow,
    )


def _seed_created(engine: Engine, draft: GameState, facts: Sequence[Fact], rng: Random) -> None:
    """Whoever created an entity this turn."""
    for fact in facts:
        created = fact.data.get("entity_id") if fact.kind == "entity_created" else None
        if isinstance(created, str):
            engine.seed(draft, draft.world.require(EntityId(created)), rng)
