"""One upstream record becomes one `LenientRecord`. Numbers land on the sheet of any entity that
refs the record, so only records that back one entity — monsters, equipment, a character's single
class — carry them; a spell reffed five times would collide. Notes and tags never touch a sheet:
they render beside the ref, so every record may carry its mechanics there."""

from collections.abc import Iterable, Mapping, Sequence

from pydantic import TypeAdapter

from aidm.state.dice import ConstantTerm, DiceTerm, terms
from aidm.state.packs import ContentRef, LenientRecord

from . import upstream as up

_SLOT_CREATIONS: TypeAdapter[list[up.SlotCreation]] = TypeAdapter(list[up.SlotCreation])

PACK_ID = "srd-2014"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
MAX_SPELL_LEVEL = 9

type Options = Mapping[str, tuple[ContentRef, ...]]


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef(pack=PACK_ID, collection=collection, index=index)


def described(record: up.Described) -> LenientRecord:
    return LenientRecord(index=record.index, name=record.name, text=_prose(record.desc))


def monster(record: up.Monster) -> LenientRecord:
    every_action = (*record.special_abilities, *record.actions, *record.legendary_actions)
    return LenientRecord(
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
        numbers={
            "armor-class": record.armor_class[0].value,
            "hp": record.hit_points,
            "xp": record.xp,
            "proficiency-bonus": record.proficiency_bonus,
            **{name: getattr(record, name) for name in ABILITIES},
            **{entry.proficiency.index: entry.value for entry in record.proficiencies},
            **_feet_numbers("speed-", record.speed),
            **_feet_numbers("", record.senses),
            **_passive_perception(record.senses),
            **_monster_spellcasting(record.special_abilities),
        },
        notes={
            **_noted("attacks", "; ".join(_attack_lines(every_action))),
            **_noted("multiattack", _multiattack(record.actions)),
            **_noted("limited-use", _limited_use(every_action)),
            **_noted("damage-vulnerabilities", ", ".join(record.damage_vulnerabilities)),
            **_noted("damage-resistances", ", ".join(record.damage_resistances)),
            **_noted("damage-immunities", ", ".join(record.damage_immunities)),
            **_noted("condition-immunities", _names(record.condition_immunities)),
            # Form names carry commas of their own ('Vampire, Bat Form'), so join on semicolons.
            **_noted("forms", "; ".join(entry.name for entry in record.forms)),
            **_monster_spell_notes(record.special_abilities),
            "size": record.size,
            "challenge-rating": _challenge(record.challenge_rating),
        },
        tags=(
            _slug(record.type),
            *((_slug(record.subtype),) if record.subtype else ()),
            *(("hover",) if record.speed.get("hover") is True else ()),
            *(("legendary",) if record.legendary_actions else ()),
            *(
                ("blind-beyond-radius",)
                if "blind beyond" in str(record.senses.get("blindsight", ""))
                else ()
            ),
        ),
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


def _feet_numbers(prefix: str, values: Mapping[str, object]) -> Mapping[str, int]:
    """Distances written '40 ft.' become whole feet; anything else stays where it was."""
    found: dict[str, int] = {}
    for name, value in values.items():
        if not isinstance(value, str) or not value:
            continue
        head = value.split()[0]
        if head.isdigit() and value.endswith(("ft.", "this radius)")):
            found[f"{prefix}{_key(name)}"] = int(head)
    return found


def _passive_perception(senses: Mapping[str, str | int]) -> Mapping[str, int]:
    found = senses.get("passive_perception")
    return {"passive-perception": found} if isinstance(found, int) else {}


def _monster_spellcasting(abilities: Sequence[up.Action]) -> Mapping[str, int]:
    for entry in abilities:
        casting = entry.spellcasting
        if casting is not None:
            return {
                **({} if casting.dc is None else {"spell-save-dc": casting.dc}),
                **({} if casting.modifier is None else {"spell-attack-bonus": casting.modifier}),
            }
    return {}


def _monster_spell_notes(abilities: Sequence[up.Action]) -> Mapping[str, str]:
    for entry in abilities:
        casting = entry.spellcasting
        if casting is None:
            continue
        by_level: dict[int, list[str]] = {}
        for known in casting.spells:
            by_level.setdefault(known.level, []).append(known.name)
        spells = "; ".join(
            f"{'cantrips' if level == 0 else f'level {level}'}: {', '.join(names)}"
            for level, names in sorted(by_level.items())
        )
        slots = ", ".join(
            f"level {number} x{count}"
            for number, count in sorted((int(at), count) for at, count in casting.slots.items())
            if count > 0
        )
        return {**_noted("spells", spells), **_noted("slots", slots)}
    return {}


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


def _limited_use(actions: Sequence[up.Action]) -> str:
    parts = [
        f"{action.name}: {_usage(action.usage)}" for action in actions if action.usage is not None
    ]
    return "; ".join(dict.fromkeys(parts))


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


def _slug(name: str) -> str:
    return "-".join(part for part in name.lower().replace(",", " ").split() if part)


def spell(record: up.Spell) -> LenientRecord:
    kind = "cantrip" if record.level == 0 else f"level {record.level} spell"
    material = f" ({record.material})" if record.material else ""
    marks = [
        word
        for word, on in (("ritual", record.ritual), ("concentration", record.concentration))
        if on
    ]
    damage, damage_scaling = _spell_damage(record.damage)
    heal, heal_scaling = _ladder(record.heal_at_slot_level, "slot")
    return LenientRecord(
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
        notes={
            "level": "cantrip" if record.level == 0 else str(record.level),
            **_noted("attack", f"{record.attack_type} spell attack" if record.attack_type else ""),
            **_noted("save", _spell_save(record.dc)),
            **_noted("damage", damage),
            **_noted("heal", heal),
            **_noted("scaling", damage_scaling or heal_scaling),
            **_noted("area", _area(record.area_of_effect)),
            "range": record.range,
            **_noted("casting-time", _exceptional(record.casting_time, "1 action")),
            **_noted("duration", _exceptional(record.duration, "Instantaneous")),
            **_noted("classes", _names(record.classes)),
            **_noted("subclasses", _names(record.subclasses)),
        },
        tags=(*marks, *(COMPONENTS[part] for part in record.components if part in COMPONENTS)),
    )


COMPONENTS = {"V": "verbal", "S": "somatic", "M": "material"}


def _exceptional(value: str, default: str) -> str:
    """The default is every caster's assumption; only a departure earns a note."""
    return "" if value == default else value


def _spell_save(dc: up.SpellDc | None) -> str:
    return "" if dc is None else _save(dc.dc_type.name, dc.dc_success)


def _save(ability: str, success: str) -> str:
    outcome = {
        "half": "half on success",
        "none": "no effect on success",
        "other": "see text",
    }.get(success)
    return ability + (f" ({outcome})" if outcome else "")


def _spell_damage(damage: up.SpellDamage | None) -> tuple[str, str]:
    if damage is None:
        return "", ""
    by_slot, by_level = damage.damage_at_slot_level, damage.damage_at_character_level
    base, scaling = _ladder(by_slot or by_level, "slot" if by_slot else "level")
    suffix = f" {damage.damage_type.name.lower()}" if base and damage.damage_type else ""
    return base + suffix, scaling


def _ladder(rungs: Mapping[str, str], step: str) -> tuple[str, str]:
    """The lowest rung is what the spell does as cast; the rest become the scaling note."""
    if not rungs:
        return "", ""
    ordered = sorted(rungs.items(), key=lambda rung: int(rung[0]))
    base = _dice(ordered[0][1])
    rest = ", ".join(f"{step} {at}: {_dice(dice)}" for at, dice in ordered[1:])
    return base, rest


def _dice(dice: str) -> str:
    return dice.replace("MOD", "spellcasting modifier")


def _area(area: up.AreaOfEffect | None) -> str:
    return "" if area is None else f"{area.size}-foot {area.type}"


def weapon(record: up.Equipment) -> LenientRecord:
    two_handed = _damage(record.two_handed_damage)
    damage = _damage(record.damage) + (f" (two-handed {two_handed})" if two_handed else "")
    # Every melee weapon carries `range.normal: 5` as baseline reach — even `reach` weapons —
    # so projecting it would misread as a ranged attack distance; `throw_range` is real either way.
    ranged = record.weapon_range == "Ranged"
    return _equipment(
        record,
        f"{record.category_range} weapon.",
        _optional("Damage", damage),
        _optional("Range", _range(record.range)) if ranged else "",
        _optional("Thrown range", _range(record.throw_range)),
        _optional("Properties", _names(record.properties)),
        after=_prose(record.special),
        numbers={
            **_damage_numbers("", record.damage),
            **_damage_numbers("two-handed-", record.two_handed_damage),
            **(_reach("range", record.range) if ranged else {}),
            **_reach("thrown", record.throw_range),
        },
        # The numbers are for a rules checker; `roll` takes an expression, so the Director copies
        # this rather than concatenating a count and a die on the turn it swings.
        notes={"damage": damage} if damage else {},
        tags=(
            *((record.weapon_range.lower(),) if record.weapon_range else ()),
            *_damage_type_tag(record),
            *(entry.index for entry in record.properties),
        ),
    )


def _damage_numbers(prefix: str, damage: up.Damage | None) -> Mapping[str, int]:
    """`1d8` lands as dice-count and die; the blowgun's flat `1` becomes one one-sided die so
    the same two keys always spell the roll."""
    if damage is None or not damage.damage_dice:
        return {}
    parsed = terms(damage.damage_dice)
    if len(parsed) != 1:
        raise ValueError(f"weapon damage {damage.damage_dice!r} is not a single term")
    match parsed[0]:
        case DiceTerm(count=count, faces=faces):
            return {f"{prefix}damage-dice-count": count, f"{prefix}damage-die": faces}
        case ConstantTerm(value=value):
            return {f"{prefix}damage-dice-count": value, f"{prefix}damage-die": 1}


def _damage_type_tag(record: up.Equipment) -> tuple[str, ...]:
    kinds = {
        entry.damage_type.name.lower()
        for entry in (record.damage, record.two_handed_damage)
        if entry is not None and entry.damage_type is not None
    }
    if len(kinds) > 1:
        raise ValueError(f"weapon {record.index!r} deals {sorted(kinds)}: one tag cannot say it")
    return tuple(kinds)


def _reach(prefix: str, entry: up.Range | None) -> Mapping[str, int]:
    if entry is None:
        return {}
    limit = {} if entry.long is None else {f"{prefix}-long": entry.long}
    return {f"{prefix}-normal": entry.normal, **limit}


def armor(record: up.Equipment) -> LenientRecord:
    value = record.armor_class
    if value is None:
        raise ValueError(f"armour {record.index!r} carries no armour class")
    shield = record.armor_category == "Shield"
    return _equipment(
        record,
        f"{record.armor_category} armour.",
        _armor_formula(record, value, shield=shield),
        numbers={
            **({"armor-bonus": value.base} if shield else {"armor-base": value.base}),
            **({} if value.max_bonus is None else {"dex-limit": value.max_bonus}),
            **({"strength-minimum": record.str_minimum} if record.str_minimum else {}),
        },
        tags=(
            *(("add-dex-modifier",) if value.dex_bonus else ()),
            *(("stealth-disadvantage",) if record.stealth_disadvantage else ()),
        ),
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


def gear(record: up.Equipment) -> LenientRecord:
    bundle = record.quantity
    return _equipment(
        record,
        f"{_category(record)}.",
        "" if bundle is None else f"Bundle of {bundle}.",
        _optional("Capacity", record.capacity),
        _optional("Contents", _contained(record.contents)),
        numbers={} if bundle is None else {"quantity": bundle},
    )


def vehicle(record: up.Equipment) -> LenientRecord:
    speed = "" if record.speed is None else f"Speed {record.speed.quantity:g} {record.speed.unit}."
    return _equipment(
        record,
        f"{_category(record)}.",
        speed,
        _optional("Capacity", record.capacity),
        numbers={**_vehicle_speed(record.speed), **_capacity_pounds(record.capacity)},
    )


def _vehicle_speed(speed: up.Quantity | None) -> Mapping[str, int]:
    """A mount's ft/round speed shares the `speed` key monsters and races use; a ship's
    miles-per-hour pace is a different quantity and keeps its unit in the key."""
    if speed is None:
        return {}
    key = {"ft/round": "speed", "mph": "speed-mph"}.get(speed.unit)
    if key is None:
        raise ValueError(f"vehicle speed unit {speed.unit!r} fits no number key")
    # The rowboat's 1.5 mph is no integer; its speed stays on the text line.
    if speed.quantity != int(speed.quantity):
        return {}
    return {key: int(speed.quantity)}


def _capacity_pounds(capacity: str) -> Mapping[str, int]:
    head, _, tail = capacity.partition(" ")
    if tail != "lb." or not (weight := head.replace(",", "")).isdigit():
        return {}
    return {"capacity-lb": int(weight)}


def _category(record: up.Equipment) -> str:
    """The finest category upstream gives: 'Arcane Foci' acts where 'Adventuring Gear' cannot."""
    finer = "" if record.gear_category is None else record.gear_category.name
    return (
        finer or record.tool_category or record.vehicle_category or record.equipment_category.name
    )


def _contained(contents: Sequence[up.Contained]) -> str:
    return ", ".join(f"{entry.item.name} x{entry.quantity}" for entry in contents)


def magic_item(record: up.MagicItem) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{record.equipment_category.name}, {record.rarity.name.lower()}.", _prose(record.desc)
        ),
        notes={
            "category": record.equipment_category.name,
            "rarity": record.rarity.name,
            **_noted("variants", _names(record.variants)),
        },
        tags=("variant",) if record.variant else (),
    )


def race(record: up.Race) -> LenientRecord:
    languages = record.language_options
    picks = _choice_refs("languages", languages)
    return LenientRecord(
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
        numbers={"speed": record.speed},
        notes={
            **_noted("ability-bonuses", _race_bonuses(record)),
            "size": record.size,
        },
        options=picks,
        choose=languages.choose if picks and languages is not None else None,
    )


def _race_bonuses(record: up.Race) -> str:
    """Half-elf's floating +1s are structured as a choice, not fixed bonuses; both must show."""
    floating = record.ability_bonus_options
    extra = "" if floating is None else f"choose {floating.choose} others +1"
    return ", ".join(part for part in (_bonuses(record.ability_bonuses), extra) if part)


def subrace(record: up.Subrace) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"Subrace of {record.race.name}.",
            _prose(record.desc),
            _optional("Ability scores", _bonuses(record.ability_bonuses)),
            _optional("Traits", _names(record.racial_traits)),
        ),
        notes=_noted("ability-bonuses", _bonuses(record.ability_bonuses)),
    )


def background(record: up.Background) -> LenientRecord:
    feature = record.feature
    gold = record.starting_gold
    languages = (
        ""
        if record.language_options is None
        else f"Choose {_plural(record.language_options.choose, 'language')}."
    )
    return LenientRecord(
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
        numbers={} if gold is None else {"starting-gold": _whole(gold, "starting gold")},
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


def klass(record: up.Class) -> LenientRecord:
    casting = record.spellcasting
    return LenientRecord(
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
        numbers={"hit-die": record.hit_die},
        notes={
            **_noted("saving-throws", _names(record.saving_throws)),
            **_noted("spellcasting", "" if casting is None else casting.spellcasting_ability.name),
        },
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


def subclass(record: up.Subclass) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{record.class_.name} {record.subclass_flavor.lower()}.", _prose(record.desc)
        ),
        notes=_noted("subclass-spells", _subclass_spells(record.spells)),
    )


def _subclass_spells(entries: Sequence[up.SubclassSpell]) -> str:
    """The domain-spell table: which spells arrive at which class level, always prepared."""
    grouped: dict[str, list[str]] = {}
    for entry in entries:
        gate = ", ".join(p.name for p in entry.prerequisites) or "always"
        grouped.setdefault(gate, []).append(entry.spell.name)
    return "; ".join(f"{gate}: {', '.join(spells)}" for gate, spells in grouped.items())


def skill(record: up.Skill) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(f"{record.ability_score.name} skill.", _prose(record.desc)),
        notes={"ability": record.ability_score.name},
    )


def language(record: up.Language) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_line(
            f"{record.type} language.",
            _optional("Script", record.script),
            _optional("Typical speakers", ", ".join(record.typical_speakers)),
        ),
    )


def alignment(record: up.Alignment) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(f"Abbreviated {record.abbreviation}.", _prose(record.desc)),
    )


def trait(record: up.Trait) -> LenientRecord:
    """Dragonborn breath weapons are the one trait with spell-grade structure; project it the
    way `spell` does, so the render carries the save, dice and ladder."""
    specific = record.trait_specific
    breath = None if specific is None else specific.breath_weapon
    damage, scaling = ("", "") if breath is None else _spell_damage(next(iter(breath.damage), None))
    collection, choice = _trait_choice(record)
    picks = _choice_refs(collection, choice)
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_prose(record.desc),
        notes={
            **_noted(
                "damage-type",
                specific.damage_type.name if specific and specific.damage_type else "",
            ),
            **_noted(
                "save",
                ""
                if breath is None or breath.dc is None
                else _save(breath.dc.dc_type.name, breath.dc.success_type),
            ),
            **_noted("damage", damage),
            **_noted("scaling", scaling),
            **_noted("area", "" if breath is None else _area(breath.area_of_effect)),
            **_noted(
                "uses", "" if breath is None or breath.usage is None else _usage(breath.usage)
            ),
            **_noted("grants-proficiency", _names(record.proficiencies)),
            **_noted("races", _names(record.races)),
            **_noted("subraces", _names(record.subraces)),
            **_noted("parent", record.parent.name if record.parent else ""),
        },
        options=picks,
        choose=choice.choose if picks and choice is not None else None,
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


def feat(record: up.Feat) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(_optional("Prerequisite", _minima(record.prerequisites)), _prose(record.desc)),
    )


def _minima(entries: Sequence[up.Prerequisite]) -> str:
    return ", ".join(f"{entry.ability_score.name} {entry.minimum_score}" for entry in entries)


def proficiency(record: up.Proficiency) -> LenientRecord:
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=f"{record.type} proficiency: {record.reference.name}.",
    )


def feature(record: up.Feature) -> LenientRecord:
    owner = record.subclass or record.class_
    choice = subfeature_options(record)
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(
            f"{owner.name if owner else 'Feature'} feature, level {record.level}.",
            _prose(record.desc),
        ),
        notes={
            **_noted("requires", _feature_requires(record.prerequisites)),
            **_noted("choose", _feature_choice(record.feature_specific)),
            **_noted("invocations", _invocations(record.feature_specific)),
            **_noted("parent", record.parent.name if record.parent else ""),
        },
        options=choice,
        choose=1 if choice else None,
    )


def _invocations(specific: up.FeatureSpecific | None) -> str:
    """Flat, not a `Choice`: how many a warlock knows is the level row's `invocations-known`."""
    return "" if specific is None else _names(specific.invocations)


def _feature_requires(entries: Sequence[up.FeaturePrerequisite]) -> str:
    def one(entry: up.FeaturePrerequisite) -> str:
        if entry.type == "level" and entry.level:
            return f"level {entry.level}"
        # Feature and spell prerequisites arrive as API paths; the tail is the index.
        return (entry.feature or entry.spell).rsplit("/", 1)[-1]

    return ", ".join(line for entry in entries if (line := one(entry)))


def _feature_choice(specific: up.FeatureSpecific | None) -> str:
    if specific is None:
        return ""
    for what, choice in (
        ("skill proficiencies for expertise", specific.expertise_options),
        ("favored enemy", specific.enemy_type_options),
        ("favored terrain", specific.terrain_type_options),
    ):
        if choice is not None:
            named = ", ".join(
                name for option in choice.options.options if (name := _option_name(option))
            )
            return _line(f"{choice.choose} {what}", _optional("from", named))
    return ""


def _option_name(option: up.Option | str) -> str:
    if isinstance(option, str):
        return option
    return option.string or (option.item.name if option.item else "")


def level(record: up.Level, options: Options) -> LenientRecord:
    owner = record.subclass or record.class_
    picks = tuple(
        pick
        for entry in record.features
        for pick in options.get(entry.index, (ref("features", entry.index),))
    )
    specific = {**record.class_specific, **record.subclass_specific}
    whole = _whole_numbers(specific)
    return LenientRecord(
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
        numbers={
            "level": record.level,
            **({} if record.prof_bonus is None else {"proficiency-bonus": record.prof_bonus}),
            **_known_spells(record.spellcasting),
            **(
                {}
                if not record.ability_score_bonuses
                else {"ability-score-bonuses": record.ability_score_bonuses}
            ),
            **{f"slot-{n}": count for n, count in _slot_maxima(record.spellcasting)},
            **{_key(name): value for name, value in whole.items()},
        },
        notes=_level_notes(specific),
        tags=tuple(
            _key(name)
            for name in ("wild_shape_fly", "wild_shape_swim")
            if specific.get(name) is True
        ),
        options=picks,
        choose=len(record.features) or None,
    )


def _known_spells(spellcasting: Mapping[str, int]) -> Mapping[str, int]:
    return {
        _key(name): count
        for name in ("cantrips_known", "spells_known")
        if (count := spellcasting.get(name, 0)) > 0
    }


def _level_notes(specific: Mapping[str, object]) -> Mapping[str, str]:
    """The class ladders `_whole_numbers` cannot carry: damage dice, fractional CR caps, the
    sorcerer's slot-creation table, and the unlimited sentinel."""
    notes: dict[str, str] = {}
    for name in ("sneak_attack", "martial_arts"):
        if isinstance(raw := specific.get(name), Mapping):
            dice = up.DieLadder.model_validate(raw)
            notes[_key(name)] = f"{dice.dice_count}d{dice.dice_value}"
    for name in ("wild_shape_max_cr", "destroy_undead_cr"):
        value = specific.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            notes[_key(name)] = _challenge(float(value))
    if isinstance(ladder := specific.get("creating_spell_slots"), list) and ladder:
        rows = _SLOT_CREATIONS.validate_python(ladder)
        notes["creating-spell-slots"] = ", ".join(
            f"slot {row.spell_slot_level} for {row.sorcery_point_cost} sorcery points"
            for row in rows
        )
    for name, value in specific.items():
        if value == UNLIMITED:
            notes[_key(name)] = "unlimited"
    return notes


def subfeature_options(record: up.Feature) -> tuple[ContentRef, ...]:
    """The picks a feature that *is* a choice offers, as the level row's options flatten them."""
    specific = record.feature_specific
    return _choice_refs("features", None if specific is None else specific.subfeature_options)


# Upstream writes 9999 where a pool stops being counted (the barbarian's level-20 rages).
UNLIMITED = 9999


def _whole_numbers(values: Mapping[str, object]) -> Mapping[str, int]:
    """Only the whole numbers: dice ladders, fractions and the unlimited sentinel go through
    `_level_notes` instead."""
    return {
        name: value
        for name, value in values.items()
        if isinstance(value, int) and not isinstance(value, bool) and 0 < value != UNLIMITED
    }


def _slot_maxima(spellcasting: Mapping[str, int]) -> Iterable[tuple[int, int]]:
    for number in range(1, MAX_SPELL_LEVEL + 1):
        count = spellcasting.get(f"spell_slots_level_{number}", 0)
        if count > 0:
            yield number, count


def _slots(spellcasting: Mapping[str, int]) -> str:
    return ", ".join(f"level {number} x{count}" for number, count in _slot_maxima(spellcasting))


def _equipment(
    record: up.Equipment,
    *lines: str,
    after: str = "",
    numbers: Mapping[str, int] | None = None,
    notes: Mapping[str, str] | None = None,
    tags: tuple[str, ...] = (),
) -> LenientRecord:
    cost = "" if record.cost is None else f"Cost {record.cost.quantity:g} {record.cost.unit}."
    weight = "" if record.weight is None else f"Weight {record.weight:g} lb."
    return LenientRecord(
        index=record.index,
        name=record.name,
        text=_joined(_line(*lines, cost, weight), _prose(record.desc), after),
        numbers={**_cost_number(record.cost), **(numbers or {})},
        notes=notes or {},
        tags=tags,
    )


def _cost_number(cost: up.Quantity | None) -> Mapping[str, int]:
    """Unit-named keys (`cost-gp 15`, `cost-sp 2`): every upstream price is whole in its own
    coin, and one normalized copper key would misstate 15 gp as 1500."""
    if cost is None:
        return {}
    return {f"cost-{cost.unit}": _whole(cost, "cost")}


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


def _noted(key: str, body: str) -> Mapping[str, str]:
    return {key: body} if body else {}


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
