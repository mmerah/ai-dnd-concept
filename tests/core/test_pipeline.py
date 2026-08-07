import json
from random import Random

import pytest
from core_test_support import (
    answered,
    initialized,
    plan,
    played,
    scripted,
    shown,
    structured,
    text,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.state.base import PLAYER_ID
from aidm.state.turn import StepTrace
from aidm.state.world import player_sheet, sheet_of
from aidm.turn.pipeline import TurnWorkspace
from aidm.turn.roles import ChannelSafeModel

STEPS = ("director", "resolve", "hooks", "narrator", "worldkeeper")


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[str] = []
    director = FunctionModel(
        scripted(
            plan(
                intent="Kael finds the map beneath the flagstone.",
                tone="hushed",
                effects=[{"op": "move-item", "item_id": "vault_map"}],
            )
        )
    )
    narrator = FunctionModel(scripted(text("A creased chart slides into your hand.")))
    result = await played(
        engine,
        state,
        "I search beneath the desk.",
        director=director,
        narrator=narrator,
        on_step=steps.append,
    )

    assert tuple(steps) == STEPS
    # Finding the map is one of the two discoveries the vault-seal thread answers to, so the
    # hook pass follows the two turn facts with its own.
    assert [fact.kind for fact in result.turn.facts] == [
        "entity_discovered",
        "entity_moved",
        "hook_fired",
        "thread_advanced",
        "entity_discovered",
    ]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert "Elena" not in shown(result.turn, "narrator")
    assert "engine_data" not in shown(result.turn, "narrator")
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_the_resolver_applies_only_the_branch_of_the_outcome_rolled() -> None:
    """The point of the redesign: the engine rolls, picks the outcome, and applies its branch."""
    engine, state = initialized()

    def branch(outcome: str) -> dict[str, object]:
        return {
            "outcome": outcome,
            "effects": [{"op": "add-tag", "entity_id": "player", "tag_id": outcome}],
        }

    director = FunctionModel(
        scripted(
            plan(
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
    narrator = FunctionModel(scripted(text("You falter.")))
    result = await played(
        engine,
        state,
        "I plead with the door.",
        director=director,
        narrator=narrator,
        rng=Random(2),
    )

    rolled = next(fact for fact in result.turn.facts if fact.kind == "dice_rolled")
    total = rolled.data["total"]
    assert isinstance(total, int)
    expected = "strong" if total >= 10 else "mixed" if total >= 7 else "setback"
    held = {tag.id for tag in player_sheet(result.state).tags}
    assert held & {"strong", "mixed", "setback"} == {expected}
    engine.validate_state(result.state)


async def test_a_plan_answered_as_plain_text_json_settles_the_turn() -> None:
    """Small models often emit the plan JSON as text before obeying the tool call; the text
    fallback accepts it so the turn costs no retry round trip."""
    engine, state = initialized()
    spoken = 'Here is the plan:\n{"intent": "Kael waits by the rail.", "tone": "flat"}'
    director = FunctionModel(scripted(text(spoken)))
    result = await played(engine, state, "I wait.", director=director)

    assert answered(result.turn, "director")["intent"] == "Kael waits by the rail."
    assert result.turn.facts == ()


async def test_a_tool_call_with_a_channel_marker_in_its_name_still_lands() -> None:
    engine, state = initialized()
    marked = ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="turn_plan<|channel|>json",
                args=json.dumps({"intent": "Kael waits by the rail.", "tone": "flat"}),
            )
        ]
    )
    director = ChannelSafeModel(FunctionModel(scripted(marked)))
    result = await played(engine, state, "I wait.", director=director)

    assert answered(result.turn, "director")["intent"] == "Kael waits by the rail."


async def test_an_illegal_plan_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    responses = scripted(
        plan(
            intent="Kael waits.",
            tone="flat",
            branches=[{"outcome": "strong", "effects": ()}],
        ),
        plan(intent="Kael waits.", tone="flat"),
    )
    calls: list[list[ModelMessage]] = []

    def recording(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return responses(messages, info)

    result = await played(engine, state, "I wait.", director=FunctionModel(recording))

    assert answered(result.turn, "director")["intent"] == "Kael waits."
    assert answered(result.turn, "director")["branches"] == []
    assert result.turn.facts == ()
    retry = calls[-1][-1]
    assert isinstance(retry, ModelRequest)
    reasons = [part.content for part in retry.parts if isinstance(part, RetryPromptPart)]
    assert any("settles no outcome" in str(reason) for reason in reasons)


async def test_worldkeeper_creations_receive_valid_engine_rules_before_commit() -> None:
    engine, state = initialized()
    detail = {
        "description": "Newly arrived from the road.",
        "hook": "Carries news from beyond the abbey.",
    }
    director = FunctionModel(scripted(plan(intent="Someone approaches.", tone="curious")))
    narrator = FunctionModel(scripted(text("A courier enters.")))
    worldkeeper = FunctionModel(
        scripted(
            structured(
                creations=[
                    {
                        "kind": "location",
                        "name": "The Rain Gallery",
                        "brief": "An open arcade beyond the study.",
                        "detail": detail,
                    },
                    {
                        "kind": "actor",
                        "name": "Iven",
                        "brief": "A rain-soaked courier.",
                        "location": "The Rain Gallery",
                        "detail": detail,
                    },
                    {
                        "kind": "item",
                        "name": "a sealed letter",
                        "brief": "Red wax bears no crest.",
                        "location": "The Rain Gallery",
                        "detail": detail,
                    },
                ]
            )
        )
    )
    result = await played(
        engine,
        state,
        "Who comes through the door?",
        director=director,
        narrator=narrator,
        worldkeeper=worldkeeper,
    )

    names = {"The Rain Gallery", "Iven", "a sealed letter"}
    created = {
        entity.kind: entity for entity in result.state.world.entities() if entity.name in names
    }
    assert set(created) == {"location", "actor", "item"}
    location, actor, item = created["location"], created["actor"], created["item"]
    assert actor.parent_id == location.id
    assert item.parent_id == location.id
    assert location.parent_id is None
    actor_sheet = sheet_of(result.state, actor.id)
    item_sheet = sheet_of(result.state, item.id)
    assert {"stress", "growth"} <= set(actor_sheet.counters)
    assert item_sheet.numbers == {} and item_sheet.counters == {}
    resolved = next(step.output for step in result.turn.steps if step.name == "resolve")
    assert resolved == "- (nothing mechanical happened)"
    assert "new actor" not in shown(result.turn, "narrator")
    engine.validate_state(result.state)


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(
        scripted(
            plan(
                intent="Kael takes the hidden map.",
                tone="grim",
                effects=[{"op": "move-item", "item_id": "vault_map"}],
            )
        )
    )
    before = state.model_dump_json()
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine, state, "I take the map.", director=director, narrator=FunctionModel(boom)
        )

    assert state.model_dump_json() == before


async def test_a_script_takes_an_extra_step_without_core_edits() -> None:
    engine, state = initialized()

    async def echo(ws: TurnWorkspace) -> None:
        ws.steps.append(StepTrace(name="echo", output="extra step ran"))

    steps: list[str] = []
    result = await played(
        engine,
        state,
        "I wait.",
        director=FunctionModel(scripted(plan(intent="Kael waits.", tone="flat"))),
        on_step=steps.append,
        extra=(("echo", echo),),
    )

    assert tuple(steps) == (*STEPS, "echo")
    echoed = next(step.output for step in result.turn.steps if step.name == "echo")
    assert echoed == "extra step ran"


async def test_a_hook_fires_on_its_fact_moves_its_thread_and_steers_the_next_turn() -> None:
    engine, state = initialized()
    found = await played(
        engine,
        state,
        "I ask Mara where the vault door is.",
        director=FunctionModel(
            scripted(
                plan(
                    intent="Mara points Kael at the undercroft.",
                    tone="wary",
                    effects=[{"op": "reveal", "entity_id": "vault"}],
                )
            )
        ),
    )

    thread = found.state.threads["vault-seal"]
    assert (thread.status, thread.stage) == ("active", "seal-found")
    assert found.state.fired_hooks == ("vault-sighted",)
    # The hook's own consequence reaches the Narrator the turn it happens; the thread never does.
    assert "Warded" in shown(found.turn, "narrator")
    assert "vault-seal" not in shown(found.turn, "narrator")

    after = await played(
        engine,
        found.state,
        "I wait.",
        director=FunctionModel(scripted(plan(intent="Kael waits.", tone="flat"))),
    )

    assert "Press on what opening the seal will cost" in shown(after.turn, "director")
    assert after.state.pending_notes == ()


async def test_a_scene_directive_replaces_the_directors_own_canon_view() -> None:
    engine, state = initialized()
    steps: list[str] = []
    scene = FunctionModel(
        scripted(
            structured(
                focus="Kael presses toward the vault door.",
                pressure="The undercroft air grows colder.",
                stakes="Finding it now or losing the trail.",
                threads=["vault-seal"],
                reveal=["vault"],
            )
        )
    )
    director = FunctionModel(scripted(plan(intent="Kael presses on.", tone="tense")))
    result = await played(
        engine,
        state,
        "I press on.",
        director=director,
        scene=scene,
        on_step=steps.append,
    )

    assert tuple(steps) == ("scene", "director", "resolve", "hooks", "narrator", "worldkeeper")
    director_prompt = shown(result.turn, "director")
    assert "Kael presses toward the vault door." in director_prompt
    assert "The sealed vault" in director_prompt
    # Named for revealing, so the Rules Director can write it; the unnamed one stays out of sight.
    assert "the sealed vault[id=vault]" in director_prompt
    assert "Elena" not in director_prompt
    assert "SCENARIO NOTES" not in director_prompt
    scene_prompt = shown(result.turn, "scene")
    assert "Elena" in scene_prompt
    assert "ACTIVE THREADS" in scene_prompt
