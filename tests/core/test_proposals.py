import json
from pathlib import Path

import pytest
from core_test_support import at_boundary
from loner3e_test_support import loner3e_session
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.app.runtime import Drafted
from aidm.content.io import FileStore, SavedGame
from aidm.engines.loner3e.engine import AdventureGrowth, Change, Mechanics
from aidm.state.model import PLAYER_ID, Applied

LEGAL = AdventureGrowth(
    changes=(Change(kind="gear", tag="Waxed Rope"),), why="he never climbs without it now"
)
ILLEGAL = AdventureGrowth(
    changes=(Change(kind="rewrite", tag="Never Held a Blade", into="Holds It Well"),),
    why="a tag the sheet does not carry",
)


def _answers(*proposals: AdventureGrowth) -> FunctionModel:
    """One scripted answer per attempt: a refused proposal sends the advisor round again."""
    remaining = iter(proposals)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(next(remaining).model_dump(mode="json")))])

    return FunctionModel(stub)


async def test_an_illegal_proposal_is_retried_with_the_engines_reason(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    game.state = at_boundary(game.state)

    offer = game.offers()[0]
    assert game.advisor is not None
    with game.advisor.override(model=_answers(ILLEGAL, LEGAL)):
        proposal = await game.propose(offer, "Kael has learned to trust his rope.")

    assert proposal == LEGAL
    gear = Mechanics.of(game.state).sheets[PLAYER_ID].gear
    assert "Waxed Rope" not in gear  # proposing commits nothing


def test_confirming_commits_exactly_the_proposed_delta(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    game.state = at_boundary(game.state)
    offer = game.offers()[0]
    drafted = Drafted(offer=offer, proposal=LEGAL)

    facts = game.apply_proposal(drafted)

    sheet = Mechanics.of(game.state).sheets[PLAYER_ID]
    assert (sheet.gear[-1], sheet.milestones.current) == ("Waxed Rope", 1)
    assert [fact.trace for fact in facts] == [
        "Kael gained gear Waxed Rope (he never climbs without it now)",
        "the player Kael[player] milestones +1 -> 1 (a milestone spent)",
    ]
    entry = Applied(subject_id=PLAYER_ID, facts=facts)
    assert game.entries == [entry]
    assert FileStore(tmp_path).load("poc") == SavedGame.of(game.state)
    assert game.offers() == ()
    with pytest.raises(ValueError, match="no longer on offer"):
        _ = game.apply_proposal(drafted)


def test_a_refused_proposal_leaves_the_committed_state_untouched(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    game.state = at_boundary(game.state)
    before = SavedGame.of(game.state).model_dump_json()
    offer = game.offers()[0]
    drafted = Drafted(offer=offer, proposal=ILLEGAL)

    with pytest.raises(ValueError, match="carries no tag"):
        _ = game.apply_proposal(drafted)

    assert SavedGame.of(game.state).model_dump_json() == before
    assert game.entries == []
    assert FileStore(tmp_path).load("poc") is None
