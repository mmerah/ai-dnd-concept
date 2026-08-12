import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from core_test_support import capability
from fivee_test_support import (
    created_game,
    dnd5e_game,
    dnd5e_session,
    paladinly,
    ready,
    wizardly,
)

from aidm.engines.counters import Counter
from aidm.engines.dnd5e.advance import (
    ABILITY_TALLY,
    ADVANCEMENT_READY,
    IMPROVEMENT,
    MAX_ABILITY,
    LevelUp,
)
from aidm.engines.dnd5e.advance import class_ref as _class_ref
from aidm.engines.dnd5e.content import load_content, lookup
from aidm.engines.dnd5e.mechanics import ABILITIES, Sheet, modifier, read, sheet_of, write
from aidm.engines.dnd5e.spells import CANTRIPS_KNOWN, SPELLS_KNOWN, slot_recharge
from aidm.engines.loader import Advancement
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.packs import Content, ContentRef, is_int_fact
from aidm.state.world import GameState

ACTION_SURGE = ContentRef(pack="srd-2014", collection="features", index="action-surge-1-use")
SECOND_WIND = ContentRef(pack="srd-2014", collection="features", index="second-wind")
SHIELD = ContentRef(pack="srd-2014", collection="spells", index="shield")
MAGE_ARMOR = ContentRef(pack="srd-2014", collection="spells", index="mage-armor")
FIREBALL = ContentRef(pack="srd-2014", collection="spells", index="fireball")
MAGIC_MISSILE = ContentRef(pack="srd-2014", collection="spells", index="magic-missile")
DUELING = ContentRef(pack="srd-2014", collection="features", index="fighting-style-dueling")
DIVINE_SMITE = ContentRef(pack="srd-2014", collection="features", index="divine-smite")
BLESS = ContentRef(pack="srd-2014", collection="spells", index="bless")
EVOCATION = ContentRef(pack="srd-2014", collection="subclasses", index="evocation")
SCULPT_SPELLS = ContentRef(pack="srd-2014", collection="features", index="sculpt-spells")
# Fighter 2 grants Action Surge and offers nothing, so a legal proposal picks nothing.
LEGAL = LevelUp(picks=(), why="second level")
OUTSIDE = LevelUp(picks=(SECOND_WIND,), why="a feature already held")
# Wizard 2 is where a wizard names its arcane tradition, so the level takes a pick as well.
CASTING = LevelUp(picks=(EVOCATION,), spells=(SHIELD, MAGE_ARMOR), why="two new spells")
SWORN = LevelUp(picks=(DUELING,), spells=(BLESS,), why="an oath takes hold")


def caster(state: GameState) -> GameState:
    """A wizard 1 already holding its three cantrips, so level 2 adds two spells and no cantrip."""
    draft = wizardly(state).draft()
    mechanics = read(draft)
    sheet_of(mechanics, draft.player).numbers[CANTRIPS_KNOWN] = 3
    write(draft, mechanics)
    return ready(draft.committed())


CLASSES = (
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
)
LAST = 20
# Every pool a level-20 sheet of the class holds beside hp and its slots, at its maximum: the ones
# creation grants at level 1 and the ones the rows bring on the way up. The paladin holds no
# divine sense because this spread leaves its Charisma a penalty, which is 1 + (-1) = no uses.
POOLS_AT_TWENTY: Mapping[str, Mapping[str, int]] = {
    "barbarian": {"rage": 6},
    "bard": {"bardic-inspiration": 1},
    "cleric": {"channel-divinity-charges": 3},
    "druid": {"wild-shape": 2},
    "fighter": {"action-surges": 2, "indomitable-uses": 3, "second-wind": 1},
    "monk": {"ki-points": 20},
    "paladin": {"lay-on-hands": 100},
    "ranger": {},
    "rogue": {},
    "sorcerer": {"sorcery-points": 20},
    "warlock": {f"mystic-arcanum-level-{level}": 1 for level in range(6, 10)},
    "wizard": {"arcane-recovery": 1},
}
# The three classes that wear no armour at 20, so every improvement to Dexterity is felt: creation
# left them at 13, 13 and 14, and nothing recomputed the number until a level-up did.
ARMOR_AT_TWENTY: Mapping[str, int] = {"barbarian": 17, "monk": 16, "rogue": 16}
# One line of the offer's spell text: how many of a kind this level adds, then the legal ones.
_ADDS = re.compile(r"Adds (\d+) \w+, from: (.+)$")


def _ref(text: str) -> ContentRef:
    pack, collection, index = text.split("/")
    return ContentRef.model_validate({"pack": pack, "collection": collection, "index": index})


def _from_the_offer(text: str) -> tuple[ContentRef, ...]:
    """What the offer's own prose leaves an advisor to pick, taken from the front of each list:
    the model sees nothing else, so a level the text under-describes cannot be answered."""
    taken: list[ContentRef] = []
    for line in text.splitlines():
        adds = _ADDS.match(line)
        if adds is not None:
            legal = re.findall(r"\[([^]]+)\]", adds[2])
            taken.extend(_ref(found) for found in legal[: int(adds[1])])
    return tuple(taken)


def _spend(sheet: Sheet, text: str) -> dict[str, int]:
    """The ability score improvement the offer asks for, poured into the scores in order."""
    asked = re.search(r"Raises ability scores by (\d+) points", text)
    owed = 0 if asked is None else int(asked[1])
    raised: dict[str, int] = {}
    for ability in ABILITIES:
        held = sheet.numbers[ability]
        spent = min(owed, MAX_ABILITY - held)
        if spent:
            raised[ability] = held + spent
            owed -= spent
    assert owed == 0
    return raised


def _sheet(state: GameState) -> Sheet:
    return sheet_of(read(state), state.player)


def _one_level(growth: Advancement, state: GameState) -> GameState:
    offer = growth.offered(state)
    assert offer is not None
    proposal = LevelUp(
        picks=offer.options[: offer.choose],
        spells=_from_the_offer(offer.text),
        abilities=_spend(_sheet(state), offer.text),
        why="the story earns a level",
    )
    assert growth.violation(state, offer, proposal) is None
    draft = state.draft()
    _ = growth.advance(draft, proposal)
    return draft.committed()


@pytest.mark.parametrize("class_index", CLASSES)
def test_a_created_character_of_every_class_plays_to_twenty_on_its_own_rows(
    class_index: str, tmp_path: Path
) -> None:
    """The whole of advancement in one pass: a character creation built, levelled by the offer's
    own text alone, ending on exactly the numbers, pools and slots its level-20 row names."""
    engine, state = created_game(tmp_path, class_index)
    growth = capability(engine)
    rolled_up = sum(_sheet(state).numbers[ability] for ability in ABILITIES)
    for _ in range(LAST - 1):
        state = _one_level(growth, ready(state))
        # Pact magic migrates its slot key: a warlock never holds two.
        assert class_index != "warlock" or len(_slots(_sheet(state))) == 1

    sheet = _sheet(state)
    content = load_content()
    row = content.require(
        ContentRef(pack="srd-2014", collection="levels", index=f"{class_index}-{LAST}")
    )
    assert set(_slots(sheet)) == {key for key in row.facts if key.startswith("slot-")}
    # A pool written as a plain number is the failure ticket 02 names: `UseFeature` on it dies at
    # `counter_of`. What must be a counter is named here rather than read off the engine's own
    # table, so moving a key out of `POOL_FACTS` fails instead of agreeing with itself.
    assert set(sheet.counters) == {"hp", *_slots(sheet), *POOLS_AT_TWENTY[class_index]}
    assert not set(sheet.counters) & set(sheet.numbers)
    for key, maximum in POOLS_AT_TWENTY[class_index].items():
        assert sheet.counters[key].maximum == maximum, key
    if class_index in ARMOR_AT_TWENTY:
        assert sheet.numbers["armor-class"] == ARMOR_AT_TWENTY[class_index]
    for key, value in row.facts.items():
        if not is_int_fact(value) or key == ABILITY_TALLY:
            continue
        held = sheet.counters.get(key)
        assert value == (sheet.numbers[key] if held is None else held.maximum), key
    for counter in _slots(sheet).values():
        assert counter.recharge == slot_recharge(class_index)
    # The whole maximum the level is worth, with the raised Constitution paid on every level: the
    # engine reaches it in nineteen additions, this reads it off the end state in one.
    die = content.require(_class_ref(sheet)).facts["hit-die"]
    assert is_int_fact(die)
    constitution = modifier(sheet.numbers["constitution"])
    assert sheet.counters["hp"].maximum == die + (LAST - 1) * (die // 2 + 1) + LAST * constitution
    # The pack's rogue tally counts down as often as up, so no level writes it to a sheet.
    assert ABILITY_TALLY not in sheet.numbers
    # Every improvement the rows handed over was spent, and none of them was spent twice.
    spent = sum(sheet.numbers[ability] for ability in ABILITIES) - rolled_up
    improvements = [ref for ref in sheet.refs if content.require(ref).name == IMPROVEMENT]
    assert spent == 2 * len(improvements)
    _the_subclass_table_was_read_too(content, sheet)


def _the_subclass_table_was_read_too(content: Content, sheet: Sheet) -> None:
    """The second table every class reads from the level it names an archetype: the subclass is
    picked, every feature its own rows hand over is held, every row that asks was answered, and
    the numbers of its last row are on the sheet beside the class's own."""
    held = [ref for ref in sheet.refs if ref.collection == "subclasses"]
    assert len(held) == 1, held
    rows = [
        row
        for level in range(1, LAST + 1)
        if (row := lookup(content, held[0].sibling("levels", f"{held[0].index}-{level}")))
        is not None
    ]
    assert rows, held[0]
    for row in rows:
        assert set(row.granted) <= set(sheet.refs), row.index
        if row.choose is not None:
            assert len(set(row.options) & set(sheet.refs)) >= row.choose, row.index
    for key, value in rows[-1].facts.items():
        if is_int_fact(value) and key != "level":
            assert sheet.numbers[key] == value, key


def _slots(sheet: Sheet) -> dict[str, Counter]:
    return {key: value for key, value in sheet.counters.items() if key.startswith("slot-")}


REMARKABLE_ATHLETE = ContentRef(pack="srd-2014", collection="features", index="remarkable-athlete")
STYLES = "fighter-fighting-style-"


def test_an_offer_reads_the_subclass_row_at_its_own_level_and_carries_what_it_says(
    tmp_path: Path,
) -> None:
    """What the advisor reads is the offer's own prose, grants and options, and from the level a
    subclass is chosen each of the three is two rows merged. The fighter is where it shows: its
    own rows for 7 and 10 say only "Martial Archetype feature", and `champion-7` hands over
    Remarkable Athlete while `champion-10` offers a second fighting style out of the six the
    class already offered at level 1."""
    engine, state = created_game(tmp_path, "fighter")
    growth = capability(engine)
    first = {ref.index for ref in _sheet(state).refs if ref.index.startswith(STYLES)}
    for _ in range(5):
        state = _one_level(growth, ready(state))

    seventh = growth.offered(ready(state))
    assert seventh is not None and seventh.prompt.startswith("Fighter 7")
    assert REMARKABLE_ATHLETE in seventh.granted
    assert "Champion, level 7." in seventh.text

    for _ in range(3):
        state = _one_level(growth, ready(state))
    tenth = growth.offered(ready(state))
    assert tenth is not None and tenth.prompt.startswith("Fighter 10")
    assert tenth.choose == 1
    # The style taken at level 1 is off the offer, and the five left are what is on it.
    assert {ref.index for ref in tenth.options} | first == {
        f"{STYLES}{style}"
        for style in (
            "archery",
            "defense",
            "dueling",
            "great-weapon-fighting",
            "protection",
            "two-weapon-fighting",
        )
    }
    assert not {ref.index for ref in tenth.options} & first

    state = _one_level(growth, ready(state))
    assert len({ref.index for ref in _sheet(state).refs if ref.index.startswith(STYLES)}) == 2


HUNTER = ContentRef(pack="srd-2014", collection="subclasses", index="hunter")
HUNTERS_PREY = {
    f"hunters-prey-{kind}" for kind in ("colossus-slayer", "giant-killer", "horde-breaker")
}


def test_a_subclass_row_that_asks_at_its_own_choice_level_is_answered_the_level_after(
    tmp_path: Path,
) -> None:
    """The ranger is the one class whose subclass row asks something at the very level the
    subclass is chosen: nothing can offer Hunter's Prey until the archetype is held, so `hunter-3`
    is carried to the next offer rather than lost, and drops off it once it is answered."""
    engine, state = created_game(tmp_path, "ranger")
    growth = capability(engine)
    state = _one_level(growth, ready(state))
    archetype = growth.offered(ready(state))
    assert archetype is not None and archetype.prompt.startswith("Ranger 3")
    assert (archetype.options, archetype.choose) == ((HUNTER,), 1)

    state = _one_level(growth, ready(state))
    assert HUNTER in _sheet(state).refs
    prey = growth.offered(ready(state))
    assert prey is not None and prey.prompt.startswith("Ranger 4")
    assert {ref.index for ref in prey.options} == HUNTERS_PREY

    state = _one_level(growth, ready(state))
    taken = {ref.index for ref in _sheet(state).refs} & HUNTERS_PREY
    assert len(taken) == 1
    after = growth.offered(ready(state))
    assert after is not None and not {ref.index for ref in after.options} & HUNTERS_PREY


def test_an_offer_leaves_out_the_options_the_character_already_took(tmp_path: Path) -> None:
    """A sorcerer takes two metamagics at level 3; the level-10 offer that used to list all eight
    now lists the six left, and the refusal a stale pick meets is the offer's own."""
    engine, state = created_game(tmp_path, "sorcerer")
    growth = capability(engine)
    for _ in range(8):
        state = _one_level(growth, ready(state))
    taken = tuple(ref for ref in _sheet(state).refs if ref.index.startswith("metamagic-"))

    offer = growth.offered(ready(state))

    assert offer is not None and offer.prompt.startswith("Sorcerer 10")
    assert len(taken) == 2
    assert (len(offer.options), offer.choose) == (6, 1)
    assert not set(offer.options) & set(taken)
    stale = LevelUp(picks=taken[:1], spells=(), why="a metamagic taken twice")
    assert "is not on offer here" in str(growth.violation(ready(state), offer, stale))


def test_an_ability_score_improvement_is_made_or_refused_but_never_skipped() -> None:
    """Fighter 4 hands over two points. The row says so, the offer says so, and a proposal that
    spends none of them, or three of them, is refused rather than quietly dropped."""
    engine, state = dnd5e_game()
    growth = capability(engine)
    draft = ready(state).draft()
    mechanics = read(draft)
    sheet_of(mechanics, draft.player).numbers["level"] = 3
    write(draft, mechanics)
    advancing = draft.committed()
    offer = growth.offered(advancing)
    assert offer is not None and "Raises ability scores by 2 points" in offer.text

    held = _sheet(advancing).numbers["strength"]
    skipped = LevelUp(why="a fourth level that improves nothing")
    overspent = LevelUp(abilities={"strength": held + 3}, why="three points from a two-point level")
    spent = LevelUp(abilities={"strength": held + 2}, why="a stronger arm")

    assert "raises ability scores by 2 points in all" in str(
        growth.violation(advancing, offer, skipped)
    )
    assert "the proposal raises 3" in str(growth.violation(advancing, offer, overspent))
    assert growth.violation(advancing, offer, spent) is None

    draft = advancing.draft()
    _ = growth.advance(draft, spent)
    assert _sheet(draft.committed()).numbers["strength"] == held + 2


def test_the_ready_tag_opens_the_next_level_row() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    assert growth.offered(state) is None

    offer = growth.offered(ready(state))

    assert offer is not None
    assert offer.prompt.startswith("Fighter 2")
    # Action Surge is the whole of Fighter 2, and the row hands it over: nothing is on offer.
    assert (offer.options, offer.choose) == ((), 0)
    assert "Action Surge" in offer.text


def test_standing_at_a_scenario_milestone_opens_the_offer_without_the_tag() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    draft = state.draft()
    _ = draft.move(draft.world.require(PLAYER_ID), draft.world.require(EntityId("vault")))
    at_vault = draft.committed()

    assert growth.offered(at_vault) is not None

    leveled = at_vault.draft()
    mechanics = read(leveled)
    sheet_of(mechanics, leveled.player).numbers["level"] = 2
    write(leveled, mechanics)
    assert growth.offered(leveled) is None


def test_a_row_that_grants_and_offers_hands_over_its_features_and_asks_only_for_the_choice(
    tmp_path: Path,
) -> None:
    """Paladin 2 is the shape the level rows used to flatten: two features handed over and one
    fighting style out of four. The count rule is pinned here because it is the only reachable
    row that asks for a pick at all."""
    engine, state = dnd5e_game()
    growth = capability(engine)
    advancing = paladinly(state)
    offer = growth.offered(advancing)
    assert offer is not None
    assert offer.choose == 1
    assert DIVINE_SMITE not in offer.options
    assert {ref.index for ref in offer.options} == {
        f"fighting-style-{style}"
        for style in ("defense", "dueling", "great-weapon-fighting", "protection")
    }

    two = SWORN.model_copy(update={"picks": (DUELING, offer.options[0])})
    assert "exactly 1 picks" in str(
        growth.violation(advancing, offer, SWORN.model_copy(update={"picks": ()}))
    )
    assert "exactly 1 picks" in str(growth.violation(advancing, offer, two))
    assert growth.violation(advancing, offer, SWORN) is None

    game = dnd5e_session(tmp_path)
    game.state = paladinly(game.state)
    _ = game.apply_proposal(SWORN)

    player = sheet_of(read(game.state), game.state.player)
    assert DUELING in player.refs
    # Handed over by the row, named by no proposal.
    assert DIVINE_SMITE in player.refs


def test_a_pick_outside_the_offer_a_wrong_pick_count_and_an_ability_over_cap_are_refused() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    advancing = ready(state)
    offer = growth.offered(advancing)
    assert offer is not None

    over_cap = LevelUp(abilities={"strength": MAX_ABILITY + 1}, why="too much")

    assert growth.violation(advancing, offer, LEGAL) is None
    assert "not on offer" in str(growth.violation(advancing, offer, OUTSIDE))
    assert f"cannot pass {MAX_ABILITY}" in str(growth.violation(advancing, offer, over_cap))


def test_the_confirmed_level_up_commits_the_whole_level(tmp_path: Path) -> None:
    """The advisor's retry loop is engine-independent and covered by the story suite; this
    exercises what is 5e's own: `advance` writing the level onto the committed state."""
    game = dnd5e_session(tmp_path)
    game.state = ready(game.state)

    _ = game.apply_proposal(LEGAL)

    player = sheet_of(read(game.state), game.state.player)
    assert (player.numbers["level"], player.counters["hp"].maximum) == (2, 18)
    # The row's own grant, added by the engine: the proposal named no pick at all.
    assert ACTION_SURGE in player.refs
    assert game.state.player.trait(ADVANCEMENT_READY) is None
    assert game.offer() is None


def test_a_caster_level_up_offers_its_spells_and_lands_the_chosen_ones(tmp_path: Path) -> None:
    game = dnd5e_session(tmp_path)
    game.state = caster(game.state)
    offer = game.offer()
    assert offer is not None
    assert "Adds 2 spells" in offer.text
    assert f"Mage Armor [{MAGE_ARMOR}]" in offer.text

    _ = game.apply_proposal(CASTING)

    player = sheet_of(read(game.state), game.state.player)
    assert (SHIELD in player.refs, MAGE_ARMOR in player.refs) == (True, True)
    # The subclass picked this level brings its own row for the same level: Sculpt Spells is
    # handed over by `evocation-2`, which nothing could reach before the pick landed.
    assert (EVOCATION in player.refs, SCULPT_SPELLS in player.refs) == (True, True)
    # A wizard's spellbook size is prose, so no pack row counts it and no number claims to.
    assert (player.numbers[CANTRIPS_KNOWN], SPELLS_KNOWN in player.numbers) == (3, False)


def test_the_wrong_spell_count_an_unreachable_spell_and_a_non_caster_are_refused() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    advancing = caster(state)
    offer = growth.offered(advancing)
    fighter = ready(state)
    fighter_offer = growth.offered(fighter)
    assert offer is not None and fighter_offer is not None

    one_short = CASTING.model_copy(update={"spells": (SHIELD,)})
    doubled = CASTING.model_copy(update={"spells": (SHIELD, SHIELD)})
    above_slots = CASTING.model_copy(update={"spells": (SHIELD, FIREBALL)})
    fighter_spell = LEGAL.model_copy(update={"spells": (SHIELD,)})

    assert growth.violation(advancing, offer, CASTING) is None
    assert "exactly 2 spells" in str(growth.violation(advancing, offer, one_short))
    # Two of the same spell counts as two against the pool, and used to die inside `add_ref`.
    assert "is named twice" in str(growth.violation(advancing, offer, doubled))
    assert "not a spell this level adds" in str(growth.violation(advancing, offer, above_slots))
    assert "not a spell this level adds" in str(
        growth.violation(fighter, fighter_offer, fighter_spell)
    )


def test_a_spell_the_caster_already_knows_is_off_the_offer_and_refused_by_it() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    advancing = caster(state)
    offer = growth.offered(advancing)
    assert offer is not None
    assert f"[{MAGIC_MISSILE}]" not in offer.text

    known_again = CASTING.model_copy(update={"spells": (MAGIC_MISSILE, MAGE_ARMOR)})

    refused = str(growth.violation(advancing, offer, known_again))
    assert ("not a spell this level adds" in refused, "already holds" in refused) == (True, False)
