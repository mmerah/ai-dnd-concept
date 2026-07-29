import os

import pytest

os.environ.setdefault(  # agents are built, never called, in tests
    "PROVIDERS__OPENROUTER__API_KEY", "test"
)

from aidm.domain.models.base import PLAYER_ID, EntityId  # noqa: E402
from aidm.domain.models.entities import ActorEntity, ItemEntity, LocationEntity  # noqa: E402
from aidm.domain.models.state import GameState, ScenarioMeta, WorldState  # noqa: E402
from aidm.domain.models.stats import StatBlock  # noqa: E402
from aidm.utils.models import Attributes  # noqa: E402


@pytest.fixture
def state() -> GameState:
    return GameState(
        scenario=ScenarioMeta(title="Test", premise="A test."),
        world=WorldState(
            entities={
                e.id: e
                for e in [
                    LocationEntity(
                        id=EntityId("study"), name="the study", brief="A room.", known=True
                    ),
                    LocationEntity(id=EntityId("vault"), name="the vault", brief="A crypt."),
                    ActorEntity(
                        id=PLAYER_ID,
                        name="Kael",
                        brief="A relic-hunter.",
                        known=True,
                        location_id=EntityId("study"),
                        stats=StatBlock(attributes=Attributes(wisdom=14), max_hp=10, hp=10),
                    ),
                    ActorEntity(
                        id=EntityId("mara"),
                        name="Mara",
                        brief="A scribe.",
                        known=True,
                        location_id=EntityId("study"),
                    ),
                    ActorEntity(
                        id=EntityId("elena"),
                        name="Elena",
                        brief="An archivist.",
                        location_id=EntityId("study"),
                    ),
                    ItemEntity(
                        id=EntityId("vault_map"),
                        name="the vault map",
                        brief="A chart.",
                        container_id=EntityId("study"),
                    ),
                    ItemEntity(
                        id=EntityId("lantern"),
                        name="a lantern",
                        brief="A tin lantern.",
                        known=True,
                        container_id=PLAYER_ID,
                    ),
                ]
            }
        ),
    )
