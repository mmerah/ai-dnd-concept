import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from core_test_support import initialized, settings
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.core.base import PLAYER_ID
from aidm.engines.story.state import DEFAULT_APPROACHES, actor_state, item_state
from aidm.workflow.agents import director_stage, shared_stages
from aidm.workflow.pipeline import TurnOptions, run_turn

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def text(body: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(body)])


def calling(tool: str, **arguments: object) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=arguments)])


def scripted(*responses: ModelResponse) -> Stub:
    """Call N answers with response N, because a tool loop asks the model more than once."""
    remaining = iter(responses)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return next(remaining)

    return stub


NOTES = structured(intent="Kael finds the map beneath the flagstone.", tone="hushed")


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(scripted(calling("take_item", item_id="vault_map"), NOTES))
            )
        )
        stack.enter_context(
            stages.narrator.agent.override(
                model=FunctionModel(scripted(text("A creased chart slides into your hand.")))
            )
        )
        stack.enter_context(
            stages.maintainer.agent.override(model=FunctionModel(scripted(structured(requests=[]))))
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

    assert [fact.kind for fact in result.turn.facts] == ["entity_discovered", "entity_moved"]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert result.turn.notes.tone == "hushed"
    assert "Elena" not in result.turn.prompts["narrator"]
    assert "engine_data" not in result.turn.prompts["narrator"]
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_the_director_reacts_to_a_real_outcome_before_it_settles_the_turn() -> None:
    """The point of the tool loop: the roll happens first, and the model answers what it read."""
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(
                    scripted(
                        calling("risk", approach="empathetic", difficulty=2),
                        calling("take_stress", amount=1),
                        structured(intent="Kael pushes too hard.", tone="tense"),
                    )
                )
            )
        )
        stack.enter_context(
            stages.narrator.agent.override(model=FunctionModel(scripted(text("You falter."))))
        )
        stack.enter_context(
            stages.maintainer.agent.override(model=FunctionModel(scripted(structured(requests=[]))))
        )
        result = await run_turn(
            state,
            "I plead with the door.",
            engine=engine,
            director=director,
            stages=stages,
            options=TurnOptions(history_window=6, max_growth=3),
            rng=Random(2),
        )

    assert [fact.kind for fact in result.turn.facts] == [
        "risk_rolled",
        "growth_marked",
        "stress_changed",
    ]
    player = actor_state(result.state.world.record(PLAYER_ID, "actor").rules)
    assert (player.growth_marks, player.stress) == (1, 1)
    engine.validate_state(result.state)


async def test_creator_growth_receives_valid_engine_rules_before_commit() -> None:
    engine, state = initialized()
    config = settings()
    director = director_stage(engine, config)
    stages = shared_stages(config)
    with ExitStack() as stack:
        stack.enter_context(
            director.agent.override(
                model=FunctionModel(
                    scripted(structured(intent="Someone approaches.", tone="curious"))
                )
            )
        )
        stack.enter_context(
            stages.narrator.agent.override(model=FunctionModel(scripted(text("A courier enters."))))
        )
        stack.enter_context(
            stages.maintainer.agent.override(
                model=FunctionModel(
                    scripted(
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
        )
        stack.enter_context(
            stages.creator.agent.override(
                model=FunctionModel(
                    scripted(
                        structured(
                            description="Newly arrived from the road.",
                            hook="Carries news from beyond the abbey.",
                        ),
                        structured(
                            description="Newly arrived from the road.",
                            hook="Carries news from beyond the abbey.",
                        ),
                        structured(
                            description="Newly arrived from the road.",
                            hook="Carries news from beyond the abbey.",
                        ),
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

    created = {entity.kind: entity for entity in result.turn.created}
    assert set(created) == {"location", "actor", "item"}
    location, actor, item = created["location"], created["actor"], created["item"]
    assert actor.parent_id == location.id
    assert item.parent_id == location.id
    assert location.parent_id is None
    world = result.state.world
    assert actor_state(world.record(actor.id, "actor").rules).approaches == DEFAULT_APPROACHES
    assert item_state(world.record(item.id, "item").rules).gear is None
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
                    scripted(
                        calling("take_item", item_id="vault_map"),
                        structured(intent="Kael takes the hidden map.", tone="grim"),
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
