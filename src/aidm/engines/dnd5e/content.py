import re
from collections.abc import Mapping
from types import MappingProxyType

from aidm.core.base import Frozen, Slug
from aidm.core.dice import DiceExpr
from aidm.core.packs import Content, ContentMiss, LenientRecord, parse_ref
from aidm.core.sheet import Sheet

ABILITIES: Mapping[str, Slug] = MappingProxyType(
    {
        "STR": "strength",
        "DEX": "dexterity",
        "CON": "constitution",
        "INT": "intelligence",
        "WIS": "wisdom",
        "CHA": "charisma",
    }
)

_TERM = r"\d+d\d+|\d+"
_DICE_EXPR = re.compile(rf"^(?:{_TERM})(?:\s[+-]\s(?:{_TERM}))*")
_MODIFIER_SUFFIX = " + spellcasting modifier"
_SCALING_ROW = re.compile(r"^(?:level|slot) (\d+):\s*(.+)$")


class Amount(Frozen):
    dice: DiceExpr
    with_modifier: bool = False

    @classmethod
    def parsed(cls, note: str) -> "Amount | None":
        matched = _DICE_EXPR.match(note)
        if matched is None:
            return None
        dice = matched.group(0)
        rest = note[matched.end() :]
        return cls(dice=dice, with_modifier=rest.startswith(_MODIFIER_SUFFIX))

    def bonus(self, caster_modifier: int) -> int:
        return caster_modifier if self.with_modifier else 0


class WeaponFacts(Frozen):
    damage: DiceExpr
    versatile_damage: DiceExpr | None = None
    ranged: bool = False
    finesse: bool = False

    @classmethod
    def from_record(cls, record: LenientRecord) -> "WeaponFacts | None":
        count = record.numbers.get("damage-dice-count")
        die = record.numbers.get("damage-die")
        if count is None or die is None:
            return None
        versatile_damage = None
        if "versatile" in record.tags:
            two_count = record.numbers.get("two-handed-damage-dice-count")
            two_die = record.numbers.get("two-handed-damage-die")
            if two_count is not None and two_die is not None:
                versatile_damage = f"{two_count}d{two_die}"
        return cls(
            damage=f"{count}d{die}",
            versatile_damage=versatile_damage,
            ranged="ranged" in record.tags,
            finesse="finesse" in record.tags,
        )

    def dice(self, two_handed: bool) -> DiceExpr:
        if two_handed and self.versatile_damage is not None:
            return self.versatile_damage
        return self.damage


class SpellFacts(Frozen):
    name: str
    level: int | None = None
    attack: bool = False
    save_ability: Slug | None = None
    half_on_save: bool = False
    damage: Amount | None = None
    heal: Amount | None = None
    scaling: tuple[tuple[int, Amount], ...] = ()
    concentration: bool = False

    @classmethod
    def from_record(cls, record: LenientRecord) -> "SpellFacts | None":
        level_note = record.notes.get("level")
        if level_note == "cantrip":
            level = None
        elif level_note is not None and level_note.isdigit():
            level = int(level_note)
        else:
            return None

        save_ability: Slug | None = None
        half_on_save = False
        save_note = record.notes.get("save")
        if save_note is not None:
            save_ability = ABILITIES.get(save_note[:3])
            if save_ability is None:
                return None
            half_on_save = "half on success" in save_note

        damage = None
        damage_note = record.notes.get("damage")
        if damage_note is not None:
            damage = Amount.parsed(damage_note)
            if damage is None:
                return None

        heal = None
        heal_note = record.notes.get("heal")
        if heal_note is not None:
            heal = Amount.parsed(heal_note)
            if heal is None:
                return None

        return cls(
            name=record.name,
            level=level,
            attack="attack" in record.notes,
            save_ability=save_ability,
            half_on_save=half_on_save,
            damage=damage,
            heal=heal,
            scaling=_scaling(record.notes.get("scaling")),
            concentration="concentration" in record.tags,
        )

    def damage_at(self, key: int) -> Amount | None:
        return _scaled(self.damage, self.scaling, key)

    def heal_at(self, key: int) -> Amount | None:
        return _scaled(self.heal, self.scaling, key)


def weapon_of(content: Content, item: Sheet) -> WeaponFacts | None:
    for ref in item.refs:
        if ref.collection != "weapons":
            continue
        record = content.get(ref, LenientRecord)
        if isinstance(record, ContentMiss):
            continue
        facts = WeaponFacts.from_record(record)
        if facts is not None:
            return facts
    return None


def spell_of(content: Content, ref: str) -> SpellFacts | None:
    reference = parse_ref(ref)
    if reference.collection != "spells":
        raise ValueError(f"{ref!r} names no spell: name a record from the spells collection")
    record = content.get(reference, LenientRecord)
    if isinstance(record, ContentMiss):
        raise ValueError(f"{record.summary}; use a ref exactly as it was shown")
    return SpellFacts.from_record(record)


def spellcasting_ability(content: Content, sheet: Sheet) -> Slug | None:
    resolved = [
        record
        for ref in sheet.refs
        if ref.collection == "classes"
        for record in (content.get(ref, LenientRecord),)
        if not isinstance(record, ContentMiss)
    ]
    if len(resolved) != 1:
        return None
    note = resolved[0].notes.get("spellcasting")
    return None if note is None else ABILITIES.get(note)


def _scaling(note: str | None) -> tuple[tuple[int, Amount], ...]:
    if note is None:
        return ()
    rows: list[tuple[int, Amount]] = []
    for piece in note.split(", "):
        matched = _SCALING_ROW.match(piece.strip())
        if matched is None:
            continue
        amount = Amount.parsed(matched.group(2))
        if amount is None:
            continue
        rows.append((int(matched.group(1)), amount))
    return tuple(sorted(rows, key=lambda row: row[0]))


def _scaled(
    base: Amount | None, scaling: tuple[tuple[int, Amount], ...], key: int
) -> Amount | None:
    if base is None:
        return None
    later = [amount for threshold, amount in scaling if threshold <= key]
    return later[-1] if later else base
