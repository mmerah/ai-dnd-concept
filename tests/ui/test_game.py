from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from nicegui import Client, ui
from support.game import open_game
from support.table import (
    Table,
    play_turn,
)

from aidm.app.present import Reader, clip_key
from aidm.config import SpeechConfig
from aidm.core.model import AnyGame
from aidm.core.play import (
    PendingDecision,
    PendingOption,
    SpokenLine,
)
from aidm.core.views import PlayerView, Subject
from aidm.ui.game import GamePage, game_page
from aidm.ui.transcript import (
    READ_ICONS,
    Observed,
    can_type,
    chat,
)
from aidm.ui.widgets import DiceSound, Speaker, media_url

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


def _spoken(reader: Reader, text: str) -> Path:
    clip = reader.saves / f"{clip_key(reader.config.model, reader.voice, text)}.wav"
    clip.parent.mkdir(parents=True, exist_ok=True)
    _ = clip.write_bytes(b"RIFF")
    return clip


async def _no_accept(_proposal: str) -> None:
    raise AssertionError("nothing to accept")


async def test_chat_gives_a_read_button_only_to_a_line_with_a_clip_and_marks_the_line_read(
    tmp_path: Path, page: Callable[[], Client]
) -> None:
    table = open_game(tmp_path)
    service = table.service
    reader = replace(
        service.presenter.reader, config=SpeechConfig(enabled=True), saves=tmp_path / "speech"
    )
    service.presenter = replace(service.presenter, reader=reader)
    lines = (
        SpokenLine(text="Nothing stirs."),
        SpokenLine(speaker_id="kael", speaker="Kael", text="Still."),
    )
    service.save(service.engine.close(service.state.draft(), lines, (), words="I wait."))
    exchange = service.state.exchanges()[-1]
    clip = _spoken(reader, exchange.lines[0].text)
    page()

    def render(reading: str) -> dict[str, ui.button]:
        return chat(
            service,
            service.player_view(),
            service.state.exchanges(),
            reading=reading,
            accept=_no_accept,
            read=lambda _exchange, _index: None,
        )

    assert service.clips(exchange) == (clip, None)
    idle = render("")
    assert list(idle) == [media_url(clip)]
    assert idle[media_url(clip)].icon == READ_ICONS[False]
    busy = render(media_url(clip))
    assert busy[media_url(clip)].icon == READ_ICONS[True]


async def test_poll_media_follows_a_new_exchange_but_not_the_clip_the_page_loaded_with(
    tmp_path: Path, page: Callable[[], Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    table = open_game(tmp_path)
    service = table.service
    reader = replace(
        service.presenter.reader, config=SpeechConfig(enabled=True), saves=tmp_path / "speech"
    )
    service.presenter = replace(service.presenter, reader=reader)
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    loaded = _spoken(reader, "Nothing stirs.")
    followed: list[tuple[tuple[str | None, ...], bool]] = []

    def follow(urls: Sequence[str | None], *, restart: bool) -> None:
        followed.append((tuple(urls), restart))

    page()
    screen = _screen(table)
    screen.speaker = Speaker()
    monkeypatch.setattr(screen.speaker, "follow", follow)
    screen.followed = service.state.exchanges()[-1]
    screen.shown_clips = (loaded,)

    screen.poll_media()
    assert followed == []

    _ = await play_turn(table, "I listen.", narration="A drip.")
    screen.poll_media()
    assert followed == [((None,), True)]

    first = _spoken(reader, "A drip.")
    screen.poll_media()
    assert followed[1:] == [((media_url(first),), False)]
