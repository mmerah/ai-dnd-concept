from dataclasses import replace
from random import Random

import pytest
from core_test_support import CATCH_BREATH, TWENTYFOURXX, game

from aidm.engines.core import play_action


def test_a_player_action_lands_as_an_exchange_that_tells_only_told_facts() -> None:
    engine, state = game(TWENTYFOURXX)
    engine = replace(engine, player_actions=(CATCH_BREATH,))

    landed, facts = play_action(engine, state, "catch-breath", {"deep": True}, Random(0))

    assert [fact.kind for fact in facts] == ["breathed", "breathed"]
    exchange = landed.history[-1]
    assert exchange.prompt == "Catch your breath"
    assert exchange.narration == "Kael breathes deep"
    assert "hidden stair" not in exchange.narration


def test_an_action_not_offered_right_now_is_refused() -> None:
    engine, state = game(TWENTYFOURXX)
    engine = replace(engine, player_actions=(CATCH_BREATH,))
    with pytest.raises(ValueError, match="not offered"):
        _ = play_action(engine, state, "catch-breath", {"deep": False}, Random(0))
