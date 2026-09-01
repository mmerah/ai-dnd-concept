from pathlib import Path

from aidm.core.creation import Picks
from aidm.engines.core import load_packs
from aidm.engines.mazerats.creation import Pack, create_character, creation_steps
from aidm.engines.mazerats.state import MazeRatsCharacterFile

PACKS = load_packs((Path(__file__).parents[2] / "src/aidm/engines/mazerats/packs",), Pack)
HAND_COST = {"heavy": 2, "ranged": 2}


def _picks(weapons: tuple[str, str] = ("light", "heavy")) -> Picks:
    steps = creation_steps(PACKS, {"pack": "srd"})
    return {
        "pack": "srd",
        **{
            step.id: step.options[0].id
            for step in steps
            if step.options and step.id not in {"pack", "weapon-one", "weapon-two"}
        },
        "items": ", ".join([*PACKS["srd"].tables["starting-items"].entries[:5], "Medicine (3)"]),
        "weapon-one": weapons[0],
        "weapon-two": weapons[1],
    }


def test_creation_asks_twelve_srd_steps_and_not_for_armour_or_a_shield() -> None:
    steps = creation_steps(PACKS, {"pack": "srd"})
    assert len(steps) == 12
    assert [step.id for step in steps] == [
        "pack",
        "abilities",
        "feature",
        "items",
        "weapon-one",
        "weapon-two",
        "appearance",
        "detail",
        "background",
        "clothing",
        "personality",
        "mannerism",
    ]
    weapons = next(step for step in steps if step.id == "weapon-one")
    assert [option.id for option in weapons.options] == ["light", "heavy", "ranged"]
    assert {option.label for option in next(s for s in steps if s.id == "background").options} >= {
        "Acolyte"
    }


def test_a_created_character_is_armoured_shielded_and_armed() -> None:
    character = create_character(PACKS, "Fen", "A careful delver.", _picks())
    assert isinstance(character, MazeRatsCharacterFile)
    inventory = character.payload.inventory
    assert len(inventory) == 10
    assert any(item.sheet.armour == "light" and item.sheet.position == "worn" for item in inventory)
    assert any(item.sheet.shield and item.sheet.position == "hands" for item in inventory)
    assert [item.sheet.weapon for item in inventory if item.sheet.weapon] == ["light", "heavy"]
    assert [item.name for item in inventory if item.sheet.medicine] == ["Medicine (3)"]
    assert character.payload.pack == "srd"


def test_two_identical_weapons_are_legal_and_stay_within_the_hand_budget() -> None:
    for weapons in (("light", "light"), ("heavy", "heavy"), ("ranged", "light")):
        character = create_character(PACKS, "Fen", "A careful delver.", _picks(weapons))
        assert isinstance(character, MazeRatsCharacterFile)
        inventory = character.payload.inventory
        hands = sum(
            HAND_COST.get(item.sheet.weapon or "", 1)
            for item in inventory
            if item.sheet.position == "hands"
        )
        assert hands <= 2, weapons
        assert sum(1 for item in inventory if item.sheet.position == "belt") <= 2, weapons
