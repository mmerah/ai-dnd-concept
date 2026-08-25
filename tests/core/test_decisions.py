from random import Random

import pytest
from core_test_support import LONER3E, game, played, recorded, scripted, shown, text, tool_call
from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets import FunctionToolset

from aidm.content.io import SavedGame
from aidm.engines.core import (
    RULES_WAIT,
    DirectorContext,
    Engine,
    apply_to_draft,
    apply_tool_call,
    sequential_toolset,
    transact,
)
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.state.entities import Slug
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import Answer, DecisionOption, Exchange, Line, PendingDecision
from aidm.turn.run import exchanges_to_messages

DECISION = PendingDecision(
    kind="defence",
    prompt="The blow lands unless something of yours breaks. What gives?",
    options=(
        DecisionOption(id="lantern", label="Break the lantern", detail="Its glass shatters."),
    ),
    payload={"outcome": "setback"},
)


class Deciding(Loner3eEngine):
    """The shipped engine plus the one decision kind these tests suspend on."""

    chains = False

    def check_pending(self, pending: PendingDecision) -> None:
        if pending.kind != DECISION.kind:
            raise ValueError(f"this engine cannot play a {pending.kind!r} decision")

    def resume(
        self, draft: Game, pending: PendingDecision, option_id: Slug, rng: Random
    ) -> tuple[Fact, ...]:
        del pending, rng
        if self.chains:
            draft.pending = DECISION
        return (
            Fact(
                kind="defence_turned",
                trace=f"{option_id} broke to turn the hit",
                told=True,
            ),
        )


def _hit(draft: Game, *, narrate: bool) -> tuple[Fact, ...]:
    draft.pending = DECISION
    return (
        Fact(
            kind="hit_taken",
            trace="the blow reaches the player",
            told=narrate,
        ),
    )


def _toolset(*, narrate: bool) -> FunctionToolset[DirectorContext]:
    def strike(ctx: RunContext[DirectorContext]) -> str:
        """Take a hit the player may turn by breaking something of theirs."""
        return apply_tool_call(ctx, lambda draft, _rng: _hit(draft, narrate=narrate))

    return sequential_toolset([strike])


def _deciding(*, narrate: bool = True, chains: bool = False) -> tuple[Engine, Game]:
    engine = Deciding()
    engine.chains = chains
    engine.director_toolsets = (_toolset(narrate=narrate),)
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


async def test_a_re_suspended_continuation_keeps_core_tools_and_loses_the_engine_s() -> None:
    engine, state = _deciding(chains=True)
    offered: list[str] = []

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        offered.extend(tool.name for tool in info.function_tools)
        return text("The lantern is gone.")

    result = await played(
        engine, _suspended(state), Answer(option_id="lantern"), director=FunctionModel(stub)
    )

    assert "reveal" in offered
    assert "strike" not in offered
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
            engine, state.draft(), lambda draft, _rng: _hit(draft, narrate=False), Random(0)
        )

    def nothing(draft: Game, rng: Random) -> tuple[Fact, ...]:
        del draft, rng
        return ()

    suspended, _ = transact(engine, _suspended(state).draft(), nothing, Random(0))
    assert suspended.pending == DECISION


def test_a_second_decision_is_refused_while_one_is_already_open() -> None:
    engine, state = _deciding()
    draft = _suspended(state).draft()

    with pytest.raises(ValueError, match="one at a time"):
        _ = apply_to_draft(engine, draft, lambda draft, _rng: _hit(draft, narrate=False), Random(0))


def test_a_paused_exchange_replays_as_a_message_and_a_silent_one_refuses() -> None:
    paused = Exchange(prompt="I charge.", place="the cloister", lines=(), decision=DECISION.prompt)
    stayed = Exchange(prompt="I press on.", place="the cloister", lines=(Line(text="It gives."),))
    moved = Exchange(prompt="I go up.", place="the bell tower", lines=(Line(text="Rope sways."),))

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
        _ = exchanges_to_messages([Exchange(prompt="I wait.", place="the cloister", lines=())])


def test_a_save_carries_a_decision_and_restore_refuses_one_the_engine_cannot_play() -> None:
    engine, state = _deciding()
    saved = SavedGame.model_validate_json(SavedGame.from_game(_suspended(state)).model_dump_json())

    assert engine.restored(saved).pending == DECISION

    unplayable = PendingDecision(
        kind="spend-momentum", prompt="Spend a point?", options=(), payload={}
    )
    with pytest.raises(ValueError, match="cannot play a 'spend-momentum' decision"):
        _ = engine.restored(SavedGame.from_game(_suspended(state, unplayable)))
