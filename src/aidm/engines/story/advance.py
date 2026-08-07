from aidm.engines.loader import Engine
from aidm.state.sheet import AdvancementOffer, Sheet
from aidm.state.world import GameState, player_sheet

from .actions import APPROACHES

GROWTH_REQUIRED = 3
MAX_APPROACH = 3
MAX_STRESS = 7
OFFER = AdvancementOffer(
    prompt="Three growth marks are ready to spend.",
    text=(
        "Say how the character has changed. One change only: raise an approach, gain an edge or "
        "a bond, leave a burden behind or rewrite it, or become more resilient."
    ),
)


def offered(engine: Engine, state: GameState) -> AdvancementOffer | None:
    del engine  # Story ships no packs, so nothing binds its growth to a record.
    growth = player_sheet(state).counters["growth"]
    return OFFER if growth.current >= GROWTH_REQUIRED else None


def check_delta(_state: GameState, after: Sheet) -> str | None:
    """Story's caps are absolute, so nothing before the change matters."""
    if raised := sorted(name for name in APPROACHES if after.numbers[name] > MAX_APPROACH):
        return f"an approach cannot pass +{MAX_APPROACH}: {raised}"
    stress = after.counters["stress"].maximum
    if stress is not None and stress > MAX_STRESS:
        return f"the stress maximum cannot pass {MAX_STRESS}, and this proposal reaches {stress}"
    if after.counters["growth"].current != 0:
        return f"the {GROWTH_REQUIRED} growth marks must be spent: take the growth counter to 0"
    return None
