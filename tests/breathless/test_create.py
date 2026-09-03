from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.breathless.world import BreathlessCharacterFile

ENGINE = BreathlessEngine()
SRD = ENGINE.packs["srd"]

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
    steps = ENGINE.creation_steps(PICKS)
    d8_ids = {option.id for option in next(s for s in steps if s.id == "skill-d8").options}
    d6_ids = {option.id for option in next(s for s in steps if s.id == "skill-d6").options}
    assert "bash" not in d8_ids
    assert {"bash", "dash"} & d6_ids == set()


def test_create_character_round_trip() -> None:
    character = ENGINE.create_character("Jax", "A wiry mechanic", PICKS)
    assert isinstance(character, BreathlessCharacterFile)
    assert character.payload.skills == {"bash": 10, "dash": 8, "sneak": 6}
    assert character.payload.item == SRD.weapons[0]


def test_preview_character_shows_the_backpack_row() -> None:
    character = ENGINE.create_character("Jax", "A wiry mechanic", PICKS)
    rows = ENGINE.preview_character(character)
    assert ("Backpack", SRD.weapons[0]) in rows
