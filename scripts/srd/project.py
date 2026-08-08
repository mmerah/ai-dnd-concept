"""One upstream record becomes one typed pack record: mechanics land in typed fields, and each
record class renders the model's view and its facts from them, so this importer writes no prose
bags. A record reffed in multiplicity — a spell, a feature — must leave its projecting facts (an
int, in a projecting collection) out, or the keys collide on every sheet that refs it.

Over CLAUDE.md's 1000-line cap by decision: a one-shot, offline importer, run by hand, output
vendored. It is one projection per upstream type, not runtime code, and splitting it would only
scatter that correspondence."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from pydantic import TypeAdapter

from aidm.state.base import Slug
from aidm.state.dice import ConstantTerm, DiceExpr, DiceTerm, terms
from aidm.state.packs import ContentRef, Record

from . import upstream as up
from .interpret import (
    ABILITY_BY_ABBREVIATION,
    AbilityBonus,
    AbilityMinimum,
    ArmorRecord,
    BackgroundRecord,
    ClassRecord,
    Cost,
    FeatRecord,
    FeatureChoice,
    FeatureRecord,
    GearRecord,
    LanguageRecord,
    LevelRecord,
    MagicItemRecord,
    MonsterRecord,
    ProficiencyRecord,
    RaceRecord,
    Reach,
    SaveSuccess,
    SkillRecord,
    SpellAmount,
    SpellArea,
    SpellGrant,
    SpellRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
    VehicleRecord,
    WeaponRecord,
    to_slug,
    weapon_damage_note,
)

_SLOT_CREATIONS: TypeAdapter[list[up.SlotCreation]] = TypeAdapter(list[up.SlotCreation])

PACK_ID = "srd-2014"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
MAX_SPELL_LEVEL = 9
_MODIFIER_TERM = " + MOD"

type Options = Mapping[str, tuple[ContentRef, ...]]


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef(pack=PACK_ID, collection=collection, index=index)


def described(record: up.Described) -> Record:
    return Record(index=record.index, name=record.name, text=_prose(record.desc))


def monster(record: up.Monster) -> MonsterRecord:
    every_action = (*record.special_abilities, *record.actions, *record.legendary_actions)
    casting = _monster_spellcasting(record.special_abilities)
    spells, slots = _monster_spell_lists(casting)
    return MonsterRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            _line(
                f"{record.size} {record.type}, {record.alignment}.",
                f"AC {_armor_entries(record.armor_class)}, {record.hit_points} hp"
                f" ({record.hit_points_roll}).",
                _optional("Speed", _pairs(record.speed)),
                f"Challenge {_challenge(record.challenge_rating)} ({record.xp} XP),",
                f"proficiency bonus +{record.proficiency_bonus}.",
            ),
            _line(*(f"{name.upper()[:3]} {getattr(record, name)}." for name in ABILITIES)),
            _optional("Skills and saving throws", _proficiencies(record.proficiencies)),
            _optional("Damage vulnerabilities", ", ".join(record.damage_vulnerabilities)),
            _optional("Damage resistances", ", ".join(record.damage_resistances)),
            _optional("Damage immunities", ", ".join(record.damage_immunities)),
            _optional("Condition immunities", _names(record.condition_immunities)),
            _optional("Senses", _pairs(record.senses)),
            _optional("Languages", record.languages),
            _actions("", record.special_abilities),
            _actions("Actions", record.actions),
            _actions("Reactions", record.reactions),
            _actions("Legendary actions", record.legendary_actions),
            _prose(record.desc),
        ),
        tags=(
            to_slug(record.type),
            *((to_slug(record.subtype),) if record.subtype else ()),
            *(("hover",) if record.speed.get("hover") is True else ()),
            *(("legendary",) if record.legendary_actions else ()),
            *(
                ("blind-beyond-radius",)
                if "blind beyond" in str(record.senses.get("blindsight", ""))
                else ()
            ),
        ),
        armor_class=record.armor_class[0].value,
        hp=record.hit_points,
        xp=record.xp,
        proficiency_bonus=record.proficiency_bonus,
        **{name: getattr(record, name) for name in ABILITIES},
        proficiencies={entry.proficiency.index: entry.value for entry in record.proficiencies},
        speeds=_feet_numbers(record.speed),
        sense_ranges=_feet_numbers(record.senses),
        passive_perception=_passive_perception(record.senses),
        spell_save_dc=None if casting is None else casting.dc,
        spell_attack_bonus=None if casting is None else casting.modifier,
        attacks=tuple(_attack_lines(every_action)),
        multiattack=_multiattack(record.actions) or None,
        limited_use=_limited_use(every_action),
        damage_vulnerabilities=tuple(record.damage_vulnerabilities),
        damage_resistances=tuple(record.damage_resistances),
        damage_immunities=tuple(record.damage_immunities),
        condition_immunities=tuple(entry.name for entry in record.condition_immunities),
        forms=tuple(entry.index for entry in record.forms),
        spells=spells,
        slots=slots,
        size=record.size,
        challenge_rating=_challenge(record.challenge_rating),
    )


def _armor_entries(entries: Sequence[up.ArmorClass]) -> str:
    def one(entry: up.ArmorClass) -> str:
        detail = entry.spell or entry.condition
        named = _names(entry.armor) or (detail.name if detail else "")
        kind = entry.desc or (f"{entry.type}: {named}" if named else entry.type)
        return f"{entry.value} ({kind})"

    return ", ".join(one(entry) for entry in entries)


def _challenge(rating: float) -> str:
    return {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(rating, f"{rating:g}")


def _feet_numbers(values: Mapping[str, object]) -> Mapping[str, int]:
    """Distances written '40 ft.' become whole feet; anything else stays where it was."""
    found: dict[str, int] = {}
    for name, value in values.items():
        if not isinstance(value, str) or not value:
            continue
        head = value.split()[0]
        if head.isdigit() and value.endswith(("ft.", "this radius)")):
            found[_key(name)] = int(head)
    return found


def _passive_perception(senses: Mapping[str, str | int]) -> int | None:
    found = senses.get("passive_perception")
    return found if isinstance(found, int) else None


def _monster_spellcasting(abilities: Sequence[up.Action]) -> up.MonsterSpellcasting | None:
    return next((entry.spellcasting for entry in abilities if entry.spellcasting is not None), None)


def _monster_spell_lists(
    casting: up.MonsterSpellcasting | None,
) -> tuple[tuple[tuple[int, tuple[str, ...]], ...], tuple[tuple[int, int], ...]]:
    if casting is None:
        return (), ()
    by_level: dict[int, list[str]] = {}
    for known in casting.spells:
        by_level.setdefault(known.level, []).append(known.name)
    spells = tuple((level, tuple(names)) for level, names in sorted(by_level.items()))
    slots = tuple(
        (number, count)
        for number, count in sorted((int(at), count) for at, count in casting.slots.items())
        if count > 0
    )
    return spells, slots


def _multiattack(actions: Sequence[up.Action]) -> str:
    for action in actions:
        if action.actions:
            return " + ".join(f"{ref.count}x {ref.action_name}" for ref in action.actions)
        if action.action_options is not None:
            groups = [_action_group(option) for option in action.action_options.options.options]
            return " or ".join(group for group in groups if group)
    return ""


def _action_group(option: up.ActionRefOption) -> str:
    if option.items:
        return " + ".join(f"{item.count}x {item.action_name}" for item in option.items)
    if option.action_name:
        return f"{option.count or 1}x {option.action_name}"
    return ""


def _limited_use(actions: Sequence[up.Action]) -> tuple[str, ...]:
    parts = [
        f"{action.name}: {_usage(action.usage)}" for action in actions if action.usage is not None
    ]
    return tuple(dict.fromkeys(parts))


def _usage(usage: up.Usage) -> str:
    match usage.type:
        case "per day" if usage.times:
            return f"{usage.times}/day"
        case "recharge on roll" if usage.min_value and usage.dice:
            return f"recharge {usage.min_value}+ on {usage.dice}"
        case "recharge after rest":
            return "recharges after a rest"
        case "per rest" if usage.times:
            return f"{usage.times}/rest"
        case _:
            return usage.type


def spell(record: up.Spell) -> SpellRecord:
    kind = "cantrip" if record.level == 0 else f"level {record.level} spell"
    material = f" ({record.material})" if record.material else ""
    marks = [
        word
        for word, on in (("ritual", record.ritual), ("concentration", record.concentration))
        if on
    ]
    _spell_scales_as_rendered(record)
    cast_damage, damage_ladder = _amounts(_damage_rungs(record.damage))
    cast_heal, heal_ladder = _amounts(record.heal_at_slot_level)
    area = record.area_of_effect
    return SpellRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            _line(
                f"{record.school.name} {kind}.",
                f"Casting time: {record.casting_time}. Range: {record.range}.",
                f"Components: {', '.join(record.components)}{material}.",
                f"Duration: {record.duration}.",
                *(f"Requires {' and '.join(marks)}." for _ in marks[:1]),
            ),
            _prose(record.desc),
            "" if record.dc is None else record.dc.desc,
            _optional("**At higher levels**", _prose(record.higher_level)),
        ),
        tags=(*marks, *(COMPONENTS[part] for part in record.components if part in COMPONENTS)),
        level=None if record.level == 0 else record.level,
        school=to_slug(record.school.name),
        attack_type=_attack_type(record.attack_type),
        save_ability=None if record.dc is None else _ability(record.dc.dc_type.name),
        save_success=None if record.dc is None else _save_success(record.dc.dc_success),
        damage=cast_damage,
        damage_type=_spell_damage_type(record.damage, cast_damage),
        heal=cast_heal,
        scaling=damage_ladder or heal_ladder,
        concentration=record.concentration,
        area=None if area is None else SpellArea(shape=area.type, size=area.size),
        range=record.range,
        casting_time=record.casting_time,
        duration=record.duration,
        classes=tuple(entry.name for entry in record.classes),
        subclasses=tuple(entry.name for entry in record.subclasses),
    )


COMPONENTS = {"V": "verbal", "S": "somatic", "M": "material"}


def _spell_scales_as_rendered(record: up.Spell) -> None:
    """`SpellRecord.noted` derives the scaling step from `level`, so a rung keyed the other way
    must fail here, not render wrong."""
    damage = record.damage
    by_slot = bool(damage and damage.damage_at_slot_level) or bool(record.heal_at_slot_level)
    by_level = bool(damage and damage.damage_at_character_level)
    if record.level == 0 and by_slot:
        raise ValueError(f"cantrip {record.index!r} scales by slot")
    if record.level > 0 and by_level:
        raise ValueError(f"leveled spell {record.index!r} scales by character level")


def _attack_type(value: str) -> Literal["melee", "ranged"] | None:
    match value:
        case "":
            return None
        case "melee" | "ranged":
            return value
        case _:
            raise ValueError(f"spell attack type {value!r} is unknown")


def _save_success(value: str) -> SaveSuccess:
    match value:
        case "half" | "none" | "other":
            return value
        case _:
            raise ValueError(f"save outcome {value!r} is unknown")


def _spell_damage_type(damage: up.SpellDamage | None, base: SpellAmount | None) -> Slug | None:
    """Typed only beside dice: a spell whose damage lives in its text keeps the type there too."""
    if damage is None or base is None or damage.damage_type is None:
        return None
    return damage.damage_type.name.lower()


def _damage_rungs(damage: up.SpellDamage | None) -> Mapping[str, str]:
    if damage is None:
        return {}
    return damage.damage_at_slot_level or damage.damage_at_character_level


def _amounts(
    rungs: Mapping[str, str],
) -> tuple[SpellAmount | None, tuple[tuple[int, SpellAmount], ...]]:
    """The lowest rung is the spell as cast; the rest is the ladder it scales along."""
    ordered = sorted(rungs.items(), key=lambda rung: int(rung[0]))
    if not ordered:
        return None, ()
    return _amount(ordered[0][1]), tuple((int(at), _amount(dice)) for at, dice in ordered[1:])


def _amount(dice: str) -> SpellAmount:
    modified = dice.endswith(_MODIFIER_TERM)
    expression = dice[: -len(_MODIFIER_TERM)] if modified else dice
    if "MOD" in expression:
        raise ValueError(f"spell amount {dice!r} places its modifier where this importer cannot")
    return SpellAmount(dice=expression, with_modifier=modified)


def _ability(name: str) -> Slug:
    ability = ABILITY_BY_ABBREVIATION.get(name)
    if ability is None:
        raise ValueError(f"spell save against unknown ability {name!r}")
    return ability


def weapon(record: up.Equipment) -> WeaponRecord:
    # Every melee weapon carries `range.normal: 5` as baseline reach — even `reach` weapons —
    # so projecting it would misread as a ranged attack distance; `throw_range` is real either way.
    ranged = record.weapon_range == "Ranged"
    properties = {entry.index for entry in record.properties}
    if record.two_handed_damage is not None and "versatile" not in properties:
        raise ValueError(f"weapon {record.index!r} has two-handed damage but is not versatile")
    dice = _weapon_dice(record.damage)
    versatile = _weapon_dice(record.two_handed_damage) if "versatile" in properties else None
    kinds = _damage_type_tag(record)
    damage_type = kinds[0] if kinds else None
    return WeaponRecord(
        index=record.index,
        name=record.name,
        text=_equipment_text(
            record,
            f"{record.category_range} weapon.",
            _optional("Damage", weapon_damage_note(dice, damage_type, versatile)),
            _optional("Range", _range(record.range)) if ranged else "",
            _optional("Thrown range", _range(record.throw_range)),
            _optional("Properties", _names(record.properties)),
            after=_prose(record.special),
        ),
        tags=(
            *((record.weapon_range.lower(),) if record.weapon_range else ()),
            *kinds,
            *(entry.index for entry in record.properties),
        ),
        damage=dice,
        damage_type=damage_type,
        versatile_damage=versatile,
        ranged=ranged,
        finesse="finesse" in properties,
        cost=_cost_of(record.cost),
        range=_reach_of(record.range) if ranged else None,
        thrown=_reach_of(record.throw_range),
    )


def _weapon_dice(damage: up.Damage | None) -> DiceExpr | None:
    """The blowgun's flat `1` becomes one one-sided die, so one expression always spells the
    roll."""
    if damage is None or not damage.damage_dice:
        return None
    parsed = terms(damage.damage_dice)
    if len(parsed) != 1:
        raise ValueError(f"weapon damage {damage.damage_dice!r} is not a single term")
    match parsed[0]:
        case DiceTerm(count=count, faces=faces):
            return f"{count}d{faces}"
        case ConstantTerm(value=value):
            return f"{value}d1"


def _damage_type_tag(record: up.Equipment) -> tuple[str, ...]:
    kinds = {
        entry.damage_type.name.lower()
        for entry in (record.damage, record.two_handed_damage)
        if entry is not None and entry.damage_type is not None
    }
    if len(kinds) > 1:
        raise ValueError(f"weapon {record.index!r} deals {sorted(kinds)}: one tag cannot say it")
    return tuple(kinds)


def _reach_of(entry: up.Range | None) -> Reach | None:
    if entry is None:
        return None
    return Reach(normal=entry.normal, long=entry.long)


def _cost_of(cost: up.Quantity | None) -> Cost | None:
    return None if cost is None else Cost(unit=cost.unit, amount=_whole(cost, "cost"))


def armor(record: up.Equipment) -> ArmorRecord:
    value = record.armor_class
    if value is None:
        raise ValueError(f"armour {record.index!r} carries no armour class")
    shield = record.armor_category == "Shield"
    return ArmorRecord(
        index=record.index,
        name=record.name,
        text=_equipment_text(
            record,
            f"{record.armor_category} armour.",
            _armor_formula(record, value, shield=shield),
        ),
        tags=(
            *(("add-dex-modifier",) if value.dex_bonus else ()),
            *(("stealth-disadvantage",) if record.stealth_disadvantage else ()),
        ),
        cost=_cost_of(record.cost),
        base=value.base,
        shield=shield,
        dex_limit=value.max_bonus,
        strength_minimum=record.str_minimum or None,
    )


def _armor_formula(record: up.Equipment, value: up.ArmorValue, *, shield: bool) -> str:
    if shield:
        worn = f"AC +{value.base}."
    else:
        capped = "" if value.max_bonus is None else f" (max {value.max_bonus})"
        worn = f"AC {value.base}" + (f" + Dex modifier{capped}." if value.dex_bonus else ".")
    return _line(
        worn,
        f"Strength {record.str_minimum} required." if record.str_minimum else "",
        "Disadvantage on Stealth." if record.stealth_disadvantage else "",
    )


def gear(record: up.Equipment) -> GearRecord:
    bundle = record.quantity
    return GearRecord(
        index=record.index,
        name=record.name,
        text=_equipment_text(
            record,
            f"{_category(record)}.",
            "" if bundle is None else f"Bundle of {bundle}.",
            _optional("Capacity", record.capacity),
            _optional("Contents", _contained(record.contents)),
        ),
        cost=_cost_of(record.cost),
        quantity=bundle,
    )


def vehicle(record: up.Equipment) -> VehicleRecord:
    speed = "" if record.speed is None else f"Speed {record.speed.quantity:g} {record.speed.unit}."
    per_round, mph = _vehicle_speed(record.speed)
    return VehicleRecord(
        index=record.index,
        name=record.name,
        text=_equipment_text(
            record,
            f"{_category(record)}.",
            speed,
            _optional("Capacity", record.capacity),
        ),
        cost=_cost_of(record.cost),
        speed=per_round,
        speed_mph=mph,
        capacity_lb=_capacity_pounds(record.capacity),
    )


def _vehicle_speed(speed: up.Quantity | None) -> tuple[int | None, int | None]:
    """A mount's ft/round pace is the `speed` monsters and races carry; a ship's miles per hour is
    a different quantity, so it lands in its own field."""
    if speed is None:
        return None, None
    if speed.unit not in ("ft/round", "mph"):
        raise ValueError(f"vehicle speed unit {speed.unit!r} fits no speed field")
    # The rowboat's 1.5 mph is no integer; its speed stays on the text line.
    if speed.quantity != int(speed.quantity):
        return None, None
    whole = int(speed.quantity)
    return (whole, None) if speed.unit == "ft/round" else (None, whole)


def _capacity_pounds(capacity: str) -> int | None:
    head, _, tail = capacity.partition(" ")
    if tail != "lb." or not (weight := head.replace(",", "")).isdigit():
        return None
    return int(weight)


def _category(record: up.Equipment) -> str:
    """The finest category upstream gives: 'Arcane Foci' acts where 'Adventuring Gear' cannot."""
    finer = "" if record.gear_category is None else record.gear_category.name
    return (
        finer or record.tool_category or record.vehicle_category or record.equipment_category.name
    )


def _contained(contents: Sequence[up.Contained]) -> str:
    return ", ".join(f"{entry.item.name} x{entry.quantity}" for entry in contents)


def magic_item(record: up.MagicItem) -> MagicItemRecord:
    return MagicItemRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{record.equipment_category.name}, {record.rarity.name.lower()}.", _prose(record.desc)
        ),
        tags=("variant",) if record.variant else (),
        category=record.equipment_category.name,
        rarity=record.rarity.name,
        variants=tuple(entry.index for entry in record.variants),
    )


def race(record: up.Race) -> RaceRecord:
    languages = record.language_options
    picks = _choice_refs("languages", languages)
    return RaceRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            _line(
                f"{record.size} humanoid, speed {record.speed} ft.",
                _optional("Ability scores", _race_bonuses(record)),
            ),
            record.size_description,
            record.age,
            _line(
                _optional("Languages", _names(record.languages) + f". {record.language_desc}"),
                ""
                if languages is None
                else f"Choose {_plural(languages.choose, 'extra language')}.",
            ),
            _optional("Traits", _names(record.traits)),
            _optional("Subraces", _names(record.subraces)),
            _optional("Alignment", record.alignment),
        ),
        options=picks,
        choose=languages.choose if picks and languages is not None else None,
        speed=record.speed,
        size=record.size,
        ability_bonuses=tuple(
            AbilityBonus(ability=b.ability_score.name, bonus=b.bonus)
            for b in record.ability_bonuses
        ),
        floating_bonus_choose=(
            None if record.ability_bonus_options is None else record.ability_bonus_options.choose
        ),
    )


def _race_bonuses(record: up.Race) -> str:
    """Half-elf's floating +1s are structured as a choice, not fixed bonuses; both must show."""
    floating = record.ability_bonus_options
    extra = "" if floating is None else f"choose {floating.choose} others +1"
    return ", ".join(part for part in (_bonuses(record.ability_bonuses), extra) if part)


def subrace(record: up.Subrace) -> SubraceRecord:
    return SubraceRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"Subrace of {record.race.name}.",
            _prose(record.desc),
            _optional("Ability scores", _bonuses(record.ability_bonuses)),
            _optional("Traits", _names(record.racial_traits)),
        ),
        race=record.race.index,
        ability_bonuses=tuple(
            AbilityBonus(ability=bonus.ability_score.name, bonus=bonus.bonus)
            for bonus in record.ability_bonuses
        ),
    )


def background(record: up.Background) -> BackgroundRecord:
    feature = record.feature
    gold = record.starting_gold
    languages = (
        ""
        if record.language_options is None
        else f"Choose {_plural(record.language_options.choose, 'language')}."
    )
    return BackgroundRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            _line(_optional("Proficiencies", _names(record.starting_proficiencies)), languages),
            _line(
                _optional("Equipment", _carried(record.starting_equipment)),
                *(_category_choice(choice) for choice in record.starting_equipment_options),
                "" if gold is None else f"Starting gold: {gold.quantity:g} {gold.unit}.",
            ),
            "" if feature is None else _joined(f"**{feature.name}.**", _prose(feature.desc)),
            _roleplay_table("Personality traits", record.personality_traits),
            _roleplay_table("Ideals", record.ideals),
            _roleplay_table("Bonds", record.bonds),
            _roleplay_table("Flaws", record.flaws),
        ),
        starting_gold=None if gold is None else _whole(gold, "starting gold"),
    )


def _category_choice(choice: up.Choice) -> str:
    category = choice.options.equipment_category
    if category is None:
        return choice.desc
    return f"Choose {_plural(choice.choose, 'item')} from the {category.name} category."


def _roleplay_table(title: str, choice: up.Choice | None) -> str:
    if choice is None:
        return ""
    lines = [f"- {body}" for option in choice.options.options if (body := _roleplay_option(option))]
    return _joined(f"**{title}** (choose {choice.choose}):", "\n".join(lines))


def _roleplay_option(option: up.Option | str) -> str:
    if isinstance(option, str):
        return option
    body = option.string or option.desc
    if body and option.alignments:
        body += f" ({', '.join(entry.name for entry in option.alignments)})"
    return body


def klass(record: up.Class) -> ClassRecord:
    casting = record.spellcasting
    return ClassRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            _line(
                f"Hit die: d{record.hit_die}.",
                _optional("Saving throws", _names(record.saving_throws)),
                _optional("Spellcasting ability", _casting_ability(casting)),
            ),
            _optional("Proficiencies", _names(record.proficiencies)),
            _joined(*(choice.desc for choice in record.proficiency_choices)),
            _optional("Starting equipment", _carried(record.starting_equipment)),
            _joined(*(choice.desc for choice in record.starting_equipment_options)),
            _multiclassing(record.multi_classing),
            _optional("Subclasses", _names(record.subclasses)),
            *(
                _joined(f"**{entry.name}.**", _prose(entry.desc))
                for entry in (casting.info if casting else [])
            ),
        ),
        hit_die=record.hit_die,
        saving_throws=tuple(_ability(entry.name) for entry in record.saving_throws),
        spellcasting=None if casting is None else _ability(casting.spellcasting_ability.name),
    )


def _casting_ability(casting: up.Spellcasting | None) -> str:
    if casting is None:
        return ""
    since = "" if casting.level in (None, 1) else f" (from level {casting.level})"
    return casting.spellcasting_ability.name + since


def _multiclassing(rules: up.MultiClassing | None) -> str:
    if rules is None:
        return ""
    either = rules.prerequisite_options
    body = _line(
        _optional("Requires", _minima(rules.prerequisites)),
        "" if either is None else f"Requires {either.choose} of: {_option_minima(either)}.",
        _optional("Grants", _names(rules.proficiencies)),
        *(_multiclass_choice(choice) for choice in rules.proficiency_choices),
    )
    return _joined("**Multiclassing.**", body) if body else ""


def _multiclass_choice(choice: up.Choice) -> str:
    if choice.desc:
        return f"Choose {_plural(choice.choose, choice.desc)}."
    named = ", ".join(name for option in choice.options.options if (name := _option_name(option)))
    return _optional(f"Choose {choice.choose} of", named)


def _option_minima(choice: up.Choice) -> str:
    return " or ".join(
        f"{option.ability_score.name} {option.minimum_score}"
        for option in choice.options.options
        if not isinstance(option, str)
        and option.ability_score is not None
        and option.minimum_score is not None
    )


def subclass(record: up.Subclass) -> SubclassRecord:
    return SubclassRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{record.class_.name} {record.subclass_flavor.lower()}.", _prose(record.desc)
        ),
        klass=record.class_.index,
        spell_grants=tuple(
            SpellGrant(
                gate=", ".join(p.name for p in entry.prerequisites) or "always",
                spell=entry.spell.name,
                spell_index=entry.spell.index,
            )
            for entry in record.spells
        ),
    )


def skill(record: up.Skill) -> SkillRecord:
    return SkillRecord(
        index=record.index,
        name=record.name,
        text=_joined(f"{record.ability_score.name} skill.", _prose(record.desc)),
        ability=record.ability_score.name,
    )


def language(record: up.Language) -> LanguageRecord:
    return LanguageRecord(
        index=record.index,
        name=record.name,
        text=_line(
            f"{record.type} language.",
            _optional("Script", record.script),
            _optional("Typical speakers", ", ".join(record.typical_speakers)),
        ),
        category=record.type,
    )


def alignment(record: up.Alignment) -> Record:
    return Record(
        index=record.index,
        name=record.name,
        text=_joined(f"Abbreviated {record.abbreviation}.", _prose(record.desc)),
    )


def trait(record: up.Trait) -> TraitRecord:
    """Dragonborn breath weapons are the one trait with spell-grade structure; project it the
    way `spell` does, so the render carries the save, dice and ladder."""
    specific = record.trait_specific
    breath = None if specific is None else specific.breath_weapon
    entry = None if breath is None else next(iter(breath.damage), None)
    _breath_scales_as_rendered(record, entry)
    damage_type = specific.damage_type.name.lower() if specific and specific.damage_type else None
    _breath_damage_type_agrees(record, entry, damage_type)
    base, ladder = _amounts(_damage_rungs(entry))
    collection, choice = _trait_choice(record)
    picks = _choice_refs(collection, choice)
    dc = None if breath is None else breath.dc
    return TraitRecord(
        index=record.index,
        name=record.name,
        text=_prose(record.desc),
        options=picks,
        choose=choice.choose if picks and choice is not None else None,
        damage_type=damage_type,
        save_ability=None if dc is None else _ability(dc.dc_type.name),
        save_success=None if dc is None else _save_success(dc.success_type),
        damage=base,
        scaling=ladder,
        area=(
            None
            if breath is None or breath.area_of_effect is None
            else SpellArea(shape=breath.area_of_effect.type, size=breath.area_of_effect.size)
        ),
        uses=_usage(breath.usage) if breath is not None and breath.usage is not None else None,
        grants_proficiency=tuple(entry.name for entry in record.proficiencies),
        races=tuple(entry.name for entry in record.races),
        subraces=tuple(entry.name for entry in record.subraces),
        parent=record.parent.name if record.parent else None,
    )


def _breath_scales_as_rendered(record: up.Trait, entry: up.SpellDamage | None) -> None:
    """`TraitRecord.noted` renders the ladder with step 'level', so a breath weapon keyed by
    slot must fail here, not render wrong."""
    if entry is not None and entry.damage_at_slot_level:
        raise ValueError(f"trait {record.index!r} breath weapon scales by slot, not level")


def _breath_damage_type_agrees(
    record: up.Trait, entry: up.SpellDamage | None, damage_type: str | None
) -> None:
    """The damage note's suffix comes from the record's single `damage_type` field, so a breath
    entry naming a different type would render silently wrong."""
    if entry is None or entry.damage_type is None:
        return
    if damage_type is None or entry.damage_type.name.lower() != damage_type:
        raise ValueError(
            f"trait {record.index!r} breath damage type {entry.damage_type.name!r} "
            f"disagrees with damage-type {damage_type!r}"
        )


def _trait_choice(record: up.Trait) -> tuple[str, up.Choice | None]:
    """A trait offers at most one pick in this dataset: subtraits (draconic ancestry), cantrips
    (high elf), languages (extra language) or proficiencies (dwarven tools, half-elf skills)."""
    specific = record.trait_specific
    sources: tuple[tuple[str, up.Choice | None], ...] = (
        ("traits", specific.subtrait_options if specific else None),
        ("spells", specific.spell_options if specific else None),
        ("languages", record.language_options),
        ("proficiencies", record.proficiency_choices),
    )
    found = [(collection, choice) for collection, choice in sources if choice is not None]
    if len(found) > 1:
        raise ValueError(f"trait {record.index!r} carries {len(found)} choices; options fit one")
    return found[0] if found else ("", None)


def feat(record: up.Feat) -> FeatRecord:
    return FeatRecord(
        index=record.index,
        name=record.name,
        text=_joined(_optional("Prerequisite", _minima(record.prerequisites)), _prose(record.desc)),
        prerequisites=tuple(
            AbilityMinimum(ability=_ability(entry.ability_score.name), minimum=entry.minimum_score)
            for entry in record.prerequisites
        ),
    )


def _minima(entries: Sequence[up.Prerequisite]) -> str:
    return ", ".join(f"{entry.ability_score.name} {entry.minimum_score}" for entry in entries)


def proficiency(record: up.Proficiency) -> ProficiencyRecord:
    return ProficiencyRecord(
        index=record.index,
        name=record.name,
        text=f"{record.type} proficiency: {record.reference.name}.",
        category=record.type,
        reference=record.reference.index,
    )


def feature(record: up.Feature) -> FeatureRecord:
    owner = record.subclass or record.class_
    choice = subfeature_options(record)
    specific = record.feature_specific
    return FeatureRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{owner.name if owner else 'Feature'} feature, level {record.level}.",
            _prose(record.desc),
        ),
        options=choice,
        choose=1 if choice else None,
        level=record.level,
        requires=_feature_requires(record.prerequisites),
        pick=_feature_choice(specific),
        # Flat, not a `Choice`: how many a warlock knows is the level row's `invocations-known`.
        invocations=() if specific is None else tuple(entry.name for entry in specific.invocations),
        parent=record.parent.name if record.parent else None,
    )


def _feature_requires(entries: Sequence[up.FeaturePrerequisite]) -> tuple[str, ...]:
    def one(entry: up.FeaturePrerequisite) -> str:
        if entry.type == "level" and entry.level:
            return f"level {entry.level}"
        # Feature and spell prerequisites arrive as API paths; the tail is the index.
        return (entry.feature or entry.spell).rsplit("/", 1)[-1]

    return tuple(line for entry in entries if (line := one(entry)))


def _feature_choice(specific: up.FeatureSpecific | None) -> FeatureChoice | None:
    if specific is None:
        return None
    for what, choice in (
        ("skill proficiencies for expertise", specific.expertise_options),
        ("favored enemy", specific.enemy_type_options),
        ("favored terrain", specific.terrain_type_options),
    ):
        if choice is not None:
            among = tuple(
                name for option in choice.options.options if (name := _option_name(option))
            )
            return FeatureChoice(count=choice.choose, what=what, among=among)
    return None


def _option_name(option: up.Option | str) -> str:
    if isinstance(option, str):
        return option
    return option.string or (option.item.name if option.item else "")


def level(record: up.Level, options: Options) -> LevelRecord:
    owner = record.subclass or record.class_
    picks = tuple(
        pick
        for entry in record.features
        for pick in options.get(entry.index, (ref("features", entry.index),))
    )
    specific = {**record.class_specific, **record.subclass_specific}
    whole = _whole_numbers(specific)
    cantrips_known = count if (count := record.spellcasting.get("cantrips_known", 0)) > 0 else None
    spells_known = count if (count := record.spellcasting.get("spells_known", 0)) > 0 else None
    return LevelRecord(
        index=record.index,
        name=f"{owner.name} {record.level}",
        text=_joined(
            _line(
                f"{owner.name}, level {record.level}.",
                _optional(
                    "Proficiency bonus",
                    "" if record.prof_bonus is None else f"+{record.prof_bonus}",
                ),
            ),
            _optional("Features gained", _names(record.features)),
            _optional("Spell slots", _slots(record.spellcasting)),
            _optional("This level's numbers", _pairs(whole)),
        ),
        tags=tuple(
            _key(name)
            for name in ("wild_shape_fly", "wild_shape_swim")
            if specific.get(name) is True
        ),
        options=picks,
        choose=len(record.features) or None,
        level=record.level,
        proficiency_bonus=record.prof_bonus,
        cantrips_known=cantrips_known,
        spells_known=spells_known,
        ability_score_bonuses=record.ability_score_bonuses or None,
        slots=tuple(_slot_maxima(record.spellcasting)),
        class_numbers={_key(name): value for name, value in whole.items()},
        dice_ladders=_level_dice_ladders(specific),
        cr_caps=_level_cr_caps(specific),
        slot_creation=_level_slot_creation(specific),
        rage_count=_rage_count(specific),
    )


def _level_dice_ladders(specific: Mapping[str, object]) -> Mapping[str, DiceExpr]:
    ladders: dict[str, DiceExpr] = {}
    for name in ("sneak_attack", "martial_arts"):
        if isinstance(raw := specific.get(name), Mapping):
            dice = up.DieLadder.model_validate(raw)
            ladders[_key(name)] = f"{dice.dice_count}d{dice.dice_value}"
    return ladders


def _level_cr_caps(specific: Mapping[str, object]) -> Mapping[str, str]:
    caps: dict[str, str] = {}
    for name in ("wild_shape_max_cr", "destroy_undead_cr"):
        value = specific.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            caps[_key(name)] = _challenge(float(value))
    return caps


def _level_slot_creation(specific: Mapping[str, object]) -> tuple[tuple[int, int], ...]:
    """The sorcerer's slot-creation table: `_whole_numbers` cannot carry it, it is not a number."""
    ladder = specific.get("creating_spell_slots")
    if not (isinstance(ladder, list) and ladder):
        return ()
    rows = _SLOT_CREATIONS.validate_python(ladder)
    return tuple((row.spell_slot_level, row.sorcery_point_cost) for row in rows)


def subfeature_options(record: up.Feature) -> tuple[ContentRef, ...]:
    """The picks a feature that *is* a choice offers, as the level row's options flatten them."""
    specific = record.feature_specific
    return _choice_refs("features", None if specific is None else specific.subfeature_options)


# Upstream writes 9999 where a pool stops being counted (the barbarian's level-20 rages).
UNLIMITED = 9999
# These three collide with a same-named `str` fact built elsewhere in this module (`_level_cr_caps`,
# `_rage_count`): the int side would only ever cover a subset of the rows the string side covers.
_STR_ONLY = ("destroy_undead_cr", "wild_shape_max_cr", "rage_count")


def _whole_numbers(values: Mapping[str, object]) -> Mapping[str, int]:
    """Only the whole numbers: dice ladders, fractions and the `_STR_ONLY` fields go through
    `_level_dice_ladders`, `_level_cr_caps` and `_rage_count` instead."""
    return {
        name: value
        for name, value in values.items()
        if name not in _STR_ONLY
        and isinstance(value, int)
        and not isinstance(value, bool)
        and 0 < value != UNLIMITED
    }


def _rage_count(specific: Mapping[str, object]) -> str | None:
    value = specific.get("rage_count")
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return "unlimited" if value == UNLIMITED else str(value)


def _slot_maxima(spellcasting: Mapping[str, int]) -> Iterable[tuple[int, int]]:
    for number in range(1, MAX_SPELL_LEVEL + 1):
        count = spellcasting.get(f"spell_slots_level_{number}", 0)
        if count > 0:
            yield number, count


def _slots(spellcasting: Mapping[str, int]) -> str:
    return ", ".join(f"level {number} x{count}" for number, count in _slot_maxima(spellcasting))


def _equipment_text(record: up.Equipment, *lines: str, after: str = "") -> str:
    cost = "" if record.cost is None else f"Cost {record.cost.quantity:g} {record.cost.unit}."
    weight = "" if record.weight is None else f"Weight {record.weight:g} lb."
    return _joined(_line(*lines, cost, weight), _prose(record.desc), after)


def _attack_lines(actions: Sequence[up.Action]) -> Iterable[str]:
    """The to-hit and save lines a monster's turn runs on, extracted from its structured actions;
    riders and conditions stay in the record text."""
    for action in actions:
        dice = _damage_line(action.damage)
        if action.attack_bonus is not None:
            hit = f"{action.name} {action.attack_bonus:+d} to hit"
            yield f"{hit}, {dice}" if dice else hit
        elif action.dc is not None:
            yield _save_line(action.name, action.dc, dice)
        for attack in action.attacks:
            if attack.dc is not None:
                yield _save_line(attack.name, attack.dc, _damage_line(attack.damage))
        if action.options is not None:
            for option in action.options.options.options:
                if option.dc is not None:
                    yield _save_line(option.name, option.dc, _damage_line(option.damage))


def _damage_line(entries: Sequence[up.ActionDamage]) -> str:
    return " plus ".join(line for entry in entries if (line := _action_damage(entry)))


def _action_damage(entry: up.ActionDamage) -> str:
    if entry.choose is not None:
        return " or ".join(
            f"{line} ({option.notes.lower()})" if option.notes else line
            for option in entry.options.options
            if (line := _damage(option))
        )
    line = _damage(entry)
    if line and entry.dc is not None:
        half = ", half on save" if entry.dc.success_type == "half" else ""
        line += f" (DC {entry.dc.dc_value} {entry.dc.dc_type.name}{half})"
    return line


def _save_line(name: str, save: up.SaveDc, dice: str) -> str:
    half = ", half on save" if save.success_type == "half" else ""
    withdice = f", {dice}" if dice else ""
    return f"{name} DC {save.dc_value} {save.dc_type.name}{withdice}{half}"


def _choice_refs(collection: str, choice: up.Choice | None) -> tuple[ContentRef, ...]:
    if choice is None:
        return ()
    return tuple(
        ref(collection, option.item.index)
        for option in choice.options.options
        if not isinstance(option, str) and option.item is not None
    )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _whole(quantity: up.Quantity, what: str) -> int:
    if quantity.quantity != int(quantity.quantity):
        raise ValueError(f"{what} {quantity.quantity} {quantity.unit!r} is not a whole number")
    return int(quantity.quantity)


def _damage(damage: up.Damage | None) -> str:
    if damage is None or damage.damage_type is None:
        return ""
    return f"{damage.damage_dice} {damage.damage_type.name.lower()}"


def _range(entry: up.Range | None) -> str:
    if entry is None:
        return ""
    return f"{entry.normal} ft." if entry.long is None else f"{entry.normal}/{entry.long} ft."


def _bonuses(bonuses: Sequence[up.AbilityBonus]) -> str:
    return ", ".join(f"{bonus.ability_score.name} +{bonus.bonus}" for bonus in bonuses)


def _carried(carried: Sequence[up.Carried]) -> str:
    return ", ".join(f"{entry.equipment.name} x{entry.quantity}" for entry in carried)


def _proficiencies(entries: Sequence[up.MonsterProficiency]) -> str:
    return ", ".join(f"{entry.proficiency.name} {entry.value:+d}" for entry in entries)


def _actions(title: str, actions: Sequence[up.Action]) -> str:
    if not actions:
        return ""
    body = _joined(*(f"**{action.name}.** {action.desc}" for action in actions))
    return body if not title else _joined(f"**{title}**", body)


def _names(entries: Sequence[up.Label]) -> str:
    return ", ".join(entry.name for entry in entries)


def _pairs(values: Mapping[str, object]) -> str:
    return ", ".join(f"{name.replace('_', ' ')} {value}" for name, value in values.items())


def _key(name: str) -> str:
    return name.replace("_", "-")


def _prose(desc: list[str] | str) -> str:
    return desc if isinstance(desc, str) else "\n\n".join(desc)


def _optional(title: str, body: str) -> str:
    trimmed = body.strip().rstrip(".")
    return f"{title}: {trimmed}." if trimmed else ""


def _line(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def _joined(*blocks: str) -> str:
    return "\n\n".join(block for block in blocks if block)
