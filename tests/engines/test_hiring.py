from collections.abc import Callable
from dataclasses import dataclass
from random import Random
from typing import cast

import pytest
from pydantic import JsonValue
from support.breathless import ENGINE as BREATHLESS_ENGINE
from support.breathless import MIRA as BREATHLESS_MIRA
from support.breathless import SKILLS_RATED
from support.breathless import hired as breathless_hired
from support.breathless import small_world as breathless_world
from support.table import narrowed, stub_worldsmith, updated
from support.tunnelgoons import ENGINE as TUNNELGOONS_ENGINE
from support.tunnelgoons import MIRA as TUNNELGOONS_MIRA
from support.tunnelgoons import small_world as tunnelgoons_world
from support.twentyfourxx import ENGINE as TWENTYFOURXX_ENGINE
from support.twentyfourxx import KESTREL
from support.twentyfourxx import hired as twentyfourxx_hired
from support.twentyfourxx import small_world as twentyfourxx_world

from aidm.core.entities import Refusal, Slug
from aidm.core.model import AnyGame, Generation
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.hiring import HIRE, SIGNED_ON
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.world import GoonSheet, TunnelGoonsGame
from aidm.engines.twentyfourxx.world import TwentyfourxxGame

TERMS = "Watch our backs"


@dataclass(frozen=True, slots=True)
class HireCase:
    engine: AnyEngine
    game: Callable[[], AnyGame]  # a fresh, unhired game
    member: Slug
    sheeted: Callable[[AnyGame], AnyGame]  # the game with `member` already carrying a sheet
    answer: dict[str, JsonValue]  # the worldsmith's sheet


def _breathless_sheeted(game: AnyGame) -> AnyGame:
    breathless_hired(narrowed(game, BreathlessGame).payload, BREATHLESS_MIRA)
    return game


def _twentyfourxx_sheeted(game: AnyGame) -> AnyGame:
    return twentyfourxx_hired(narrowed(game, TwentyfourxxGame), KESTREL, skills={"Intimidation": 8})


def _tunnelgoons_sheeted(game: AnyGame) -> AnyGame:
    tunnelgoons_game = narrowed(game, TunnelGoonsGame)
    tunnelgoons_game.payload.npcs[TUNNELGOONS_MIRA].sheet = GoonSheet(
        abilities={"brute": 1, "skulker": 1, "erudite": 1}
    )
    return game


# Breathless and 24XX read a pack off the game when hiring, so their cases carry one.
CASES = (
    HireCase(
        engine=BREATHLESS_ENGINE,
        game=lambda: updated(breathless_world(), packs=(SRD_PACK,)),
        member=BREATHLESS_MIRA,
        sheeted=_breathless_sheeted,
        answer={
            "pronouns": "he/him",
            "job": "Bell-ringer",
            "skills": cast(dict[str, JsonValue], SKILLS_RATED),
            "item": "Boat hook",
        },
    ),
    HireCase(
        engine=TWENTYFOURXX_ENGINE,
        game=lambda: updated(twentyfourxx_world(), packs=(SRD_PACK,)),
        member=KESTREL,
        sheeted=_twentyfourxx_sheeted,
        answer={"specialty": "Muscle", "skills": {"Intimidation": 8}, "items": ["Crowbar"]},
    ),
    HireCase(
        engine=TUNNELGOONS_ENGINE,
        game=tunnelgoons_world,
        member=TUNNELGOONS_MIRA,
        sheeted=_tunnelgoons_sheeted,
        answer={"abilities": {"brute": 2, "skulker": 1, "erudite": 0}},
    ),
)


def _case_id(case: HireCase) -> str:
    return case.engine.id


def _hire(case: HireCase, draft: AnyGame) -> None:
    args: dict[str, JsonValue] = {"entity_id": case.member, "terms": TERMS}
    _ = case.engine.tools["hire"].call(draft, args, Random(0))


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_hire_sets_the_generation_and_ends_the_turn(case: HireCase) -> None:
    draft = case.game().draft()
    _hire(case, draft)
    assert draft.generation == Generation(operation=HIRE, detail=TERMS, target=case.member)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_hire_refuses_a_sheeted_member(case: HireCase) -> None:
    draft = case.sheeted(case.game()).draft()
    with pytest.raises(Refusal, match="already carries a sheet"):
        _hire(case, draft)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
async def test_advance_on_a_hire_installs_the_sheet_and_joins_the_party(case: HireCase) -> None:
    draft = case.game().draft()
    generation = Generation(operation=HIRE, detail=TERMS, target=case.member)
    written = await case.engine.advance(draft, generation, stub_worldsmith(case.answer))
    world = case.engine.world_of(draft)
    member = world.require_member_here(case.member)
    assert member.hired
    assert case.member in world.party
    assert written.telling == SIGNED_ON.format(name=member.name)
