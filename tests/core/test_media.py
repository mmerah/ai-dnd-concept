from pathlib import Path

from core_test_support import initialized, with_entity
from pydantic import SecretStr

from aidm.app.media import Illustrator, illustration_request, scene_key
from aidm.app.views import player_scene
from aidm.config import MediaConfig, ProviderConfig
from aidm.state.base import Entity, EntityId
from aidm.state.world import Game

NARRATION = "The door groans open."


def _placed(state: Game, name: str, *, known: bool) -> Game:
    return with_entity(
        state,
        Entity(
            id=EntityId(name.lower().replace(" ", "_")),
            kind="item",
            name=name,
            brief=f"A {name.lower()}.",
            known=known,
            parent_id=state.player_location,
        ),
    )


def test_illustration_request_names_the_scene_and_no_unrevealed_canon() -> None:
    _, state = initialized()
    state = _placed(_placed(state, "Brass Lantern", known=True), "Pale Watcher", known=False)
    request = illustration_request(player_scene(state), NARRATION)
    assert state.world.require(state.player_location).name in request
    assert "Brass Lantern" in request
    assert NARRATION in request
    assert "Pale Watcher" not in request


def test_scene_key_moves_only_when_the_revealed_cast_does() -> None:
    _, state = initialized()
    key = scene_key(player_scene(state))
    assert scene_key(player_scene(_placed(state, "Pale Watcher", known=False))) == key
    assert scene_key(player_scene(_placed(state, "Brass Lantern", known=True))) != key


def test_an_icon_is_looked_up_in_the_directory_its_entity_belongs_to(tmp_path: Path) -> None:
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
        icon_dirs={EntityId("mara"): scenario_dir, EntityId("player"): character_dir},
    )
    assert illustrator.icon(EntityId("mara")) == scenario_dir / "mara.png"
    assert illustrator.icon(EntityId("player")) == character_dir / "player.png"
    assert illustrator.icon(EntityId("invented")) == saves_dir / "icons" / "invented.png"
    assert illustrator.icon(EntityId("nobody")) is None
