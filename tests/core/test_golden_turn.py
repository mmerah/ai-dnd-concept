from collections.abc import Mapping
from random import Random

import pytest
from core_test_support import DND5E, STORY, game, plan, played, scripted, structured, text
from golden_test_support import FIXTURES, dumped, golden
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.function import FunctionModel

from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId
from aidm.state.world import Exchange, GameState
from aidm.turn.pipeline import TurnResult

PROMPT = "I lever up the loose flagstone and listen at the vault door."
# Played turns, so the history window, its rendering, and its replay as messages all run on real
# exchanges rather than on an empty tuple.
HISTORY = (
    Exchange(prompt="I try the vault door.", narration="The iron handle does not turn."),
    Exchange(
        prompt="I look for another way in.",
        narration="A flagstone by the wall sits proud of its neighbours.",
    ),
)
NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."
SEED = 11
# One unconditional effect every engine shares, so the two traces differ only by their action.
TAKE_THE_MAP = {"op": "move", "entity_id": "vault_map"}
CREATIONS = [
    {
        "kind": "actor",
        "name": "Sister Auber",
        "brief": "A lay sister who keeps the vault keys.",
        "detail": {
            "description": "She has kept the abbey's keys for thirty years.",
            "hook": "She knows which doors were sealed and by whom.",
        },
    }
]
TURN_STEPS = ("scene", "director", "resolve", "hooks", "narrator", "worldkeeper")


def _branch(outcome: str) -> dict[str, object]:
    return {
        "outcome": outcome,
        "effects": [
            {"op": "trait-change", "mode": "add", "entity_id": "player", "trait_id": outcome}
        ],
    }


def _plan(action: dict[str, object], outcomes: tuple[str, ...]) -> ModelResponse:
    return plan(
        effects=[TAKE_THE_MAP],
        action=action,
        branches=[_branch(outcome) for outcome in outcomes],
    )


# The same fiction under both engines, resolved by each one's own action and outcome labels.
SCRIPTS: Mapping[EngineId, ModelResponse] = {
    STORY: _plan(
        {
            "act": "risk",
            "actor_id": "player",
            "approach": "subtle",
            "difficulty": "demanding",
            "stakes": "listening past the vault door unheard",
        },
        ("strong", "mixed", "setback"),
    ),
    DND5E: _plan(
        {
            "act": "check",
            "actor_id": "player",
            "bonus": 2,
            "dc": 12,
            "reason": "listening past the vault door",
        },
        ("success", "failure"),
    ),
}


def _behind(state: GameState) -> GameState:
    draft = state.draft()
    draft.history = HISTORY
    return draft.committed()


async def _played(engine_id: EngineId) -> TurnResult:
    engine, state = game(engine_id)
    return await played(
        engine,
        _behind(state),
        PROMPT,
        director=FunctionModel(scripted(SCRIPTS[engine_id])),
        narrator=FunctionModel(scripted(text(NARRATION))),
        worldkeeper=FunctionModel(scripted(structured(creations=CREATIONS))),
        rng=Random(SEED),
    )


@pytest.mark.parametrize("engine_id", engine_ids())
async def test_a_scripted_turn_renders_and_records_unchanged(engine_id: EngineId) -> None:
    result = await _played(engine_id)

    assert tuple(step.name for step in result.turn.steps) == TURN_STEPS
    for step in result.turn.steps:
        if step.prompt is not None:
            golden(FIXTURES / "prompts" / engine_id / f"{step.name}.txt", step.prompt)
    # The prompts live in their own fixtures; the trace holds everything else the turn recorded.
    golden(
        FIXTURES / "turn" / f"{engine_id}.json",
        dumped(result.turn, exclude={"steps": {"__all__": {"prompt"}}}),
    )
    golden(FIXTURES / "save" / f"{engine_id}.json", dumped(result.state))
