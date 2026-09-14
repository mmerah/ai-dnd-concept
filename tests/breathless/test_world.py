import pytest

from aidm.core.entities import Refusal
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.world import (
    LOOT_START,
    SKILLS,
    Die,
    Skill,
    Supply,
    Survivor,
    SurvivorSheet,
    stepped,
)


def _player() -> Survivor:
    rated: dict[Skill, Die] = {**dict.fromkeys(SKILLS, 4), "bash": 10, "dash": 8, "sneak": 6}
    return Survivor(
        id=PLAYER_ID,
        name="Jax",
        brief="A wiry mechanic",
        known=True,
        sheet=SurvivorSheet(skills=rated, worn=rated),
    )


def test_a_sheet_short_of_the_six_skills_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 6"):
        _ = SurvivorSheet(skills={"bash": 10, "dash": 8, "sneak": 6}, worn=dict.fromkeys(SKILLS, 4))


def test_a_sheet_rated_off_the_creation_spread_is_refused() -> None:
    with pytest.raises(ValueError, match="three d4"):
        _ = SurvivorSheet(skills=dict.fromkeys(SKILLS, 12), worn=dict.fromkeys(SKILLS, 12))


def test_stepped_floors_at_d4() -> None:
    assert stepped(4) == 4
    assert stepped(12) == 10


def test_wear_steps_the_worn_skill() -> None:
    sheet = _player().require_sheet()
    sheet.wear("bash")
    assert sheet.worn["bash"] == stepped(10)


def test_spend_stunt_refuses_a_second_time() -> None:
    sheet = _player().require_sheet()
    sheet.spend_stunt("Jax")
    assert sheet.stunted
    with pytest.raises(Refusal, match="catches their breath"):
        sheet.spend_stunt("Jax")


def test_step_loot_steps_the_loot_die() -> None:
    sheet = _player().require_sheet()
    sheet.step_loot()
    assert sheet.loot == stepped(LOOT_START)


def test_wear_item_at_d4_removes_it_and_writes_the_fact() -> None:
    player = _player()
    player.require_sheet().items["knife"] = Supply(name="Knife", die=6)
    facts = player.wear_item("knife")
    assert "knife" not in player.require_sheet().items
    assert facts[0].card == "Knife is gone"


def test_wear_item_above_d4_steps_the_die_and_writes_no_fact() -> None:
    player = _player()
    player.require_sheet().items["knife"] = Supply(name="Knife", die=10)
    facts = player.wear_item("knife")
    assert player.require_sheet().items["knife"].die == stepped(10)
    assert facts == []


def test_catch_breath_restores_worn_loot_and_stunt() -> None:
    player = _player()
    sheet = player.require_sheet()
    sheet.worn["bash"] = 4
    sheet.loot = 6
    sheet.stunted = True

    facts = player.catch_breath()

    assert sheet.worn == sheet.skills
    assert sheet.loot == LOOT_START
    assert not sheet.stunted
    assert facts[0].card == "Caught breath — skills and loot die restored"
