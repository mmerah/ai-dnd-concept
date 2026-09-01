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
    Scene,
    SceneRun,
    Survivor,
)
from aidm.engines.core import PLAYER_ID

MIRA = EntityId("mira")
DAX = EntityId("dax")
WRENCH = EntityId("wrench")
SITUATION = (
    "Booths lie overturned and glass covers the floor of the diner, the front door barred "
    "shut against the mob still pounding just outside in the street."
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
