import json
from pathlib import Path

from fivee_test_support import dnd5e_game, dnd5e_session, ready
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.core.packs import ContentRef
from aidm.core.sheet import (
    AddRef,
    ChangeCounter,
    RemoveTag,
    SetNumber,
    SheetDelta,
    player_sheet,
)
from aidm.engines.dnd5e.engine import ADVANCEMENT_READY

ACTION_SURGE = ContentRef(pack="srd-2014", collection="features", index="action-surge-1-use")
SECOND_WIND = ContentRef(pack="srd-2014", collection="features", index="second-wind")
SPENT = RemoveTag(why="the level is taken", tag_id=ADVANCEMENT_READY)
LEGAL = SheetDelta(
    changes=(
        AddRef(why="the level's feature", ref=ACTION_SURGE),
        SetNumber(why="second level", key="level", value=2),
        ChangeCounter(why="a fighter's hit die and constitution", key="hp", delta=7, maximum=18),
        SPENT,
    )
)
WRONG_LEVEL = SheetDelta(changes=(AddRef(why="the level's feature", ref=ACTION_SURGE), SPENT))


def _answers(*deltas: SheetDelta) -> FunctionModel:
    remaining = iter(deltas)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(next(remaining).model_dump(mode="json")))])

    return FunctionModel(stub)


def test_the_ready_tag_opens_the_next_level_row() -> None:
    engine, state = dnd5e_game()
    assert engine.proposal.offered(state) is None

    offer = engine.proposal.offered(ready(state))

    assert offer is not None
    assert offer.prompt.startswith("Fighter 2")
    assert offer.options == (ACTION_SURGE,)
    assert offer.choose == 1


def test_a_pick_outside_the_offer_and_a_level_that_does_not_move_are_both_refused() -> None:
    engine, state = dnd5e_game()
    advancing = ready(state)
    offer = engine.proposal.offered(advancing)
    assert offer is not None
    outside = SheetDelta(changes=(AddRef(why="a feature already held", ref=SECOND_WIND), SPENT))

    assert engine.proposal.violation(advancing, offer, LEGAL) is None
    assert "not on offer" in str(engine.proposal.violation(advancing, offer, outside))
    assert "level 2" in str(engine.proposal.violation(advancing, offer, WRONG_LEVEL))


async def test_a_refused_proposal_is_retried_and_the_confirmed_one_commits(tmp_path: Path) -> None:
    game = dnd5e_session(tmp_path)
    game.state = ready(game.state)

    with game.advisor.agent.override(model=_answers(WRONG_LEVEL, LEGAL)):
        drafted = await game.propose("I take my second level of fighter.")
    assert drafted == LEGAL

    _ = game.apply_proposal(LEGAL)

    player = player_sheet(game.state)
    assert (player.numbers["level"], player.counters["hp"].maximum) == (2, 18)
    assert ACTION_SURGE in player.refs
    assert player.tag(ADVANCEMENT_READY) is None
    assert game.offer() is None
