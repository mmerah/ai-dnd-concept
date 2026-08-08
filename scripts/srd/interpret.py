import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.base import Slug
from aidm.state.dice import DiceExpr
from aidm.state.packs import EMPTY_FROZEN_MAP, FrozenMap, Record, Value

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

_SLUG_DROP = re.compile(r"['’]")
_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


def to_slug(name: str) -> Slug:
    # An apostrophe joins a word rather than separating it: "Artisan's" is one term, not two.
    return _SLUG_CLEAN.sub("-", _SLUG_DROP.sub("", name.lower())).strip("-")


class SpellAmount(Value):
    dice: DiceExpr
    with_modifier: bool = False


class SpellArea(Value):
    shape: Slug
    size: int


class Cost(Value):
    unit: Slug
    amount: int


class Reach(Value):
    normal: int
    long: int | None = None


def weapon_damage_note(
    damage: DiceExpr | None, damage_type: Slug | None, versatile: DiceExpr | None
) -> str:
    if damage is None or damage_type is None:
        return ""
    two_handed = f" (two-handed {versatile} {damage_type})" if versatile is not None else ""
    return f"{damage} {damage_type}{two_handed}"


def _cost_numbers(cost: Cost | None) -> Mapping[Slug, int]:
    return {} if cost is None else {f"cost-{cost.unit}": cost.amount}


def _noted(key: Slug, body: str) -> Mapping[Slug, str]:
    return {key: body} if body else {}


def _numbered(key: Slug, value: int | None) -> Mapping[Slug, int]:
    return {} if value is None else {key: value}


def _reach_numbers(prefix: str, reach: Reach | None) -> Mapping[Slug, int]:
    if reach is None:
        return {}
    limit = {} if reach.long is None else {f"{prefix}-long": reach.long}
    return {f"{prefix}-normal": reach.normal, **limit}


def _amount_ladder(
    index: str, key: str, base: SpellAmount | None, scaling: tuple[tuple[int, SpellAmount], ...]
) -> Mapping[Slug, JsonValue]:
    """Rung 0 is the amount as cast, later rungs the scaling ladder. Steps are slot levels for
    spells and character levels for traits — derivable from the collection, so no key says which."""
    if base is None:
        return {}
    if any(amount.with_modifier != base.with_modifier for _, amount in scaling):
        raise ValueError(f"{index}: with_modifier differs across the scaling ladder")
    facts: dict[Slug, JsonValue] = {}
    if base.with_modifier:
        facts[f"{key}-with-modifier"] = True
    ladder: list[JsonValue] = [[0, base.dice]]
    ladder.extend([at, amount.dice] for at, amount in scaling)
    facts[f"{key}-ladder"] = ladder
    return facts


class Interpreted(Record):
    """An authoring-time intermediate: typed upstream fields in, one generic `Record` out."""

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {}

    def generic(self) -> Record:
        return Record(
            index=self.index,
            name=self.name,
            text=self.text,
            tags=self.tags,
            options=self.options,
            choose=self.choose,
            facts=self.mechanical_facts(),
        )


class AbilityMinimum(Value):
    ability: Slug
    minimum: int


class LanguageRecord(Interpreted):
    category: str

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {"category": to_slug(self.category)}


class ProficiencyRecord(Interpreted):
    category: str
    reference: str

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {"category": to_slug(self.category), "reference": self.reference}


class FeatRecord(Interpreted):
    prerequisites: tuple[AbilityMinimum, ...] = ()

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        if not self.prerequisites:
            return {}
        minima: list[JsonValue] = [
            {"ability": e.ability, "minimum": e.minimum} for e in self.prerequisites
        ]
        return {"prerequisites": minima}


class AbilityBonus(Value):
    ability: str
    bonus: int


class SubraceRecord(Interpreted):
    race: Slug
    ability_bonuses: tuple[AbilityBonus, ...] = ()

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {"race": self.race, **_bonus_facts(self.ability_bonuses)}


class SpellGrant(Value):
    gate: str
    # The name feeds the model-facing note, the index the joinable fact.
    spell: str
    spell_index: Slug


class SubclassRecord(Interpreted):
    klass: Slug
    spell_grants: tuple[SpellGrant, ...] = ()

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        grouped: dict[str, list[str]] = {}
        for grant in self.spell_grants:
            grouped.setdefault(grant.gate, []).append(grant.spell)
        line = "; ".join(f"{gate}: {', '.join(spells)}" for gate, spells in grouped.items())
        grants: list[JsonValue] = [
            {"gate": g.gate, "spell": g.spell_index} for g in self.spell_grants
        ]
        return {
            "class": self.klass,
            **({"spell-grants": grants} if grants else {}),
            **_noted("subclass-spells", line),
        }


class ArmorRecord(Interpreted):
    cost: Cost | None = None
    base: int
    shield: bool = False
    dex_limit: int | None = None
    strength_minimum: int | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            **_cost_numbers(self.cost),
            **({"armor-bonus": self.base} if self.shield else {"armor-base": self.base}),
            **_numbered("dex-limit", self.dex_limit),
            **_numbered("strength-minimum", self.strength_minimum),
        }


class GearRecord(Interpreted):
    cost: Cost | None = None
    quantity: int | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {**_cost_numbers(self.cost), **_numbered("quantity", self.quantity)}


class VehicleRecord(Interpreted):
    cost: Cost | None = None
    speed: int | None = None
    speed_mph: int | None = None
    capacity_lb: int | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            **_cost_numbers(self.cost),
            # 'speed' means a creature's walking speed everywhere else; a mount's ft/round pace
            # gets its own key so a vehicle ref cannot overwrite it on an actor's sheet.
            **_numbered("speed-ft-round", self.speed),
            **_numbered("speed-mph", self.speed_mph),
            **_numbered("capacity-lb", self.capacity_lb),
        }


class RaceRecord(Interpreted):
    speed: int
    size: str
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    # Half-elf's floating +1s are structured as a choice, not fixed bonuses; both must show.
    floating_bonus_choose: int | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            "speed": self.speed,
            "size": self.size,
            **_bonus_facts(self.ability_bonuses, self.floating_bonus_choose),
        }


class BackgroundRecord(Interpreted):
    starting_gold: int | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return _numbered("starting-gold", self.starting_gold)


class FeatureChoice(Value):
    count: int
    what: str
    among: tuple[str, ...] = ()

    def prose(self) -> str:
        named = ", ".join(self.among).strip().rstrip(".")
        chosen = f"{self.count} {self.what}"
        return f"{chosen} from: {named}." if named else chosen


class FeatureRecord(Interpreted):
    level: int
    requires: tuple[str, ...] = ()
    pick: FeatureChoice | None = None
    # Flat, not a choice: how many a warlock knows is the level row's `invocations-known`.
    invocations: tuple[str, ...] = ()
    parent: str | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            "level": self.level,
            **_noted("requires", ", ".join(self.requires)),
            **_noted("choose", "" if self.pick is None else self.pick.prose()),
            **_noted("invocations", ", ".join(self.invocations)),
            **_noted("parent", self.parent or ""),
        }


class TraitRecord(Interpreted):
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

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            **({"damage-type": self.damage_type} if self.damage_type else {}),
            **({"save-ability": self.save_ability} if self.save_ability else {}),
            **({"save-success": self.save_success} if self.save_success else {}),
            **_amount_ladder(self.index, "damage", self.damage, self.scaling),
            **({"area": f"{self.area.size}-foot {self.area.shape}"} if self.area else {}),
            **({"uses": self.uses} if self.uses else {}),
            **_noted("grants-proficiency", ", ".join(self.grants_proficiency)),
            **_noted("races", ", ".join(self.races)),
            **_noted("subraces", ", ".join(self.subraces)),
            **_noted("parent", self.parent or ""),
        }


class SkillRecord(Interpreted):
    ability: str

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {"ability": ABILITY_BY_ABBREVIATION[self.ability]}


class MagicItemRecord(Interpreted):
    category: str
    rarity: str
    variants: tuple[Slug, ...] = ()

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            "category": to_slug(self.category),
            "rarity": to_slug(self.rarity),
            **({"variants": list(self.variants)} if self.variants else {}),
        }


class SpellRecord(Interpreted):
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

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        thresholds = [at for at, _ in self.scaling]
        if thresholds != sorted(set(thresholds)):
            raise ValueError(f"{self.index}: scaling thresholds are not strictly increasing")
        facts: dict[Slug, JsonValue] = {}
        if self.level is not None:
            facts["level"] = self.level
        if self.attack_type is not None:
            facts["attack-type"] = self.attack_type
        if self.save_ability is not None:
            facts["save-ability"] = self.save_ability
        if self.save_success is not None:
            facts["save-success"] = self.save_success
        if self.damage_type is not None:
            facts["damage-type"] = self.damage_type
        if self.concentration:
            facts["concentration"] = True
        facts.update(_amount_ladder(self.index, "damage", self.damage, self.scaling))
        facts.update(_amount_ladder(self.index, "heal", self.heal, self.scaling))
        if self.area is not None:
            facts["area"] = f"{self.area.size}-foot {self.area.shape}"
        facts["range"] = self.range
        # The default every caster assumes; only a departure earns a fact.
        if self.casting_time != "1 action":
            facts["casting-time"] = self.casting_time
        if self.duration != "Instantaneous":
            facts["duration"] = self.duration
        if self.classes:
            facts["classes"] = ", ".join(self.classes)
        if self.subclasses:
            facts["subclasses"] = ", ".join(self.subclasses)
        return facts


class WeaponRecord(Interpreted):
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

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        facts: dict[Slug, JsonValue] = {
            **_cost_numbers(self.cost),
            **_reach_numbers("range", self.range),
            **_reach_numbers("thrown", self.thrown),
        }
        if self.damage is not None:
            facts["damage"] = self.damage
        if self.versatile_damage is not None:
            facts["versatile-damage"] = self.versatile_damage
        if self.damage_type is not None:
            facts["damage-type"] = self.damage_type
        if self.finesse:
            facts["finesse"] = True
        if self.ranged:
            facts["ranged"] = True
        return facts


class ClassRecord(Interpreted):
    hit_die: int
    saving_throws: tuple[Slug, ...] = ()
    spellcasting: Slug | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            "hit-die": self.hit_die,
            **_noted(
                "saving-throws",
                ", ".join(ABBREVIATION_BY_ABILITY[ability] for ability in self.saving_throws),
            ),
            **({"spellcasting": self.spellcasting} if self.spellcasting is not None else {}),
        }


class LevelRecord(Interpreted):
    level: int
    proficiency_bonus: int | None = None
    cantrips_known: int | None = None
    spells_known: int | None = None
    ability_score_bonuses: int | None = None
    slots: tuple[tuple[int, int], ...] = ()
    # Whole-number class ladders (ki-points, sorcery-points, ...): keys are open-ended per class.
    class_numbers: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    dice_ladders: FrozenMap[Slug, DiceExpr] = EMPTY_FROZEN_MAP
    cr_caps: FrozenMap[Slug, str] = EMPTY_FROZEN_MAP
    slot_creation: tuple[tuple[int, int], ...] = ()
    # Barbarian rage count: a small int through level 19, then the level-20 sentinel. One string
    # fact carries both halves so they don't split across two keys.
    rage_count: str | None = None

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        return {
            "level": self.level,
            **_numbered("proficiency-bonus", self.proficiency_bonus),
            **_numbered("cantrips-known", self.cantrips_known),
            **_numbered("spells-known", self.spells_known),
            **_numbered("ability-score-bonuses", self.ability_score_bonuses),
            **{f"slot-{number}": count for number, count in self.slots},
            **self.class_numbers,
            **self.dice_ladders,
            **self.cr_caps,
            **_noted("rage-count", self.rage_count or ""),
            **(
                {"creating-spell-slots": [[at, cost] for at, cost in self.slot_creation]}
                if self.slot_creation
                else {}
            ),
        }


class MonsterRecord(Interpreted):
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
    # Sibling monster indexes (a vampire's bat/mist forms), not names: a monster ref, not prose.
    forms: tuple[Slug, ...] = ()
    spells: tuple[tuple[int, tuple[str, ...]], ...] = ()
    slots: tuple[tuple[int, int], ...] = ()
    size: str
    challenge_rating: str

    def mechanical_facts(self) -> Mapping[Slug, JsonValue]:
        spells = "; ".join(
            f"{'cantrips' if level == 0 else f'level {level}'}: {', '.join(names)}"
            for level, names in self.spells
        )
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
            **_noted("attacks", "; ".join(self.attacks)),
            **_noted("multiattack", self.multiattack or ""),
            **_noted("limited-use", "; ".join(self.limited_use)),
            **_noted("damage-vulnerabilities", ", ".join(self.damage_vulnerabilities)),
            **_noted("damage-resistances", ", ".join(self.damage_resistances)),
            **_noted("damage-immunities", ", ".join(self.damage_immunities)),
            **_noted("condition-immunities", ", ".join(self.condition_immunities)),
            **({"forms": list(self.forms)} if self.forms else {}),
            **_noted("spells", spells),
            **({"slots": [[number, count] for number, count in self.slots]} if self.slots else {}),
            "size": self.size,
            "challenge-rating": self.challenge_rating,
        }


def _bonus_facts(
    bonuses: tuple[AbilityBonus, ...], floating_choose: int | None = None
) -> Mapping[Slug, JsonValue]:
    entries: list[JsonValue] = [
        {"ability": ABILITY_BY_ABBREVIATION[b.ability], "bonus": b.bonus} for b in bonuses
    ]
    if floating_choose is not None:
        entries.append({"ability": "choice", "bonus": 1, "choose": floating_choose})
    return {"ability-bonuses": entries} if entries else {}
