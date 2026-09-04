from pathlib import Path
from random import Random

import pytest
from pydantic import Field, ValidationError
from support.loner import open_game
from support.table import Table, narrowed, play_turn, tool_call

from aidm.core.entities import Frozen, Refusal
from aidm.core.facts import Fact
from aidm.core.io import decode
from aidm.core.model import AnyGame
from aidm.core.play import Answer, PendingDecision, PendingOption
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.seam import AnyEngine
from aidm.turn.run import RULES_WAIT, Turn


class Broken(Frozen):
    item: str = Field(description="What breaks to turn the hit.")


def _turned(item: str) -> tuple[Fact, ...]:
    return (Fact(kind="defence_turned", trace=f"{item} broke to turn the hit", told=True),)


TURN_THE_HIT: MasterTool[Loner3eGame] = master_tool(
    "turn_the_hit",
    "Break something to turn the hit.",
    Broken,
    lambda _draft, args, _rng: _turned(args.item),
)


def _chained(draft: AnyGame, item: str) -> tuple[Fact, ...]:
    _loner(draft).pending = DECISION
    return _turned(item)


CHAIN_THE_HIT: MasterTool[Loner3eGame] = master_tool(
    "chain_the_hit",
    "Break something and leave the rules waiting on the same decision again.",
    Broken,
    lambda draft, args, _rng: _chained(draft, args.item),
)


def _decision(resolver: MasterTool[Loner3eGame]) -> PendingDecision:
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


def _hit(draft: AnyGame, *, narrate: bool) -> tuple[Fact, ...]:
    _loner(draft).pending = DECISION
    return (
        Fact(
            kind="hit_taken",
            trace="the blow reaches the player",
            told=narrate,
        ),
    )


def _strike_tool(*, narrate: bool) -> MasterTool[Loner3eGame]:
    return master_tool(
        "strike",
        "Take a hit the player may turn by breaking something of theirs.",
        NoArgs,
        lambda draft, _args, _rng: _hit(draft, narrate=narrate),
    )


def _engine(*, narrate: bool = True) -> AnyEngine:
    engine = Loner3eEngine()
    tools = (_strike_tool(narrate=narrate), TURN_THE_HIT, CHAIN_THE_HIT)
    engine.tools = {tool.name: tool for tool in tools}
    return engine


def _deciding(saves: Path, *, narrate: bool = True) -> Table[Loner3eGame]:
    return open_game(saves, engine=_engine(narrate=narrate))


def _suspend(table: Table[Loner3eGame], decision: PendingDecision = DECISION) -> None:
    table.service.commit(_pending(table.service.state, decision))


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
    assert state.payload.exchanges()[-1].decision == DECISION.prompt
    assert [role for role, _ in table.spawner.prompts] == ["master", "narrator"]


async def test_a_hand_back_that_moved_no_fiction_gets_no_prose(tmp_path: Path) -> None:
    table = _deciding(tmp_path, narrate=False)
    table.spawner.turns.append(table.plays((tool_call("strike"),)))

    await table.service.play(Answer(text="I charge the guard."))

    state = table.service.state
    assert [role for role, _ in table.spawner.prompts] == ["master"]
    assert state.payload.exchanges()[-1].lines == ()
    assert state.payload.exchanges()[-1].narration == ""


async def test_a_closed_answer_resolves_in_engine_code_before_the_master_continues(
    tmp_path: Path,
) -> None:
    table = _deciding(tmp_path)
    _suspend(table)

    state = await play_turn(table, Answer(option_id="lantern"))

    assert [fact.kind for fact in table.facts] == ["defence_turned"]
    assert "lantern broke to turn the hit" in table.spawner.prompt("master")
    assert state.payload.exchanges()[-1].prompt == "Break the lantern"
    assert state.pending is None


async def test_an_answer_that_re_suspends_spawns_no_master(tmp_path: Path) -> None:
    """Every tool would be refused while the rules wait, so the spawn would play nothing."""
    table = _deciding(tmp_path)
    _suspend(table, CHAINING)

    state = await play_turn(table, Answer(option_id="lantern"))

    assert state.pending == DECISION
    assert [role for role, _ in table.spawner.prompts] == ["narrator"]


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
    _ = turn._apply(nothing)  # pyright: ignore[reportPrivateUsage]
    assert turn.draft.pending == DECISION


def test_a_second_decision_is_refused_while_one_is_already_open(tmp_path: Path) -> None:
    engine, state = _engine(), open_game(tmp_path).service.state
    turn = Turn(engine=engine, draft=_pending(state).draft(), rng=Random(0))

    with pytest.raises(Refusal, match="one at a time"):
        _ = turn._apply(lambda draft, _rng: _hit(draft, narrate=False))  # pyright: ignore[reportPrivateUsage]


def _option(**changes: object) -> PendingOption:
    return PendingOption.model_validate(
        {"id": "lantern", "label": "Break the lantern", "name": TURN_THE_HIT.name} | changes
    )


def test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused(
    tmp_path: Path,
) -> None:
    engine, suspended = _engine(), _pending(open_game(tmp_path).service.state)
    draft = suspended.draft()

    assert engine.restore(decode(suspended.model_dump_json())).pending == DECISION

    with pytest.raises(Refusal, match="no tool 'spend_momentum' to play option 'lantern'"):
        _ = engine.answer(draft, _option(name="spend_momentum"), Random(0))
    with pytest.raises(Refusal, match="item: Field required"):
        _ = engine.answer(draft, _option(args={"nothing": "of theirs"}), Random(0))


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
    state = narrowed(state, Loner3eGame)
    return state
