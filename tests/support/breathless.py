from collections.abc import Sequence

from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import (
    BreathlessGame,
    BreathlessWorld,
    Die,
    Item,
    Skill,
    Survivor,
)
from aidm.engines.scenes.world import SceneRun

MIRA = EntityId("mira")
DAX = EntityId("dax")
WRENCH = EntityId("wrench")
SKILLS_RATED: dict[Skill, Die] = {
    "bash": 6,
    "dash": 4,
    "sneak": 8,
    "shoot": 4,
    "think": 10,
    "sway": 4,
}
SITUATION = (
    "Booths lie overturned and glass covers the floor of the diner, the front door barred "
    "shut against the mob still pounding just outside in the street."
)


def small_world() -> BreathlessGame:
    mira = Person(id=MIRA, name="Mira", brief="A neighbor", known=True)
    dax = Person(id=DAX, name="Dax", brief="A looter", known=False)
    world = BreathlessWorld(
        cast={MIRA: mira, DAX: dax},
        player=_player(),
        runs=[_scene(here=[MIRA, DAX])],
    )
    return BreathlessGame(
        scenario_id="diner",
        character_id="jax",
        scenario=ScenarioMeta(
            title="Diner", premise="A quiet diner, disturbed.", scope="One quiet night in."
        ),
        engine=EngineId("breathless"),
        payload=world,
    )


def _scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place="diner",
        title="The Diner",
        question="Can they reach the back door?",
        situation=SITUATION,
        here=list(here),
    )


def _player() -> Survivor:
    return Survivor(
        id=PLAYER_ID,
        name="Jax",
        brief="A wiry mechanic",
        known=True,
        skills=SKILLS_RATED,
        worn=dict(SKILLS_RATED),
        items={WRENCH: Item(name="Wrench", die=10)},
    )
