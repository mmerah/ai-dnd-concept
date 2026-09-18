from asyncio import Event, create_task, sleep
from collections.abc import Awaitable, Callable, Sequence
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import pytest
from nicegui import Client, app, ui
from support.game import open_game
from support.table import (
    TWENTYFOURXX,
    Table,
    narrated,
    offline_settings,
    play_turn,
    scenario_for,
    updated,
)

from aidm.app.present import scene_key
from aidm.app.runtime import IN_FLIGHT_ELSEWHERE, IN_FLIGHT_HERE, Busy, LaunchTarget
from aidm.config import MediaConfig, Role
from aidm.core.entities import Refusal
from aidm.core.model import AnyGame
from aidm.core.play import (
    Answer,
    DecisionOption,
    Exchange,
    PendingDecision,
    PendingOption,
    SpokenLine,
)
from aidm.core.views import PlayerView, Subject
from aidm.ui.game import TURN_FAILED, GamePage, game_page
from aidm.ui.transcript import (
    Observed,
    can_type,
    draft_spent,
    near_end,
    placeholder,
    standing_proposal,
    whole_page,
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


def test_placeholder_names_the_working_role_between_turns() -> None:
    assert placeholder(_view(), "master") != placeholder(_view(), None)
    assert placeholder(_view(decision=_pick(allows_text=False)), None) != placeholder(
        _view(decision=_pick(allows_text=True)), None
    )


def test_placeholder_names_game_over_before_anything_else() -> None:
    assert placeholder(_view(ending="Wren is dead"), None) == (
        "The game is over. Restart it from the menu."
    )
    assert placeholder(_view(ending="Wren is dead"), "master") == (
        "The game is over. Restart it from the menu."
    )


def test_draft_spent_once_the_matching_exchange_has_landed() -> None:
    assert draft_spent("I open the door.", "I open the door.")


def test_draft_spent_ignores_an_unrelated_landed_prompt() -> None:
    assert not draft_spent("I open the door.", "(the party speaks)")


def test_draft_spent_is_false_for_an_empty_draft() -> None:
    assert not draft_spent("", "")


def test_only_a_moving_fact_count_spares_the_whole_page() -> None:
    seen = Observed(working_role="master", facts=2, exchanges=1, action=None, ending=None)
    assert not whole_page(replace(seen, facts=3), seen)
    assert whole_page(replace(seen, facts=3, exchanges=2), seen)
    assert whole_page(replace(seen, working_role=None), seen)


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


async def test_a_change_that_lands_nothing_keeps_a_draft_matching_the_last_prompt(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    page()
    screen = _screen(table)
    screen.box.value = "I wait."

    table.service.working_role = "master"  # a turn starts elsewhere; nothing has landed yet
    screen.poll_turn()
    assert screen.box.value == "I wait."

    table.service.working_role = None
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    screen.poll_turn()
    assert screen.box.value == ""


async def test_decision_buttons_grey_out_while_a_turn_is_in_flight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, page: Callable[[], Client]
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
    page()
    screen = _screen(table)
    screen.view = _view(decision=_pick(allows_text=False))

    table.service.working_role = None
    screen.decision_panel()
    table.service.working_role = "master"
    screen.decision_panel()

    assert seen == [True, False]


REFUSED = "the rules wait on the player's decision first"


@pytest.mark.parametrize(
    ("failure", "expected", "expected_raise"),
    [
        (Busy(elsewhere=False), [], None),
        (Busy(elsewhere=True), [IN_FLIGHT_ELSEWHERE], None),
        (Refusal(REFUSED), [REFUSED], None),
        (RuntimeError("secret path"), [TURN_FAILED], RuntimeError),
    ],
    ids=("this game is busy", "another game is busy", "a refusal", "a bug"),
)
async def test_a_turn_that_fails_toasts_only_what_the_player_is_owed(
    failure: Exception,
    expected: list[str],
    expected_raise: type[Exception] | None,
    tmp_path: Path,
    page: Callable[[], Client],
    notified: list[str],
) -> None:
    table = open_game(tmp_path)

    async def failing() -> None:
        raise failure

    page()
    screen = _screen(table)
    raised = nullcontext() if expected_raise is None else pytest.raises(expected_raise)
    with raised:
        assert await screen._run(failing) is False  # pyright: ignore[reportPrivateUsage]

    assert notified == expected


class _FakeTimer:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


async def test_opened_retries_silently_while_the_gate_is_held_by_another_game(
    tmp_path: Path, page: Callable[[], Client], notified: list[str]
) -> None:
    table = open_game(tmp_path)
    gate = Event()

    async def hold_narrator(role: Role, prompt: str) -> None:
        del prompt
        if role == "narrator":
            await gate.wait()

    table.spawner.hooks.append(hold_narrator)
    table.spawner.answers["narrator"] = [narrated("Elsewhere begins.")]
    elsewhere = table.runtime.session(
        LaunchTarget(scenario_id=scenario_for(TWENTYFOURXX), character_id="kael")
    )
    held = create_task(elsewhere.open())
    await sleep(0)

    opener = _FakeTimer()
    page()
    screen = _screen(table)
    await screen._opened(opener)  # pyright: ignore[reportPrivateUsage, reportArgumentType]

    assert notified == []
    assert not opener.cancelled

    gate.set()
    await held


async def test_restart_item_greys_out_while_a_turn_is_in_flight(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    page()
    screen = _screen(table)
    assert screen.restart_item.enabled is True

    table.service.working_role = "master"
    screen.poll_turn()
    assert screen.restart_item.enabled is False

    table.service.working_role = None
    screen.poll_turn()
    assert screen.restart_item.enabled is True


async def test_a_restart_refused_by_this_games_own_gate_still_reaches_the_player(
    tmp_path: Path, page: Callable[[], Client], notified: list[str]
) -> None:
    """Restart runs through `GamePage.restart`, not `_run`: its own gate, its own toast."""
    table = open_game(tmp_path)
    gate = Event()

    async def hold_master(role: Role, prompt: str) -> None:
        del prompt
        if role == "master":
            await gate.wait()

    table.spawner.hooks.append(hold_master)
    table.spawner.turns.append(lambda: None)
    table.spawner.answers["narrator"] = [narrated("You wait.")]
    playing = create_task(table.service.play(Answer(text="I wait.")))
    await sleep(0)

    page()
    await _screen(table).restart()

    assert notified == [IN_FLIGHT_HERE]

    gate.set()
    await playing


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


async def test_build_remembers_scene_art_already_on_disk_like_the_clip(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    settings = updated(offline_settings(tmp_path), media=MediaConfig(enabled=True).model_dump())
    table = open_game(tmp_path, settings=settings)
    session = table.service
    assert session.presenter.illustrator.config.enabled
    art_dir = session.presenter.illustrator.saves
    art_dir.mkdir(parents=True, exist_ok=True)
    key = scene_key(session.engine.narrator_view(session.state))
    (art_dir / f"{key}.png").write_bytes(b"")

    client = page()
    client.tab_id = "test-tab"
    # composer() reads app.storage.tab, which a real handshake would have created for this tab.
    await app.storage._create_tab_storage(client.tab_id)  # pyright: ignore[reportPrivateUsage]
    screen = GamePage(session)

    screen.build()

    assert screen.shown_art == session.scene_art()
