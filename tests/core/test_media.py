from core_test_support import initialized, with_entity

from aidm.app.media import illustration_request, scene_key, visible
from aidm.state.base import Entity, EntityId
from aidm.state.world import GameState

NARRATION = "The door groans open."


def _placed(state: GameState, name: str, *, known: bool) -> GameState:
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
    request = illustration_request(visible(state), NARRATION)
    assert state.world.require(state.player_location).name in request
    assert "Brass Lantern" in request
    assert NARRATION in request
    assert "Pale Watcher" not in request


def test_scene_key_moves_only_when_the_revealed_cast_does() -> None:
    _, state = initialized()
    key = scene_key(visible(state))
    assert scene_key(visible(_placed(state, "Pale Watcher", known=False))) == key
    assert scene_key(visible(_placed(state, "Brass Lantern", known=True))) != key
