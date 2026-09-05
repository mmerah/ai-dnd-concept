import pytest

from aidm.core.entities import EntityId
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import (
    SKILLS,
    BreathlessWorld,
    Die,
    Skill,
    Survivor,
    stepped,
)
from aidm.engines.scenes.world import SceneRun

MIRA = EntityId("mira")


def _scene(*, here: list[EntityId] | None = None) -> SceneRun:
    return SceneRun(
        place="diner",
        title="The Diner",
        focus="Can they reach the back door?",
        situation="Booths overturned, glass everywhere, the front door barred shut.",
        here=here or [],
    )


def _player() -> Survivor:
    rated: dict[Skill, Die] = {**dict.fromkeys(SKILLS, 4), "bash": 10, "dash": 8, "sneak": 6}
    return Survivor(
        id=PLAYER_ID, name="Jax", brief="A wiry mechanic", known=True, skills=rated, worn=rated
    )


def _world() -> BreathlessWorld:
    return BreathlessWorld(cast={}, player=_player(), runs=[_scene()])


def test_a_sheet_short_of_the_six_skills_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 6"):
        _ = Survivor(
            id=PLAYER_ID,
            name="Jax",
            brief="A wiry mechanic",
            known=True,
            skills={"bash": 10, "dash": 8, "sneak": 6},
            worn=dict.fromkeys(SKILLS, 4),
        )


def test_a_sheet_rated_off_the_creation_spread_is_refused() -> None:
    with pytest.raises(ValueError, match="three d4"):
        _ = Survivor(
            id=PLAYER_ID,
            name="Jax",
            brief="A wiry mechanic",
            known=True,
            skills=dict.fromkeys(SKILLS, 12),
            worn=dict.fromkeys(SKILLS, 12),
        )


def test_stepped_floors_at_d4() -> None:
    assert stepped(4) == 4
    assert stepped(12) == 10


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
