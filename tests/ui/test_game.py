from collections.abc import Callable
from pathlib import Path

import pytest
from nicegui import Client, ui
from support.game import open_game, session
from support.table import (
    Table,
    play_turn,
)

from aidm.core.model import AnyGame
from aidm.core.play import (
    PendingDecision,
    PendingOption,
)
from aidm.core.views import PlayerView, Subject
from aidm.ui.game import GamePage, game_page
from aidm.ui.transcript import (
    Observed,
    can_type,
)
from aidm.ui.widgets import DiceSound

WREN = Subject(id="player", name="Wren", brief="A quiet scout")


def _view(decision: PendingDecision | None = None, ending: str | None = None) -> PlayerView:
    return PlayerView(
        premise="",
        player=WREN,
        scene_title="The Cloister Walk",
        situation="Rain drums the arcade.",
        panels=(),
        decision=decision,
        action=None,
        ending=ending,
    )


def _pick(*, allows_text: bool) -> PendingDecision:
    return PendingDecision(
        kind="pick",
        prompt="Which door?",
        options=(PendingOption(id="left", name="Left", tool_name="pick"),),
        allows_text=allows_text,
    )


def test_the_composer_opens_only_between_turns_on_a_game_still_going() -> None:
    assert can_type(_view(), None)
    assert not can_type(_view(), "master")
    assert not can_type(_view(decision=_pick(allows_text=False)), None)
    assert can_type(_view(decision=_pick(allows_text=True)), None)
    assert not can_type(_view(ending="Wren is dead"), None)


def _screen[G: AnyGame](table: Table[G]) -> GamePage:
    """The few elements `poll_turn` touches, built without a socket connection."""
    screen = GamePage(table.service)
    screen.scroll = ui.scroll_area()
    screen.new_activity = ui.button("New activity")
    screen.dice = DiceSound()
    screen.box = ui.input()
    screen.send = ui.button()
    screen.action_button = ui.button()
    screen.over_label = ui.label()
    screen.restart_item = ui.menu_item("Restart this game")
    screen.view, screen.history = table.service.player_view(), table.service.state.exchanges()
    screen.seen = Observed.of(table.service, screen.view, screen.history)
    return screen


async def test_poll_turn_follows_only_on_the_readers_own_move(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    page()
    screen = _screen(table)
    screen.at_end = False
    screen.own_move = True

    table.service.working_role = "master"  # another tab's turn starting: not the reader's move
    screen.poll_turn()
    assert screen.new_activity.visible is False

    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    screen.poll_turn()
    assert screen.new_activity.visible is False

    screen.own_move = False
    table.service.working_role = "narrator"
    screen.poll_turn()
    assert screen.new_activity.visible is True


REFUSED = "the rules wait on the player's decision first"


async def test_a_page_is_not_built_for_a_client_deleted_before_the_handshake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    built: list[object] = []

    class _Recorder:
        def __init__(self, session: object) -> None:
            built.append(session)

        def build(self) -> None:
            built.append("built")

    monkeypatch.setattr("aidm.ui.game.GamePage", _Recorder)
    client = page()
    client.delete()

    game_page(table.service)

    assert built == []


async def test_the_composer_greys_while_another_game_holds_the_gate(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    page()
    screen = _screen(table)

    screen._set_composer()  # pyright: ignore[reportPrivateUsage]
    assert screen.box.enabled

    table.service.gate.admitted = session(tmp_path / "other")
    screen._set_composer()  # pyright: ignore[reportPrivateUsage]
    assert not screen.box.enabled

    table.service.gate.admitted = None
    screen.poll_turn()
    assert screen.box.enabled


async def test_a_turn_polls_when_it_ends_but_not_onto_a_deleted_client(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    client = page()
    screen = _screen(table)
    polls: list[None] = []
    screen.poll_turn = lambda: polls.append(None)  # pyright: ignore[reportAttributeAccessIssue]

    async def nothing() -> None:
        return

    assert await screen._run(nothing)  # pyright: ignore[reportPrivateUsage]
    assert len(polls) == 1

    client.delete()
    assert await screen._run(nothing)  # pyright: ignore[reportPrivateUsage]
    assert len(polls) == 1
