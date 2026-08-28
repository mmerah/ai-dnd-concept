from random import Random

import pytest
from core_test_support import (
    TWENTYFOURXX,
    at_boundary,
    game,
    initialized,
    narrated,
    played,
    recorded,
    scripted,
    sheet_of,
    shown,
    structured,
    text,
    tool_call,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.engines.loner3e.rules import Sheet as LonerSheet
from aidm.engines.loner3e.rules import outcome_for
from aidm.engines.twentyfourxx.rules import Sheet
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import player_events
from aidm.turn.run import TurnStep


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[TurnStep] = []
    director = FunctionModel(
        scripted(
            tool_call("move", entity_id="vault-map", to_id="player"),
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

    assert tuple(steps) == ("director", "narrator")
    assert [fact.kind for fact in result.turn.facts] == [
        "entity_discovered",
        "entity_moved",
    ]
    assert {item.id for item in result.state.world.children(PLAYER_ID, "item")} == {
        "lantern",
        "vault-map",
    }
    assert "Elena" not in shown(result.turn, "narrator")
    assert "engine_data" not in shown(result.turn, "narrator")
    assert result.state.turn == 1
    assert result.state.history[-1].prompt == "I search beneath the desk."


async def test_on_event_fires_once_per_visible_tool_in_resolver_order() -> None:
    engine, state = initialized()
    fired: list[str] = []
    director = FunctionModel(
        scripted(
            tool_call("move", entity_id="vault-map", to_id="player"),
            tool_call("add_trait", entity_id="player", name="Listening", text="listening"),
            text("Kael takes the map and listens."),
        )
    )
    result = await played(
        engine,
        state,
        "I take the map and listen.",
        director=director,
        on_event=lambda event: fired.append(event.title),
    )

    assert fired == ["Took the vault map", "Kael gained Listening"]
    assert [event.title for event in result.state.history[-1].events] == [
        "Took the vault map",
        "Kael gained Listening",
    ]


async def test_a_narrator_failure_leaves_history_and_events_untouched() -> None:
    engine, state = initialized()
    fired: list[str] = []

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(
        scripted(
            tool_call("move", entity_id="vault-map", to_id="player"),
            text("The map is in hand."),
        )
    )
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine,
            state,
            "I take the map.",
            director=director,
            narrator=FunctionModel(boom),
            on_event=lambda event: fired.append(event.title),
        )

    assert fired == ["Took the vault map"]
    assert state.history == ()


async def test_the_engine_rolls_the_outcome_the_facts_then_record() -> None:
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

    answer = next(fact for fact in result.turn.facts if fact.kind == "question_answered")
    assert answer.event is not None
    chance, risk = answer.event.dice
    rolled = [fact.trace for fact in result.turn.facts if fact.kind == "dice_rolled"]
    for die, trace in zip(answer.event.dice, rolled, strict=True):
        assert trace.endswith(f"-> {die.kept}")
    assert answer.event.outcome == outcome_for(chance.kept, risk.kept).name
    engine.validate(result.state)


async def test_the_director_reacts_in_run_to_its_own_earlier_tool_call() -> None:
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I search the cloister for another way up.",
        director=FunctionModel(
            scripted(
                tool_call("move", entity_id="player", to_id="cloister"),
                tool_call("move", entity_id="player", to_id="bell-tower"),
                text("A rotten ladder climbs into the dark."),
            )
        ),
    )

    assert result.state.player.parent_id == "bell-tower"
    assert tuple(step.name for step in result.turn.steps) == ("director", "narrator")


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
    engine, state = initialized()
    director = recorded(
        tool_call("advance_thread", thread_id="vault-seal"),
        tool_call("advance_thread", thread_id="vault-seal", stage="seal-found"),
        text("The seal is found."),
    )
    result = await played(engine, state, "I press on.", director=FunctionModel(director.stub))

    thread = result.state.world.thread("vault-seal")
    assert thread is not None and thread.stage == "seal-found"
    reason = "status, its stage, its clock, or its note"
    assert any(reason in seen for seen in director.reasons())


async def test_a_later_call_is_judged_against_the_mechanics_the_earlier_one_moved() -> None:
    engine, state = game(TWENTYFOURXX)
    credits = sheet_of(state, PLAYER_ID, Sheet).credits.current
    director = recorded(
        tool_call("change_credits", actor_id="player", amount=-credits),
        tool_call("change_credits", actor_id="player", amount=-1),
        text("The purse is empty."),
    )
    result = await played(engine, state, "I pay what I owe.", director=FunctionModel(director.stub))

    assert sheet_of(result.state, PLAYER_ID, Sheet).credits.current == 0
    assert director.reasons()


async def test_a_narrated_line_spoken_by_someone_not_here_is_retried_with_the_id() -> None:
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
            tool_call("move", entity_id="vault-map", to_id="player"),
            text("The map is in hand."),
        )
    )
    before = state.model_dump_json()
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine, state, "I take the map.", director=director, narrator=FunctionModel(boom)
        )

    assert state.model_dump_json() == before


async def test_a_director_run_that_fails_discards_what_the_earlier_tool_call_did() -> None:
    engine, state = initialized()
    before = state.model_dump_json()
    first = tool_call("move", entity_id="vault-map", to_id="player")
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

    assert state.model_dump_json() == before
    assert state.world.require(EntityId("vault-map")).parent_id != PLAYER_ID


async def test_an_owed_advance_is_noted_lands_on_call_and_is_refused_once_spent() -> None:
    engine, state = initialized()
    growth: dict[str, object] = {
        "subject_id": PLAYER_ID,
        "changes": [{"kind": "gear", "tag": "Waxed Rope", "why": "he never climbs without it now"}],
    }
    director = recorded(
        tool_call("advance", **growth),
        tool_call("advance", **growth),
        text("The rope is his for good."),
    )
    result = await played(
        engine,
        at_boundary(state, LonerSheet),
        "I keep the rope.",
        director=FunctionModel(director.stub),
    )

    assert "Kael has an advance owed" in shown(result.turn, "director")
    assert [event.icon for event in player_events(result.turn.facts)] == ["military_tech"] * 2
    sheet = sheet_of(result.state, PLAYER_ID, LonerSheet)
    assert (sheet.gear[-1], sheet.milestones) == ("Waxed Rope", 1)
    assert any("has no advance owed" in reason for reason in director.reasons())
