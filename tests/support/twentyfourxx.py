from collections.abc import Sequence

from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.world import SceneRun
from aidm.engines.twentyfourxx.world import (
    Crewmate,
    Item,
    Sheet,
    SkillDie,
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
    kestrel = Crewmate(id=KESTREL, name="Kestrel", brief="A dockhand", known=True)
    sable = Crewmate(id=SABLE, name="Sable", brief="A rival operator", known=False)
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


def hired(
    state: TwentyfourxxGame, entity_id: EntityId, *, skills: dict[str, SkillDie]
) -> TwentyfourxxGame:
    """Give a cast member a sheet and put them in the party, for tests that need a hired hand."""
    draft = state.draft()
    draft.payload.cast[entity_id].sheet = Sheet(specialty="Muscle", skills=skills)
    draft.payload.party.append(entity_id)
    return draft.commit()


def _scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place="loading-bay",
        title="The Loading Bay",
        focus="Can they reach the cargo before the lights come back?",
        situation=SITUATION,
        here=list(here),
    )


def _player() -> Crewmate:
    return Crewmate(
        id=PLAYER_ID,
        name="Rook",
        brief="A quiet operator",
        known=True,
        sheet=Sheet(
            specialty="Sneak",
            origin="Human",
            skills={"Stealth": 10},
            items={LOCKPICKS: Item(name="Lockpick set")},
        ),
    )
