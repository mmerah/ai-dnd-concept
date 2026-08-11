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

from aidm.engines.story.mechanics import read
from aidm.state.base import PLAYER_ID
from aidm.turn.pipeline import TURN_STEPS
from aidm.turn.roles import ChannelSafeModel

STEPS = ("scene", "director", "resolve", "hooks", "narrator", "worldkeeper")


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[str] = []
    director = FunctionModel(scripted(plan(effects=[{"op": "move", "entity_id": "vault_map"}])))
    narrator = FunctionModel(scripted(text("A creased chart slides into your hand.")))
    result = await played(
        engine,
        state,
        "I search beneath the desk.",
        director=director,
        narrator=narrator,
        on_step=steps.append,
    )

    assert tuple(steps) == STEPS == TURN_STEPS
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
            "effects": [
                {"op": "trait-change", "mode": "add", "entity_id": "player", "trait_id": outcome}
            ],
        }

    director = FunctionModel(
        scripted(
            plan(
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
    held = {trait.id for trait in result.state.player.traits}
    assert held & {"strong", "mixed", "setback"} == {expected}
    engine.commit(result.state)


async def test_a_plan_answered_as_plain_text_json_settles_the_turn() -> None:
    """Small models often emit the plan JSON as text before obeying the tool call; the text
    fallback accepts it so the turn costs no retry round trip."""
    engine, state = initialized()
    spoken = 'Here is the plan:\n{"branches": []}'
    director = FunctionModel(scripted(text(spoken)))
    result = await played(engine, state, "I wait.", director=director)

    assert answered(result.turn, "director")["branches"] == []
    assert result.turn.facts == ()


async def test_a_tool_call_with_a_channel_marker_in_its_name_still_lands() -> None:
    engine, state = initialized()
    marked = ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="turn_plan<|channel|>json",
                args=json.dumps({"branches": []}),
            )
        ]
    )
    director = ChannelSafeModel(FunctionModel(scripted(marked)))
    result = await played(engine, state, "I wait.", director=director)

    assert answered(result.turn, "director")["branches"] == []


async def test_an_illegal_plan_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    responses = scripted(
        plan(branches=[{"outcome": "strong", "effects": ()}]),
        plan(),
    )
    calls: list[list[ModelMessage]] = []

    def recording(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return responses(messages, info)

    result = await played(engine, state, "I wait.", director=FunctionModel(recording))

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
    director = FunctionModel(scripted(plan()))
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
        entity.kind: entity
        for entity in result.state.world.entities.values()
        if entity.name in names
    }
    assert set(created) == {"location", "actor", "item"}
    location, actor, item = created["location"], created["actor"], created["item"]
    assert actor.parent_id == location.id
    assert item.parent_id == location.id
    assert location.parent_id is None
    mechanics = read(result.state)
    assert {"stress", "growth"} <= set(mechanics.actors[actor.id].counters())
    assert item.id not in mechanics.actors
    resolved = next(step.output for step in result.turn.steps if step.name == "resolve")
    assert resolved == "- (nothing mechanical happened)"
    assert "new actor" not in shown(result.turn, "narrator")
    engine.commit(result.state)


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(scripted(plan(effects=[{"op": "move", "entity_id": "vault_map"}])))
    before = state.model_dump_json()
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine, state, "I take the map.", director=director, narrator=FunctionModel(boom)
        )

    assert state.model_dump_json() == before


async def test_a_hook_fires_on_its_fact_moves_its_thread_and_steers_the_next_turn() -> None:
    engine, state = initialized()
    found = await played(
        engine,
        state,
        "I ask Mara where the vault door is.",
        director=FunctionModel(scripted(plan(effects=[{"op": "reveal", "entity_id": "vault"}]))),
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
        director=FunctionModel(scripted(plan())),
    )

    # The note steers the Scene Director, which is the only role shown the scenario's own voice.
    assert "Press on what opening the seal will cost" in shown(after.turn, "scene")
    assert after.state.pending_notes == ()


async def test_both_directors_read_the_canon_and_only_the_narrator_is_kept_from_it() -> None:
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
    director = FunctionModel(scripted(plan()))
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
    # The directive passed Elena over; both directors still see her, the narrator never does.
    assert "Elena" in director_prompt
    assert "Elena" in shown(result.turn, "scene")
    assert "Elena" not in shown(result.turn, "narrator")
