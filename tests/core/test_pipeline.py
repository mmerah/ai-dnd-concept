import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from core_test_support import initialized, settings
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.agents.stages import director_stage, shared_stages
from aidm.domain.base import PLAYER_ID
from aidm.domain.entities import ActorEntity, ItemEntity, LocationEntity
from aidm.pipeline import TurnOptions, run_turn
from aidm_story.models import DEFAULT_APPROACHES
from aidm_story.state import story_state

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def structured(**output: object) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(json.dumps(output))])

    return stub


def text(body: str) -> Stub:
    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(body)])

    return stub


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(
                    structured(
                        intent="Kael finds the map beneath the flagstone.",
                        tone="hushed",
                        mechanics=[{"action": "take_item", "item_id": "vault_map"}],
                    )
                )
            )
        )
        stack.enter_context(
            stages.narrator.agent.override(
                model=FunctionModel(text("A creased chart slides into your hand."))
            )
        )
        stack.enter_context(
            stages.maintainer.agent.override(model=FunctionModel(structured(requests=[])))
        )
        turn = await run_turn(
            state,
            "I search beneath the desk.",
            engine=engine,
            director=director,
            stages=stages,
            options=TurnOptions(history_window=6, max_growth=3),
            rng=Random(0),
        )

    assert [fact.fact for fact in turn.facts] == ["entity_discovered", "item_moved"]
    assert {item.id for item in turn.state.world.carried_by(PLAYER_ID)} == {
        "a_guttering_lantern",
        "vault_map",
    }
    assert turn.direction.engine == "story"
    assert "Elena" not in turn.prompts["narrator"]
    assert "engine_data" not in turn.prompts["narrator"]
    assert turn.state.turn == 1
    assert turn.state.history[-1].prompt == "I search beneath the desk."


async def test_creator_growth_receives_valid_engine_rules_before_commit() -> None:
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(structured(intent="Someone approaches.", tone="curious"))
            )
        )
        stack.enter_context(
            stages.narrator.agent.override(model=FunctionModel(text("A courier enters.")))
        )
        stack.enter_context(
            stages.maintainer.agent.override(
                model=FunctionModel(
                    structured(
                        requests=[
                            {
                                "kind": "location",
                                "name": "The Rain Gallery",
                                "brief": "An open arcade beyond the study.",
                            },
                            {
                                "kind": "actor",
                                "name": "Iven",
                                "brief": "A rain-soaked courier.",
                                "location": "The Rain Gallery",
                            },
                            {
                                "kind": "item",
                                "name": "a sealed letter",
                                "brief": "Red wax bears no crest.",
                                "location": "The Rain Gallery",
                            },
                        ]
                    )
                )
            )
        )
        stack.enter_context(
            stages.creator.agent.override(
                model=FunctionModel(
                    structured(
                        description="Newly arrived from the road.",
                        hook="Carries news from beyond the abbey.",
                    )
                )
            )
        )
        turn = await run_turn(
            state,
            "Who comes through the door?",
            engine=engine,
            director=director,
            stages=stages,
            options=TurnOptions(history_window=6, max_growth=3),
            rng=Random(0),
        )

    assert len(turn.created) == 3
    assert any(isinstance(entity, ActorEntity) for entity in turn.created)
    assert any(isinstance(entity, ItemEntity) for entity in turn.created)
    location = next(entity for entity in turn.created if isinstance(entity, LocationEntity))
    actor = next(entity for entity in turn.created if isinstance(entity, ActorEntity))
    item = next(entity for entity in turn.created if isinstance(entity, ItemEntity))
    assert actor.location_id == location.id
    assert item.container_id == location.id
    engine_state = story_state(turn.state)
    assert engine_state.actor(actor.id).approaches == DEFAULT_APPROACHES
    assert engine_state.item(item.id).gear is None
    assert location.id not in engine_state.actors
    assert turn.narrator_evidence == "- (nothing mechanical happened)"
    assert "new actor" not in turn.prompts["narrator"]
    engine.rules.validate_state(turn.state)


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    before = state.model_dump_json()
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(
                    structured(
                        intent="Kael takes the hidden map.",
                        tone="grim",
                        mechanics=[{"action": "take_item", "item_id": "vault_map"}],
                    )
                )
            )
        )
        stack.enter_context(stages.narrator.agent.override(model=FunctionModel(boom)))
        with pytest.raises(RuntimeError, match="narrator exploded"):
            await run_turn(
                state,
                "I take the map.",
                engine=engine,
                director=director,
                stages=stages,
                options=TurnOptions(history_window=6, max_growth=3),
                rng=Random(0),
            )

    assert state.model_dump_json() == before
