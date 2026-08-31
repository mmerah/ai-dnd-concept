from dataclasses import replace
from pathlib import Path
from random import Random

import pytest
from core_test_support import ENGINES_BUILT, LONER3E, Table, opened, played, tool_call
from pydantic import Field, ValidationError

from aidm.core.entities import Frozen
from aidm.core.facts import Fact
from aidm.core.model import Game
from aidm.core.play import Answer, PendingDecision, PendingOption
from aidm.core.tools import MasterTool, NoArgs, apply_to_draft, master_tool
from aidm.engines.core import Engine
from aidm.turn.run import RULES_WAIT, Turn, TurnStep, consume_answer


class Broken(Frozen):
    item: str = Field(description="What breaks to turn the hit.")


def _turned(item: str) -> tuple[Fact, ...]:
    return (Fact(kind="defence_turned", trace=f"{item} broke to turn the hit", told=True),)


def _chained(draft: Game, item: str) -> tuple[Fact, ...]:
    draft.pending = DECISION
    return _turned(item)


TURN_THE_HIT = master_tool(
    "turn_the_hit",
    "Break something to turn the hit.",
    Broken,
    lambda _draft, one, _rng: _turned(one.item),
)

CHAIN_THE_HIT = master_tool(
    "chain_the_hit",
    "Break something and leave the rules waiting on the same decision again.",
    Broken,
    lambda draft, one, _rng: _chained(draft, one.item),
)


def _decision(resolver: MasterTool) -> PendingDecision:
    return PendingDecision(
        kind="defence",
        prompt="The blow lands unless something of yours breaks. What gives?",
        options=(
            PendingOption(
                id="lantern",
                label="Break the lantern",
                detail="Its glass shatters.",
                name=resolver.name,
                args={"item": "lantern"},
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


def _strike_tool(*, narrate: bool) -> MasterTool:
    return master_tool(
        "strike",
        "Take a hit the player may turn by breaking something of theirs.",
        NoArgs,
        lambda draft, _args, _rng: _hit(draft, narrate=narrate),
    )


def _engine(*, narrate: bool = True) -> Engine:
    return replace(
        ENGINES_BUILT[LONER3E],
        tools=(_strike_tool(narrate=narrate), TURN_THE_HIT, CHAIN_THE_HIT),
    )


def _deciding(saves: Path, *, narrate: bool = True) -> Table:
    return opened(saves, engine=_engine(narrate=narrate))


def _suspend(table: Table, decision: PendingDecision = DECISION) -> None:
    draft = table.service.state.draft()
    draft.pending = decision
    table.service.commit(draft.committed())


def test_an_answer_is_a_chosen_option_or_written_text_but_never_both_nor_neither() -> None:
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer()
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer(option_id="lantern", text="I dive behind the crate")


async def test_a_suspending_resolver_ends_the_run_and_records_the_pause(tmp_path: Path) -> None:
    table = _deciding(tmp_path)
    steps: list[TurnStep] = []

    state = await played(table, "I charge the guard.", tool_call("strike"), on_step=steps.append)

    assert any(RULES_WAIT in answer for answer in table.answers)
    assert state.pending == DECISION
    assert state.world.exchanges()[-1].decision == DECISION.prompt
    assert steps == ["master", "narrator"]


async def test_a_hand_back_that_moved_no_fiction_gets_no_prose(tmp_path: Path) -> None:
    table = _deciding(tmp_path, narrate=False)
    steps: list[TurnStep] = []
    table.spawner.turns.append(table.plays((tool_call("strike"),)))

    await table.service.play("I charge the guard.", on_step=steps.append)

    state = table.service.state
    assert steps == ["master"]
    assert state.world.exchanges()[-1].lines == ()
    assert state.world.exchanges()[-1].narration == ""


async def test_a_closed_answer_resolves_in_engine_code_before_the_master_continues(
    tmp_path: Path,
) -> None:
    table = _deciding(tmp_path)
    _suspend(table)
    facts: list[Fact] = []

    state = await played(table, Answer(option_id="lantern"), on_fact=facts.append)

    assert [fact.kind for fact in facts] == ["defence_turned"]
    assert "lantern broke to turn the hit" in table.answers[0]
    assert state.world.exchanges()[-1].prompt == "Break the lantern"
    assert state.pending is None


async def test_a_re_suspended_continuation_keeps_the_rules_waiting(tmp_path: Path) -> None:
    table = _deciding(tmp_path)
    _suspend(table, CHAINING)

    state = await played(table, Answer(option_id="lantern"))

    assert state.pending == DECISION
    # A re-suspension has no tool answer to carry the wait, so the picture has to end on it.
    resolved = table.answers[0].split("\n\nPLAYER ACTION:")[0]
    assert resolved.endswith(f"- {RULES_WAIT}")


async def test_an_option_the_decision_never_offered_raises(tmp_path: Path) -> None:
    table = _deciding(tmp_path)
    _suspend(table)

    with pytest.raises(ValueError, match="offers no option 'vest'"):
        _ = await played(table, Answer(option_id="vest"))


def test_a_change_may_run_on_a_state_already_suspended_on_a_decision(tmp_path: Path) -> None:
    engine, state = _engine(), opened(tmp_path).service.state

    def nothing(draft: Game, rng: Random) -> tuple[Fact, ...]:
        del draft, rng
        return ()

    draft = _pending(state).draft()
    _ = apply_to_draft(engine.validate, draft, nothing, Random(0))
    suspended = draft.committed()
    assert suspended.pending == DECISION


def test_a_second_decision_is_refused_while_one_is_already_open(tmp_path: Path) -> None:
    engine, draft = _engine(), _pending(opened(tmp_path).service.state).draft()

    with pytest.raises(ValueError, match="one at a time"):
        _ = apply_to_draft(
            engine.validate, draft, lambda draft, _rng: _hit(draft, narrate=False), Random(0)
        )


def _option(**changes: object) -> PendingOption:
    return PendingOption.model_validate(
        {"id": "lantern", "label": "Break the lantern", "name": TURN_THE_HIT.name} | changes
    )


def test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused(
    tmp_path: Path,
) -> None:
    engine, suspended = _engine(), _pending(opened(tmp_path).service.state)
    draft = suspended.draft()

    assert engine.restored(suspended.model_dump_json()).pending == DECISION

    with pytest.raises(ValueError, match="no tool 'spend_momentum' to play option 'lantern'"):
        _ = engine.answer(draft, _option(name="spend_momentum"), Random(0))
    with pytest.raises(ValidationError):
        _ = engine.answer(draft, _option(args={"nothing": "of theirs"}), Random(0))


def test_a_decision_whose_options_are_the_whole_pick_refuses_an_answer_in_words(
    tmp_path: Path,
) -> None:
    engine, state = _engine(), opened(tmp_path).service.state
    closed = DECISION.model_copy(update={"allows_text": False})

    with pytest.raises(ValueError, match="takes one of its options, not words"):
        _ = consume_answer(
            Turn(engine=engine, draft=_pending(state, closed).draft(), rng=Random(0)),
            Answer(text="I dive aside"),
        )


def _pending(state: Game, decision: PendingDecision = DECISION) -> Game:
    draft = state.draft()
    draft.pending = decision
    return draft.committed()
