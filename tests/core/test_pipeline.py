import json
from collections.abc import Callable
from contextlib import ExitStack
from random import Random

import pytest
from core_test_support import initialized, settings
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.core.base import PLAYER_ID
from aidm.core.sheet import Sheet, player_sheet
from aidm.core.world import rules_of
from aidm.workflow.pipeline import TurnOptions, TurnWorkspace, default_cast, run_turn

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]

STEPS = ("director", "resolve", "narrator", "maintainer", "creator")


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def text(body: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(body)])


def scripted(*responses: ModelResponse) -> Stub:
    """Call N answers with response N, because a retried output asks the model again."""
    remaining = iter(responses)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return next(remaining)

    return stub


PLAN = structured(intent="Kael finds the map beneath the flagstone.", tone="hushed")

OPTIONS = TurnOptions(history_window=6, max_growth=3)


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())
    steps: list[str] = []
    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(
                        structured(
                            intent="Kael finds the map beneath the flagstone.",
                            tone="hushed",
                            effects=[{"op": "take-item", "item_id": "vault_map"}],
                        )
                    )
                )
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

    assert tuple(steps) == STEPS
    assert [fact.kind for fact in result.turn.facts] == ["entity_discovered", "entity_moved"]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert "Elena" not in result.turn.prompts["narrator"]
    assert "engine_data" not in result.turn.prompts["narrator"]
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_the_resolver_applies_only_the_branch_of_the_outcome_rolled() -> None:
    """The point of the redesign: the engine rolls, picks the outcome, and applies its branch."""
    engine, state = initialized()
    members = default_cast(engine, settings())

    def branch(outcome: str) -> dict[str, object]:
        return {
            "outcome": outcome,
            "effects": [
                {"op": "add-tag", "entity_id": "player", "tag_id": outcome, "name": outcome}
            ],
        }

    with ExitStack() as stack:
        stack.enter_context(
            members.director.agent.override(
                model=FunctionModel(
                    scripted(
                        structured(
                            intent="Kael pleads with the door.",
                            tone="tense",
                            action={
                                "act": "risk",
                                "actor_id": "player",
                                "approach": "empathetic",
                                "difficulty": "risky",
                                "stakes": "pleading with the door",
                            },
                            branches=[branch("strong"), branch("mixed"), branch("setback")],
                        )
                    )
                )
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

    rolled = next(fact for fact in result.turn.facts if fact.kind == "dice_rolled")
    total = rolled.data["total"]
    assert isinstance(total, int)
    expected = "strong" if total >= 10 else "mixed" if total >= 7 else "setback"
    held = {tag.id for tag in player_sheet(result.state).tags}
    assert held & {"strong", "mixed", "setback"} == {expected}
    engine.validate_state(result.state)


async def test_an_illegal_plan_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    members = default_cast(engine, settings())
    responses = scripted(
        structured(
            intent="Kael waits.",
            tone="flat",
            branches=[{"outcome": "strong", "effects": ()}],
        ),
        structured(intent="Kael waits.", tone="flat"),
    )
    calls: list[list[ModelMessage]] = []

    def recording(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return responses(messages, info)

    with ExitStack() as stack:
        stack.enter_context(members.director.agent.override(model=FunctionModel(recording)))
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
            script=members.script(engine, OPTIONS),
            options=OPTIONS,
            rng=Random(0),
        )

    assert result.turn.plan["intent"] == "Kael waits."
    assert result.turn.plan["branches"] == []
    assert result.turn.facts == ()
    retry = calls[-1][-1]
    assert isinstance(retry, ModelRequest)
    reasons = [part.content for part in retry.parts if isinstance(part, RetryPromptPart)]
    assert any("settles no outcome" in str(reason) for reason in reasons)


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
                        structured(
                            intent="Kael takes the hidden map.",
                            tone="grim",
                            effects=[{"op": "take-item", "item_id": "vault_map"}],
                        )
                    )
                )
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
        stack.enter_context(members.director.agent.override(model=FunctionModel(scripted(PLAN))))
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

    assert tuple(steps) == (*STEPS, "echo")
    assert result.turn.prompts["echo"] == "extra step ran"
