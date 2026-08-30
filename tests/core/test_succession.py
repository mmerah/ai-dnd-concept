from random import Random

import pytest
from core_test_support import initialized, loner_sheet

from aidm.engines.core import Engine
from aidm.state.entities import DEAD, PLAYER_ID, EntityId
from aidm.state.model import Game
from aidm.state.play import Answer, Line
from aidm.turn.run import Turn, close_segment, consume_answer
from aidm.world import actions

MARA = EntityId("mara")
FELL = (Line(text="Kael falls, and does not get up."),)


def _died(engine: Engine, state: Game, *, companion: bool) -> Game:
    """A committed turn that leaves the played character dead, with or without a companion."""
    draft = state.draft()
    if companion:
        _ = actions.join_party(draft, MARA)
    _ = actions.kill(draft, draft.player_id, engine.validate)
    return close_segment(engine.scene(draft).label, draft, "I open the vault.", FELL, ())


def _turn(engine: Engine, draft: Game) -> Turn:
    return Turn(engine=engine, draft=draft, rng=Random(0), commit=lambda _: None)


def _answered(engine: Engine, state: Game, option_id: str) -> Game:
    draft = state.draft()
    _ = consume_answer(_turn(engine, draft), Answer(option_id=option_id))
    return draft.committed()


def _reopened(engine: Engine, state: Game) -> Game:
    return engine.restored(state.model_dump_json())


def test_a_takeover_moves_the_played_id_and_leaves_the_rest_of_the_game_alone() -> None:
    engine, state = initialized()
    died = _died(engine, state, companion=True)
    assert died.pending is not None
    assert (died.pending.kind, [one.id for one in died.pending.options]) == ("succession", [MARA])
    chosen = died.pending.options[0]
    assert (chosen.name, chosen.args) == ("take_over", {"successor_id": MARA})

    landed = _answered(engine, died, MARA)

    assert landed.player_id == MARA
    assert landed.player.name == died.world.require(MARA).name
    assert landed.world.entities == died.world.entities
    assert landed.history == died.history
    assert landed.world.require(PLAYER_ID).trait(DEAD) is not None
    assert MARA not in landed.world.party
    # What the scene draws: the successor's own sheet, read through the played id.
    assert loner_sheet(landed, MARA).rows()[0][1] in str(engine.scene(landed).sections)


def test_a_death_with_nobody_to_carry_on_ends_the_game_as_it_always_did() -> None:
    engine, state = initialized()
    died = _died(engine, state, companion=False)

    assert died.pending is None
    with pytest.raises(ValueError, match="You died."):
        _ = consume_answer(_turn(engine, died.draft()), "I get back up.")


def test_the_death_decision_survives_the_save_it_is_written_into() -> None:
    engine, state = initialized()
    died = _died(engine, state, companion=True)

    reopened = _reopened(engine, died)

    assert reopened.pending == died.pending
    assert reopened.player_id == PLAYER_ID


def test_a_save_written_after_a_takeover_reopens_on_the_successor() -> None:
    engine, state = initialized()
    landed = _answered(engine, _died(engine, state, companion=True), MARA)

    reopened = _reopened(engine, landed)

    assert reopened.player_id == MARA
    assert engine.scene(reopened).sections == engine.scene(landed).sections
