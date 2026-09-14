import pytest
from support.twentyfourxx import ENGINE

from aidm.core.entities import Refusal
from aidm.core.model import PackSelection
from aidm.engines.scenes.packs import SRD_PACK

SNEAK = {
    "specialty": "sneak",
    "origin": "human",
    "increase-1": "stealth",
    "increase-2": "stealth",
    "increase-3": "piloting",
}


@pytest.mark.parametrize(
    ("picks", "expected"),
    [
        ({}, ["specialty"]),
        ({"specialty": "sneak"}, ["specialty", "origin"]),
        ({"specialty": "muscle"}, ["specialty", "specialty-choice", "weapon", "origin"]),
        ({"specialty": "sneak", "origin": "alien"}, ["specialty", "origin", "trait-1", "trait-2"]),
        (
            {"specialty": "sneak", "origin": "android"},
            ["specialty", "origin", "body", "increase-1"],
        ),
        (
            {"specialty": "sneak", "origin": "human"},
            ["specialty", "origin", "increase-1", "increase-2", "increase-3"],
        ),
    ],
)
def test_creation_steps_grow_with_picks(picks: dict[str, str], expected: list[str]) -> None:
    assert [s.id for s in ENGINE.creation_steps(picks)] == expected


def test_create_character_builds_the_sheet() -> None:
    character = ENGINE.create_character("Rook", "A quiet operator", SNEAK)
    sheet = character.payload.require_sheet()
    assert sheet.skills == {"Stealth": 12, "Climbing": 8, "Piloting": 8}
    assert sheet.specialty == "Sneak"
    assert sheet.origin == "Human"
    assert sheet.traits == ()


def test_create_character_records_the_picked_pack() -> None:
    character = ENGINE.create_character("Rook", "A quiet operator", SNEAK)
    assert character.packs == PackSelection(ids=(SRD_PACK,))


def test_create_character_with_a_typed_skill_name_adds_it_at_d8() -> None:
    picks = {**SNEAK, "increase-3": "Sabotage"}
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    sheet = character.payload.require_sheet()
    assert sheet.skills["Sabotage"] == 8


def test_create_character_with_a_typed_name_matching_a_printed_skill_canonicalises() -> None:
    picks = {**SNEAK, "increase-3": "PILOTING"}
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    sheet = character.payload.require_sheet()
    assert sheet.skills == {"Stealth": 12, "Climbing": 8, "Piloting": 8}


def test_pick_past_d12_is_refused() -> None:
    with pytest.raises(Refusal):
        ENGINE.create_character("Rook", "A quiet operator", {**SNEAK, "increase-3": "stealth"})


def test_items_land_in_order_comm_kit_weapon() -> None:
    picks = {
        "specialty": "muscle",
        "specialty-choice": "shooting",
        "weapon": "firearm",
        "origin": "human",
        "increase-1": "connections",
        "increase-2": "labor",
        "increase-3": "running",
    }
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    assert [item.name for item in character.payload.require_sheet().items.values()] == [
        "Comm",
        "Firearm",
    ]


def test_preview_character_ends_with_gear_row() -> None:
    character = ENGINE.create_character("Rook", "A quiet operator", SNEAK)
    rows = ENGINE.preview_character(character)
    assert rows[-1] == ("Gear", "Comm, Climbing gear, Night vision goggles")


def test_preview_character_refuses_a_sheet_that_is_not_the_players() -> None:
    picks = {"specialty": "sneak", "origin": "alien", "trait-1": "a", "trait-2": "b"}
    character = ENGINE.create_character("Rook", "A quiet operator", picks)
    stranger = character.model_copy(
        update={"payload": character.payload.model_copy(update={"id": "rook"})}
    )
    with pytest.raises(Refusal, match="the player's"):
        ENGINE.preview_character(stranger)
