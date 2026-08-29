from core_test_support import ENGINES_BUILT, LONER3E

from aidm.state.entities import PLAYER_ID, Entity, EntityId, Exit, Kind
from aidm.state.model import Game, ScenarioMeta, Thread, WorldState
from aidm.state.scene import VisibleScene


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
    engine = ENGINES_BUILT[LONER3E]
    held = state()

    scene = VisibleScene.revealed_from(engine.scene(held), held.world)

    shown = str(scene.model_dump())
    assert "The Secret" not in shown
    assert "crypt" not in shown
    assert "Mara" in shown
