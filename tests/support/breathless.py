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
from aidm.engines.hub import Attempt, Campaign, Job, Offer
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


def small_world() -> BreathlessGame:
    """One player, one known NPC present, one hidden NPC, a Wrench in the backpack."""
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
    """A campaign world: a hub run with a known keeper, then one job run away from it."""
    keeper = Person(id=KEEPER, name="Keeper", brief="Runs the camp", known=True)
    hub_run = _hub_scene(here=[KEEPER])
    job_run = _job_scene()
    world = BreathlessWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=[hub_run, job_run],
        campaign=Campaign(
            place=HUB_PLACE,
            board=(
                Offer(title="Job One", pitch="I take job one."),
                Offer(title="Job Two", pitch="I take job two."),
            ),
            jobs=[
                Job(
                    title="The Pharmacy Run",
                    place=JOB_PLACE,
                    terms=JOB,
                    attempts=[Attempt(started=1)],
                )
            ],
        ),
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


def _hub_scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place=HUB_PLACE,
        title="The Camp",
        question="What keeps the group coming back to the camp?",
        situation=HUB_SITUATION,
        here=list(here),
    )


def _job_scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place=JOB_PLACE,
        title="The Pharmacy Run",
        question="Can Jax clear the pharmacy before the Crawlers notice?",
        situation=JOB_SITUATION,
        here=list(here),
    )
