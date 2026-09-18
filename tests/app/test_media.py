from asyncio import gather, sleep
from collections.abc import Sequence
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
from aidm.core.io import FileStore
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
