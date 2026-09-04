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
from support.scenes import HubNames, hub_campaign, hub_runs

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
KEEPER = EntityId("keeper")
HUB_PLACE = "the-camp"
JOB_PLACE = "the-pharmacy"
HUB_SITUATION = (
    "The camp is quiet before the evening watch, and the supply board is chalked up by the gate."
)
JOB_SITUATION = (
    "The pharmacy shelves are half-looted already, and something shuffles behind the counter "
    "in the dark."
)
JOB = (
    "Mira's group is nearly out of medicine and Keeper wants the pharmacy's shelves cleared "
    "before the Crawlers wake; whoever goes brings back what they can carry."
)
NAMES = HubNames(
    hub_place=HUB_PLACE,
    hub_title="The Camp",
    hub_question="What keeps the group coming back to the camp?",
    hub_situation=HUB_SITUATION,
    job_place=JOB_PLACE,
    job_title="The Pharmacy Run",
    job_question="Can Jax clear the pharmacy before the Crawlers notice?",
    job_situation=JOB_SITUATION,
    terms=JOB,
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
        scenario=ScenarioMeta(title="Diner", premise="A quiet diner, disturbed."),
        engine=EngineId("breathless"),
        payload=world,
    )


def hub_world() -> BreathlessGame:
    keeper = Person(id=KEEPER, name="Keeper", brief="Runs the camp", known=True)
    world = BreathlessWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=hub_runs(NAMES, keeper=KEEPER),
        campaign=hub_campaign(NAMES),
    )
    return BreathlessGame(
        scenario_id="the-camp",
        character_id="jax",
        scenario=ScenarioMeta(title="The Camp", premise="A hub campaign.", kind="campaign"),
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
