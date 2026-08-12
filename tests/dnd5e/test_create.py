from pathlib import Path

from core_test_support import DND5E, settings
from fivee_test_support import scenario

from aidm.app.session import begin_game, build_engine
from aidm.content.store import load_character, write_character
from aidm.engines.dnd5e.mechanics import read
from aidm.engines.loader import Creation
from aidm.state.base import PLAYER_ID
from aidm.state.creation import Picks
from aidm.state.packs import ContentRef


def _creation() -> Creation:
    creation = build_engine(DND5E, settings()).creation
    assert creation is not None
    return creation


def test_a_created_fighter_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    creation = _creation()
    picks: Picks = {
        "race": ("half-elf",),
        "class": ("fighter",),
        "background": ("acolyte",),
        "abilities": ("might",),
    }
    follow_ups = {step.id for step in creation.steps(picks)}
    assert {"half-elf", "fighter-1"} <= follow_ups
    # Half-elf has no subrace, so no subrace step is offered.
    assert "half-elf-subrace" not in follow_ups
    picks = {
        **picks,
        "half-elf": ("dwarvish",),
        "fighter-1": ("fighter-fighting-style-defense", "second-wind"),
        "fighter-skills": ("athletics", "perception"),
        "half-elf-bonus": ("strength", "dexterity"),
        "acolyte-languages": ("dwarvish", "goblin"),
    }
    # Everyone speaks Common, and a half-elf already speaks Elvish: neither is on offer.
    language_step = next(step for step in creation.steps(picks) if step.id == "acolyte-languages")
    assert "elvish" not in {option.id for option in language_step.options}
    created = creation.create("Borin", "A wall of a man with a debt to the abbey.", picks)
    write_character(tmp_path, "borin", DND5E, created)
    engine = build_engine(DND5E, settings())
    state = begin_game(engine, scenario(), load_character(tmp_path, "borin", DND5E))
    sheet = read(state).sheets[PLAYER_ID]
    # Half-elf: +2 CHA flat, and the two chosen +1s land before AC is derived from DEX.
    assert sheet.numbers["strength"] == 16
    assert sheet.numbers["charisma"] == 10
    assert sheet.numbers["level"] == 1
    assert sheet.numbers["proficiency-bonus"] == 2
    assert sheet.numbers["armor-class"] == 12
    assert (sheet.counters["hp"].current, sheet.counters["hp"].maximum) == (12, 12)
    assert ContentRef(pack="srd-2014", collection="features", index="second-wind") in sheet.refs
    # Common and Elvish are half-elf automatic languages; no step had to pick them.
    assert ContentRef(pack="srd-2014", collection="languages", index="common") in sheet.refs
    assert ContentRef(pack="srd-2014", collection="languages", index="elvish") in sheet.refs
    # Dwarvish rides both the half-elf step and the background step; the ref lands once.
    dwarvish = ContentRef(pack="srd-2014", collection="languages", index="dwarvish")
    assert sheet.refs.count(dwarvish) == 1
    wind = sheet.counters["second-wind"]
    assert (wind.current, wind.maximum, wind.recharge) == (1, 1, "short-rest")
    proficient = {ref.index for ref in sheet.refs if ref.collection == "proficiencies"}
    # Athletics and perception are the class picks; insight and religion ride the background.
    assert proficient == {"skill-athletics", "skill-perception", "skill-insight", "skill-religion"}


def test_a_created_caster_arrives_with_slots(tmp_path: Path) -> None:
    creation = _creation()
    picks: Picks = {
        "race": ("elf",),
        "class": ("wizard",),
        "background": ("acolyte",),
        "abilities": ("focus",),
    }
    picks = {
        **picks,
        **{
            step.id: tuple(option.id for option in step.options[: step.choose])
            for step in creation.steps(picks)
            if step.id not in picks
        },
    }
    created = creation.create("Sela", "A scholar chasing the vault's first sealing.", picks)
    write_character(tmp_path, "sela", DND5E, created)
    engine = build_engine(DND5E, settings())
    state = begin_game(engine, scenario(), load_character(tmp_path, "sela", DND5E))
    sheet = read(state).sheets[PLAYER_ID]
    # Focus leads INT at 15; high elf (the elf-subrace step's only option) adds +1.
    assert sheet.numbers["intelligence"] == 16
    # Elf: the flat +2 DEX lands before AC is derived.
    assert sheet.numbers["dexterity"] == 15
    assert sheet.numbers["armor-class"] == 12
    assert ContentRef(pack="srd-2014", collection="subraces", index="high-elf") in sheet.refs
    # Elvish arrives automatically with the race, not from any picked step.
    assert ContentRef(pack="srd-2014", collection="languages", index="elvish") in sheet.refs
    slot = sheet.counters["slot-1"]
    assert (slot.current, slot.maximum, slot.recharge) == (2, 2, "long-rest")
