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

from aidm.engines.counters import read_mechanics
from aidm.engines.loner3e.mechanics import Mechanics
from aidm.engines.loner3e.resolve import outcome_for
from aidm.engines.loner3e.rules import LABELS
from aidm.state.base import PLAYER_ID, Counter, EntityId
from aidm.state.world import Hook, HookMatch, Memory, Thread
from aidm.turn.pipeline import TURN_STEPS
from aidm.turn.roles import ChannelSafeModel

STEPS = ("director", "resolve", "hooks", "narrator", "worldkeeper")


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
    # Finding the map reveals the vault in the same pass, which fires the vault's own hook in
    # the same turn: the round-based drain lets one hook's fact feed the next.
    assert [fact.kind for fact in result.turn.facts] == [
        "entity_discovered",
        "entity_moved",
        "hook_fired",
        "thread_advanced",
        "entity_discovered",
        "hook_fired",
        "thread_advanced",
        "trait_added",
    ]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert "Elena" not in shown(result.turn, "narrator")
    assert "engine_data" not in shown(result.turn, "narrator")
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_a_speaker_the_turn_walks_away_from_narrates_the_scene_instead_of_dying() -> None:
    """The director picks a speaker who is here; the plan then moves the player elsewhere. The
    speaker leaving is fiction, so the turn still commits."""
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I leave for the cloister.",
        director=FunctionModel(
            scripted(
                plan(
                    effects=[{"op": "move", "to_id": "cloister"}],
                    focus="Kael leaves.",
                    speaker_id="mara",
                )
            )
        ),
    )

    assert result.state.player.parent_id == "cloister"
    assert result.state.turn == 1
    assert "(none — narrate the scene)" in shown(result.turn, "narrator")


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
                    "act": "question",
                    "actor_id": "player",
                    "question": "Does the door give before the whispering finds him?",
                },
                branches=[branch(outcome) for outcome in sorted(LABELS)],
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

    chance, risk = (fact.data["kept"] for fact in result.turn.facts if fact.kind == "dice_rolled")
    assert isinstance(chance, int) and isinstance(risk, int)
    held = {trait.id for trait in result.state.player.traits}
    assert held & LABELS == {outcome_for(chance, risk)}
    engine.validate(result.state)


async def test_a_plan_answered_as_plain_text_json_settles_the_turn() -> None:
    """Small models often emit the plan JSON as text before obeying the tool call; the text
    fallback accepts it so the turn costs no retry round trip."""
    engine, state = initialized()
    spoken = 'Here is the plan:\n{"focus": "Kael waits.", "branches": []}'
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
                args=json.dumps({"focus": "Kael waits.", "branches": []}),
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
    mechanics = read_mechanics(result.state, Mechanics)
    assert set(mechanics.sheets[actor.id].counters()) == {"luck"}
    assert item.id not in mechanics.sheets
    resolved = next(step.output for step in result.turn.steps if step.name == "resolve")
    assert resolved == "- (nothing mechanical happened)"
    assert "new actor" not in shown(result.turn, "narrator")
    engine.validate(result.state)


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

    thread = found.state.world.threads["vault-seal"]
    assert (thread.status, thread.stage) == ("active", "seal-found")
    assert found.state.world.fired_hooks == ("vault-sighted",)
    # The hook's own consequence reaches the Narrator the turn it happens; the thread never does.
    assert "Warded" in shown(found.turn, "narrator")
    assert "vault-seal" not in shown(found.turn, "narrator")

    after = await played(
        engine,
        found.state,
        "I wait.",
        director=FunctionModel(scripted(plan())),
    )

    # The note steers the Director, which is the only role shown the scenario's own voice.
    assert "Press on what opening the seal will cost" in shown(after.turn, "director")
    assert after.state.world.pending_notes == ()


async def test_a_clock_the_worldkeeper_ticks_fires_its_hook_in_the_same_turn() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.threads["trial"] = Thread(
        id="trial", title="The trial", clock=Counter(current=1, maximum=2)
    )
    draft.world.hooks = (
        Hook(
            id="trial-complete",
            match=HookMatch(kind="thread_advanced", data={"clock_filled": True}),
            note="The trial is complete; press the consequence.",
        ),
    )
    primed = draft.committed()

    result = await played(
        engine,
        primed,
        "I wait.",
        director=FunctionModel(scripted(plan())),
        worldkeeper=FunctionModel(
            scripted(
                structured(
                    creations=[],
                    thread_moves=[{"op": "advance-thread", "thread_id": "trial", "tick": 1}],
                )
            )
        ),
    )

    assert result.state.world.fired_hooks == ("trial-complete",)
    assert "hook_fired" in [fact.kind for fact in result.turn.facts]
    assert result.state.world.pending_notes == ("The trial is complete; press the consequence.",)


async def test_memory_reaches_the_director_alone_and_only_for_who_is_here() -> None:
    """A memory may hold canon the player has not earned, so the narrating role is shown none."""
    engine, state = initialized()
    draft = state.draft()
    elsewhere = Memory(
        id="tomas-kept-the-keys",
        owner=EntityId("tomas"),
        text="Brother Tomas kept the undercroft keys.",
    )
    here = Memory(
        id="the-study-was-searched", owner=EntityId("study"), text="The study was searched once."
    )
    for memory in (elsewhere, here):
        draft.world.memories[memory.id] = memory
    result = await played(
        engine,
        draft.committed(),
        "I look around.",
        director=FunctionModel(scripted(plan())),
    )

    remembered = "Mara catalogued the vault ledgers"
    director_prompt = shown(result.turn, "director")
    assert remembered in director_prompt
    assert "The abbey emptied in a single night" in director_prompt
    assert "The study was searched once." in director_prompt
    # Tomas sweeps the cloister, so what he remembers is not this scene's to weave in.
    assert "undercroft keys" not in director_prompt
    assert remembered not in shown(result.turn, "narrator")


async def test_the_director_reads_the_canon_and_only_the_narrator_is_kept_from_it() -> None:
    engine, state = initialized()
    steps: list[str] = []
    director = FunctionModel(
        scripted(
            plan(
                focus="Kael presses toward the vault door.",
                pressure="The undercroft air grows colder.",
                stakes="Finding it now or losing the trail.",
            )
        )
    )
    result = await played(
        engine,
        state,
        "I press on.",
        director=director,
        on_step=steps.append,
    )

    assert tuple(steps) == ("director", "resolve", "hooks", "narrator", "worldkeeper")
    director_prompt = shown(result.turn, "director")
    # Elena reaches the one Director's prompt; the narrator never does.
    assert "Elena" in director_prompt
    assert "Elena" not in shown(result.turn, "narrator")
