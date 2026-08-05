import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from story_test_support import grown, story_game, story_session

from aidm.core.engine import AdvancementOffer
from aidm.core.packs import ContentRef
from aidm.core.sheet import AddRef, ChangeCounter, SetNumber, SheetDelta, player_sheet
from aidm.core.store import FileSaves, FileTraces
from aidm.core.turn import Advance

SPEND = ChangeCounter(why="the three marks are spent", key="growth", delta=-3)
LEGAL = SheetDelta(changes=(SetNumber(why="hard-won patience", key="clever", value=2), SPEND))
OVER_CAP = SheetDelta(changes=(SetNumber(why="greed", key="bold", value=4), SPEND))


def _answers(*deltas: SheetDelta) -> FunctionModel:
    """One scripted answer per attempt: a refused delta sends the advisor round again."""
    remaining = iter(deltas)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(next(remaining).model_dump(mode="json")))])

    return FunctionModel(stub)


async def test_an_illegal_proposal_is_retried_with_the_engines_reason(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = grown(game.state)

    with game.advisor.agent.override(model=_answers(OVER_CAP, LEGAL)):
        drafted = await game.propose("Kael has learned patience.")

    assert drafted == LEGAL
    assert player_sheet(game.state).numbers["clever"] == 1  # nothing is committed by proposing


def test_confirming_commits_exactly_the_proposed_delta(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = grown(game.state)

    facts = game.apply_proposal(LEGAL)

    player = player_sheet(game.state)
    assert (player.numbers["clever"], player.counters["growth"].current) == (2, 0)
    assert [fact.trace for fact in facts] == [
        "clever 1 -> 2 (hard-won patience)",
        "growth -> 0/3 (the three marks are spent)",
    ]
    assert game.entries == [Advance(facts=facts)]
    assert FileTraces(tmp_path).load("poc") == (Advance(facts=facts),)
    assert FileSaves(tmp_path).load("poc", game.engine.state_type) == game.state
    assert game.offer() is None


def test_picks_are_checked_against_the_offer_and_the_trial_sheet_must_validate() -> None:
    engine, state = story_game()
    blade = ContentRef(pack="growth", collection="paths", index="blade")
    ward = ContentRef(pack="growth", collection="paths", index="ward")
    feast = ContentRef(pack="growth", collection="paths", index="feast")
    offer = AdvancementOffer(prompt="Choose a path.", options=(blade, ward), choose=1)
    judge = engine.proposal.violation

    def pick(ref: ContentRef) -> AddRef:
        return AddRef(why="the chosen path", ref=ref)

    outside = judge(state, offer, SheetDelta(changes=(pick(feast),)))
    assert outside is not None and "not on offer" in outside

    unpicked = judge(state, offer, SheetDelta())
    assert unpicked == "this offer takes exactly 1 picks, the proposal makes 0"

    # `stress` is a counter: writing it as a number is the misname crossover the sheet refuses.
    crossover = SheetDelta(changes=(pick(blade), SetNumber(why="err", key="stress", value=3)))
    corrupt = judge(state, offer, crossover)
    assert corrupt is not None and "both a number and a counter" in corrupt

    assert judge(state, offer, SheetDelta(changes=(pick(blade),))) is None


def test_a_refused_proposal_leaves_the_committed_state_untouched(tmp_path: Path) -> None:
    game = story_session(tmp_path)
    game.state = grown(game.state)
    before = game.state.model_dump_json()

    with pytest.raises(ValueError, match="cannot pass"):
        _ = game.apply_proposal(OVER_CAP)

    assert game.state.model_dump_json() == before
    assert game.entries == []
    assert FileSaves(tmp_path).load("poc", game.engine.state_type) is None
