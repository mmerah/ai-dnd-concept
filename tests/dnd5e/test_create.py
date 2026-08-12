from pathlib import Path

import pytest
from core_test_support import DND5E, settings
from fivee_test_support import FOCUS, MIGHT, creation_of, filled_picks, scenario

from aidm.app.session import begin_game, build_engine
from aidm.content.store import load_character, write_character
from aidm.engines.dnd5e.content import load_content
from aidm.engines.dnd5e.equipment import armor_class
from aidm.engines.dnd5e.mechanics import Sheet, read
from aidm.engines.loader import Creation, Engine
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.creation import Amounts, CreationStep, Picks
from aidm.state.packs import ContentRef
from aidm.state.world import GameState


def _creation() -> Creation:
    return creation_of(build_engine(DND5E, settings()))


def test_a_created_fighter_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    creation = _creation()
    picks: Picks = {
        "race": ("half-elf",),
        "class": ("fighter",),
        "background": ("acolyte",),
        "ability-method": ("standard-array",),
        "abilities-standard-array": MIGHT,
    }
    follow_ups = {step.id for step in creation.steps(picks)}
    assert {"half-elf", "fighter-1"} <= follow_ups
    # Half-elf has no subrace, so no subrace step is offered.
    assert "half-elf-subrace" not in follow_ups
    picks = {
        **picks,
        "half-elf": ("dwarvish",),
        # One fighting style: Second Wind is granted by the row, not picked from it.
        "fighter-1": ("fighter-fighting-style-defense",),
        "fighter": ("skill-athletics", "skill-perception"),
        "half-elf-bonus": ("strength", "dexterity"),
        "acolyte": ("celestial", "goblin"),
        "fighter-equipment-1": ("chain-mail",),
        # "a martial weapon and a shield": the option handed the shield over and left the weapon
        # open, so picking it is what offers the weapon step below.
        "fighter-equipment-2": ("fighter-equipment-2-a",),
        "fighter-equipment-3": ("handaxe",),
        "fighter-equipment-4": ("explorers-pack",),
    }
    # Everyone speaks Common, and a half-elf already speaks Elvish: neither is on offer, because
    # the race record hands both over and what is handed over is never also offered.
    language_step = next(
        step
        for step in creation.steps(picks)
        if isinstance(step, CreationStep) and step.id == "acolyte"
    )
    assert {"elvish", "common"}.isdisjoint({option.id for option in language_step.options})
    # A skill the acolyte grants is off the fighter's list for the same reason.
    skill_step = next(
        step
        for step in creation.steps(picks)
        if isinstance(step, CreationStep) and step.id == "fighter"
    )
    assert "skill-insight" not in {option.id for option in skill_step.options}
    picks = {**picks, "fighter-equipment-2-a": ("longsword",)}
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
    # Chain mail (16, no DEX) plus a shield beats the unarmoured 10 + DEX.
    assert sheet.numbers["armor-class"] == 18
    assert (sheet.counters["hp"].current, sheet.counters["hp"].maximum) == (12, 12)
    longsword = state.world.require_kind(EntityId("longsword"), "item")
    assert (longsword.known, longsword.parent_id) == (True, PLAYER_ID)
    # The weapon ref on the item's own sheet is all an Attack needs.
    assert read(state).sheets[longsword.id].refs == (
        ContentRef(pack="srd-2014", collection="weapons", index="longsword"),
    )
    # The row grants Second Wind: it lands, and its pool with it, without a step offering it.
    assert ContentRef(pack="srd-2014", collection="features", index="second-wind") in sheet.refs
    # Common and Elvish are half-elf automatic languages; no step had to pick them.
    assert ContentRef(pack="srd-2014", collection="languages", index="common") in sheet.refs
    assert ContentRef(pack="srd-2014", collection="languages", index="elvish") in sheet.refs
    wind = sheet.counters["second-wind"]
    assert (wind.current, wind.maximum, wind.recharge) == (1, 1, "short-rest")
    proficient = {ref.index for ref in sheet.refs if ref.collection == "proficiencies"}
    # Athletics and perception are the class picks; insight and religion ride the background.
    assert proficient == {"skill-athletics", "skill-perception", "skill-insight", "skill-religion"}


def _created_wizard(tmp_path: Path) -> tuple[Engine, GameState]:
    """Sela, a high-elf wizard, through the authored write and load path into a started game."""
    creation = _creation()
    picks: Picks = {
        "race": ("elf",),
        "class": ("wizard",),
        "background": ("acolyte",),
        "ability-method": ("point-buy",),
        "abilities-point-buy": FOCUS,
    }
    picks = {
        **picks,
        "wizard-cantrips": ("fire-bolt", "light", "mage-hand"),
        "wizard-spells": (
            "magic-missile",
            "shield",
            "burning-hands",
            "sleep",
            "mage-armor",
            "detect-magic",
        ),
    }
    # Wizard 1 grants both its features and asks nothing: a step for it would be a non-choice.
    assert "wizard-1" not in {step.id for step in creation.steps(picks)}
    # Picking the subrace is what offers its cantrip, exactly as the page refreshes per pick.
    picks = {**picks, "elf-subrace": ("high-elf",)}
    picks = {**picks, "high-elf-cantrip": ("prestidigitation",)}
    picks = filled_picks(creation, picks)
    created = creation.create("Sela", "A scholar chasing the vault's first sealing.", picks)
    write_character(tmp_path, "sela", DND5E, created)
    engine = build_engine(DND5E, settings())
    return engine, begin_game(engine, scenario(), load_character(tmp_path, "sela", DND5E))


def test_a_created_caster_arrives_with_slots(tmp_path: Path) -> None:
    _, state = _created_wizard(tmp_path)
    sheet = read(state).sheets[PLAYER_ID]
    # Focus leads INT at 15; high elf (the elf-subrace step's only option) adds +1.
    assert sheet.numbers["intelligence"] == 16
    # Elf: the flat +2 DEX lands before AC is derived.
    assert sheet.numbers["dexterity"] == 15
    # A wizard wears no armour and has no Unarmored Defense, so AC stays 10 + DEX.
    assert sheet.numbers["armor-class"] == 12
    assert ContentRef(pack="srd-2014", collection="subraces", index="high-elf") in sheet.refs
    # Elvish arrives automatically with the race, not from any picked step.
    assert ContentRef(pack="srd-2014", collection="languages", index="elvish") in sheet.refs
    slot = sheet.counters["slot-1"]
    assert (slot.current, slot.maximum, slot.recharge) == (2, 2, "long-rest")
    # The spellbook is handed over unasked; the other three answer one group each.
    assert {item.id for item in load_character(tmp_path, "sela", DND5E).profile.items} == {
        "spellbook",
        "quarterstaff",
        "component-pouch",
        "scholars-pack",
    }
    # Elf Weapon Training is one of the three traits the high elf hands over, none of them asked.
    assert ContentRef(pack="srd-2014", collection="traits", index="elf-weapon-training") in (
        sheet.refs
    )
    # Three cantrips and six spellbook spells from the class, plus the high elf's own cantrip.
    known = {ref.index for ref in sheet.refs if ref.collection == "spells"}
    assert known == {
        "fire-bolt",
        "light",
        "mage-hand",
        "prestidigitation",
        "magic-missile",
        "shield",
        "burning-hands",
        "sleep",
        "mage-armor",
        "detect-magic",
    }


def test_a_created_cleric_chooses_a_domain_and_lands_the_domains_own_level_one_row() -> None:
    """Cleric, sorcerer and warlock choose their subclass at level 1, and the choice sits on the
    class's own level-1 row: picking the domain is what brings `life-1`'s grants to the sheet,
    exactly as picking a class brings `cleric-1`'s."""
    creation = _creation()
    picks: Picks = {
        "race": ("human",),
        "class": ("cleric",),
        "background": ("acolyte",),
        "ability-method": ("standard-array",),
        "abilities-standard-array": FOCUS,
    }
    domain = next(
        step
        for step in creation.steps(picks)
        if isinstance(step, CreationStep) and step.id == "cleric-1"
    )
    assert [option.id for option in domain.options] == ["life"]

    created = creation.create("Ilya", "A hand that mends.", filled_picks(creation, picks))

    sheet = Sheet.model_validate(created.overlay.character)

    def ref(collection: str, index: str) -> ContentRef:
        return ContentRef(pack="srd-2014", collection=collection, index=index)

    assert ref("subclasses", "life") in sheet.refs
    # Both handed over by `life-1`, which no created cleric could reach until the domain was
    # picked. `cleric-1`'s own Domain Spells feature was landing before this and says nothing
    # about which domain: the pair below is what the choice is worth.
    assert ref("features", "bonus-proficiency") in sheet.refs
    assert ref("features", "disciple-of-life") in sheet.refs


def test_one_spell_picked_in_two_steps_is_refused_rather_than_silently_dropped() -> None:
    creation = _creation()
    picks: Picks = {
        "race": ("elf",),
        "class": ("wizard",),
        "background": ("acolyte",),
        "ability-method": ("point-buy",),
        "abilities-point-buy": FOCUS,
        "elf-subrace": ("high-elf",),
        # The high elf's list is wizard cantrips, so both steps offer Light.
        "high-elf-cantrip": ("light",),
        "wizard-cantrips": ("fire-bolt", "light", "mage-hand"),
    }
    picks = {
        **picks,
        **{
            step.id: tuple(option.id for option in step.options[: step.choose])
            for step in creation.steps(picks)
            if isinstance(step, CreationStep) and step.id not in picks
        },
    }
    with pytest.raises(ValueError, match="Light is picked twice"):
        _ = creation.create("Sela", "A scholar who reaches for the same light twice.", picks)


def test_a_created_casters_spell_refs_are_what_a_cast_is_checked_against(tmp_path: Path) -> None:
    """A ref shape creation and the resolver disagree on passes every unit test and refuses the
    created caster every spell it holds."""
    engine, state = _created_wizard(tmp_path)
    held = engine.plan_type.model_validate(
        {
            "action": {
                "act": "cast-spell",
                "actor_id": PLAYER_ID,
                "spell": "srd-2014/spells/mage-hand",
            },
            "branches": (),
        }
    )
    assert engine.check_plan(state, held) is None
    unheld = engine.plan_type.model_validate(
        {
            "action": {
                "act": "cast-spell",
                "actor_id": PLAYER_ID,
                "spell": "srd-2014/spells/grease",
                "slot_level": 1,
            },
            "branches": (),
        }
    )
    refused = engine.check_plan(state, unheld)
    assert refused is not None and "does not know" in refused


def test_armor_class_reads_the_armor_worn_and_the_feature_granted() -> None:
    content = load_content()
    modifiers = {"dexterity": 3, "constitution": 2, "wisdom": 2}

    def carried(*items: tuple[str, str]) -> tuple[ContentRef, ...]:
        return tuple(
            ContentRef(pack="srd-2014", collection=collection, index=index)
            for collection, index in items
        )

    scale = ("armor", "scale-mail")
    shield = ("armor", "shield")
    # Scale mail is 14 and admits at most +2 DEX; the shield adds on top of that.
    assert armor_class(content, carried(scale), modifiers, ()) == 16
    assert armor_class(content, carried(scale, shield), modifiers, ()) == 18
    unarmored = carried(("features", "monk-unarmored-defense"))
    # Every monk carries Unarmored Defense: 10 + DEX + WIS while it wears nothing.
    assert armor_class(content, carried(("weapons", "quarterstaff")), modifiers, unarmored) == 15
    keeps_shield = carried(("features", "barbarian-unarmored-defense"))
    # Studded leather (12, +3 DEX) and a shield beat the feature, which armour switches off.
    worn = carried(("armor", "studded-leather-armor"), shield)
    assert armor_class(content, worn, modifiers, keeps_shield) == 17


# The six scores seed 12 rolls, high to low, and where they land: `mechanics.ABILITIES` order.
ROLLED = (17, 15, 13, 13, 12, 10)
ABILITY_ORDER = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SEEDED: Picks = {
    "race": ("human",),
    "class": ("fighter",),
    "background": ("acolyte",),
    "ability-method": ("roll",),
    "ability-seed": {"seed": 12},
}


def test_a_rolled_character_carries_the_scores_its_seed_rolled(tmp_path: Path) -> None:
    """The third generation method end to end: nothing about the spread is picked, the seed is,
    and the same seed always rebuilds the same six scores."""
    creation = _creation()
    step = next(s for s in creation.steps(SEEDED) if s.id == "abilities-roll")
    assert f"Assign the roll: {', '.join(str(score) for score in ROLLED)}" == step.prompt
    picks = filled_picks(
        creation, {**SEEDED, "abilities-roll": dict(zip(ABILITY_ORDER, ROLLED, strict=True))}
    )

    created = creation.create("Tarn", "A soldier who rolled well.", picks)
    write_character(tmp_path, "tarn", DND5E, created)
    engine = build_engine(DND5E, settings())
    state = begin_game(engine, scenario(), load_character(tmp_path, "tarn", DND5E))

    sheet = read(state).sheets[PLAYER_ID]
    # A human's flat +1 lands on the rolled scores exactly as it lands on an assigned array.
    assert sheet.numbers["strength"] == ROLLED[0] + 1
    assert sheet.numbers["charisma"] == ROLLED[-1] + 1
    # The third rolled score lands on Constitution, and hp is the hit die plus its modifier.
    assert sheet.numbers["constitution"] == ROLLED[2] + 1
    assert sheet.counters["hp"].maximum == 10 + (ROLLED[2] + 1 - 10) // 2


def test_a_tampered_roll_an_overspend_a_score_out_of_bounds_and_a_fraction_are_refused() -> None:
    creation = _creation()
    # Within the roll's own bounds, but not the multiset it rolled: a swapped 12 for a 13.
    inflated: Amounts = dict(zip(ABILITY_ORDER, (17, 15, 13, 13, 13, 10), strict=True))
    tampered = filled_picks(creation, {**SEEDED, "abilities-roll": inflated})
    buying = {key: value for key, value in SEEDED.items() if key != "ability-seed"}
    buying = {**buying, "ability-method": ("point-buy",)}
    over = filled_picks(creation, {**buying, "abilities-point-buy": {**FOCUS, "strength": 12}})
    outside = filled_picks(creation, {**buying, "abilities-point-buy": {**FOCUS, "strength": 16}})

    # A float is what a browser number input hands over; `Amounts` says int and nothing enforces it.
    fraction: Amounts = {**FOCUS, "strength": 8.5}  # pyright: ignore[reportAssignmentType]
    fractional = filled_picks(creation, {**buying, "abilities-point-buy": fraction})

    for picks, reason in (
        (tampered, "the scores to assign are 17, 15, 13, 13, 12, 10"),
        (fractional, "takes whole numbers"),
        (over, "point buy spends 31 of 27"),
        (outside, "lies outside"),
    ):
        with pytest.raises(ValueError, match=reason):
            _ = creation.create("Tarn", "A soldier who rolled too well.", picks)
