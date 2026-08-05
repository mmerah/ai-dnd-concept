from pathlib import Path

from aidm.core.engine import AdvancementOffer, Engine
from aidm.core.enginepack import load_engine
from aidm.core.packs import Content
from aidm.core.registry import EnginePlugin
from aidm.core.sheet import Sheet, SheetDelta, apply_delta, player_sheet
from aidm.core.world import GameState

from .identity import ENGINE_ID

ENGINE_DIR = Path(__file__).parent
APPROACHES = ("bold", "subtle", "clever", "empathetic")
MAX_APPROACH = 3
MAX_STRESS = 7
GROWTH_REQUIRED = 3
OFFER = AdvancementOffer(
    prompt="Three growth marks are ready to spend.",
    text=(
        "Say how the character has changed. One change only: raise an approach, gain an edge or "
        "a bond, leave a burden behind or rewrite it, or become more resilient."
    ),
)


def _offered(state: GameState[Sheet], content: Content) -> AdvancementOffer | None:
    del content  # Story ships no packs, so nothing binds its growth to a record.
    growth = player_sheet(state).counters["growth"]
    return OFFER if growth.current >= GROWTH_REQUIRED else None


def _check(state: GameState[Sheet], offer: AdvancementOffer, delta: SheetDelta) -> str | None:
    """Story's own caps, read off the sheet the delta would leave behind."""
    del offer
    after = player_sheet(state).model_copy(deep=True)
    _ = apply_delta(after, delta)
    if raised := sorted(name for name in APPROACHES if after.numbers[name] > MAX_APPROACH):
        return f"an approach cannot pass +{MAX_APPROACH}: {raised}"
    stress = after.counters["stress"].maximum
    if stress is not None and stress > MAX_STRESS:
        return f"the stress maximum cannot pass {MAX_STRESS}, and this proposal reaches {stress}"
    if after.counters["growth"].current != 0:
        return f"the {GROWTH_REQUIRED} growth marks must be spent: take the growth counter to 0"
    return None


def build_story_engine() -> Engine[Sheet]:
    return load_engine(ENGINE_DIR, ENGINE_ID, offered=_offered, check=_check)


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    build=lambda _config: build_story_engine(),
    badge=("STORY", "deep-purple-6"),
)
