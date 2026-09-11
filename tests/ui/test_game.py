from asyncio import get_running_loop
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from nicegui import Client, core, ui
from support.game import open_game
from support.table import Table, play_turn

from aidm.core.model import AnyGame
from aidm.core.play import Exchange, PendingDecision, PendingOption, SpokenLine
from aidm.core.views import PlayerView, Subject
from aidm.ui import theme
from aidm.ui.dice import DiceTray
from aidm.ui.game import (
    GamePage,
    Observed,
    can_type,
    draft_spent,
    insert_at_caret,
    near_end,
    placeholder,
    standing_proposal,
)

WREN = Subject(id="player", label="Wren", detail="A quiet scout")


def _view(prompt: PendingDecision | None = None, over: str | None = None) -> PlayerView:
    return PlayerView(
        player=WREN,
        scene_title="The Cloister Walk",
        situation="Rain drums the arcade.",
        panels=(),
        prompt=prompt,
        action=None,
        over=over,
    )


def _pick(*, allows_text: bool) -> PendingDecision:
    return PendingDecision(
        kind="pick",
        prompt="Which door?",
        options=(PendingOption(id="left", label="Left", name="pick"),),
        allows_text=allows_text,
    )


def test_the_composer_opens_only_between_turns_on_a_game_still_going() -> None:
    assert can_type(_view(), None)
    assert not can_type(_view(), "master")
    assert not can_type(_view(prompt=_pick(allows_text=False)), None)
    assert can_type(_view(prompt=_pick(allows_text=True)), None)
    assert not can_type(_view(over="Wren is dead"), None)


def _spoken(*, proposal: str = "") -> Exchange:
    return Exchange(
        prompt="",
        mark="interjection",
        lines=(SpokenLine(speaker_id="vessa-rune", speaker="Vessa", text="Wait."),),
        proposal=proposal,
    )


def test_standing_proposal_holds_the_newest_proposal_between_turns_only() -> None:
    proposed = (_spoken(proposal="I check the door."),)

    assert standing_proposal(proposed, _view(), None) == proposed[-1]
    assert standing_proposal(proposed, _view(), "master") is None
    assert standing_proposal(proposed, _view(prompt=_pick(allows_text=True)), None) is None
    assert standing_proposal((_spoken(),), _view(), None) is None


def test_near_end_follows_a_reader_within_slack_of_the_bottom() -> None:
    assert near_end(1000, 1600, 600)
    assert near_end(960, 1600, 600)
    assert not near_end(400, 1600, 600)
    assert near_end(0, 300, 600)


def test_insert_at_caret_spaces_only_against_a_non_space_neighbour() -> None:
    assert insert_at_caret("abcd", "x", 2) == "ab x cd"
    assert insert_at_caret("I go", "north", 4) == "I go north"
    assert insert_at_caret("", "hi", 0) == "hi"
    assert insert_at_caret("I ", "go", 2) == "I go"


def test_placeholder_names_the_working_role_between_turns() -> None:
    assert placeholder(_view(), "master") != placeholder(_view(), None)
    assert placeholder(_view(prompt=_pick(allows_text=False)), None) != placeholder(
        _view(prompt=_pick(allows_text=True)), None
    )


def test_placeholder_names_game_over_before_anything_else() -> None:
    assert placeholder(_view(over="Wren is dead"), None) == (
        "The game is over. Restart it from the menu."
    )
    assert placeholder(_view(over="Wren is dead"), "master") == (
        "The game is over. Restart it from the menu."
    )


def test_draft_spent_once_the_matching_exchange_has_landed() -> None:
    assert draft_spent("I open the door.", "I open the door.")


def test_draft_spent_ignores_an_unrelated_landed_prompt() -> None:
    assert not draft_spent("I open the door.", "(the party speaks)")


def test_draft_spent_is_false_for_an_empty_draft() -> None:
    assert not draft_spent("", "")


@contextmanager
def _nicegui_loop() -> Generator[None]:
    """A refreshable's background task asserts NiceGUI's loop is set; only `ui.run()` sets it."""
    core.loop = get_running_loop()
    try:
        yield
    finally:
        core.loop = None


def _page[G: AnyGame](table: Table[G]) -> GamePage:
    """The few elements `poll_turn` touches, built without a socket connection."""
    page = GamePage(table.runtime, table.service)
    page.transcript = ui.scroll_area()
    page.new_activity = ui.button("New activity")
    page.dice = DiceTray(theme.dice_look(table.service.engine_id))
    page.box = ui.input()
    page.send = ui.button()
    page.action_button = ui.button()
    page.over_label = ui.label()
    page.view, page.history = table.service.player_view(), table.service.history()
    page.seen = Observed.of(table.service, page.view, page.history)
    return page


async def test_poll_turn_follows_only_on_the_readers_own_move(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            page.at_end = False
            page.own_move = True

            table.service.phase = "master"  # another tab's turn starting: not the reader's move
            page.poll_turn()
            assert page.new_activity.visible is False

        _ = await play_turn(table, "I wait.", narration="Nothing stirs.")

        with _nicegui_loop(), client:
            page.poll_turn()
            assert page.new_activity.visible is False

            page.own_move = False
            table.service.phase = "narrator"
            page.poll_turn()
            assert page.new_activity.visible is True
    finally:
        client.delete()


async def test_a_change_that_lands_nothing_keeps_a_draft_matching_the_last_prompt(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            page.box.value = "I wait."

            table.service.phase = "master"  # a turn starts elsewhere; nothing has landed yet
            page.poll_turn()

            assert page.box.value == "I wait."
            table.service.phase = None

        _ = await play_turn(table, "I wait.", narration="Nothing stirs.")

        with _nicegui_loop(), client:
            page.poll_turn()
            assert page.box.value == ""
    finally:
        client.delete()
