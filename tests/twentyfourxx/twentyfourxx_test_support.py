from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.core import PLAYER_ID
from aidm.engines.scenes import Scene, SceneRun
from aidm.engines.twentyfourxx.world import (
    Item,
    Npc,
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


def small_world() -> TwentyfourxxGame:
    """One operator, one known NPC present, one hidden NPC, lockpicks in the kit."""
    kestrel = Npc(id=KESTREL, name="Kestrel", brief="A dockhand", known=True)
    sable = Npc(id=SABLE, name="Sable", brief="A rival operator", known=False)
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


def _scene() -> Scene:
    return Scene(
        place="loading-bay",
        title="The Loading Bay",
        question="Can they reach the cargo before the lights come back?",
        situation=SITUATION,
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
