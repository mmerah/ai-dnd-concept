from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import Offer
from aidm.engines.scenes.world import Scene, SceneRun
from aidm.engines.twentyfourxx.world import (
    Item,
    Operator,
    TwentyfourxxGame,
    TwentyfourxxState,
    TwentyfourxxWorld,
)

KESTREL = EntityId("kestrel")
SABLE = EntityId("sable")
LOCKPICKS = EntityId("lockpicks")
SITUATION = (
    "Cargo containers stack three high across the loading bay, and the station's night crew "
    "has just killed the lights for a scheduled power-saving cycle."
)
FIXER = EntityId("fixer")
HUB_PLACE = "amber-tap"
JOB_PLACE = "dock-run"
HUB_SITUATION = "The bar is quiet before the evening rush, and the fixer's board is up on the wall."
JOB_SITUATION = "The dockside warehouse is stacked with crates nobody has claimed in a week."
JOB = "Sable wants the crates counted and hauled clear before the shift change; she pays on drop."


def small_world() -> TwentyfourxxGame:
    """One operator, one known NPC present, one hidden NPC, lockpicks in the kit."""
    kestrel = Person(id=KESTREL, name="Kestrel", brief="A dockhand", known=True)
    sable = Person(id=SABLE, name="Sable", brief="A rival operator", known=False)
    world = TwentyfourxxWorld(
        cast={KESTREL: kestrel, SABLE: sable},
        player=_player(),
        runs=[SceneRun(scene=_scene(), present=[KESTREL], hidden=[SABLE])],
    )
    return TwentyfourxxGame(
        scenario_id="loading-bay",
        character_id="rook",
        scenario=ScenarioMeta(title="Loading Bay", premise="A cargo job gone quiet."),
        engine=EngineId("twentyfourxx"),
        payload=TwentyfourxxState(world=world),
    )


def hub_world() -> TwentyfourxxGame:
    """A campaign world: a hub run with a known fixer, then one job run away from it."""
    fixer = Person(id=FIXER, name="Fixer", brief="Runs the board", known=True)
    hub_run = SceneRun(scene=_hub_scene(), present=[FIXER])
    job_run = SceneRun(scene=_job_scene())
    world = TwentyfourxxWorld(
        cast={FIXER: fixer},
        player=_player(),
        runs=[hub_run, job_run],
        hub=HUB_PLACE,
        board=(
            Offer(title="Job One", pitch="I take job one."),
            Offer(title="Job Two", pitch="I take job two."),
        ),
    )
    return TwentyfourxxGame(
        scenario_id="amber-tap",
        character_id="rook",
        scenario=ScenarioMeta(title="The Amber Tap", premise="A hub campaign.", kind="campaign"),
        engine=EngineId("twentyfourxx"),
        payload=TwentyfourxxState(world=world),
    )


def _scene() -> Scene:
    return Scene(
        place="loading-bay",
        title="The Loading Bay",
        question="Can they reach the cargo before the lights come back?",
        situation=SITUATION,
    )


def _hub_scene() -> Scene:
    return Scene(
        place=HUB_PLACE,
        title="The Amber Tap",
        question="What job does Kael take off the board tonight?",
        situation=HUB_SITUATION,
    )


def _job_scene() -> Scene:
    return Scene(
        place=JOB_PLACE,
        title="The Dock Run",
        question="Can Kael clear the warehouse before the shift change?",
        situation=JOB_SITUATION,
        job=JOB,
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
