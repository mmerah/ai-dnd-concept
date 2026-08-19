from random import Random

import pytest
from core_test_support import (
    TWENTYFOURXX,
    answered,
    call,
    game,
    initialized,
    narrated,
    plan,
    played,
    scripted,
    settings,
    shown,
    structured,
)
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, RetryPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.engines.loner3e.actions import outcome_for
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.world import Memory
from aidm.turn.pipeline import TURN_STEPS

QUIET_STEPS = ("director", "resolve", "hooks", "narrator", "worldkeeper")
ASKED = call(
    "question",
    actor_id="player",
    question="Does the door give before the whispering finds him?",
)


async def test_an_engine_uses_the_shared_pipeline_and_safe_narrator_prompt() -> None:
    engine, state = initialized()
    steps: list[str] = []
    director = FunctionModel(
        scripted(plan(effects=[call("move", entity_id="vault_map", to_id="player")]))
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

    # A turn that rolls nothing costs one Director call: the beat badge never lights.
    assert tuple(steps) == QUIET_STEPS
    assert set(TURN_STEPS) == {*QUIET_STEPS, "beat"}
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


async def test_the_engine_rolls_the_outcome_the_facts_then_record() -> None:
    """The engine makes every roll and picks the outcome; the plan never states one."""
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I plead with the door.",
        director=FunctionModel(scripted(plan(roll=ASKED), plan())),
        narrator=FunctionModel(scripted(narrated("You falter."))),
        rng=Random(2),
    )

    chance, risk = (fact.data["kept"] for fact in result.turn.facts if fact.kind == "dice_rolled")
    assert isinstance(chance, int) and isinstance(risk, int)
    answer = next(fact for fact in result.turn.facts if fact.kind == "question_answered")
    assert answer.data["outcome"] == outcome_for(chance, risk)
    engine.validate(result.state)


async def test_a_later_beat_walks_the_way_the_first_one_opened() -> None:
    """The semantic heart of the loop: a consequence written after the roll, against the state
    that roll left behind — legal only because the beat before it revealed the way."""
    engine, state = initialized()
    onward = call("move", entity_id="player", to_id="bell_tower")
    result = await played(
        engine,
        state,
        "I search the cloister for another way up.",
        director=FunctionModel(
            scripted(
                plan(
                    roll=ASKED,
                    effects=[
                        call("move", entity_id="player", to_id="cloister"),
                        call(
                            "relation-change",
                            mode="reveal",
                            kind="connected",
                            source="cloister",
                            target="bell_tower",
                        ),
                    ],
                ),
                plan(effects=[onward]),
            )
        ),
    )

    assert result.state.player.parent_id == "bell_tower"
    assert [step.name for step in result.turn.steps] == [
        "director",
        "beat-1",
        "resolve",
        "hooks",
        "narrator",
        "worldkeeper",
    ]
    too_early = engine.beat_type.model_validate({"effects": [onward]})
    assert engine.check_beat(state, too_early, False) is not None


async def test_the_loop_stops_at_max_beats_and_still_gets_its_settle_pass() -> None:
    """The cap cuts the rolling short; the last roll still reaches the Director as a settle beat,
    which may write what it caused but may not roll again."""
    engine, state = initialized()
    asked = plan(roll=ASKED)
    # Two rolling continuations, then the settle pass: a fifth call would run the script dry and
    # fail the turn.
    result = await played(
        engine,
        state,
        "I keep working at the seal.",
        director=FunctionModel(
            scripted(asked, asked, asked, plan(effects=[call("reveal", entity_id="vault")]))
        ),
    )

    assert settings().max_beats == 3
    assert [step.name for step in result.turn.steps] == [
        "director",
        "beat-1",
        "beat-2",
        "beat-3",
        "resolve",
        "hooks",
        "narrator",
        "worldkeeper",
    ]
    assert [fact.kind for fact in result.turn.facts].count("question_answered") == 3
    assert result.state.world.require(EntityId("vault")).known


async def test_a_roll_that_settles_the_turn_still_gets_its_last_beat() -> None:
    """Trouble landing is where the turn stops asking for more dice — but not before the Director
    is shown what it caused and asked what it leaves behind."""
    engine, state = game(TWENTYFOURXX)
    result = await played(
        engine,
        state,
        "I listen at the door.",
        director=FunctionModel(
            scripted(
                plan(roll=call("luck-test", actor_id="player", subject="a patrol wandering by")),
                plan(effects=[call("reveal", entity_id="vault")]),
            )
        ),
        rng=Random(2),
    )

    assert [fact.kind for fact in result.turn.facts].count("luck_tested") == 1
    assert [step.name for step in result.turn.steps] == [
        "director",
        "beat-1",
        "resolve",
        "hooks",
        "narrator",
        "worldkeeper",
    ]
    assert result.state.world.require(EntityId("vault")).known


async def test_a_settle_beat_that_rolls_again_is_refused() -> None:
    engine, state = initialized()
    result = await played(
        engine,
        state,
        "I keep working at the seal.",
        director=FunctionModel(
            scripted(
                plan(roll=ASKED),  # director
                plan(roll=ASKED),  # beat-1
                plan(roll=ASKED),  # beat-2
                plan(roll=ASKED),  # beat-3, attempt 1: refused, the settle pass may not roll
                plan(),  # beat-3, attempt 2
            )
        ),
    )

    assert [step.name for step in result.turn.steps].count("beat-3") == 1
    assert [fact.kind for fact in result.turn.facts].count("question_answered") == 3


async def test_a_beat_that_fails_discards_what_the_beats_before_it_did() -> None:
    engine, state = initialized()
    before = state.model_dump_json()
    first = plan(roll=ASKED, effects=[call("move", entity_id="vault_map", to_id="player")])
    calls = 0

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        raise RuntimeError("the beat exploded")

    with pytest.raises(RuntimeError, match="the beat exploded"):
        await played(
            engine,
            state,
            "I take the map and read it.",
            director=FunctionModel(stub),
        )

    assert state.model_dump_json() == before
    assert state.world.require(EntityId("vault_map")).parent_id != PLAYER_ID


async def test_an_illegal_plan_is_retried_with_the_reason() -> None:
    engine, state = initialized()
    responses = scripted(
        plan(effects=[call("reveal", entity_id="nowhere")]),
        plan(),
    )
    calls: list[list[ModelMessage]] = []

    def recording(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return responses(messages, info)

    result = await played(engine, state, "I wait.", director=FunctionModel(recording))

    assert answered(result.turn, "director")["effects"] == []
    assert result.turn.facts == ()
    retry = calls[-1][-1]
    assert isinstance(retry, ModelRequest)
    reasons = [part.content for part in retry.parts if isinstance(part, RetryPromptPart)]
    assert any("unknown entity id 'nowhere'" in str(reason) for reason in reasons)


async def test_a_narrated_line_spoken_by_someone_not_here_is_retried_with_the_id() -> None:
    """The leak rule holds on `speaker_id` too: Elena is real canon, unmet and elsewhere."""
    engine, state = initialized()
    responses = scripted(
        structured(lines=[{"speaker_id": "elena", "text": "You should not be here."}]),
        narrated("The door settles."),
    )
    calls: list[list[ModelMessage]] = []

    def recording(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return responses(messages, info)

    result = await played(
        engine,
        state,
        "I wait.",
        director=FunctionModel(scripted(plan())),
        narrator=FunctionModel(recording),
    )

    retry = calls[-1][-1]
    assert isinstance(retry, ModelRequest)
    reasons = [part.content for part in retry.parts if isinstance(part, RetryPromptPart)]
    assert any("elena" in str(reason) for reason in reasons)
    assert result.state.history[-1].narration == "The door settles."


async def test_a_failed_role_never_mutates_the_input_state() -> None:
    engine, state = initialized()

    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        raise RuntimeError("narrator exploded")

    director = FunctionModel(
        scripted(plan(effects=[call("move", entity_id="vault_map", to_id="player")]))
    )
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
        director=FunctionModel(scripted(plan(effects=[call("reveal", entity_id="vault")]))),
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
    director = FunctionModel(scripted(plan()))
    result = await played(
        engine,
        state,
        "I press on.",
        director=director,
        on_step=steps.append,
    )

    assert tuple(steps) == QUIET_STEPS
    director_prompt = shown(result.turn, "director")
    # Elena reaches the one Director's prompt; the narrator never does.
    assert "Elena" in director_prompt
    assert "Elena" not in shown(result.turn, "narrator")
