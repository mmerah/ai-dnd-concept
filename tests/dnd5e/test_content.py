from pathlib import Path

import pytest
from core_test_support import updated
from fivee_test_support import (
    PACK_DIR,
    actor_of,
    all_of,
    content,
    new_game,
    pack,
    player_of,
    ruleset,
)
from pydantic import ValidationError

from aidm.core.base import EntityId
from aidm.engines.dnd5e import bestiary, dice
from aidm.engines.dnd5e import presentation as views
from aidm.engines.dnd5e.content.library import ContentMiss, load, write_pack
from aidm.engines.dnd5e.content.records.base import ContentRef, Record
from aidm.engines.dnd5e.content.records.character import (
    BackgroundRecord,
    ClassRecord,
    FeatureRecord,
    RaceRecord,
    SaveProficiency,
    SubclassRecord,
    TraitRecord,
)
from aidm.engines.dnd5e.content.records.equipment import (
    ArmorRecord,
    GearRecord,
    ToolRecord,
    WeaponRecord,
)
from aidm.engines.dnd5e.content.records.monsters import (
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
)
from aidm.engines.dnd5e.content.records.rules import ConditionRecord
from aidm.engines.dnd5e.content.records.spells import SpellRecord
from aidm.engines.dnd5e.state import Dnd5eActorDefinition, Dnd5eItemDefinition, StatBlock

PACK_ID = "srd-2014"
CONTENT = content()
RULES = ruleset()
PACK = pack()
MONSTERS = list(all_of(PACK, "monsters", MonsterRecord).values())
WEAPONS = list(all_of(PACK, "weapons", WeaponRecord).values())
ARMOR = list(all_of(PACK, "armor", ArmorRecord).values())
SPELLS = list(all_of(PACK, "spells", SpellRecord).values())
CLASSES = all_of(PACK, "classes", ClassRecord)
FEATURES = all_of(PACK, "features", FeatureRecord)
LEVELS = all_of(PACK, "levels", Record)  # two arms; told apart by isinstance below
PROFICIENCIES = all_of(PACK, "proficiencies", Record)
CHOICES = [
    choice
    for records in (
        CLASSES,
        FEATURES,
        all_of(PACK, "races", RaceRecord),
        all_of(PACK, "traits", TraitRecord),
        all_of(PACK, "backgrounds", BackgroundRecord),
    )
    for record in records.values()
    for choice in record.choices
]

# Upstream data defects, named so they fail loudly if their number changes.
NO_DAMAGE = {"net"}  # a weapon that only restrains
NO_PROPERTIES = {"flail", "morningstar", "war-pick"}  # plain martial melee, nothing to declare
NO_ACTIONS = {"frog", "sea-horse", "shrieker", "vampire-mist"}
# Two damage types in one string with a single `damage_type` field: a sum-of-terms parser gets the
# total right and the type wrong, which is invisible until resistances matter.
TWO_TYPES_IN_ONE_STRING = {"flame-strike", "ice-storm", "meteor-swarm"}
# Multiattacks whose repeat count is not a number — 'Number of Heads', '1d4'. They stay prose
# rather than being defaulted to one attack.
UNCOUNTABLE_MULTIATTACK = {"hydra", "violet-fungus"}


def ref(collection: str, index: str, pack: str = PACK_ID) -> ContentRef:
    return ContentRef.model_validate({"pack": pack, "collection": collection, "index": index})


def test_a_record_is_addressed_by_pack_collection_and_index() -> None:
    """`shield` is an Equipment *and* a Spell — one of 79 cross-collection collisions in this pack
    alone, which is why an index alone could never be the identity."""
    armor = CONTENT.get(ref("armor", "shield"), ArmorRecord)
    spell = CONTENT.get(ref("spells", "shield"), SpellRecord)
    assert not isinstance(armor, ContentMiss) and armor.base_ac == 2
    assert not isinstance(spell, ContentMiss) and spell.level == 1


def test_an_unresolved_ref_is_a_value_with_a_reason() -> None:
    """A turn-time miss must degrade visibly: raising would let the pipeline eat the move."""
    misses = [
        CONTENT.get(ref("monsters", "tarrasque-of-the-second-edition"), MonsterRecord),
        CONTENT.get(ref("monsters", "goblin", pack="homebrew"), MonsterRecord),
        CONTENT.get(ref("monsters", "goblin"), SpellRecord),  # right index, wrong collection
        CONTENT.get(ref("proficiencies", "skill-arcana"), SaveProficiency),  # wrong arm
    ]
    assert [m.reason for m in misses if isinstance(m, ContentMiss)] == [
        "unknown_index",
        "unknown_pack",
        "wrong_collection",
        "wrong_type",
    ]


def test_a_collection_is_reachable_the_moment_its_record_class_exists() -> None:
    """The drift this replaced: `Pack` carried 22 collections and the lookup exposed 14 accessors,
    so eight — tools and conditions among them — loaded, validated and were reachable by nothing.
    One registry row is what makes a collection exist now, so the two cannot disagree."""
    tools = CONTENT.get(ref("tools", "thieves-tools"), ToolRecord)
    assert not isinstance(tools, ContentMiss) and tools.tool_category == "Other Tools"
    blinded = CONTENT.get(ref("conditions", "blinded"), ConditionRecord)
    assert not isinstance(blinded, ContentMiss) and blinded.desc
    with pytest.raises(ValueError, match="unknown_index"):
        CONTENT.require(ref("tools", "sonic-screwdriver"), ToolRecord)


def test_the_manifest_counts_every_collection_the_pack_ships() -> None:
    """Twenty-two collections, and the count is what catches a half-written one — the failure a
    shape test cannot see."""
    assert PACK.manifest.provides == {
        "monsters": 334,
        "weapons": 37,
        "armor": 13,
        "gear": 116,
        "tools": 31,
        "vehicles": 40,
        "magic_items": 362,
        "spells": 319,
        "skills": 18,
        "conditions": 15,
        "alignments": 9,
        "languages": 16,
        "classes": 12,
        "subclasses": 12,
        "levels": 290,
        "features": 407,
        "races": 9,
        "subraces": 4,
        "traits": 38,
        "backgrounds": 1,
        "feats": 1,
        "proficiencies": 117,
    }
    with pytest.raises(ValidationError, match="promises 334 monsters"):
        updated(PACK, records={**PACK.records, "monsters": {}})


def test_a_loaded_pack_writes_back_byte_for_byte(tmp_path: Path) -> None:
    """`scripts/srd/corrections` calls byte-identical round-trip the importer's regression check,
    but that check is a manual re-import against an external 5e-database checkout. This is the
    automated one: nothing else stands between a change to the pack shape and silent corruption."""
    write_pack(tmp_path, PACK)
    source = PACK_DIR
    written = sorted(path.name for path in tmp_path.iterdir())
    assert written == sorted(path.name for path in source.iterdir())
    for name in written:
        assert (tmp_path / name).read_bytes() == (source / name).read_bytes(), name


def test_each_collection_is_validated_by_its_own_spec() -> None:
    """What the routing buys: `monsters.json` cannot hold a level record, and a collection no
    registry row names cannot load at all. Without it every record would be validated against the
    bare `Record` base, which declares two fields."""
    fighter = LEVELS["fighter-1"]
    with pytest.raises(ValidationError, match="instance of MonsterRecord"):
        updated(PACK, records={**PACK.records, "monsters": {"fighter-1": fighter}})
    with pytest.raises(ValidationError, match="nonsense"):
        updated(PACK, records={**PACK.records, "nonsense": {}})


def test_a_pack_survives_being_dumped_and_revalidated() -> None:
    """`updated()` round-trips through `model_dump`, so a record must keep the fields its own class
    declares rather than the base's two — the failure that would make every edit lossy."""
    goblin = all_of(updated(PACK), "monsters", MonsterRecord)["goblin"]
    assert goblin.hit_points == 7 and len(goblin.actions) == 2


def test_a_gap_must_be_declared_rather_than_left_out() -> None:
    """A count of 0 is how a pack says "this ships no backgrounds" up front. Silence could not
    carry that, so silence is refused."""
    counted = {name: c for name, c in PACK.manifest.provides.items() if name != "languages"}
    with pytest.raises(ValidationError, match=r"no count for \['languages'\]"):
        updated(PACK, manifest=updated(PACK.manifest, provides=counted))


def test_a_loaded_record_cannot_be_edited() -> None:
    """The packs are loaded once, so every turn shares one record object: `frozen=True` guards a
    model's fields but not a dict inside one, and an edit here would outlive the turn that made
    it."""
    goblin = CONTENT.get(ref("monsters", "goblin"), MonsterRecord)
    fireball = CONTENT.get(ref("spells", "fireball"), SpellRecord)
    assert not isinstance(goblin, ContentMiss) and not isinstance(fireball, ContentMiss)
    assert fireball.damage is not None
    for keyed in (goblin.saving_throws, goblin.skills, fireball.damage.at_slot_level):
        with pytest.raises(TypeError):
            keyed["anything"] = 1  # pyright: ignore[reportIndexIssue, reportArgumentType]


def test_every_weapon_deals_damage_and_declares_how_it_is_wielded() -> None:
    """R6a kept `two_handed_damage` — the consequence — and dropped `versatile`, its precondition.
    Finesse, thrown and reach are unresolvable without the properties too."""
    assert {w.index for w in WEAPONS if w.damage is None} == NO_DAMAGE
    assert {w.index for w in WEAPONS if not w.properties} == NO_PROPERTIES
    versatile = {w.index for w in WEAPONS if "versatile" in w.properties}
    assert versatile == {w.index for w in WEAPONS if w.two_handed_damage is not None}
    assert {w.index for w in WEAPONS if w.throw_range is not None} == {
        w.index for w in WEAPONS if "thrown" in w.properties
    }


def test_every_armor_carries_the_fields_the_importer_must_not_default() -> None:
    """All three are optional upstream only because one type covers 237 records; a `or 0` would arm
    plate at Strength 0 and validate perfectly."""
    assert {a.index: a.str_minimum for a in ARMOR if a.str_minimum} == {
        "chain-mail": 13,
        "splint-armor": 15,
        "plate-armor": 15,
    }
    assert sum(a.stealth_disadvantage for a in ARMOR) == 7
    assert sum(a.max_dex_bonus is not None for a in ARMOR) == 5


def test_an_item_entity_has_something_to_point_at() -> None:
    """The scenario's lantern was refless because gear did not exist; all five item collections do
    now, and `bestiary` lets an item name any of them."""
    lantern = CONTENT.get(ref("gear", "lantern-hooded"), GearRecord)
    assert not isinstance(lantern, ContentMiss) and str(lantern.cost) == "5 gp"
    pack = CONTENT.get(ref("gear", "burglars-pack"), GearRecord)
    assert not isinstance(pack, ContentMiss) and len(pack.contents) == 14


def test_every_monster_can_act() -> None:
    assert {m.index for m in MONSTERS if not m.actions} == NO_ACTIONS


def test_every_action_is_an_attack_a_save_a_multiattack_or_named_prose() -> None:
    """The counts are the corpus: a renamed `attack_bonus` upstream would move 534 attacks into
    prose instead of validating silently. R6a projected 227 of these as prose; typing multiattack
    and flattening the dragons' two-breath entries into saves leaves 61."""
    actions = [a for m in MONSTERS for a in m.actions]
    counted = {
        "attack": sum(isinstance(a, MonsterAttack) for a in actions),
        "save": sum(isinstance(a, MonsterSave) for a in actions),
        "multiattack": sum(isinstance(a, MonsterMultiattack) for a in actions),
        "procedure": sum(isinstance(a, MonsterProcedure) for a in actions),
    }
    assert counted == {"attack": 534, "save": 120, "multiattack": 146, "procedure": 61}
    assert {
        m.index
        for m in MONSTERS
        for a in m.actions
        if a.name == "Multiattack" and isinstance(a, MonsterProcedure)
    } == UNCOUNTABLE_MULTIATTACK


def test_a_dragons_breath_is_limited_and_typed() -> None:
    """One upstream entry holds two breaths behind one recharge. Without `usage` the breath is
    unlimited, which is a different monster; without the flattening both breaths are prose."""
    dragon = CONTENT.get(ref("monsters", "adult-brass-dragon"), MonsterRecord)
    assert not isinstance(dragon, ContentMiss)
    breaths = [a for a in dragon.actions if a.name.startswith("Breath Weapons")]
    assert [b.name for b in breaths] == [
        "Breath Weapons: Fire Breath",
        "Breath Weapons: Sleep Breath",
    ]
    fire = breaths[0]
    assert isinstance(fire, MonsterSave)
    assert (fire.dc, fire.save_ability, fire.on_success) == (18, "dexterity", "half")
    assert all(str(b.usage) == "recharge 5+ on 1d6" for b in breaths)
    with_usage = sum(1 for m in MONSTERS for a in m.actions if a.usage is not None)
    assert with_usage == 107


def test_the_action_economy_r6a_dropped_is_projected() -> None:
    """Each of these was discarded, not absent. `saving_throw()` is unbuildable without the
    proficiencies, and `apply_condition` does nothing useful without the immunities."""
    assert sum(len(m.legendary_actions) for m in MONSTERS) == 99
    assert sum(1 for m in MONSTERS if m.legendary_actions) == 32
    assert sum(len(m.reactions) for m in MONSTERS) == 12
    assert sum(len(m.condition_immunities) for m in MONSTERS) == 339
    assert sum(len(m.saving_throws) + len(m.skills) for m in MONSTERS) == 714
    assert sum(1 for m in MONSTERS if m.spellcasting) == 36


def test_a_monsters_own_spells_resolve_to_records() -> None:
    """Upstream carries `{name, level, url}` with no index at all, so a dangling ref here would
    mean the url was misread — the one reference this pack reconstructs rather than reads."""
    spells = [s for m in MONSTERS if m.spellcasting for s in m.spellcasting.spells]
    assert len(spells) == 313
    assert not [s.ref for s in spells if CONTENT.resolves(s.ref) is not None]


def test_a_monsters_traits_keep_their_mechanics() -> None:
    """The balor's Death Throes is a DC 20 save for 20d6 fire, flattened to a string before R6b."""
    balor = CONTENT.get(ref("monsters", "balor"), MonsterRecord)
    assert not isinstance(balor, ContentMiss)
    (throes,) = [t for t in balor.traits if t.name == "Death Throes"]
    assert isinstance(throes, MonsterSave)
    assert (throes.dc, throes.save_ability) == (20, "dexterity")
    assert [(d.dice, d.damage_type) for d in throes.damage] == [("20d6", "fire")]


def _scaling(spell: SpellRecord) -> list[str]:
    """Every dice expression a spell scales by, whether by slot level or by character level."""
    if spell.damage is None:
        return []
    return [*spell.damage.at_slot_level.values(), *spell.damage.at_character_level.values()]


def test_a_scaling_value_carries_one_damage_type() -> None:
    """One record, one `damage_type`: a value holding two dice groups is holding two types."""
    multi = {
        spell.index
        for spell in SPELLS
        for expression in _scaling(spell)
        if sum(isinstance(t, dice.DiceTerm) for t in dice.terms(expression)) > 1
    }
    assert multi == TWO_TYPES_IN_ONE_STRING


def test_every_spell_names_the_classes_that_may_cast_it() -> None:
    """Without this, nothing could say which class casts which spell and `cast` had no gate at all.
    `subclasses` is not decoration: 132 entries add a spell to a class whose own list omits it —
    Fireball to a Fiend warlock, Beacon of Hope to a Devotion paladin."""
    listed = {klass for spell in SPELLS for klass in spell.classes}
    assert listed == {record.index for record in CLASSES.values() if record.spellcasting}
    fireball = CONTENT.get(ref("spells", "fireball"), SpellRecord)
    assert not isinstance(fireball, ContentMiss)
    assert fireball.classes == ("sorcerer", "wizard") and "fiend" in fireball.subclasses
    expanded = {
        (spell.index, subclass)
        for spell in SPELLS
        for subclass in spell.subclasses
        if all_of(PACK, "subclasses", SubclassRecord)[subclass].class_index not in spell.classes
    }
    assert len(expanded) == 132


def test_a_class_declares_how_its_slots_come_back() -> None:
    """Upstream states the recharge only in the "Spell Slots" prose. Pact Magic returns on a short
    rest and every other list on a long one, and the slots themselves carry no such field."""
    recharges = {
        index: record.spellcasting.slot_recharge
        for index, record in CLASSES.items()
        if record.spellcasting is not None
    }
    assert {index for index, rest in recharges.items() if rest == "short"} == {"warlock"}
    assert len(recharges) == 8


def test_a_monster_is_snapshotted_into_an_entity_not_read_live() -> None:
    """The numbers the reducer touches are copied in at creation; a pack bump must not be able to
    move a saved actor's hit points, nor make a devil newly poisonable."""
    goblin = RULES.archetype(ref("monsters", "goblin"))
    assert goblin is not None
    stats = goblin.stats
    assert (stats.ac, stats.hp, stats.max_hp, stats.attributes["strength"]) == (15, 7, 7, 8)
    zombie = RULES.archetype(ref("monsters", "zombie"))
    assert zombie is not None and zombie.stats.condition_immunities == ("poisoned",)
    # Every to-hit in the economy and nothing without one: the Director's swings resolve off these.
    assert [(a.name, a.to_hit, a.damage) for a in goblin.attacks] == [
        ("Scimitar", 4, "1d6+2"),
        ("Shortbow", 4, "1d6+2"),
    ]


def test_an_authored_actor_is_statted_from_the_record_it_names() -> None:
    authored = Dnd5eActorDefinition(ref=ref("monsters", "giant-rat"))
    statted = bestiary.statted_actor(EntityId("rat"), authored.model_dump(mode="json"), RULES)
    assert statted.stats.ac == 12  # the pack supplies numbers, the author the fiction


def test_an_entity_may_not_contradict_the_record_it_names() -> None:
    """Both are broken invariants, not content gaps: silently overwriting authored stats, or letting
    a lantern point at a monster, would put a lie in the save."""
    giant_rat = ref("monsters", "giant-rat")
    own_stats = Dnd5eActorDefinition(ref=giant_rat, stats=StatBlock(hp=3, max_hp=7))
    with pytest.raises(ValueError, match="declares its own stats"):
        bestiary.statted_actor(EntityId("rat"), own_stats.model_dump(mode="json"), RULES)
    with pytest.raises(ValueError, match="may not name a monsters record"):
        item_def = Dnd5eItemDefinition(ref=giant_rat)
        bestiary.statted_item(EntityId("rat_tail"), item_def.model_dump(mode="json"), RULES)


def test_content_nothing_provides_is_unplayable() -> None:
    """A character's starting item is held, not placed, so it only reaches this check when the
    engine state is composed — which is why the composed world is statted, not the definition."""
    phaser = Dnd5eItemDefinition(ref=ref("weapons", "phaser"))
    with pytest.raises(ValueError, match="nothing provides"):
        bestiary.statted_item(EntityId("lantern"), phaser.model_dump(mode="json"), RULES)


def test_the_directors_slice_is_the_mechanics_never_the_record() -> None:
    """A gargoyle record is thousands of bytes; this is the few hundred the Director can act on.
    Damage immunities and condition immunities stay apart: `poison` and `poisoned` are different
    words for different rules, and the prose entries carry commas of their own."""
    authored = Dnd5eActorDefinition(ref=ref("monsters", "gargoyle"))
    gargoyle = bestiary.statted_actor(EntityId("gargoyle"), authored.model_dump(mode="json"), RULES)
    under = updated(gargoyle, stats=updated(gargoyle.stats, conditions=("prone",)))
    shown = views.actor_summary(under.stats, under.ref, RULES)
    assert shown == (
        "hp 52/52 — ac 15 — under prone"
        " — attributes strength 15, dexterity 11, constitution 16, intelligence 6,"
        " wisdom 11, charisma 7"
        " — immune to the conditions exhaustion, petrified, poisoned"
        " — Multiattack: Bite x1 + Claws x1; Bite +4 (1d6+2 piercing); Claws +4 (1d6+2 slashing)"
        " — resists bludgeoning, piercing, and slashing from nonmagical weapons"
        " that aren't adamantine"
        " — immune to poison"
    )


def test_a_condition_is_shown_on_anyone_who_holds_one() -> None:
    """A condition no role can read is one the Director can never lift. It comes from the entity,
    so it shows on an invented actor that names no record, and on the player's own sheet."""
    state = new_game()
    mara = actor_of(state, EntityId("mara"))
    blinded = updated(mara.state, stats=updated(mara.stats, conditions=("blinded",)))
    assert "hp 4/4 — ac 10 — under blinded" in views.actor_summary(
        blinded.stats,
        blinded.ref,
        RULES,
    )
    player = player_of(state)
    prone = updated(player.stats, conditions=("prone",))
    assert "under prone" in views.player_state(prone, player.progression, RULES)


def test_two_packs_cannot_claim_one_id() -> None:
    with pytest.raises(ValueError, match="same id"):
        load([PACK_DIR, PACK_DIR])
