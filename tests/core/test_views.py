from core_test_support import initialized, with_entity

from aidm.core.entities import PLAYER_ID, EntityId
from aidm.engines.loner3e.state import ActorSheet, LonerSheet
from aidm.kits.entities import Entity

SECRET = Entity[LonerSheet](
    id=EntityId("hidden-actor"),
    kind="actor",
    name="The Secret",
    brief="Unrevealed canon.",
    sheet=ActorSheet(concept="A Watcher"),
)


def test_the_narrator_view_names_nobody_in_the_scene_the_player_has_not_met() -> None:
    engine, state = initialized()

    shown = str(engine.narrator_view(with_entity(state, SECRET)).model_dump())

    assert "The Secret" not in shown
    # The vault map is hidden here, and Mara is standing in the room.
    assert "vault map" not in shown
    assert "Mara" in shown


def test_the_player_view_panels_carry_icon_ids_for_who_is_here() -> None:
    engine, state = initialized()

    view = engine.player_view(with_entity(state, SECRET))

    assert tuple(panel.title for panel in view.panels) == (
        "This scene",
        "Here",
        "Traits",
        "Carrying",
        "Threads",
        "Trail",
    )
    here = next(panel for panel in view.panels if panel.title == "Here")
    icon_ids = {row.icon_id for row in here.rows}
    assert PLAYER_ID in icon_ids
    assert EntityId("mara") in icon_ids
    assert all(row.label != "The Secret" for panel in view.panels for row in panel.rows)
