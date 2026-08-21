from random import Random

import pytest
from core_test_support import (
    TWENTYFOURXX,
    game,
    initialized,
    narrated,
    played,
    recorded,
    scripted,
    settings,
    shown,
    structured,
    text,
    tool_call,
    updated,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.config import RoleConfig
from aidm.content.store import SavedGame
from aidm.engines.loner3e.actions import outcome_for
from aidm.engines.twentyfourxx.mechanics import Mechanics
from aidm.state.model import PLAYER_ID, EntityId
from aidm.turn.pipeline import TURN_STEPS


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[str] = []
    director = FunctionModel(
        scripted(
            tool_call("move", entity_id="vault_map", to_id="player"),
            text("The map is in hand."),
        )
    )
    narrator = FunctionModel(scripted(narrated("A creased chart slides into your hand.")))
    result = await played(
        engine,
        state,
        "I search beneath the desk.",
        director=director,
        narrator=narrator,
        on_step=steps.append,
    )

    assert tuple(steps) == TURN_STEPS
    assert [fact.kind for fact in result.turn.facts] == [
        "entity_discovered",
        "entity_moved",
    ]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault_map",
    }
    assert "Elena" not in shown(result.turn, "narrator")
    assert "engine_data" not in shown(result.turn, "narrator")
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."
    outcomes = result.state.history[-1].outcomes
    assert outcomes == tuple(fact.trace for fact in result.turn.facts)


async def test_the_engine_rolls_the_outcome_the_facts_then_record() -> None:
    """The engine makes every roll and picks the outcome; the director's tool never states one."""
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I plead with the door.",
        director=FunctionModel(
            scripted(
                tool_call(
                    "roll_question",
                    actor_id="player",
                    question="Does the door give before the whispering finds him?",
                ),
                text("The door does not move."),
            )
        ),
        narrator=FunctionModel(scripted(narrated("You falter."))),
        rng=Random(2),
    )

    chance, risk = (fact.data["kept"] for fact in result.turn.facts if fact.kind == "dice_rolled")
    assert isinstance(chance, int) and isinstance(risk, int)
    answer = next(fact for fact in result.turn.facts if fact.kind == "question_answered")
    assert answer.data["outcome"] == outcome_for(chance, risk)
    engine.validate(result.state)


async def test_the_director_reacts_in_run_to_its_own_earlier_tool_call() -> None:
    """The semantic heart of the new loop: a later tool call is judged against the draft an
    earlier call in the same run already changed — legal only because of that ordering."""
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I search the cloister for another way up.",
        director=FunctionModel(
            scripted(
                tool_call("move", entity_id="player", to_id="cloister"),
                tool_call("move", entity_id="player", to_id="bell_tower"),
                text("A rotten ladder climbs into the dark."),
            )
        ),
    )

    assert result.state.player.parent_id == "bell_tower"
    assert tuple(step.name for step in result.turn.steps) == TURN_STEPS


async def test_an_illegal_tool_call_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    director = recorded(
        tool_call("reveal", entity_id="nowhere"),
        tool_call("reveal", entity_id="vault"),
        text("Something is there."),
    )
    result = await played(engine, state, "I wait.", director=FunctionModel(director.stub))

    assert result.state.world.require(EntityId("vault")).known
    assert any("unknown entity id 'nowhere'" in reason for reason in director.reasons())


async def test_a_discovered_entitys_instruction_comes_back_with_the_tool_result() -> None:
    engine, state = initialized()
    director = recorded(tool_call("reveal", entity_id="vault"), text("Something is there."))
    await played(engine, state, "I wait.", director=FunctionModel(director.stub))

    returns = [
        part.content
        for msg in director.calls[-1]
        for part in msg.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert any("press on what opening it will cost" in str(c) for c in returns)


async def test_a_call_its_own_fields_refuse_is_retried_rather_than_killing_the_turn() -> None:
    """Every op is built inside the play, so a cross-field validator reaches the model as a
    retry."""
    engine, state = initialized()
    director = recorded(
        tool_call("advance_thread", thread_id="vault-seal"),
        tool_call("advance_thread", thread_id="vault-seal", stage="seal-found"),
        text("The seal is found."),
    )
    result = await played(engine, state, "I press on.", director=FunctionModel(director.stub))

    thread = result.state.world.thread("vault-seal")
    assert thread is not None and thread.stage == "seal-found"
    assert any("status, its stage, or its clock" in reason for reason in director.reasons())


async def test_a_later_call_is_judged_against_the_mechanics_the_earlier_one_moved() -> None:
    """A trial copy carries the pool the earlier call emptied, so the second call is refused as a
    retry rather than dying outside it."""
    engine, state = game(TWENTYFOURXX)
    credits = Mechanics.of(state).sheets[PLAYER_ID].credits.current
    director = recorded(
        tool_call("change_credits", actor_id="player", amount=-credits),
        tool_call("change_credits", actor_id="player", amount=-1),
        text("The purse is empty."),
    )
    result = await played(engine, state, "I pay what I owe.", director=FunctionModel(director.stub))

    assert Mechanics.of(result.state).sheets[PLAYER_ID].credits.current == 0
    assert director.reasons()


async def test_a_narrated_line_spoken_by_someone_not_here_is_retried_with_the_id() -> None:
    """The leak rule holds on `speaker_id` too: Elena is real canon, unmet and elsewhere."""
    engine, state = initialized()
    narrator = recorded(
        structured(lines=[{"speaker_id": "elena", "text": "You should not be here."}]),
        narrated("The door settles."),
    )
    result = await played(
        engine,
        state,
        "I wait.",
        director=FunctionModel(scripted(text("Nothing stirs."))),
        narrator=FunctionModel(narrator.stub),
    )

    assert any("elena" in reason for reason in narrator.reasons())
    assert result.state.history[-1].narration == "The door settles."


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(
        scripted(
            tool_call("move", entity_id="vault_map", to_id="player"),
            text("The map is in hand."),
        )
    )
    before = SavedGame.of(state).model_dump_json()
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine, state, "I take the map.", director=director, narrator=FunctionModel(boom)
        )

    assert SavedGame.of(state).model_dump_json() == before


async def test_a_turn_over_its_role_ceiling_fails_before_any_model_call() -> None:
    """A ceiling this low is exceeded by the director's own rendered prompt alone, so the turn
    never reaches a model — an aidm-owned error instead of a raw provider 400."""
    engine, state = initialized()
    tiny = updated(settings(), roles={"director": RoleConfig(max_input_tokens=1)})
    before = SavedGame.of(state).model_dump_json()

    with pytest.raises(ValueError, match="director"):
        await played(
            engine,
            state,
            "I take the map.",
            director=FunctionModel(scripted(text("unreachable"))),
            config=tiny,
        )

    assert SavedGame.of(state).model_dump_json() == before


async def test_a_director_run_that_fails_discards_what_the_earlier_tool_call_did() -> None:
    engine, state = initialized()
    before = SavedGame.of(state).model_dump_json()
    first = tool_call("move", entity_id="vault_map", to_id="player")
    calls = 0

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        raise RuntimeError("the director exploded")

    with pytest.raises(RuntimeError, match="the director exploded"):
        await played(
            engine,
            state,
            "I take the map and read it.",
            director=FunctionModel(stub),
        )

    assert SavedGame.of(state).model_dump_json() == before
    assert state.world.require(EntityId("vault_map")).parent_id != PLAYER_ID
