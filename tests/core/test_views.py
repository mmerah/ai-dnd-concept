from core_test_support import LONER3E

from aidm.state.entities import PLAYER_ID, Entity, EntityId, Exit, Kind
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState
from aidm.turn.context import player_scene


def _entity(entity_id: str, kind: Kind, name: str, brief: str, **fields: object) -> Entity:
    return Entity.model_validate(
        {"id": entity_id, "kind": kind, "name": name, "brief": brief} | fields
    )


def state() -> Game:
    entities = (
        _entity(
            "study",
            "location",
            "Study",
            "A small room.",
            known=True,
            exits=[Exit(to=EntityId("crypt"))],
        ),
        _entity("player", "actor", "Kael", "A hunter.", known=True, parent_id="study"),
        _entity("mara", "actor", "Mara", "A known scribe.", known=True, parent_id="study"),
        _entity("hidden-actor", "actor", "The Secret", "Unrevealed canon.", parent_id="study"),
        _entity("crypt", "location", "Crypt", "A sealed vault.", known=False),
    )
    threads = (
        Thread(
            id="the-vault",
            title="The Vault",
            note="Director steering text",
        ),
    )
    held = Game(
        scenario_id="whispering-vault",
        character_id="kael",
        scenario=ScenarioMeta(title="Test", premise="Test"),
        engine=LONER3E,
        packs=("srd",),
        player_id=PLAYER_ID,
        world=WorldState(
            entities={entity.id: entity for entity in entities},
            threads={thread.id: thread for thread in threads},
        ),
        turn_facts=(),
    )
    return held.committed()


def test_the_player_scene_holds_no_unrevealed_entity_or_unknown_exit() -> None:
    scene = player_scene(state())

    assert "The Secret" not in str(scene.model_dump())
    assert "crypt" not in {exit.to for exit in scene.exits}
    assert EntityId("mara") in {entity.id for entity in scene.here}
