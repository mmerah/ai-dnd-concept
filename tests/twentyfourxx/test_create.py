import pytest
from pydantic import BaseModel

from aidm.core.entities import EngineId
from aidm.core.model import Character
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine

ENGINE = TwentyfourxxEngine()


class _OtherPayload(BaseModel):
    pass


def test_steps_grow_as_picks_land() -> None:
    assert [s.id for s in ENGINE.creation_steps({})] == ["pack"]
    steps = ENGINE.creation_steps({"pack": "srd"})
    assert [s.id for s in steps] == ["pack", "specialty"]
    steps = ENGINE.creation_steps({"pack": "srd", "specialty": "sneak"})
    assert [s.id for s in steps] == ["pack", "specialty", "origin"]


def test_muscle_shows_specialty_choice_and_weapon() -> None:
    ids = [s.id for s in ENGINE.creation_steps({"pack": "srd", "specialty": "muscle"})]
    assert "specialty-choice" in ids
    assert "weapon" in ids


def test_sneak_shows_neither_specialty_choice_nor_weapon() -> None:
    ids = [s.id for s in ENGINE.creation_steps({"pack": "srd", "specialty": "sneak"})]
    assert "specialty-choice" not in ids
    assert "weapon" not in ids


def test_alien_shows_two_trait_steps() -> None:
    picks = {"pack": "srd", "specialty": "sneak", "origin": "alien"}
    ids = [s.id for s in ENGINE.creation_steps(picks)]
    assert ids[-2:] == ["trait-1", "trait-2"]


def test_android_shows_body_and_one_increase() -> None:
    picks = {"pack": "srd", "specialty": "sneak", "origin": "android"}
    ids = [s.id for s in ENGINE.creation_steps(picks)]
    assert "body" in ids
    assert ids.count("increase-1") == 1
    assert "increase-2" not in ids


def test_human_shows_three_increases() -> None:
    picks = {"pack": "srd", "specialty": "sneak", "origin": "human"}
    ids = [s.id for s in ENGINE.creation_steps(picks)]
    assert [i for i in ids if i.startswith("increase-")] == [
        "increase-1",
        "increase-2",
        "increase-3",
    ]


def test_create_character_builds_the_sheet() -> None:
    picks = {
        "pack": "srd",
        "specialty": "sneak",
        "origin": "human",
        "increase-1": "stealth",
        "increase-2": "stealth",
        "increase-3": "piloting",
    }
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    assert character.payload.skills == {"Stealth": 12, "Climbing": 8, "Piloting": 8}
    assert character.payload.specialty == "Sneak"
    assert character.payload.origin == "Human"
    assert character.payload.traits == ()


def test_pick_past_d12_is_refused() -> None:
    picks = {
        "pack": "srd",
        "specialty": "sneak",
        "origin": "human",
        "increase-1": "stealth",
        "increase-2": "stealth",
        "increase-3": "stealth",
    }
    with pytest.raises(ValueError):
        ENGINE.create_character("Rook", "A quiet operator", picks)


def test_items_land_in_order_comm_kit_weapon() -> None:
    picks = {
        "pack": "srd",
        "specialty": "muscle",
        "specialty-choice": "shooting",
        "weapon": "firearm",
        "origin": "human",
        "increase-1": "connections",
        "increase-2": "labor",
        "increase-3": "running",
    }
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    assert [item.name for item in character.payload.items.values()] == ["Comm", "Firearm"]


def test_preview_character_ends_with_gear_row() -> None:
    picks = {
        "pack": "srd",
        "specialty": "sneak",
        "origin": "human",
        "increase-1": "stealth",
        "increase-2": "stealth",
        "increase-3": "piloting",
    }
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    rows = ENGINE.preview_character(character)
    assert rows[-1] == ("Gear", "Comm, Climbing gear, Night vision goggles")


def test_preview_character_refuses_foreign_character_type() -> None:
    foreign = Character(id="x", engine=EngineId("other"), payload=_OtherPayload())
    with pytest.raises(ValueError):
        ENGINE.preview_character(foreign)


def test_preview_character_refuses_a_sheet_that_is_not_the_players() -> None:
    picks = {"pack": "srd", "specialty": "sneak", "origin": "alien", "trait-1": "a", "trait-2": "b"}
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    stranger = character.model_copy(
        update={"payload": character.payload.model_copy(update={"id": "rook"})}
    )
    with pytest.raises(ValueError, match="the player's"):
        ENGINE.preview_character(stranger)
