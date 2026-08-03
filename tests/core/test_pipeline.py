import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from core_test_support import initialized, settings
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.agents import director_stage, shared_stages
from aidm.base import PLAYER_ID, ActorEntity, ItemEntity, LocationEntity
from aidm.engines.story.access import actor_state, item_state
from aidm.engines.story.state import DEFAULT_APPROACHES
from aidm.pipeline import TurnOptions, run_turn

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
        result = await run_turn(
            state,
            "I search beneath the desk.",
            engine=engine,
            director=director,
            stages=stages,
            options=TurnOptions(history_window=6, max_growth=3),
            rng=Random(0),
        )

    assert [fact.kind for fact in result.turn.facts] == ["entity_discovered", "item_moved"]
    assert {record.entity.id for record in result.state.world.carried_by(PLAYER_ID)} == {
        "lantern",
        "vault_map",
    }
    assert result.turn.direction.engine == "story"
    assert "Elena" not in result.turn.prompts["narrator"]
    assert "engine_data" not in result.turn.prompts["narrator"]
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


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
        result = await run_turn(
            state,
            "Who comes through the door?",
            engine=engine,
            director=director,
            stages=stages,
            options=TurnOptions(history_window=6, max_growth=3),
            rng=Random(0),
        )

    assert len(result.turn.created) == 3
    assert any(isinstance(entity, ActorEntity) for entity in result.turn.created)
    assert any(isinstance(entity, ItemEntity) for entity in result.turn.created)
    location = next(entity for entity in result.turn.created if isinstance(entity, LocationEntity))
    actor = next(entity for entity in result.turn.created if isinstance(entity, ActorEntity))
    item = next(entity for entity in result.turn.created if isinstance(entity, ItemEntity))
    assert actor.location_id == location.id
    assert item.container_id == location.id
    world = result.state.world
    assert actor_state(world.actor(actor.id).rules).approaches == DEFAULT_APPROACHES
    assert item_state(world.item(item.id).rules).gear is None
    assert location.id not in result.state.world.actors
    assert result.turn.narrator_evidence == "- (nothing mechanical happened)"
    assert "new actor" not in result.turn.prompts["narrator"]
    engine.validate_state(result.state)


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
