from pathlib import Path
from random import Random

import pytest
from pydantic import Field, ValidationError
from support.game import open_game
from support.table import NO_PACKS, Table, narrowed, play_turn, tool_call

from aidm.core.entities import Frozen, Refusal
from aidm.core.facts import Fact
from aidm.core.model import AnyGame
from aidm.core.play import Answer, PendingDecision, PendingOption
from aidm.core.tools import NoArgs, tool, tools_of
from aidm.engines.engine import AnyEngine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame
from aidm.turn.run import PAUSED_TO_ASK, RULES_WAIT, Turn


class Broken(Frozen):
    item: str = Field(description="What breaks to turn the hit.")


def _turned(item: str) -> tuple[Fact, ...]:
    return (Fact(trace=f"{item} broke to turn the hit", told=True),)


class Deciding:
    """The three tools a suspending decision runs, marked on one class instead of an engine."""

    def __init__(self, *, told: bool) -> None:
        self.told = told

    @tool
    def strike(self, draft: AnyGame, _args: NoArgs, _rng: Random) -> tuple[Fact, ...]:
        """Take a hit the player may turn by breaking something of theirs."""
        _loner(draft).pending = DECISION
        return (Fact(trace="the blow reaches the player", told=self.told),)

    @tool
    def turn_the_hit(self, _draft: AnyGame, args: Broken, _rng: Random) -> tuple[Fact, ...]:
        """Break something to turn the hit."""
        return _turned(args.item)

    @tool
    def chain_the_hit(self, draft: AnyGame, args: Broken, _rng: Random) -> tuple[Fact, ...]:
        """Break something and leave the rules waiting on the same decision again."""
        _loner(draft).pending = DECISION
        return _turned(args.item)


def _decision(resolver_name: str) -> PendingDecision:
    return PendingDecision(
        kind="defence",
        prompt="The blow lands unless something of yours breaks. What gives?",
        options=(
            PendingOption(
                id="lantern",
                name="Break the lantern",
                brief="Its glass shatters.",
                tool_name=resolver_name,
                args={"item": "lantern"},
            ),
        ),
        allows_text=True,
    )


DECISION = _decision("turn_the_hit")
CHAINING = _decision("chain_the_hit")


def _engine(*, told: bool = True) -> AnyEngine:
    engine = Loner3eEngine(NO_PACKS)
    engine.tools = tools_of(Deciding(told=told))
    return engine


def _deciding(saves: Path, *, told: bool = True) -> Table[Loner3eGame]:
    return open_game(saves, engine=_engine(told=told))


def _suspend(table: Table[Loner3eGame], decision: PendingDecision = DECISION) -> None:
    table.service.save(_pending(table.service.state, decision))


def test_an_answer_is_a_chosen_option_or_written_text_but_never_both_nor_neither() -> None:
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer()
    with pytest.raises(ValidationError, match="either a chosen option or written text"):
        _ = Answer(option_id="lantern", text="I dive behind the crate")


async def test_a_suspending_resolver_ends_the_run_and_records_the_pause(tmp_path: Path) -> None:
    table = _deciding(tmp_path)

    state = await play_turn(table, "I charge the guard.", tool_call("strike"))

    assert any(RULES_WAIT in answer for answer in table.answers)
    assert state.pending == DECISION
    assert state.exchanges()[-1].decision == DECISION.prompt
    assert [role for role, _ in table.spawner.prompts] == ["master", "narrator"]


async def test_a_hand_back_that_moved_no_fiction_gets_no_prose(tmp_path: Path) -> None:
    table = _deciding(tmp_path, told=False)
    table.spawner.turns.append(table.plays((tool_call("strike"),)))

    await table.service.play(Answer(text="I charge the guard."))

    state = table.service.state
    assert [role for role, _ in table.spawner.prompts] == ["master"]
    assert state.exchanges()[-1].lines == ()
    assert state.exchanges()[-1].narration() == ""


async def test_a_closed_answer_resolves_in_engine_code_before_the_master_continues(
    tmp_path: Path,
) -> None:
    table = _deciding(tmp_path)
    _suspend(table)

    state = await play_turn(table, Answer(option_id="lantern"))

    assert [fact.trace for fact in table.facts] == ["lantern broke to turn the hit"]
    assert "lantern broke to turn the hit" in table.spawner.prompt("master")
    assert state.exchanges()[-1].words == "Break the lantern"
    assert state.pending is None


async def test_an_answer_that_re_suspends_spawns_no_master(tmp_path: Path) -> None:
    """Every tool would be refused while the rules wait, so the spawn would play nothing."""
    table = _deciding(tmp_path)
    _suspend(table, CHAINING)

    state = await play_turn(table, Answer(option_id="lantern"))

    assert state.pending == DECISION
    assert [role for role, _ in table.spawner.prompts] == ["narrator"]


async def test_a_re_suspended_turns_note_survives_to_the_next_masters_prompt(
    tmp_path: Path,
) -> None:
    """`_consume` writes the note one line before `begin` used to drain it unconditionally."""
    table = _deciding(tmp_path)
    _suspend(table, CHAINING)
    note = PAUSED_TO_ASK.format(prompt=CHAINING.prompt)

    state = await play_turn(table, Answer(option_id="lantern"))

    assert any(entry.startswith(note) for entry in state.notes)

    _ = await play_turn(table, Answer(option_id="lantern"))

    assert note in table.spawner.prompt("master")


async def test_an_option_the_decision_never_offered_raises(tmp_path: Path) -> None:
    table = _deciding(tmp_path)
    _suspend(table)

    with pytest.raises(Refusal, match="offers no option 'vest'"):
        _ = await play_turn(table, Answer(option_id="vest"))


def test_a_change_may_run_on_a_state_already_suspended_on_a_decision(tmp_path: Path) -> None:
    engine, state = _engine(), open_game(tmp_path).service.state

    def nothing(draft: AnyGame, rng: Random) -> tuple[Fact, ...]:
        del draft, rng
        return ()

    turn = Turn(engine=engine, draft=_pending(state).draft(), rng=Random(0))
    _ = turn.apply(nothing)
    assert turn.draft.pending == DECISION


def _option(**changes: object) -> PendingOption:
    return PendingOption.model_validate(
        {"id": "lantern", "name": "Break the lantern", "tool_name": "turn_the_hit"} | changes
    )


def test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused(
    tmp_path: Path,
) -> None:
    engine, suspended = _engine(), _pending(open_game(tmp_path).service.state)
    draft = suspended.draft()

    assert engine.restore(suspended.model_dump_json()).pending == DECISION

    with pytest.raises(Refusal, match="'spend_momentum' is not a tool of the"):
        _ = engine.play_option(draft, _option(tool_name="spend_momentum"), Random(0))
    with pytest.raises(Refusal, match="Extra inputs are not permitted"):
        _ = engine.play_option(draft, _option(args={"nothing": "of theirs"}), Random(0))


def test_a_decision_whose_options_are_the_whole_pick_refuses_an_answer_in_words(
    tmp_path: Path,
) -> None:
    engine, state = _engine(), open_game(tmp_path).service.state
    closed = DECISION.model_copy(update={"allows_text": False})

    with pytest.raises(Refusal, match="takes one of its options, not words"):
        Turn.begin(engine, _pending(state, closed), Answer(text="I dive aside"), Random(0))


def _pending(state: AnyGame, decision: PendingDecision = DECISION) -> Loner3eGame:
    draft = _loner(state).draft()
    draft.pending = decision
    return draft.commit()


def _loner(state: AnyGame) -> Loner3eGame:
    return narrowed(state, Loner3eGame)
