from dataclasses import replace
from random import Random

import pytest
from core_test_support import (
    ENGINES_BUILT,
    LONER3E,
    game,
    played,
    recorded,
    scripted,
    shown,
    text,
    tool_call,
)
from pydantic import Field, ValidationError
from pydantic_ai.messages import TextPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from aidm.engines.core import Engine
from aidm.state.entities import Frozen
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import (
    Answer,
    Exchange,
    Line,
    PendingDecision,
    PendingOption,
    ToolCall,
)
from aidm.state.tools import (
    DirectorTool,
    NoArgs,
    apply_to_draft,
    director_tool,
    transact,
)
from aidm.turn.run import RULES_WAIT, TurnRecord, consume_answer, exchanges_to_messages


class Broken(Frozen):
    item: str = Field(description="What breaks to turn the hit.")


def _turned(item: str) -> tuple[Fact, ...]:
    return (Fact(kind="defence_turned", trace=f"{item} broke to turn the hit", told=True),)


def _chained(draft: Game, item: str) -> tuple[Fact, ...]:
    draft.pending = DECISION
    return _turned(item)


TURN_THE_HIT = director_tool(
    "turn_the_hit",
    "Break something to turn the hit.",
    Broken,
    lambda _draft, one, _rng: _turned(one.item),
)

CHAIN_THE_HIT = director_tool(
    "chain_the_hit",
    "Break something and leave the rules waiting on the same decision again.",
    Broken,
    lambda draft, one, _rng: _chained(draft, one.item),
)


def _decision(resolver: DirectorTool) -> PendingDecision:
    return PendingDecision(
        kind="defence",
        prompt="The blow lands unless something of yours breaks. What gives?",
        options=(
            PendingOption(
                id="lantern",
                label="Break the lantern",
                detail="Its glass shatters.",
                call=ToolCall(name=resolver.name, args={"item": "lantern"}),
            ),
        ),
        allows_text=True,
    )


DECISION = _decision(TURN_THE_HIT)
CHAINING = _decision(CHAIN_THE_HIT)


def _hit(draft: Game, *, narrate: bool) -> tuple[Fact, ...]:
    draft.pending = DECISION
    return (
        Fact(
            kind="hit_taken",
            trace="the blow reaches the player",
            told=narrate,
        ),
    )


def _strike_tool(*, narrate: bool) -> DirectorTool:
    return director_tool(
        "strike",
        "Take a hit the player may turn by breaking something of theirs.",
        NoArgs,
        lambda draft, _args, _rng: _hit(draft, narrate=narrate),
    )


def _deciding(*, narrate: bool = True) -> tuple[Engine, Game]:
    engine = replace(
        ENGINES_BUILT[LONER3E],
        tools=(_strike_tool(narrate=narrate),),
        resolvers=(TURN_THE_HIT, CHAIN_THE_HIT),
    )
    _, state = game(LONER3E)
    return engine, state


def _suspended(state: Game, decision: PendingDecision = DECISION) -> Game:
    draft = state.draft()
    draft.pending = decision
    return draft.committed()


def test_an_answer_is_a_chosen_option_or_written_text_but_never_both_nor_neither() -> None:
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer()
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer(option_id="lantern", text="I dive behind the crate")


async def test_a_suspending_resolver_ends_the_run_and_records_the_pause() -> None:
    engine, state = _deciding()
    director = recorded(tool_call("strike"), text("The rules wait on the player."))

    result = await played(
        engine, state, "I charge the guard.", director=FunctionModel(director.stub)
    )

    answers = [
        str(part.content)
        for messages in director.calls
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert any(RULES_WAIT in answer for answer in answers)
    assert result.state.pending == DECISION
    assert result.state.history[-1].decision == DECISION.prompt
    assert [step.name for step in result.turn.steps] == ["director", "narrator"]


async def test_a_hand_back_that_moved_no_fiction_gets_no_prose() -> None:
    engine, state = _deciding(narrate=False)

    result = await played(
        engine,
        state,
        "I charge the guard.",
        director=FunctionModel(scripted(tool_call("strike"), text("The rules wait."))),
    )

    assert [step.name for step in result.turn.steps] == ["director"]
    assert result.turn.narration == ""
    assert result.state.history[-1].lines == ()


async def test_a_closed_answer_resolves_in_engine_code_before_the_director_continues() -> None:
    engine, state = _deciding()

    result = await played(
        engine,
        _suspended(state),
        Answer(option_id="lantern"),
        director=FunctionModel(scripted(text("The lantern is gone."))),
    )

    assert [fact.kind for fact in result.turn.facts] == ["defence_turned"]
    assert "lantern broke to turn the hit" in shown(result.turn, "director")
    assert result.state.history[-1].prompt == "Break the lantern"
    assert result.state.pending is None


async def test_a_re_suspended_continuation_keeps_the_rules_waiting() -> None:
    engine, state = _deciding()

    result = await played(
        engine,
        _suspended(state, CHAINING),
        Answer(option_id="lantern"),
        director=FunctionModel(scripted(text("The lantern is gone."))),
    )

    assert result.state.pending == DECISION


async def test_an_option_the_decision_never_offered_raises() -> None:
    engine, state = _deciding()

    with pytest.raises(ValueError, match="offers no option 'vest'"):
        _ = await played(
            engine,
            _suspended(state),
            Answer(option_id="vest"),
            director=FunctionModel(scripted(text("unreachable"))),
        )


def test_a_change_outside_a_turn_cannot_open_a_decision_but_may_run_on_a_suspended_state() -> None:
    engine, state = _deciding()

    with pytest.raises(ValueError, match="cannot open a decision"):
        _ = transact(
            engine.validate,
            state.draft(),
            lambda draft, _rng: _hit(draft, narrate=False),
            Random(0),
        )

    def nothing(draft: Game, rng: Random) -> tuple[Fact, ...]:
        del draft, rng
        return ()

    suspended, _ = transact(engine.validate, _suspended(state).draft(), nothing, Random(0))
    assert suspended.pending == DECISION


def test_a_second_decision_is_refused_while_one_is_already_open() -> None:
    engine, state = _deciding()
    draft = _suspended(state).draft()

    with pytest.raises(ValueError, match="one at a time"):
        _ = apply_to_draft(
            engine.validate, draft, lambda draft, _rng: _hit(draft, narrate=False), Random(0)
        )


def test_a_paused_exchange_replays_as_a_message_and_a_silent_one_refuses() -> None:
    paused = Exchange(prompt="I charge.", scene="the cloister", lines=(), decision=DECISION.prompt)
    stayed = Exchange(prompt="I press on.", scene="the cloister", lines=(Line(text="It gives."),))
    moved = Exchange(prompt="I go up.", scene="the bell tower", lines=(Line(text="Rope sways."),))

    rendered = [
        part.content
        for message in exchanges_to_messages([paused, stayed, moved])
        for part in message.parts
        if isinstance(part, TextPart)
    ]

    assert rendered == [
        f"[At the cloister]\n[The rules paused the turn for the player: {DECISION.prompt}]",
        "[At the cloister]\nIt gives.",
        "[At the bell tower]\nRope sways.",
    ]
    with pytest.raises(ValueError, match="nothing to replay"):
        _ = exchanges_to_messages([Exchange(prompt="I wait.", scene="the cloister", lines=())])


def test_restore_refuses_an_option_whose_call_names_no_tool_or_carries_args_it_rejects() -> None:
    engine, state = _deciding()

    assert engine.restored(_suspended(state).model_dump_json()).pending == DECISION

    unknown = _decision(TURN_THE_HIT).model_copy(
        update={
            "options": (
                PendingOption(
                    id="lantern",
                    label="Break the lantern",
                    call=ToolCall(name="spend_momentum", args={}),
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="no tool 'spend_momentum' to play option 'lantern'"):
        _ = engine.restored(_suspended(state, unknown).model_dump_json())

    ill_typed = _decision(TURN_THE_HIT).model_copy(
        update={
            "options": (
                PendingOption(
                    id="lantern",
                    label="Break the lantern",
                    call=ToolCall(name=TURN_THE_HIT.name, args={"nothing": "of theirs"}),
                ),
            )
        }
    )
    with pytest.raises(ValidationError):
        _ = engine.restored(_suspended(state, ill_typed).model_dump_json())


def test_a_decision_whose_options_are_the_whole_pick_refuses_an_answer_in_words() -> None:
    engine, state = _deciding()
    draft = _suspended(state, DECISION.model_copy(update={"allows_text": False})).draft()

    with pytest.raises(ValueError, match="takes one of its options, not words"):
        _ = consume_answer(engine, draft, Answer(text="I dive aside"), Random(0), TurnRecord())
