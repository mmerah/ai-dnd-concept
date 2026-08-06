from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.state.base import Slug
from aidm.state.dice import DiceExpr, DiceTerm, terms
from aidm.state.packs import (
    EMPTY_FROZEN_MAP,
    Content,
    ContentMiss,
    FrozenMap,
    Record,
    Value,
    parse_ref,
)
from aidm.state.sheet import Sheet

ABILITY_BY_ABBREVIATION: Mapping[str, Slug] = MappingProxyType(
    {
        "STR": "strength",
        "DEX": "dexterity",
        "CON": "constitution",
        "INT": "intelligence",
        "WIS": "wisdom",
        "CHA": "charisma",
    }
)
ABBREVIATION_BY_ABILITY: Mapping[Slug, str] = MappingProxyType(
    {ability: abbreviation for abbreviation, ability in ABILITY_BY_ABBREVIATION.items()}
)
type SaveSuccess = Literal["half", "none", "other"]
SAVE_OUTCOMES: Mapping[SaveSuccess, str] = MappingProxyType(
    {"half": "half on success", "none": "no effect on success", "other": "see text"}
)


class SpellAmount(Value):
    dice: DiceExpr
    with_modifier: bool = False

    def bonus(self, caster_modifier: int) -> int:
        return caster_modifier if self.with_modifier else 0

    def prose(self) -> str:
        return self.dice + (" + spellcasting modifier" if self.with_modifier else "")


class SpellArea(Value):
    shape: Slug
    size: int


class SpellRecord(Record):
    level: Annotated[int, Field(ge=1, le=9)] | None = None
    school: Slug
    attack_type: Literal["melee", "ranged"] | None = None
    save_ability: Slug | None = None
    save_success: SaveSuccess | None = None
    damage: SpellAmount | None = None
    damage_type: Slug | None = None
    heal: SpellAmount | None = None
    scaling: tuple[tuple[int, SpellAmount], ...] = ()
    concentration: bool = False
    area: SpellArea | None = None
    range: str
    casting_time: str
    duration: str
    classes: tuple[str, ...] = ()
    subclasses: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _save_is_whole(self) -> Self:
        if (self.save_ability is None) != (self.save_success is None):
            raise ValueError("save_ability and save_success are set together, or neither is")
        return self

    @property
    def attack(self) -> bool:
        return self.attack_type is not None

    @property
    def half_on_save(self) -> bool:
        return self.save_success == "half"

    def damage_at(self, key: int) -> SpellAmount | None:
        return _scaled(self.damage, self.scaling, key)

    def heal_at(self, key: int) -> SpellAmount | None:
        return _scaled(self.heal, self.scaling, key)

    def noted(self) -> Mapping[Slug, str]:
        # Leveled spells scale by the slot spent, cantrips by caster level; the importer
        # refuses upstream rows that break this, so the step can derive from `level`.
        step = "level" if self.level is None else "slot"
        return {
            "level": "cantrip" if self.level is None else str(self.level),
            **_noted("attack", f"{self.attack_type} spell attack" if self.attack_type else ""),
            **_noted("save", _save_note(self.save_ability, self.save_success)),
            **_noted("damage", _damage_note(self.damage, self.damage_type)),
            **_noted("heal", "" if self.heal is None else self.heal.prose()),
            **_noted("scaling", _scaling_prose(step, self.scaling)),
            **_noted("area", _area_note(self.area)),
            "range": self.range,
            **_noted("casting-time", _exceptional(self.casting_time, "1 action")),
            **_noted("duration", _exceptional(self.duration, "Instantaneous")),
            **_noted("classes", ", ".join(self.classes)),
            **_noted("subclasses", ", ".join(self.subclasses)),
        }


class Cost(Value):
    unit: Slug
    amount: int


class Reach(Value):
    normal: int
    long: int | None = None


class WeaponRecord(Record):
    damage: DiceExpr | None = None
    damage_type: Slug | None = None
    versatile_damage: DiceExpr | None = None
    ranged: bool = False
    finesse: bool = False
    cost: Cost | None = None
    range: Reach | None = None
    thrown: Reach | None = None

    def dice(self, two_handed: bool) -> DiceExpr | None:
        if two_handed and self.versatile_damage is not None:
            return self.versatile_damage
        return self.damage

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {
            **_cost_numbers(self.cost),
            **_dice_numbers("", self.damage),
            **_dice_numbers("two-handed-", self.versatile_damage),
            **_reach_numbers("range", self.range),
            **_reach_numbers("thrown", self.thrown),
        }

    def noted(self) -> Mapping[Slug, str]:
        # `roll` takes an expression, so the Director copies this line rather than
        # concatenating a count and a die on the turn it swings.
        line = weapon_damage_note(self.damage, self.damage_type, self.versatile_damage)
        return _noted("damage", line)


class SkillRecord(Record):
    ability: str

    def noted(self) -> Mapping[Slug, str]:
        return {"ability": self.ability}


class MagicItemRecord(Record):
    category: str
    rarity: str
    variants: tuple[str, ...] = ()

    def noted(self) -> Mapping[Slug, str]:
        return {
            "category": self.category,
            "rarity": self.rarity,
            **_noted("variants", ", ".join(self.variants)),
        }


class AbilityMinimum(Value):
    ability: Slug
    minimum: int


class LanguageRecord(Record):
    category: str
    script: str = ""
    typical_speakers: tuple[str, ...] = ()


class AlignmentRecord(Record):
    abbreviation: str


class ProficiencyRecord(Record):
    category: str
    reference: str


class FeatRecord(Record):
    prerequisites: tuple[AbilityMinimum, ...] = ()


class AbilityBonus(Value):
    ability: str
    bonus: int


class SubraceRecord(Record):
    race: str
    ability_bonuses: tuple[AbilityBonus, ...] = ()

    def noted(self) -> Mapping[Slug, str]:
        return _noted("ability-bonuses", _bonus_note(self.ability_bonuses))


class SpellGrant(Value):
    gate: str
    spell: str


class SubclassRecord(Record):
    klass: str
    flavor: str
    spell_grants: tuple[SpellGrant, ...] = ()

    def noted(self) -> Mapping[Slug, str]:
        grouped: dict[str, list[str]] = {}
        for grant in self.spell_grants:
            grouped.setdefault(grant.gate, []).append(grant.spell)
        line = "; ".join(f"{gate}: {', '.join(spells)}" for gate, spells in grouped.items())
        return _noted("subclass-spells", line)


class ArmorRecord(Record):
    cost: Cost | None = None
    base: int
    shield: bool = False
    dex_limit: int | None = None
    strength_minimum: int | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {
            **_cost_numbers(self.cost),
            **({"armor-bonus": self.base} if self.shield else {"armor-base": self.base}),
            **_numbered("dex-limit", self.dex_limit),
            **_numbered("strength-minimum", self.strength_minimum),
        }


class GearRecord(Record):
    cost: Cost | None = None
    quantity: int | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {**_cost_numbers(self.cost), **_numbered("quantity", self.quantity)}


class VehicleRecord(Record):
    cost: Cost | None = None
    speed: int | None = None
    speed_mph: int | None = None
    capacity_lb: int | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {
            **_cost_numbers(self.cost),
            **_numbered("speed", self.speed),
            **_numbered("speed-mph", self.speed_mph),
            **_numbered("capacity-lb", self.capacity_lb),
        }


class ClassRecord(Record):
    hit_die: int
    saving_throws: tuple[Slug, ...] = ()
    spellcasting: Slug | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {"hit-die": self.hit_die}

    def noted(self) -> Mapping[Slug, str]:
        return {
            **_noted(
                "saving-throws",
                ", ".join(ABBREVIATION_BY_ABILITY[ability] for ability in self.saving_throws),
            ),
            **_noted(
                "spellcasting",
                "" if self.spellcasting is None else ABBREVIATION_BY_ABILITY[self.spellcasting],
            ),
        }


class RaceRecord(Record):
    speed: int
    size: str
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    # Half-elf's floating +1s are structured as a choice, not fixed bonuses; both must show.
    floating_bonus_choose: int | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {"speed": self.speed}

    def noted(self) -> Mapping[Slug, str]:
        extra = (
            ""
            if self.floating_bonus_choose is None
            else f"choose {self.floating_bonus_choose} others +1"
        )
        bonuses = ", ".join(part for part in (_bonus_note(self.ability_bonuses), extra) if part)
        return {**_noted("ability-bonuses", bonuses), "size": self.size}


class BackgroundRecord(Record):
    starting_gold: int | None = None

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return _numbered("starting-gold", self.starting_gold)


class FeatureChoice(Value):
    count: int
    what: str
    among: tuple[str, ...] = ()

    def prose(self) -> str:
        named = ", ".join(self.among).strip().rstrip(".")
        chosen = f"{self.count} {self.what}"
        return f"{chosen} from: {named}." if named else chosen


class FeatureRecord(Record):
    level: int
    requires: tuple[str, ...] = ()
    pick: FeatureChoice | None = None
    # Flat, not a choice: how many a warlock knows is the level row's `invocations-known`.
    invocations: tuple[str, ...] = ()
    parent: str | None = None

    def noted(self) -> Mapping[Slug, str]:
        return {
            **_noted("requires", ", ".join(self.requires)),
            **_noted("choose", "" if self.pick is None else self.pick.prose()),
            **_noted("invocations", ", ".join(self.invocations)),
            **_noted("parent", self.parent or ""),
        }


class TraitRecord(Record):
    damage_type: Slug | None = None
    save_ability: Slug | None = None
    save_success: SaveSuccess | None = None
    damage: SpellAmount | None = None
    # A breath weapon scales with character level, never slots; the importer refuses otherwise.
    scaling: tuple[tuple[int, SpellAmount], ...] = ()
    area: SpellArea | None = None
    uses: str | None = None
    grants_proficiency: tuple[str, ...] = ()
    races: tuple[str, ...] = ()
    subraces: tuple[str, ...] = ()
    parent: str | None = None

    @model_validator(mode="after")
    def _save_is_whole(self) -> Self:
        if (self.save_ability is None) != (self.save_success is None):
            raise ValueError("save_ability and save_success are set together, or neither is")
        return self

    def noted(self) -> Mapping[Slug, str]:
        return {
            **_noted("damage-type", self.damage_type or ""),
            **_noted("save", _save_note(self.save_ability, self.save_success)),
            **_noted("damage", _damage_note(self.damage, self.damage_type)),
            **_noted("scaling", _scaling_prose("level", self.scaling)),
            **_noted("area", _area_note(self.area)),
            **_noted("uses", self.uses or ""),
            **_noted("grants-proficiency", ", ".join(self.grants_proficiency)),
            **_noted("races", ", ".join(self.races)),
            **_noted("subraces", ", ".join(self.subraces)),
            **_noted("parent", self.parent or ""),
        }


class LevelRecord(Record):
    level: int
    proficiency_bonus: int | None = None
    cantrips_known: int | None = None
    spells_known: int | None = None
    ability_score_bonuses: int | None = None
    slots: tuple[tuple[int, int], ...] = ()
    # Whole-number class ladders (rage-count, ki-points, ...): keys are open-ended per class.
    class_numbers: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    dice_ladders: FrozenMap[Slug, DiceExpr] = EMPTY_FROZEN_MAP
    cr_caps: FrozenMap[Slug, str] = EMPTY_FROZEN_MAP
    slot_creation: tuple[tuple[int, int], ...] = ()
    unlimited: tuple[Slug, ...] = ()

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {
            "level": self.level,
            **_numbered("proficiency-bonus", self.proficiency_bonus),
            **_numbered("cantrips-known", self.cantrips_known),
            **_numbered("spells-known", self.spells_known),
            **_numbered("ability-score-bonuses", self.ability_score_bonuses),
            **{f"slot-{number}": count for number, count in self.slots},
            **self.class_numbers,
        }

    def noted(self) -> Mapping[Slug, str]:
        created = ", ".join(
            f"slot {number} for {cost} sorcery points" for number, cost in self.slot_creation
        )
        return {
            **self.dice_ladders,
            **self.cr_caps,
            **_noted("creating-spell-slots", created),
            **{key: "unlimited" for key in self.unlimited},
        }


class MonsterRecord(Record):
    armor_class: int
    hp: int
    xp: int
    proficiency_bonus: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    proficiencies: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    speeds: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    sense_ranges: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    passive_perception: int | None = None
    spell_save_dc: int | None = None
    spell_attack_bonus: int | None = None
    attacks: tuple[str, ...] = ()
    multiattack: str | None = None
    limited_use: tuple[str, ...] = ()
    damage_vulnerabilities: tuple[str, ...] = ()
    damage_resistances: tuple[str, ...] = ()
    damage_immunities: tuple[str, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    forms: tuple[str, ...] = ()
    spells: tuple[tuple[int, tuple[str, ...]], ...] = ()
    slots: tuple[tuple[int, int], ...] = ()
    size: str
    challenge_rating: str

    def sheet_numbers(self) -> Mapping[Slug, int]:
        return {
            "armor-class": self.armor_class,
            "hp": self.hp,
            "xp": self.xp,
            "proficiency-bonus": self.proficiency_bonus,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            **self.proficiencies,
            **{f"speed-{key}": feet for key, feet in self.speeds.items()},
            **self.sense_ranges,
            **_numbered("passive-perception", self.passive_perception),
            **_numbered("spell-save-dc", self.spell_save_dc),
            **_numbered("spell-attack-bonus", self.spell_attack_bonus),
        }

    def noted(self) -> Mapping[Slug, str]:
        spells = "; ".join(
            f"{'cantrips' if level == 0 else f'level {level}'}: {', '.join(names)}"
            for level, names in self.spells
        )
        slots = ", ".join(f"level {number} x{count}" for number, count in self.slots)
        return {
            **_noted("attacks", "; ".join(self.attacks)),
            **_noted("multiattack", self.multiattack or ""),
            **_noted("limited-use", "; ".join(self.limited_use)),
            **_noted("damage-vulnerabilities", ", ".join(self.damage_vulnerabilities)),
            **_noted("damage-resistances", ", ".join(self.damage_resistances)),
            **_noted("damage-immunities", ", ".join(self.damage_immunities)),
            **_noted("condition-immunities", ", ".join(self.condition_immunities)),
            # Form names carry commas of their own ('Vampire, Bat Form'), so join on semicolons.
            **_noted("forms", "; ".join(self.forms)),
            **_noted("spells", spells),
            **_noted("slots", slots),
            "size": self.size,
            "challenge-rating": self.challenge_rating,
        }


def weapon_damage_note(
    damage: DiceExpr | None, damage_type: Slug | None, versatile: DiceExpr | None
) -> str:
    if damage is None or damage_type is None:
        return ""
    two_handed = f" (two-handed {versatile} {damage_type})" if versatile is not None else ""
    return f"{damage} {damage_type}{two_handed}"


def _cost_numbers(cost: Cost | None) -> Mapping[Slug, int]:
    return {} if cost is None else {f"cost-{cost.unit}": cost.amount}


def _save_note(ability: Slug | None, success: SaveSuccess | None) -> str:
    if ability is None or success is None:
        return ""
    return f"{ABBREVIATION_BY_ABILITY[ability]} ({SAVE_OUTCOMES[success]})"


def _damage_note(amount: SpellAmount | None, damage_type: Slug | None) -> str:
    if amount is None:
        return ""
    return amount.prose() + (f" {damage_type}" if damage_type else "")


def _area_note(area: SpellArea | None) -> str:
    return "" if area is None else f"{area.size}-foot {area.shape}"


def _scaling_prose(step: str, ladder: tuple[tuple[int, SpellAmount], ...]) -> str:
    return ", ".join(f"{step} {at}: {amount.prose()}" for at, amount in ladder)


def _bonus_note(bonuses: tuple[AbilityBonus, ...]) -> str:
    return ", ".join(f"{entry.ability} +{entry.bonus}" for entry in bonuses)


def _exceptional(value: str, default: str) -> str:
    """The default is every caster's assumption; only a departure earns a note."""
    return "" if value == default else value


def _noted(key: Slug, body: str) -> Mapping[Slug, str]:
    return {key: body} if body else {}


def _numbered(key: Slug, value: int | None) -> Mapping[Slug, int]:
    return {} if value is None else {key: value}


def _dice_numbers(prefix: str, expr: DiceExpr | None) -> Mapping[Slug, int]:
    if expr is None:
        return {}
    match terms(expr):
        case (DiceTerm(count=count, faces=faces),):
            return {f"{prefix}damage-dice-count": count, f"{prefix}damage-die": faces}
        case parsed:
            raise ValueError(f"weapon damage {expr!r} is not a single dice term: {parsed}")


def _reach_numbers(prefix: str, reach: Reach | None) -> Mapping[Slug, int]:
    if reach is None:
        return {}
    limit = {} if reach.long is None else {f"{prefix}-long": reach.long}
    return {f"{prefix}-normal": reach.normal, **limit}


def _scaled(
    base: SpellAmount | None, scaling: tuple[tuple[int, SpellAmount], ...], key: int
) -> SpellAmount | None:
    if base is None:
        return None
    later = [amount for threshold, amount in scaling if threshold <= key]
    return later[-1] if later else base


def weapon_of(content: Content, item: Sheet) -> WeaponRecord | None:
    for ref in item.refs:
        if ref.collection != "weapons":
            continue
        record = content.get(ref, WeaponRecord)
        if isinstance(record, ContentMiss) or record.damage is None:
            continue
        return record
    return None


def spell_of(content: Content, ref: str) -> SpellRecord:
    reference = parse_ref(ref)
    if reference.collection != "spells":
        raise ValueError(f"{ref!r} names no spell: name a record from the spells collection")
    record = content.get(reference, SpellRecord)
    if isinstance(record, ContentMiss):
        raise ValueError(f"{record.summary}; use a ref exactly as it was shown")
    return record


def spellcasting_ability(content: Content, sheet: Sheet) -> Slug | None:
    resolved = [
        record
        for ref in sheet.refs
        if ref.collection == "classes"
        for record in (content.get(ref, ClassRecord),)
        if not isinstance(record, ContentMiss)
    ]
    if len(resolved) != 1:
        return None
    return resolved[0].spellcasting
