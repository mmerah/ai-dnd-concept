"""The vendored SRD pack, asserted as content — not as a shape.

A shape test is a false safety net here: an upstream rename of `attack_bonus` validates perfectly on
all 334 monsters and every goblin silently attacks at +0. These pin the corpus instead, and name the
genuine upstream defects in allowlists rather than summing them away."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from support import PACK_DIR, all_of, content, new_game, pack, ruleset

from aidm.agents import views
from aidm.agents.context import Scene
from aidm.content import ContentMiss, ContentRef, load, loaded, write_pack
from aidm.content.records import (
    ArmorRecord,
    BackgroundRecord,
    ClassLevelRecord,
    ClassRecord,
    ConditionRecord,
    EquipmentProficiency,
    FeatureRecord,
    GearRecord,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
    RaceRecord,
    Record,
    RecordOption,
    SaveProficiency,
    SkillProficiency,
    SpellRecord,
    SubclassLevelRecord,
    ToolRecord,
    TraitRecord,
    WeaponRecord,
)
from aidm.domain.models import (
    MAX_LEVEL,
    ActorEntity,
    Entity,
    EntityId,
    GameState,
    ItemEntity,
    Origin,
    updated,
)
from aidm.engine import bestiary
from aidm.engine.pack_ruleset import compile_ruleset
from aidm.utils import dice

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
    actor = ActorEntity(
        id=EntityId("rat"),
        name="a bloated rat",
        brief="Fat on the dead garden.",
        location_id=EntityId("cloister"),
        ref=ref("monsters", "giant-rat"),
    )
    statted = bestiary.statted(actor, RULES)
    assert isinstance(statted, ActorEntity) and statted.stats.ac == 12
    assert statted.name == "a bloated rat"  # the pack supplies numbers, the author the fiction


def test_an_entity_may_not_contradict_the_record_it_names() -> None:
    """Both are broken invariants, not content gaps: silently overwriting authored stats, or letting
    a lantern point at a monster, would put a lie in the save."""
    rat = ActorEntity(
        id=EntityId("rat"),
        name="a bloated rat",
        brief="Fat on the dead garden.",
        location_id=EntityId("cloister"),
        ref=ref("monsters", "giant-rat"),
    )
    with pytest.raises(ValueError, match="declares its own stats"):
        bestiary.statted(updated(rat, stats={"hp": 3, "max_hp": 7}), RULES)
    trophy = ItemEntity(
        id=EntityId("rat_tail"),
        name="a rat's tail",
        brief="Trophy.",
        ref=ref("monsters", "giant-rat"),
        container_id=EntityId("cloister"),
    )
    with pytest.raises(ValueError, match="may not name a monsters record"):
        bestiary.statted(trophy, RULES)


def _with(state: GameState, entity: Entity) -> GameState:
    world = updated(state.world, entities={**state.world.entities, entity.id: entity})
    return updated(state, world=world)


def test_a_world_naming_content_nothing_provides_is_unplayable(state: GameState) -> None:
    """A character's starting item is held, not placed, so it only reaches this check once the
    world is composed — which is why the composed world is statted, not the scenario definition."""
    held = state.world.entities[EntityId("lantern")]
    with pytest.raises(ValueError, match="nothing provides"):
        bestiary.statted_world(_with(state, updated(held, ref=ref("weapons", "phaser"))), RULES)


def test_the_directors_slice_is_the_mechanics_never_the_record() -> None:
    """A gargoyle record is thousands of bytes; this is the few hundred the Director can act on.
    Damage immunities and condition immunities stay apart: `poison` and `poisoned` are different
    words for different rules, and the prose entries carry commas of their own."""
    state = new_game("whispering_vault")
    gargoyle = bestiary.statted(
        ActorEntity(
            id=EntityId("gargoyle"),
            name="a crouching gargoyle",
            brief="Stone until it is not.",
            known=True,
            location_id=state.player.location_id,
            ref=ref("monsters", "gargoyle"),
        ),
        RULES,
    )
    assert isinstance(gargoyle, ActorEntity)
    under = updated(gargoyle, stats=updated(gargoyle.stats, conditions=("prone",)))
    shown = views.statblocks(Scene.of(_with(state, under)), RULES)
    assert shown.endswith(
        "- a crouching gargoyle[id=gargoyle] — ac 15 — under prone"
        " — Multiattack: Bite x1 + Claws x1; Bite +4 (1d6+2 piercing); Claws +4 (1d6+2 slashing)"
        " — resists bludgeoning, piercing, and slashing from nonmagical weapons"
        " that aren't adamantine"
        " — immune to poison"
        " — immune to the conditions exhaustion, petrified, poisoned"
    )
    assert "hp" not in shown  # `intent` reaches the Narrator


def test_a_condition_is_shown_on_anyone_who_holds_one() -> None:
    """A condition no role can read is one the Director can never lift. It comes from the entity,
    so it shows on an invented actor that names no record, and on the player's own sheet."""
    state = new_game("whispering_vault")
    mara = state.world.entities[EntityId("mara")]
    assert isinstance(mara, ActorEntity)
    blinded = updated(mara, stats=updated(mara.stats, conditions=("blinded",)))
    assert "Mara[id=mara] — ac 10 — under blinded" in views.statblocks(
        Scene.of(_with(state, blinded)), RULES
    )
    player = updated(state.player, stats=updated(state.player.stats, conditions=("prone",)))
    assert "under prone" in views.character(Scene.of(_with(state, player)), RULES)


def test_two_packs_cannot_claim_one_id() -> None:
    with pytest.raises(ValueError, match="same id"):
        load([PACK_DIR, PACK_DIR])


def test_a_level_record_is_a_class_one_or_a_subclass_one() -> None:
    """Discriminated rather than a bag of optionals: 50 of the 290 carry features and nothing else,
    and reading a missing `prof_bonus` as 0 would give a level-20 fighter a +0 to everything."""
    levels = list(LEVELS.values())
    assert sum(isinstance(x, ClassLevelRecord) for x in levels) == 240
    assert sum(isinstance(x, SubclassLevelRecord) for x in levels) == 50
    # The cumulative totals the level-up diff is taken between.
    fighter = [LEVELS[f"fighter-{n}"] for n in range(1, 7)]
    assert [x.ability_score_bonuses for x in fighter if isinstance(x, ClassLevelRecord)] == [
        0,
        0,
        0,
        1,
        1,
        2,
    ]


def test_every_class_grants_its_improvements_at_the_levels_5e_says() -> None:
    """A published defect, corrected at import: upstream's rogue totals *fall* at 11 —
    2,2,3,*2*,4 over levels 8-12 — and a level-up is the diff of two of them, so as published the
    pack said level 11 takes an improvement away and level 12 grants two. `scripts/srd/corrections`
    holds the fix; this asserts the whole corpus rather than the one record, because the next such
    defect will not be in the rogue."""
    extra = {"fighter": {6, 14}, "rogue": {10}}  # everyone else improves at 4, 8, 12, 16, 19 alone
    for klass in CLASSES:
        at = {4, 8, 12, 16, 19} | extra.get(klass, set())
        totals = [LEVELS[f"{klass}-{n}"] for n in range(1, MAX_LEVEL + 1)]
        assert [t.ability_score_bonuses for t in totals if isinstance(t, ClassLevelRecord)] == [
            sum(1 for level in at if level <= n) for n in range(1, MAX_LEVEL + 1)
        ]
    # What the defect cost: level 12 offered two improvements, and 11 and 13 offered none.
    rogue = Origin(class_ref=ref("classes", "rogue"))
    assert [RULES.level(rogue, n).improvements for n in range(8, 14)] == [1, 0, 1, 0, 1, 0]


def test_a_class_ladder_that_falls_is_refused_at_load_not_absorbed() -> None:
    """Why the defect was corrected rather than floored in the compiler: a pack whose totals fall is
    unplayable, and a level quietly offering nothing would hide it until a player got there."""
    fallen = updated(LEVELS["rogue-11"], ability_score_bonuses=2)
    broken = updated(PACK, records={**PACK.records, "levels": {**LEVELS, "rogue-11": fallen}})
    with pytest.raises(ValueError, match="rogue-11: ability score improvements fall from 3 to 2"):
        compile_ruleset(loaded([broken]))


def test_every_class_can_be_played_and_ships_one_subclass() -> None:
    """The SRD's stated gap: one subclass per class, chosen at the level it first grants
    something."""
    classes = list(CLASSES.values())
    assert len(classes) == 12
    assert all(
        record.subclass is not None and len(record.subclass.options) == 1 for record in classes
    )
    assert sum(1 for record in classes if record.spellcasting_ability) == 8
    subclass = CLASSES["cleric"].subclass
    assert subclass is not None and subclass.level == 1  # a cleric picks a domain at level 1


def test_a_choice_id_is_unique_pack_wide_and_every_option_resolves() -> None:
    """A saved character's decisions are keyed by these ids, so a collision would silently re-point
    a choice already made; a dangling option would be a pick that grants nothing."""
    ids = [choice.id for choice in CHOICES]
    assert len(ids) == len(set(ids)) == 41
    refs = [o.ref for c in CHOICES for o in c.options if isinstance(o, RecordOption)]
    assert len(refs) == 387
    assert not [str(r) for r in refs if CONTENT.resolves(r) is not None]


def test_only_an_expertise_choice_doubles_rather_than_grants() -> None:
    """Expertise offers every skill whether the character holds it or not, so a pick read as a grant
    would hand out a proficiency the pack never gave them. Nothing else in the pack doubles."""
    doubling = sorted(choice.id for choice in CHOICES if choice.effect == "double")
    assert doubling == [
        "bard-expertise-1-expertise",
        "bard-expertise-2-expertise",
        "rogue-expertise-1-expertise",
        "rogue-expertise-2-expertise",
    ]


def test_a_nested_choice_is_flattened_by_unioning_its_arms() -> None:
    """Exact wherever the arms spend the same number of picks. The monk's "one artisan's tool or one
    musical instrument" is one pick from 19 + 10; `rogue-expertise-1`'s "two skills, or one skill
    and thieves' tools" is two picks from 18 + 1. Disagreeing arms are refused by the importer."""
    tools = CLASSES["monk"].choices[1]
    assert (tools.choose, len(tools.options)) == (1, 29)
    (expertise,) = FEATURES["rogue-expertise-1"].choices
    assert (expertise.choose, len(expertise.options)) == (2, 19)


def test_a_proficiency_says_what_it_covers_rather_than_naming_a_category() -> None:
    """An `equipment_category` reference is expanded to its members at import, so a to-hit asks
    whether the weapon is in the set instead of re-deriving a category mid-turn."""
    kinds = [type(p).__name__ for p in PROFICIENCIES.values()]
    assert len(kinds) == 117
    assert kinds.count(EquipmentProficiency.__name__) == 93
    assert kinds.count(SkillProficiency.__name__) == 18
    assert kinds.count(SaveProficiency.__name__) == 6
    martial = PROFICIENCIES["martial-weapons"]
    assert isinstance(martial, EquipmentProficiency) and len(martial.equipment) == 23
