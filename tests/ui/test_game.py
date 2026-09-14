from asyncio import get_running_loop
from collections.abc import Awaitable, Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from nicegui import Client, app, core, ui
from nicegui.events import GenericEventArguments
from support.game import open_game
from support.table import Table, offline_settings, play_turn, updated

from aidm.app.media import scene_key
from aidm.app.runtime import IN_FLIGHT
from aidm.config import MediaConfig
from aidm.core.entities import Refusal
from aidm.core.model import AnyGame
from aidm.core.play import DecisionOption, Exchange, PendingDecision, PendingOption, SpokenLine
from aidm.core.views import PlayerView, Subject
from aidm.ui.dice import DiceTray
from aidm.ui.game import (
    GamePage,
    Observed,
    can_type,
    draft_spent,
    game_page,
    insert_at_caret,
    near_end,
    placeholder,
    standing_proposal,
    whole_page,
)

WREN = Subject(id="player", label="Wren", detail="A quiet scout")


def _view(decision: PendingDecision | None = None, over: str | None = None) -> PlayerView:
    return PlayerView(
        player=WREN,
        scene_title="The Cloister Walk",
        situation="Rain drums the arcade.",
        panels=(),
        decision=decision,
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
    assert not can_type(_view(decision=_pick(allows_text=False)), None)
    assert can_type(_view(decision=_pick(allows_text=True)), None)
    assert not can_type(_view(over="Wren is dead"), None)


def _spoken(*, proposal: str = "") -> Exchange:
    return Exchange(
        words="",
        mark="interjection",
        lines=(SpokenLine(speaker_id="vessa-rune", speaker="Vessa", text="Wait."),),
        proposal=proposal,
    )


def test_standing_proposal_holds_the_newest_proposal_between_turns_only() -> None:
    proposed = (_spoken(proposal="I check the door."),)

    assert standing_proposal(proposed, _view(), None) == proposed[-1]
    assert standing_proposal(proposed, _view(), "master") is None
    assert standing_proposal(proposed, _view(decision=_pick(allows_text=True)), None) is None
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
    assert placeholder(_view(decision=_pick(allows_text=False)), None) != placeholder(
        _view(decision=_pick(allows_text=True)), None
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


def test_only_a_moving_fact_count_spares_the_whole_page() -> None:
    seen = Observed(phase="master", facts=2, exchanges=1, action=None, over=None)
    assert not whole_page(replace(seen, facts=3), seen)
    assert whole_page(replace(seen, facts=3, exchanges=2), seen)
    assert whole_page(replace(seen, phase=None), seen)


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
    page = GamePage(table.service)
    page.transcript = ui.scroll_area()
    page.new_activity = ui.button("New activity")
    page.dice = DiceTray(table.service.engine.look.dice)
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


async def test_decision_buttons_grey_out_while_a_turn_is_in_flight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = open_game(tmp_path)
    seen: list[bool] = []

    def spy_decision_widget(
        prompt: str,
        options: Sequence[DecisionOption],
        answer: Callable[[str], Awaitable[None]],
        *,
        enabled: bool = True,
    ) -> None:
        del prompt, options, answer
        seen.append(enabled)

    monkeypatch.setattr("aidm.ui.game.decision_widget", spy_decision_widget)
    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            page.view = _view(decision=_pick(allows_text=False))

            table.service.phase = None
            page.decision_panel()
            table.service.phase = "master"
            page.decision_panel()
    finally:
        client.delete()

    assert seen == [True, False]


async def test_any_games_in_flight_guard_is_kept_from_the_player(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = open_game(tmp_path)
    notified: list[str] = []

    def spy_notify(message: str, **_kwargs: object) -> None:
        notified.append(message)

    monkeypatch.setattr("aidm.ui.game.ui.notify", spy_notify)

    async def busy_here() -> None:
        raise Refusal(IN_FLIGHT.format(slug=table.service.slug))

    async def busy_elsewhere() -> None:
        raise Refusal(IN_FLIGHT.format(slug="some-other-save"))

    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            landed = await page._run(busy_here)  # pyright: ignore[reportPrivateUsage]
            _ = await page._run(busy_elsewhere)  # pyright: ignore[reportPrivateUsage]
    finally:
        client.delete()

    assert landed is False
    assert notified == []


async def test_a_refusal_that_is_not_the_in_flight_guard_still_toasts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = open_game(tmp_path)
    notified: list[str] = []

    def spy_notify(message: str, **_kwargs: object) -> None:
        notified.append(message)

    monkeypatch.setattr("aidm.ui.game.ui.notify", spy_notify)

    async def refused() -> None:
        raise Refusal("the rules wait on the player's decision first")

    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            landed = await page._run(refused)  # pyright: ignore[reportPrivateUsage]
    finally:
        client.delete()

    assert landed is False
    assert notified == ["the rules wait on the player's decision first"]


async def test_a_page_is_not_built_for_a_client_deleted_before_the_handshake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = open_game(tmp_path)
    built: list[object] = []

    class _Recorder:
        def __init__(self, session: object) -> None:
            built.append(session)

        def build(self) -> None:
            built.append("built")

    monkeypatch.setattr("aidm.ui.game.GamePage", _Recorder)
    client = Client(ui.page("/"))
    client.delete()

    with _nicegui_loop(), client:
        game_page(table.service)

    assert built == []


async def test_build_remembers_scene_art_already_on_disk_like_the_clip(tmp_path: Path) -> None:
    settings = updated(offline_settings(tmp_path), media=MediaConfig(enabled=True).model_dump())
    table = open_game(tmp_path, settings=settings)
    session = table.service
    assert session.media is not None
    art_dir = session.media.saves
    art_dir.mkdir(parents=True, exist_ok=True)
    key = scene_key(session.engine.narrator_view(session.state))
    (art_dir / f"{key}.png").write_bytes(b"")

    client = Client(ui.page("/"))
    client.tab_id = "test-tab"
    # composer() reads app.storage.tab, which a real handshake would have created for this tab.
    await app.storage._create_tab_storage(client.tab_id)  # pyright: ignore[reportPrivateUsage]
    try:
        with _nicegui_loop(), client:
            page = GamePage(session)
            page.build()
            assert page.shown_art == session.scene_art()
    finally:
        client.delete()


async def test_dictated_rejects_a_payload_missing_what_dictation_js_promises(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            event = GenericEventArguments(sender=page.box, client=client, args={"text": "north"})
            with pytest.raises(Refusal):
                page.dictated(event)
    finally:
        client.delete()


async def test_dictated_inserts_a_well_formed_payload_at_the_caret(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    client = Client(ui.page("/"))
    try:
        with _nicegui_loop(), client:
            page = _page(table)
            page.box.value = "I go"
            event = GenericEventArguments(
                sender=page.box, client=client, args={"text": "north", "caret": 4}
            )
            page.dictated(event)
            assert page.box.value == "I go north"
    finally:
        client.delete()
