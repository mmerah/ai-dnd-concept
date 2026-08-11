import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from story_test_support import grown, story_session

from aidm.content.store import FileSaves, FileTraces
from aidm.engines.story.advance import MAX_APPROACH, Growth
from aidm.engines.story.mechanics import read, write
from aidm.state.base import PLAYER_ID
from aidm.state.turn import Advance
from aidm.state.world import GameState

LEGAL = Growth(approach="clever", why="hard-won patience")
OVER_CAP = Growth(approach="bold", why="greed")


def _capped(state: GameState) -> GameState:
    """Kael's bold approach already sits at the cap, so raising it once trips the cap check."""
    draft = state.draft()
    mechanics = read(draft)
    mechanics.actors[PLAYER_ID].bold = MAX_APPROACH
    write(draft, mechanics)
    return draft.committed()


def _answers(*proposals: Growth) -> FunctionModel:
    """One scripted answer per attempt: a refused proposal sends the advisor round again."""
    remaining = iter(proposals)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(next(remaining).model_dump(mode="json")))])

    return FunctionModel(stub)


async def test_an_illegal_proposal_is_retried_with_the_engines_reason(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = _capped(grown(game.state))

    with game.advisor.agent.override(model=_answers(OVER_CAP, LEGAL)):
        drafted = await game.propose("Kael has learned patience.")

    assert drafted == LEGAL
    assert read(game.state).actors[PLAYER_ID].clever == 1  # nothing is committed by proposing


def test_confirming_commits_exactly_the_proposed_delta(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = grown(game.state)

    facts = game.apply_proposal(LEGAL)

    player = read(game.state).actors[PLAYER_ID]
    assert (player.clever, player.growth.current) == (2, 0)
    assert [fact.trace for fact in facts] == [
        "Kael clever -> 2 (hard-won patience)",
        "Kael growth -3 -> 0/3 (growth spent)",
    ]
    assert game.entries == [Advance(facts=facts)]
    assert FileTraces(tmp_path).load("poc") == (Advance(facts=facts),)
    assert FileSaves(tmp_path).load("poc") == game.state
    assert game.offer() is None


def test_a_refused_proposal_leaves_the_committed_state_untouched(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = _capped(grown(game.state))
    before = game.state.model_dump_json()

    with pytest.raises(ValueError, match="cannot pass"):
        _ = game.apply_proposal(OVER_CAP)

    assert game.state.model_dump_json() == before
    assert game.entries == []
    assert FileSaves(tmp_path).load("poc") is None
