import pytest

from aidm.core.entities import EngineId, EntityId
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import (
    SKILLS,
    STARTING_ITEM,
    BreathlessCharacterFile,
    BreathlessPayload,
    BreathlessWorld,
    Item,
    Survivor,
    player_survivor,
    stepped,
)
from aidm.engines.scenes.world import SceneRun

MIRA = EntityId("mira")


def _scene(*, here: list[EntityId] | None = None) -> SceneRun:
    return SceneRun(
        place="diner",
        title="The Diner",
        question="Can they reach the back door?",
        situation="Booths overturned, glass everywhere, the front door barred shut.",
        here=here or [],
    )


def _player() -> Survivor:
    return Survivor(id=PLAYER_ID, name="Jax", brief="A wiry mechanic", known=True)


def _world() -> BreathlessWorld:
    return BreathlessWorld(cast={}, player=_player(), runs=[_scene()])


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
        BreathlessPayload(
            pronouns="they",
            job="Mechanic",
            skills={"bash": 10, "dash": 10, "sneak": 6},
            item="Wrench",
        )


def test_a_cast_that_holds_the_player_is_refused() -> None:
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    with pytest.raises(ValueError, match="the player is in the cast"):
        BreathlessWorld(
            cast={PLAYER_ID: decoy},
            player=_player(),
            runs=[_scene(here=[PLAYER_ID])],
        )


def test_require_returns_the_player_for_player_id() -> None:
    world = _world()
    assert world.require(PLAYER_ID) is world.player


def test_here_yields_the_player_first_then_present_cast() -> None:
    mira = Person(id=MIRA, name="Mira", brief="A neighbor", known=True)
    world = BreathlessWorld(
        cast={MIRA: mira},
        player=_player(),
        runs=[_scene(here=[MIRA])],
    )
    assert list(world.here()) == [world.player, mira]


def test_player_survivor_files_the_item_under_its_slug_at_d10() -> None:
    character = BreathlessCharacterFile(
        id="jax",
        engine=EngineId("breathless"),
        name="Jax",
        brief="A wiry mechanic",
        payload=BreathlessPayload(
            pronouns="they",
            job="Mechanic",
            skills={"bash": 10, "dash": 8, "sneak": 6},
            item="Tire Iron",
        ),
    )
    survivor = player_survivor(character)
    assert survivor.items[EntityId("tire-iron")] == Item(name="Tire Iron", die=STARTING_ITEM)
