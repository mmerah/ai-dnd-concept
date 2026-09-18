import json
from asyncio import CancelledError, Event, create_task, gather, sleep
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from pydantic import SecretStr
from support.game import TARGET, initialized, with_entity
from support.table import offline_settings

from aidm.app.present import (
    ICON_DIR,
    GeneratedImage,
    Illustrator,
    Presenter,
    illustration_request,
    scene_key,
)
from aidm.config import MediaConfig, ProviderConfig
from aidm.core.io import FileStore, publish
from aidm.core.views import NarratorView
from aidm.engines.engine import AnyEngine
from aidm.engines.loner3e.world import Loner3eEntity, Loner3eGame

NARRATION = "The door groans open."
STYLE = "Painterly fantasy illustration, muted colours, no text or lettering."


def _illustrator(saves: Path, icon_dirs: tuple[Path, ...] = ()) -> Illustrator:
    return Illustrator(
        config=MediaConfig(enabled=True),
        provider=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test")),
        saves=saves,
        icon_dirs=icon_dirs,
        style=STYLE,
    )


def _placed(state: Loner3eGame, name: str, *, known: bool) -> Loner3eGame:
    return with_entity(
        state,
        Loner3eEntity(
            id=name.lower().replace(" ", "-"),
            name=name,
            brief=f"A {name.lower()}.",
            known=known,
            concept=name,
        ),
    )


def _scene(engine: AnyEngine, state: Loner3eGame) -> NarratorView:
    return engine.narrator_view(state)


def test_illustration_request_names_the_scene_and_no_unrevealed_canon() -> None:
    engine, state = initialized()
    state = _placed(_placed(state, "Brass Warden", known=True), "Pale Watcher", known=False)
    request = illustration_request(_scene(engine, state), NARRATION, STYLE)
    assert state.world.scene.title in request
    assert "Brass Warden" in request
    assert "A brass warden." in request
    assert NARRATION in request
    assert "Pale Watcher" not in request


def test_scene_key_holds_through_a_change_of_cast_but_not_of_place() -> None:
    engine, state = initialized()
    key = scene_key(_scene(engine, state))
    assert scene_key(_scene(engine, _placed(state, "Pale Watcher", known=False))) == key
    assert scene_key(_scene(engine, _placed(state, "Brass Warden", known=True))) == key
    draft = state.draft()
    draft.world.scene.place = "cloister"
    assert scene_key(_scene(engine, draft.commit())) != key


def test_an_icon_is_looked_up_in_each_authored_directory_in_order(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "scenario"
    character_dir = tmp_path / "character"
    saves_dir = tmp_path / "save.media"
    for directory, stem in (
        (scenario_dir, "mara"),
        (character_dir, "player"),
        (saves_dir / "icons", "invented"),
    ):
        directory.mkdir(parents=True)
        (directory / f"{stem}.png").write_bytes(b"\x89PNG")
    illustrator = _illustrator(saves_dir, (scenario_dir, character_dir))
    assert illustrator.icon("mara") == scenario_dir / "mara.png"
    assert illustrator.icon("player") == character_dir / "player.png"
    assert illustrator.icon("invented") == saves_dir / "icons" / "invented.png"
    assert illustrator.icon("nobody") is None


async def test_concurrent_illustrations_of_one_scene_generate_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, state = initialized()
    scene = engine.narrator_view(state)
    player = engine.player_view(state).player
    prompts: list[str] = []

    async def _generate(
        _self: Illustrator, prompt: str, _ratio: str, _references: Sequence[Path] = ()
    ) -> GeneratedImage | None:
        prompts.append(prompt)
        await sleep(0)  # a real generation suspends; without this nothing can interleave
        return GeneratedImage(data=b"\x89PNG", suffix=".png")

    monkeypatch.setattr(Illustrator, "_generate", _generate)
    illustrator = _illustrator(tmp_path / "save.media")
    _ = await gather(
        illustrator.illustrate(scene, player, NARRATION),
        illustrator.illustrate(scene, player, NARRATION),
    )
    scene_prompts = [prompt for prompt in prompts if prompt.startswith("Draw one wide")]
    assert len(scene_prompts) == 1
    # Every other prompt is an icon: a repeat is a second bill for the same picture.
    assert len(prompts) == len(set(prompts))
    assert illustrator.claims.held == set()


async def test_cancelling_illustrate_during_the_icon_await_releases_the_scene_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, state = initialized()
    scene = engine.narrator_view(state)
    player = engine.player_view(state).player
    entered = Event()

    async def _hang(_self: Illustrator, _subject: object) -> Path | None:
        entered.set()
        await sleep(1e9)
        return None

    async def _generate(
        _self: Illustrator, _prompt: str, _ratio: str, _references: Sequence[Path] = ()
    ) -> GeneratedImage:
        return GeneratedImage(data=b"\x89PNG", suffix=".png")

    monkeypatch.setattr(Illustrator, "_drawn_icon", _hang)
    monkeypatch.setattr(Illustrator, "_generate", _generate)
    illustrator = _illustrator(tmp_path / "save.media")

    task = create_task(illustrator.illustrate(scene, player, NARRATION))
    await entered.wait()
    task.cancel()
    with pytest.raises(CancelledError):
        await task

    assert illustrator.claims.held == set()

    monkeypatch.undo()
    monkeypatch.setattr(Illustrator, "_generate", _generate)
    await illustrator.illustrate(scene, player, NARRATION)

    assert illustrator.scene_art(scene) is not None


async def test_a_drawn_icon_still_holds_its_claim_while_the_file_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim freed before the write lets a second caller miss the cache and pay again."""
    engine, state = initialized()
    scene = engine.narrator_view(state)
    player = engine.player_view(state).player
    held_while_writing: dict[str, set[str]] = {}

    async def _generate(
        _self: Illustrator, _prompt: str, _ratio: str, _references: Sequence[Path] = ()
    ) -> GeneratedImage:
        return GeneratedImage(data=b"\x89PNG", suffix=".png")

    def _publish(path: Path, write: Callable[[Path], None]) -> None:
        held_while_writing[path.stem] = set(illustrator.claims.held)
        publish(path, write)

    monkeypatch.setattr(Illustrator, "_generate", _generate)
    monkeypatch.setattr("aidm.app.present.publish", _publish)
    illustrator = _illustrator(tmp_path / "save.media")

    await illustrator.illustrate(scene, player, NARRATION)

    assert f"icon:{player.id}" in held_while_writing[player.id]
    assert illustrator.claims.held == set()


async def test_a_reply_holding_unreadable_base64_leaves_illustrate_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, state = initialized()
    scene = engine.narrator_view(state)
    player = engine.player_view(state).player

    async def _bad_reply(_provider: object, _path: str, _body: object, _timeout: float) -> bytes:
        reply = {
            "choices": [
                {"message": {"images": [{"image_url": {"url": "data:image/png;base64,abc"}}]}}
            ]
        }
        return json.dumps(reply).encode()

    monkeypatch.setattr("aidm.app.present.post_bearer", _bad_reply)
    illustrator = _illustrator(tmp_path / "save.media")

    await illustrator.illustrate(scene, player, NARRATION)

    assert illustrator.scene_art(scene) is None
    assert illustrator.claims.held == set()


def test_media_off_asks_for_no_art_and_hides_what_an_earlier_run_cached(tmp_path: Path) -> None:
    engine, state = initialized()
    scene = _scene(engine, state)
    player = engine.player_view(state).player
    off = Presenter.open(
        offline_settings(tmp_path),
        FileStore(tmp_path),
        TARGET.slug,
        style=STYLE,
        icon_dirs=(),
        voice="",
    )

    # nothing is cached yet: a gate that let this through would hand back a coroutine
    assert off.present(scene, player, None) == ()
    (off.illustrator.saves / ICON_DIR).mkdir(parents=True)
    (off.illustrator.saves / ICON_DIR / f"{player.id}.png").write_bytes(b"")
    (off.illustrator.saves / f"{scene_key(scene)}.png").write_bytes(b"")

    assert off.illustrator.scene_art(scene) is None
    assert off.illustrator.icon(player.id) is None


def test_illustrator_open_takes_the_passed_style_and_is_disabled_when_media_is_off(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path)
    on = offline_settings(tmp_path).model_copy(update={"media": MediaConfig(enabled=True)})
    illustrator = Illustrator.open(on, store, TARGET.slug, style="woodcut", icon_dirs=())
    assert illustrator.style == "woodcut"

    off = offline_settings(tmp_path)
    assert (
        Illustrator.open(off, store, TARGET.slug, style="woodcut", icon_dirs=()).config.enabled
        is False
    )
