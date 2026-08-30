from core_test_support import initialized, with_entity

from aidm.engines.loner3e.state import ActorSheet, LonerSheet
from aidm.kits.scenes.state import Entity
from aidm.state.entities import EntityId

SECRET = Entity[LonerSheet](
    id=EntityId("hidden-actor"),
    kind="actor",
    name="The Secret",
    brief="Unrevealed canon.",
    sheet=ActorSheet(concept="A Watcher"),
)


def test_the_narrator_view_names_nobody_in_the_scene_the_player_has_not_met() -> None:
    engine, state = initialized()

    shown = str(engine.views(with_entity(state, SECRET)).narrator.model_dump())

    assert "The Secret" not in shown
    # The vault map is hidden here, and Mara is standing in the room.
    assert "vault map" not in shown
    assert "Mara" in shown
