import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from core_test_support import initialized, settings
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.core.base import PLAYER_ID
from aidm.core.sheet import Sheet, player_sheet
from aidm.core.world import rules_of
from aidm.workflow.pipeline import TurnOptions, TurnWorkspace, default_cast, run_turn

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

OPTIONS = TurnOptions(history_window=6, max_growth=3)


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())
    steps: list[str] = []
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(scripted(calling("take_item", item_id="vault_map"), NOTES))
            )
        )
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(scripted(structured(objection=None)))
            )
        )
        stack.enter_context(
            members.narrator.agent.override(
                model=FunctionModel(scripted(text("A creased chart slides into your hand.")))
            )
        )
        stack.enter_context(
            members.maintainer.agent.override(
                model=FunctionModel(scripted(structured(requests=[])))
            )
        )
        result = await run_turn(
            state,
            "I search beneath the desk.",
            engine=engine,
            script=members.script(engine, OPTIONS),
            options=OPTIONS,
            rng=Random(0),
            on_step=steps.append,
        )

    assert steps == ["director", "referee", "narrator", "maintainer", "creator"]
    assert [fact.kind for fact in result.turn.facts] == ["entity_discovered", "entity_moved"]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert "Elena" not in result.turn.prompts["narrator"]
    assert "engine_data" not in result.turn.prompts["narrator"]
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_the_director_reacts_to_a_real_outcome_before_it_settles_the_turn() -> None:
    """The point of the tool loop: the roll happens first, and the model answers what it read."""
    engine, state = initialized()
    members = default_cast(engine, settings())
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(
                        calling("roll", dice="2d6+0", reason="pleading with the door", vs=7),
                        calling(
                            "adjust",
                            entity_id="player",
                            counter="stress",
                            delta=1,
                            reason="the strain of pleading",
                        ),
                        structured(intent="Kael pushes too hard.", tone="tense"),
                    )
                )
            )
        )
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(scripted(structured(objection=None)))
            )
        )
        stack.enter_context(
            members.narrator.agent.override(model=FunctionModel(scripted(text("You falter."))))
        )
        stack.enter_context(
            members.maintainer.agent.override(
                model=FunctionModel(scripted(structured(requests=[])))
            )
        )
        result = await run_turn(
            state,
            "I plead with the door.",
            engine=engine,
            script=members.script(engine, OPTIONS),
            options=OPTIONS,
            rng=Random(2),
        )

    assert [fact.kind for fact in result.turn.facts] == ["dice_rolled", "counter_changed"]
    assert player_sheet(result.state).counters["stress"].current == 1
    engine.validate_state(result.state)


async def test_creator_growth_receives_valid_engine_rules_before_commit() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(structured(intent="Someone approaches.", tone="curious"))
                )
            )
        )
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(scripted(structured(objection=None)))
            )
        )
        stack.enter_context(
            members.narrator.agent.override(
                model=FunctionModel(scripted(text("A courier enters.")))
            )
        )
        stack.enter_context(
            members.maintainer.agent.override(
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
            members.creator.agent.override(
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
            script=members.script(engine, OPTIONS),
            options=OPTIONS,
            rng=Random(0),
        )

    created = {entity.kind: entity for entity in result.turn.created}
    assert set(created) == {"location", "actor", "item"}
    location, actor, item = created["location"], created["actor"], created["item"]
    assert actor.parent_id == location.id
    assert item.parent_id == location.id
    assert location.parent_id is None
    actor_sheet = rules_of(result.state.world.record(actor.id), Sheet)
    item_sheet = rules_of(result.state.world.record(item.id), Sheet)
    assert {"stress", "growth"} <= set(actor_sheet.counters)
    assert item_sheet.numbers == {} and item_sheet.counters == {}
    assert result.turn.narrator_evidence == "- (nothing mechanical happened)"
    assert "new actor" not in result.turn.prompts["narrator"]
    engine.validate_state(result.state)


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    before = state.model_dump_json()
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(
                        calling("take_item", item_id="vault_map"),
                        structured(intent="Kael takes the hidden map.", tone="grim"),
                    )
                )
            )
        )
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(scripted(structured(objection=None)))
            )
        )
        stack.enter_context(members.narrator.agent.override(model=FunctionModel(boom)))
        with pytest.raises(RuntimeError, match="narrator exploded"):
            await run_turn(
                state,
                "I take the map.",
                engine=engine,
                script=members.script(engine, OPTIONS),
                options=OPTIONS,
                rng=Random(0),
            )

    assert state.model_dump_json() == before


async def test_a_script_takes_an_extra_step_without_core_edits() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())

    async def echo(ws: TurnWorkspace) -> None:
        ws.prompts["echo"] = "extra step ran"

    steps: list[str] = []
    with ExitStack() as stack:
        stack.enter_context(members.director.agent.override(model=FunctionModel(scripted(NOTES))))
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(scripted(structured(objection=None)))
            )
        )
        stack.enter_context(
            members.narrator.agent.override(model=FunctionModel(scripted(text("You wait."))))
        )
        stack.enter_context(
            members.maintainer.agent.override(
                model=FunctionModel(scripted(structured(requests=[])))
            )
        )
        result = await run_turn(
            state,
            "I wait.",
            engine=engine,
            script=(*members.script(engine, OPTIONS), ("echo", echo)),
            options=OPTIONS,
            rng=Random(0),
            on_step=steps.append,
        )

    assert steps == ["director", "referee", "narrator", "maintainer", "creator", "echo"]
    assert result.turn.prompts["echo"] == "extra step ran"


async def test_an_objection_continues_the_director_once_and_commits_its_correction() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(
                        structured(intent="Kael hesitates.", tone="flat"),
                        calling(
                            "adjust",
                            entity_id="player",
                            counter="stress",
                            delta=1,
                            reason="the strain of forcing the door",
                        ),
                        structured(intent="Kael forces the door.", tone="tense"),
                    )
                )
            )
        )
        stack.enter_context(
            members.referee.agent.override(
                model=FunctionModel(
                    scripted(
                        structured(
                            objection="The player forced the door and nothing was rolled;"
                            " resolve the risk now."
                        )
                    )
                )
            )
        )
        stack.enter_context(
            members.narrator.agent.override(model=FunctionModel(scripted(text("The door gives."))))
        )
        stack.enter_context(
            members.maintainer.agent.override(
                model=FunctionModel(scripted(structured(requests=[])))
            )
        )
        result = await run_turn(
            state,
            "I force the door.",
            engine=engine,
            script=members.script(engine, OPTIONS),
            options=OPTIONS,
            rng=Random(0),
        )

    assert [fact.kind for fact in result.turn.facts] == ["referee_objection", "counter_changed"]
    assert result.turn.notes.intent == "Kael forces the door."
    assert player_sheet(result.state).counters["stress"].current == 1
    assert "forced the door" not in result.turn.narrator_evidence
