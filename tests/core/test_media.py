from asyncio import gather, sleep
from collections.abc import Sequence
from pathlib import Path

import pytest
from core_test_support import initialized, with_entity
from pydantic import SecretStr

from aidm.app.media import GeneratedImage, Illustrator, illustration_request, scene_key
from aidm.config import MediaConfig, ProviderConfig
from aidm.engines.core import Engine
from aidm.kernel.views import NarratorView
from aidm.state.entities import PLAYER_ID, Entity, EntityId
from aidm.state.model import Game
from aidm.world import actions
from aidm.world.topology import player_location

NARRATION = "The door groans open."
STYLE = MediaConfig().style
CLOISTER = EntityId("cloister")


def _illustrator(tmp_path: Path) -> Illustrator:
    return Illustrator(
        config=MediaConfig(enabled=True),
        provider=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test")),
        saves=tmp_path / "save.media",
        icon_dirs=(),
        style=STYLE,
    )


def _placed(state: Game, name: str, *, known: bool) -> Game:
    return with_entity(
        state,
        Entity(
            id=EntityId(name.lower().replace(" ", "-")),
            kind="item",
            name=name,
            brief=f"A {name.lower()}.",
            known=known,
            parent_id=player_location(state),
        ),
    )


def _scene(engine: Engine, state: Game) -> NarratorView:
    return engine.views(state).narrator


def test_illustration_request_names_the_scene_and_no_unrevealed_canon() -> None:
    engine, state = initialized()
    state = _placed(_placed(state, "Brass Lantern", known=True), "Pale Watcher", known=False)
    request = illustration_request(_scene(engine, state), NARRATION, STYLE)
    assert state.world.require(player_location(state)).name in request
    assert "Brass Lantern" in request
    assert NARRATION in request
    assert "Pale Watcher" not in request


def test_scene_key_holds_through_a_change_of_cast_but_not_of_place() -> None:
    engine, state = initialized()
    key = scene_key(_scene(engine, state))
    assert scene_key(_scene(engine, _placed(state, "Pale Watcher", known=False))) == key
    assert scene_key(_scene(engine, _placed(state, "Brass Lantern", known=True))) == key
    draft = state.draft()
    _ = actions.move(draft, PLAYER_ID, CLOISTER)
    assert scene_key(_scene(engine, draft.committed())) != key


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
    illustrator = Illustrator(
        config=MediaConfig(enabled=True),
        provider=ProviderConfig(base_url="https://example.invalid/v1", api_key=SecretStr("test")),
        saves=saves_dir,
        icon_dirs=(scenario_dir, character_dir),
        style=STYLE,
    )
    assert illustrator.icon(EntityId("mara")) == scenario_dir / "mara.png"
    assert illustrator.icon(EntityId("player")) == character_dir / "player.png"
    assert illustrator.icon(EntityId("invented")) == saves_dir / "icons" / "invented.png"
    assert illustrator.icon(EntityId("nobody")) is None


async def test_concurrent_illustrations_of_one_scene_generate_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, state = initialized()
    views = engine.views(state)
    prompts: list[str] = []

    async def _generate(
        _self: Illustrator, prompt: str, _ratio: str, _references: Sequence[Path] = ()
    ) -> GeneratedImage | None:
        prompts.append(prompt)
        await sleep(0)  # a real generation suspends; without this nothing can interleave
        return GeneratedImage(data=b"\x89PNG", suffix=".png")

    monkeypatch.setattr(Illustrator, "_generate", _generate)
    illustrator = _illustrator(tmp_path)
    _ = await gather(
        illustrator.illustrate(views, NARRATION),
        illustrator.illustrate(views, NARRATION),
    )
    scene_prompts = [prompt for prompt in prompts if prompt.startswith("Draw one wide")]
    assert len(scene_prompts) == 1
    # Every other prompt is an icon: a repeat is a second bill for the same picture.
    assert len(prompts) == len(set(prompts))
    assert illustrator.generating == set()
