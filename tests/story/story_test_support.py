from random import Random

from core_test_support import initialized as initial_story_game
from core_test_support import tool_context, turn_context

from aidm.core.facts import Fact
from aidm.core.registry import AnyEngine
from aidm.core.world import EngineRules, GameState
from aidm.engines.story.tools import risk, take_stress

__all__ = ["initial_story_game", "setback"]

SETBACK_SEED = 2  # Random(2) rolls 1+1, so an extreme risk on an unraised approach always fails


def setback(
    engine: AnyEngine, state: GameState[EngineRules], *, stress: bool = False
) -> tuple[GameState[EngineRules], tuple[Fact, ...]]:
    """A player setback driven through the tools: the only thing that earns a growth mark."""
    context = turn_context(engine, state, Random(SETBACK_SEED))
    run = tool_context(context)
    _ = risk(run, approach="empathetic", difficulty=2)
    if stress:
        _ = take_stress(run, amount=1)
    return context.draft.committed(), tuple(context.facts)
