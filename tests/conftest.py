import os

import pytest

os.environ.setdefault(  # agents are built, never called, in tests
    "PROVIDERS__OPENROUTER__API_KEY", "test"
)

from aidm.domain.models import (  # noqa: E402
    Attributes,
    Character,
    Entity,
    EntityId,
    GameState,
    ScenarioMeta,
    WorldState,
)


@pytest.fixture
def state() -> GameState:
    return GameState(
        character=Character(
            name="Kael",
            attributes=Attributes(wisdom=14),
            inventory=["a lantern"],
            location_id=EntityId("study"),
        ),
        scenario=ScenarioMeta(title="Test", premise="A test."),
        world=WorldState(
            entities={
                e.id: e
                for e in [
                    Entity(
                        id=EntityId("study"),
                        kind="location",
                        name="the study",
                        brief="A room.",
                        known=True,
                    ),
                    Entity(
                        id=EntityId("vault"), kind="location", name="the vault", brief="A crypt."
                    ),
                    Entity(
                        id=EntityId("mara"), kind="npc", name="Mara", brief="A scribe.", known=True
                    ),
                    Entity(id=EntityId("elena"), kind="npc", name="Elena", brief="An archivist."),
                    Entity(
                        id=EntityId("vault_map"),
                        kind="item",
                        name="the vault map",
                        brief="A chart.",
                    ),
                ]
            }
        ),
    )
