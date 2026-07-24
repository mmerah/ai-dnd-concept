import os

import pytest

os.environ.setdefault(  # agents are built, never called, in tests
    "PROVIDERS__OPENROUTER__API_KEY", "test"
)

from aidm.domain.models import (  # noqa: E402
    Attributes,
    Character,
    EntityId,
    GameState,
    ItemEntity,
    LocationEntity,
    NpcEntity,
    ScenarioMeta,
    WorldState,
)


@pytest.fixture
def state() -> GameState:
    return GameState(
        character=Character(
            name="Kael",
            attributes=Attributes(wisdom=14),
            max_hp=10,
            hp=10,
            location_id=EntityId("study"),
            inventory=[EntityId("lantern")],  # held: lantern's location_id is None
        ),
        scenario=ScenarioMeta(title="Test", premise="A test."),
        world=WorldState(
            entities={
                e.id: e
                for e in [
                    LocationEntity(
                        id=EntityId("study"), name="the study", brief="A room.", known=True
                    ),
                    LocationEntity(id=EntityId("vault"), name="the vault", brief="A crypt."),
                    NpcEntity(
                        id=EntityId("mara"),
                        name="Mara",
                        brief="A scribe.",
                        known=True,
                        location_id=EntityId("study"),
                    ),
                    NpcEntity(
                        id=EntityId("elena"),
                        name="Elena",
                        brief="An archivist.",
                        location_id=EntityId("study"),
                    ),
                    ItemEntity(
                        id=EntityId("vault_map"),
                        name="the vault map",
                        brief="A chart.",
                        location_id=EntityId("study"),  # lying in the study, hidden
                    ),
                    ItemEntity(
                        id=EntityId("lantern"), name="a lantern", brief="A tin lantern.", known=True
                    ),
                ]
            }
        ),
    )
