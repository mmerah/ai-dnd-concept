from random import Random

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from story_test_support import initial_story_game

from aidm.base import PLAYER_ID, EntityId
from aidm.engines.story.actions import DropItem
from aidm.engines.story.direction import HelpfulGear, Risk, StoryDirection, TakeStress
from aidm.engines.story.director import StoryDirector
from aidm.engines.story.rules import StoryRules
from aidm.engines.story.state import StoryActorState
from aidm.transition import Transition
from aidm.world import GameState


def _director_context(state: GameState) -> RunContext[GameState]:
    return RunContext(deps=state, model=TestModel(), usage=RunUsage())


def test_taking_an_actor_out_mid_turn_retries_instead_of_raising() -> None:
    # F15: a setback that takes Mara out only becomes visible once resolve() folds
    # state forward; the pre-turn scene alone cannot see it.
    engine, state = initial_story_game()
    direction = StoryDirection(
        intent="Kael pushes Mara past her limit, then asks more of her.",
        tone="tense",
        mechanics=[
            TakeStress(amount=5, actor_id=EntityId("mara")),
            Risk(actor_id=EntityId("mara"), approach="bold", difficulty=0),
        ],
    )

    with pytest.raises(ModelRetry, match="taken out"):
        engine.director.validate(_director_context(state), direction)


def test_using_just_dropped_gear_retries_instead_of_raising() -> None:
    engine, state = initial_story_game()
    (lantern,) = state.world.carried_by(PLAYER_ID)
    direction = StoryDirection(
        intent="Kael drops the lantern, then leans on its light anyway.",
        tone="uncertain",
        mechanics=[
            DropItem(item_id=lantern.id),
            Risk(approach="clever", difficulty=0, helpful=HelpfulGear(item_id=lantern.id)),
        ],
    )

    with pytest.raises(ModelRetry, match="not carried"):
        engine.director.validate(_director_context(state), direction)


def test_repeating_a_core_action_after_it_changes_state_retries() -> None:
    engine, state = initial_story_game()
    (lantern,) = state.world.carried_by(PLAYER_ID)
    direction = StoryDirection(
        intent="Kael tries to drop the same lantern twice.",
        tone="uncertain",
        mechanics=[
            DropItem(item_id=lantern.id),
            DropItem(item_id=lantern.id),
        ],
    )

    with pytest.raises(ModelRetry, match="does not carry"):
        engine.director.validate(_director_context(state), direction)


def test_a_genuine_validation_error_is_not_turned_into_a_retry() -> None:
    # Guards against copying 5e's `except ValueError`: ValidationError is a ValueError
    # subclass, so only the dedicated StoryProposalRejected may be caught here.
    _, state = initial_story_game()

    class _CorruptRules(StoryRules):
        def resolve(
            self,
            direction: StoryDirection,
            state: GameState,
            rng: Random,
        ) -> Transition:
            del direction, rng
            StoryActorState.model_validate({})
            return Transition(state=state.draft().committed(), facts=())

    broken_director = StoryDirector(_CorruptRules())
    direction = StoryDirection(intent="Kael waits.", tone="quiet", mechanics=[])

    with pytest.raises(ValidationError):
        broken_director.validate(_director_context(state), direction)
