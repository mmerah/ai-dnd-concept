from pathlib import Path

from aidm.engines.breathless.creation import (
    Pack,
    create_character,
    creation_steps,
    preview_character,
)
from aidm.engines.breathless.world import BreathlessCharacterFile
from aidm.engines.core import load_packs

PACKS_DIR = Path(__file__).parents[2] / "src" / "aidm" / "engines" / "breathless" / "packs"
PACKS = load_packs((PACKS_DIR,), Pack)
SRD = PACKS["srd"]

PICKS = {
    "pack": "srd",
    "pronouns": "she/her",
    "job": SRD.jobs[0],
    "skill-d10": "bash",
    "skill-d8": "dash",
    "skill-d6": "sneak",
    "item": SRD.weapons[0],
}


def test_skill_steps_exclude_earlier_picks() -> None:
    steps = creation_steps(PACKS, PICKS)
    d8_ids = {option.id for option in next(s for s in steps if s.id == "skill-d8").options}
    d6_ids = {option.id for option in next(s for s in steps if s.id == "skill-d6").options}
    assert "bash" not in d8_ids
    assert {"bash", "dash"} & d6_ids == set()


def test_create_character_round_trip() -> None:
    character = create_character(PACKS, "Jax", "A wiry mechanic", PICKS)
    assert isinstance(character, BreathlessCharacterFile)
    assert character.payload.skills == {"bash": 10, "dash": 8, "sneak": 6}
    assert character.payload.item == SRD.weapons[0]


def test_preview_character_shows_the_backpack_row() -> None:
    character = create_character(PACKS, "Jax", "A wiry mechanic", PICKS)
    rows = preview_character(character)
    assert ("Backpack", SRD.weapons[0]) in rows
