from collections.abc import Sequence

from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.scenes.world import SceneRun
from aidm.engines.twentyfourxx.world import (
    Item,
    Operator,
    TwentyfourxxGame,
    TwentyfourxxWorld,
)

KESTREL = EntityId("kestrel")
SABLE = EntityId("sable")
LOCKPICKS = EntityId("lockpicks")
SITUATION = (
    "Cargo containers stack three high across the loading bay, and the station's night crew "
    "has just killed the lights for a scheduled power-saving cycle."
)


def small_world() -> TwentyfourxxGame:
    kestrel = Person(id=KESTREL, name="Kestrel", brief="A dockhand", known=True)
    sable = Person(id=SABLE, name="Sable", brief="A rival operator", known=False)
    world = TwentyfourxxWorld(
        cast={KESTREL: kestrel, SABLE: sable},
        player=_player(),
        runs=[_scene(here=[KESTREL, SABLE])],
    )
    return TwentyfourxxGame(
        scenario_id="loading-bay",
        character_id="rook",
        scenario=ScenarioMeta(
            title="Loading Bay", premise="A cargo job gone quiet.", scope="One tense night shift."
        ),
        engine=EngineId("twentyfourxx"),
        payload=world,
    )


def _scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place="loading-bay",
        title="The Loading Bay",
        focus="Can they reach the cargo before the lights come back?",
        situation=SITUATION,
        here=list(here),
    )


def _player() -> Operator:
    return Operator(
        id=PLAYER_ID,
        name="Rook",
        brief="A quiet operator",
        known=True,
        specialty="Sneak",
        origin="Human",
        skills={"Stealth": 10},
        items={LOCKPICKS: Item(name="Lockpick set")},
    )
