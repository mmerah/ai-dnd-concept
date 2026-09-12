from collections.abc import Sequence

from aidm.core.entities import EngineId, Slug
from aidm.core.model import PackSelection, ScenarioMeta
from aidm.core.play import Chapter
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.breathless.world import (
    BreathlessGame,
    BreathlessWorld,
    Die,
    Skill,
    Supply,
    Survivor,
    SurvivorSheet,
)
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.world import SceneRun
from support.table import BREATHLESS, ENGINES_BUILT, narrowed

MIRA: Slug = "mira"
DAX: Slug = "dax"
WRENCH: Slug = "wrench"
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
ENGINE = narrowed(ENGINES_BUILT[BREATHLESS], BreathlessEngine)


def small_world() -> BreathlessGame:
    mira = Survivor(id=MIRA, name="Mira", brief="A neighbor", known=True)
    dax = Survivor(id=DAX, name="Dax", brief="A looter", known=False)
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
        packs=PackSelection(ids=(SRD_PACK,)),
        log=[Chapter(title="The Diner", focus="Can they reach the back door?")],
        payload=world,
    )


def hired(world: BreathlessWorld, member_id: Slug) -> Survivor:
    member = world.cast[member_id]
    member.sheet = SurvivorSheet(skills=dict(SKILLS_RATED), worn=dict(SKILLS_RATED))
    if member_id not in world.party:
        world.join_party(member_id)
    return member


def _scene(*, here: Sequence[Slug] = ()) -> SceneRun:
    return SceneRun(
        place="diner",
        title="The Diner",
        focus="Can they reach the back door?",
        situation=SITUATION,
        here=list(here),
    )


def _player() -> Survivor:
    return Survivor(
        id=PLAYER_ID,
        name="Jax",
        brief="A wiry mechanic",
        known=True,
        sheet=SurvivorSheet(
            skills=SKILLS_RATED,
            worn=dict(SKILLS_RATED),
            items={WRENCH: Supply(name="Wrench", die=10)},
        ),
    )
