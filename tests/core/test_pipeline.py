from random import Random

import pytest
from core_test_support import (
    changed,
    initialized,
    loner_at_boundary,
    loner_sheet,
    narrated,
    played,
    recorded,
    scripted,
    structured,
    text,
    tool_call,
)
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.engines.loner3e.rules import outcome_for
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import Fact, cards
from aidm.turn.run import TurnStep

MAP = EntityId("vault-map")
FOUND = changed("reveal", entity_id="vault-map")
TAKEN = changed("move_item", item_id="vault-map", to="player")


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[TurnStep] = []
    director = FunctionModel(scripted(FOUND, TAKEN, text("The map is in hand.")))
    narrator = recorded(narrated("A creased chart slides into your hand."))
    facts: list[Fact] = []
    state = await played(
        engine,
        state,
        "I search beneath the desk.",
        director=director,
        narrator=FunctionModel(narrator.stub),
        on_step=steps.append,
        on_fact=facts.append,
    )

    assert tuple(steps) == ("director", "narrator")
    assert [fact.kind for fact in facts] == [
        "entity_discovered",
        "entity_moved",
    ]
    assert {one.id for one in state.world.carried_by(PLAYER_ID)} == {"vault-map"}
    assert "Elena" not in narrator.prompt()
    # The sheets are the game master's: no tag the engine rolls by reaches the narrator.
    assert "concept" not in narrator.prompt()
    assert state.turn == 1
    assert state.history[-1].prompt == "I search beneath the desk."


async def test_on_fact_reports_the_visible_facts_in_resolver_order() -> None:
    engine, state = initialized()
    fired: list[Fact] = []
    director = FunctionModel(
        scripted(
            FOUND,
            TAKEN,
            changed("add_trait", entity_id="player", name="Listening", text="listening"),
            text("Kael takes the map and listens."),
        )
    )
    state = await played(
        engine,
        state,
        "I take the map and listen.",
        director=director,
        on_fact=fired.append,
    )

    landed = ["The vault map discovered", "Took the vault map", "Kael gained Listening"]
    assert [fact.card for fact in cards(fired)] == landed
    assert [fact.card for fact in state.history[-1].facts] == landed


async def test_a_narrator_failure_leaves_history_and_events_untouched() -> None:
    engine, state = initialized()
    fired: list[Fact] = []

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(scripted(FOUND, TAKEN, text("The map is in hand.")))
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine,
            state,
            "I take the map.",
            director=director,
            narrator=FunctionModel(boom),
            on_fact=fired.append,
        )

    assert [fact.card for fact in cards(fired)] == [
        "The vault map discovered",
        "Took the vault map",
    ]
    assert state.history == ()


async def test_the_engine_rolls_the_outcome_the_facts_then_record() -> None:
    engine, state = initialized()
    fired: list[Fact] = []
    state = await played(
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
        on_fact=fired.append,
    )

    answer = next(fact for fact in fired if fact.kind == "question_answered")
    chance, risk = answer.dice
    rolled = [fact.trace for fact in fired if fact.kind == "dice_rolled"]
    for die, trace in zip(answer.dice, rolled, strict=True):
        assert trace.endswith(f"[{', '.join(str(v) for v in die.rolled)}]")
    assert answer.card.endswith(f"→ {outcome_for(max(chance.rolled), max(risk.rolled)).name}")
    engine.validate(state)
    assert any(fact.kind == "dice_rolled" and not fact.told for fact in fired)


async def test_the_director_reacts_in_run_to_its_own_earlier_tool_call() -> None:
    engine, state = initialized()
    state = await played(
        engine,
        state,
        "I call the old porter over.",
        director=FunctionModel(
            scripted(
                changed("enter", entity_id="tomas"),
                changed("join_party", actor_id="tomas"),
                text("Tomas shuffles in and stays at his shoulder."),
            )
        ),
    )

    assert state.world.companions == ["tomas"]


async def test_an_illegal_tool_call_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    director = recorded(
        changed("reveal", entity_id="nowhere"),
        FOUND,
        text("Something is there."),
    )
    state = await played(engine, state, "I wait.", director=FunctionModel(director.stub))

    assert state.world.require(MAP).known
    assert any("unknown id 'nowhere'" in reason for reason in director.reasons())


async def test_a_call_its_own_fields_refuse_is_retried_rather_than_killing_the_turn() -> None:
    engine, state = initialized()
    director = recorded(
        changed("advance_thread", thread_id="vault-seal"),
        changed("advance_thread", thread_id="vault-seal", note="The seal is found."),
        text("The seal is found."),
    )
    state = await played(engine, state, "I press on.", director=FunctionModel(director.stub))

    assert state.world.threads["vault-seal"].note == "The seal is found."
    reason = "status or its note"
    assert any(reason in seen for seen in director.reasons())


async def test_a_later_call_is_judged_against_the_sheet_the_earlier_one_moved() -> None:
    engine, state = initialized()
    growth = {
        "subject_id": PLAYER_ID,
        "changes": [{"kind": "skill", "tag": "Vault-Wise", "why": "the seal gave up its trick"}],
    }
    director = recorded(
        tool_call("complete_chapter"),
        tool_call("advance", **growth),
        tool_call("advance", **growth),
        text("The chapter closes."),
    )
    state = await played(engine, state, "I close the book.", director=FunctionModel(director.stub))

    assert loner_sheet(state, PLAYER_ID).milestones == 1
    assert any("no advance owed" in reason for reason in director.reasons())


async def test_a_narrated_line_spoken_by_someone_not_here_is_retried_with_the_id() -> None:
    engine, state = initialized()
    narrator = recorded(
        structured(lines=[{"speaker_id": "elena", "text": "You should not be here."}]),
        narrated("The door settles."),
    )
    state = await played(
        engine,
        state,
        "I wait.",
        director=FunctionModel(scripted(text("Nothing stirs."))),
        narrator=FunctionModel(narrator.stub),
    )

    assert any("elena" in reason for reason in narrator.reasons())
    assert state.history[-1].narration == "The door settles."


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(scripted(FOUND, TAKEN, text("The map is in hand.")))
    before = state.model_dump_json()
    with pytest.raises(RuntimeError, match="narrator exploded"):
        await played(
            engine, state, "I take the map.", director=director, narrator=FunctionModel(boom)
        )

    assert state.model_dump_json() == before


async def test_a_director_run_that_fails_discards_what_the_earlier_tool_call_did() -> None:
    engine, state = initialized()
    before = state.model_dump_json()
    calls = 0

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        nonlocal calls
        calls += 1
        if calls == 1:
            return FOUND
        raise RuntimeError("the director exploded")

    with pytest.raises(RuntimeError, match="the director exploded"):
        await played(
            engine,
            state,
            "I take the map and read it.",
            director=FunctionModel(stub),
        )

    assert state.model_dump_json() == before
    assert not state.world.require(MAP).known


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
    facts: list[Fact] = []
    state = await played(
        engine,
        loner_at_boundary(state),
        "I keep the rope.",
        director=FunctionModel(director.stub),
        on_fact=facts.append,
    )

    assert "Kael has an advance owed" in director.prompt()
    assert len(cards(tuple(facts))) == 2
    sheet = loner_sheet(state, PLAYER_ID)
    assert (sheet.gear[-1], sheet.milestones) == ("Waxed Rope", 1)
    assert any("has no advance owed" in reason for reason in director.reasons())
