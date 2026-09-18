import pytest
from support.table import NO_PACKS
from support.twentyfourxx import ENGINE

from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption
from aidm.engines.packs import SRD_PACK, PackSet
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.pack import TwentyfourxxPack

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
    assert [s.id for s in ENGINE.creation_steps(SRD_PACK, picks)] == expected


def test_a_written_pack_adds_no_skills_to_the_increase_step() -> None:
    engine = TwentyfourxxEngine(NO_PACKS)
    engine.packs = PackSet(
        engine.id,
        {
            SRD_PACK: engine.packs.srd(),
            "extra": TwentyfourxxPack(
                name="Extra",
                source="",
                license="",
                skills=(DecisionOption(id="brewing", name="Brewing"),),
            ),
        },
        {},
    )

    increase = engine.creation_steps("extra", SNEAK)[-1]
    assert increase.options == engine.packs.srd().skills


def test_create_character_builds_the_sheet() -> None:
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, SNEAK)
    sheet = character.sheet.require_sheet()
    assert sheet.skills == {"Stealth": 12, "Climbing": 8, "Piloting": 8}
    assert sheet.specialty == "Sneak"
    assert sheet.origin == "Human"
    assert sheet.traits == ()


def test_create_character_with_a_typed_skill_name_adds_it_at_d8() -> None:
    picks = {**SNEAK, "increase-3": "Sabotage"}
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, picks)
    sheet = character.sheet.require_sheet()
    assert sheet.skills["Sabotage"] == 8


def test_create_character_with_a_typed_name_matching_a_printed_skill_canonicalises() -> None:
    picks = {**SNEAK, "increase-3": "PILOTING"}
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, picks)
    sheet = character.sheet.require_sheet()
    assert sheet.skills == {"Stealth": 12, "Climbing": 8, "Piloting": 8}


def test_pick_past_d12_is_refused() -> None:
    with pytest.raises(Refusal):
        ENGINE.create_character(
            "Rook", "A quiet operator", SRD_PACK, {**SNEAK, "increase-3": "stealth"}
        )


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
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, picks)
    assert [item.name for item in character.sheet.require_sheet().items.values()] == [
        "Comm",
        "Firearm",
    ]


def test_preview_character_ends_with_gear_row() -> None:
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, SNEAK)
    rows = ENGINE.preview_character(character)
    assert rows[-1] == ("Gear", "Comm, Climbing gear, Night vision goggles")


def test_preview_character_refuses_a_sheet_that_is_not_the_players() -> None:
    picks = {"specialty": "sneak", "origin": "alien", "trait-1": "a", "trait-2": "b"}
    character = ENGINE.create_character("Rook", "A quiet operator", SRD_PACK, picks)
    stranger = character.model_copy(
        update={"sheet": character.sheet.model_copy(update={"id": "rook"})}
    )
    with pytest.raises(Refusal, match="the player's"):
        ENGINE.preview_character(stranger)
