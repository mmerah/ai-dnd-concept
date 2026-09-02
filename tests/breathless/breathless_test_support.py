import pytest

from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.core.model import ScenarioMeta
from aidm.engines.breathless.tools import ChangeWorld, apply_change
from aidm.engines.breathless.world import (
    BreathlessGame,
    BreathlessState,
    BreathlessWorld,
    Item,
    Npc,
    Survivor,
)
from aidm.engines.core import PLAYER_ID
from aidm.engines.hub import Offer
from aidm.engines.scenes import Scene, SceneRun

MIRA = EntityId("mira")
DAX = EntityId("dax")
WRENCH = EntityId("wrench")
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
    mira = Npc(id=MIRA, name="Mira", brief="A neighbor", known=True)
    dax = Npc(id=DAX, name="Dax", brief="A looter", known=False)
    world = BreathlessWorld(
        cast={MIRA: mira, DAX: dax},
        player=_player(),
        runs=[SceneRun(scene=_scene(), present=[MIRA], hidden=[DAX])],
    )
    return BreathlessGame(
        scenario_id="diner",
        character_id="jax",
        scenario=ScenarioMeta(title="Diner", premise="A quiet diner, disturbed."),
        engine=EngineId("breathless"),
        payload=BreathlessState(world=world),
    )


def hub_world() -> BreathlessGame:
    """A campaign world: a hub run with a known keeper, then one job run away from it."""
    keeper = Npc(id=KEEPER, name="Keeper", brief="Runs the camp", known=True)
    hub_run = SceneRun(scene=_hub_scene(), present=[KEEPER])
    job_run = SceneRun(scene=_job_scene())
    world = BreathlessWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=[hub_run, job_run],
        hub=HUB_PLACE,
        board=(
            Offer(title="Job One", pitch="I take job one."),
            Offer(title="Job Two", pitch="I take job two."),
        ),
    )
    return BreathlessGame(
        scenario_id="the-camp",
        character_id="jax",
        scenario=ScenarioMeta(title="The Camp", premise="A hub campaign.", kind="campaign"),
        engine=EngineId("breathless"),
        payload=BreathlessState(world=world),
    )


def changed_facts(draft: BreathlessGame, verb: str, **fields: object) -> list[Fact]:
    change = ChangeWorld.model_validate({"change": {"verb": verb, **fields}})
    return apply_change(draft.payload.world, change.change)


def changed(draft: BreathlessGame, verb: str, **fields: object) -> list[str]:
    return [fact.trace for fact in changed_facts(draft, verb, **fields)]


def refused(draft: BreathlessGame, verb: str, **fields: object) -> str:
    with pytest.raises(ValueError) as raised:
        _ = changed(draft, verb, **fields)
    return str(raised.value)


def _scene() -> Scene:
    return Scene(
        place="diner",
        title="The Diner",
        question="Can they reach the back door?",
        situation=SITUATION,
    )


def _player() -> Survivor:
    return Survivor(
        id=PLAYER_ID,
        name="Jax",
        brief="A wiry mechanic",
        known=True,
        skills={"think": 10, "sneak": 8, "bash": 6},
        items={WRENCH: Item(name="Wrench", die=10)},
    )


def _hub_scene() -> Scene:
    return Scene(
        place=HUB_PLACE,
        title="The Camp",
        question="What keeps the group coming back to the camp?",
        situation=HUB_SITUATION,
    )


def _job_scene() -> Scene:
    return Scene(
        place=JOB_PLACE,
        title="The Pharmacy Run",
        question="Can Jax clear the pharmacy before the Crawlers notice?",
        situation=JOB_SITUATION,
        job=JOB,
    )
