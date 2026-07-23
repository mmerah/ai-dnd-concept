import os

import pytest

os.environ.setdefault("AI_API_KEY", "test")  # agents are built, never called, in tests

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
            location="the study",
        ),
        scenario=ScenarioMeta(title="Test", premise="A test."),
        world=WorldState(
            entities=[
                Entity(id=EntityId("mara"), kind="npc", name="Mara", brief="A scribe.", known=True),
                Entity(id=EntityId("elena"), kind="npc", name="Elena", brief="An archivist."),
                Entity(
                    id=EntityId("vault_map"), kind="item", name="the vault map", brief="A chart."
                ),
            ]
        ),
    )
