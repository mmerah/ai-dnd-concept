import pytest

from aidm.core.entities import EngineId, EntityId
from aidm.core.play import Exchange
from aidm.engines.breathless.world import (
    SKILLS,
    STARTING_ITEM,
    BreathlessCharacter,
    BreathlessCharacterFile,
    BreathlessWorld,
    Item,
    Npc,
    Survivor,
    player_survivor,
    stepped,
)
from aidm.engines.core import PLAYER_ID
from aidm.engines.scenes import SCENE_TURN_CAP, Scene, SceneRun, scene_spent

MIRA = EntityId("mira")


def _scene() -> Scene:
    return Scene(
        place="diner",
        title="The Diner",
        question="Can they reach the back door?",
        situation="Booths overturned, glass everywhere, the front door barred shut.",
    )


def _player() -> Survivor:
    return Survivor(id=PLAYER_ID, name="Jax", brief="A wiry mechanic", known=True)


def _world() -> BreathlessWorld:
    return BreathlessWorld(cast={}, player=_player(), runs=[SceneRun(scene=_scene())])


def test_missing_skills_fill_with_d4_and_worn_mirrors_skills() -> None:
    survivor = _player()
    assert survivor.skills == dict.fromkeys(SKILLS, 4)
    assert survivor.worn == dict.fromkeys(SKILLS, 4)


def test_worn_missing_only_fills_from_skills() -> None:
    survivor = Survivor(
        id=PLAYER_ID,
        name="Jax",
        brief="A wiry mechanic",
        known=True,
        skills={"bash": 10, "dash": 8, "sneak": 6},
        worn={"bash": 6},
    )
    assert survivor.worn["bash"] == 6
    assert survivor.worn["dash"] == 8
    assert survivor.worn["shoot"] == 4


def test_stepped_floors_at_d4() -> None:
    assert stepped(4) == 4
    assert stepped(12) == 10


def test_two_d10_skills_are_refused() -> None:
    with pytest.raises(ValueError, match="one d10, one d8, one d6"):
        BreathlessCharacter(
            pronouns="they",
            job="Mechanic",
            skills={"bash": 10, "dash": 10, "sneak": 6},
            item="Wrench",
        )


def test_player_id_in_present_is_refused() -> None:
    decoy = Npc(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    with pytest.raises(ValueError, match="never listed"):
        BreathlessWorld(
            cast={PLAYER_ID: decoy},
            player=_player(),
            runs=[SceneRun(scene=_scene(), present=[PLAYER_ID])],
        )


def test_require_returns_the_player_for_player_id() -> None:
    world = _world()
    assert world.require(PLAYER_ID) is world.player


def test_here_yields_the_player_first_then_present_cast() -> None:
    mira = Npc(id=MIRA, name="Mira", brief="A neighbor", known=True)
    world = BreathlessWorld(
        cast={MIRA: mira},
        player=_player(),
        runs=[SceneRun(scene=_scene(), present=[MIRA])],
    )
    assert list(world.here()) == [world.player, mira]


def test_scene_spent_reports_its_own_spent_reason() -> None:
    run = SceneRun(scene=_scene(), spent="the door is barred")
    assert scene_spent(run, someone_dead=False) == "the door is barred"


def test_scene_spent_reports_someone_dead() -> None:
    run = SceneRun(scene=_scene())
    assert scene_spent(run, someone_dead=True) == "someone here is dead"


def test_scene_spent_reports_the_turn_cap() -> None:
    exchange = Exchange(prompt="p", lines=())
    run = SceneRun(scene=_scene(), exchanges=[exchange] * SCENE_TURN_CAP)
    assert scene_spent(run, someone_dead=False) == f"{SCENE_TURN_CAP} turns have passed here"


def test_player_survivor_files_the_item_under_its_slug_at_d10() -> None:
    character = BreathlessCharacterFile(
        id="jax",
        engine=EngineId("breathless"),
        name="Jax",
        brief="A wiry mechanic",
        payload=BreathlessCharacter(
            pronouns="they",
            job="Mechanic",
            skills={"bash": 10, "dash": 8, "sneak": 6},
            item="Tire Iron",
        ),
    )
    survivor = player_survivor(character)
    assert survivor.items[EntityId("tire-iron")] == Item(name="Tire Iron", die=STARTING_ITEM)
