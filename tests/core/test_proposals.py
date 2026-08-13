import json
from pathlib import Path

import pytest
from oracle_test_support import at_milestone, oracle_session
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.content.store import FileSaves, FileTraces
from aidm.engines.oracle.advance import MAX_EDGES, Milestone
from aidm.engines.oracle.mechanics import read, write
from aidm.state.base import PLAYER_ID
from aidm.state.turn import Advance
from aidm.state.world import GameState

LEGAL = Milestone(gain_gear="Waxed Rope", why="he never climbs without it now")
OVER_CAP = Milestone(gain_edge="One Edge Too Many", why="pushed past what he can hold")


def _capped(state: GameState) -> GameState:
    """Kael's edges already sit at the cap, so gaining one more trips the cap check."""
    draft = state.draft()
    mechanics = read(draft)
    mechanics.sheets[PLAYER_ID].edges = tuple(f"Edge {n}" for n in range(MAX_EDGES))
    write(draft, mechanics)
    return draft.committed()


def _answers(*proposals: Milestone) -> FunctionModel:
    """One scripted answer per attempt: a refused proposal sends the advisor round again."""
    remaining = iter(proposals)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(next(remaining).model_dump(mode="json")))])

    return FunctionModel(stub)


async def test_an_illegal_proposal_is_retried_with_the_engines_reason(tmp_path: Path) -> None:
    game = oracle_session(tmp_path)
    game.state = _capped(at_milestone(game.state))

    assert game.advancer is not None
    with game.advancer.advisor.agent.override(model=_answers(OVER_CAP, LEGAL)):
        drafted = await game.propose("Kael has learned to trust his rope.")

    assert drafted == LEGAL
    assert "Waxed Rope" not in read(game.state).sheets[PLAYER_ID].gear  # proposing commits nothing


def test_confirming_commits_exactly_the_proposed_delta(tmp_path: Path) -> None:
    game = oracle_session(tmp_path)
    game.state = at_milestone(game.state)

    facts = game.apply_proposal(LEGAL)

    sheet = read(game.state).sheets[PLAYER_ID]
    assert (sheet.gear[-1], sheet.milestones.current) == ("Waxed Rope", 1)
    assert [fact.trace for fact in facts] == [
        "Kael gained gear Waxed Rope (he never climbs without it now)",
        "Kael milestones +1 -> 1 (a milestone spent)",
    ]
    assert game.entries == [Advance(facts=facts)]
    assert FileTraces(tmp_path).load("poc") == (Advance(facts=facts),)
    assert FileSaves(tmp_path).load("poc") == game.state
    assert game.offer() is None


def test_a_refused_proposal_leaves_the_committed_state_untouched(tmp_path: Path) -> None:
    game = oracle_session(tmp_path)
    game.state = _capped(at_milestone(game.state))
    before = game.state.model_dump_json()

    with pytest.raises(ValueError, match="holds at most"):
        _ = game.apply_proposal(OVER_CAP)

    assert game.state.model_dump_json() == before
    assert game.entries == []
    assert FileSaves(tmp_path).load("poc") is None
