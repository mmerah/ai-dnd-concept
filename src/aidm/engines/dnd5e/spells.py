from collections.abc import Mapping

from aidm.state.base import Slug
from aidm.state.packs import Content, ContentRef, Record, is_int_fact

CANTRIPS_KNOWN = "cantrips-known"
SPELLS_KNOWN = "spells-known"
# Ordered as every count here returns: cantrips first, then leveled spells.
KEYS: tuple[Slug, Slug] = (CANTRIPS_KNOWN, SPELLS_KNOWN)

# A pack level row counts what a class *knows*. A prepared caster's list size lives only in class
# prose: a wizard's spellbook holds six 1st-level spells, and a cleric or druid prepares its
# casting modifier + level, which the standard array makes three at level 1. Creation seeds one
# list per caster and play reads only that, so a prepared caster cannot swap its list on a long
# rest — the one SRD rule this model trades away for a single piece of state.
_PREPARED_AT_LEVEL_ONE: Mapping[Slug, int] = {"cleric": 3, "druid": 3, "wizard": 6}
# What a level-up adds where the pack counts nothing: the wizard copies two spells into its
# spellbook, and a prepared list grows by one with the level in its own formula.
_PREPARED_GROWTH: Mapping[Slug, int] = {"cleric": 1, "druid": 1, "paladin": 1, "wizard": 2}


def slot_recharge(class_index: Slug) -> str:
    """Pact magic slots return on a short rest; every other class waits for a long one."""
    return "short-rest" if class_index == "warlock" else "long-rest"


def castable(content: Content, class_name: str, level: int) -> tuple[ContentRef, ...]:
    """Every spell of that class at that level, cantrips at level 0. A spell names its classes by
    display name, which is the class record's own `name`; `subclasses` marks bonus domain lists a
    base class never gets, so it stays unread."""
    found = [
        (record.name, ref)
        for ref in content.records
        if ref.collection == "spells"
        for record in (content.require(ref),)
        if _level(record) == level and class_name in _classes(record)
    ]
    return tuple(ref for _, ref in sorted(found))


def known_at_level_one(class_index: Slug, level_one: Record) -> tuple[int, int]:
    """How many cantrips and leveled spells a new character of the class picks."""
    return (
        _count(level_one, CANTRIPS_KNOWN),
        _count(level_one, SPELLS_KNOWN) or _PREPARED_AT_LEVEL_ONE.get(class_index, 0),
    )


def growth(
    class_index: Slug, sheet_numbers: Mapping[Slug, int], next_level: Record
) -> tuple[int, int]:
    """How many cantrips and spells one level adds: what the new row totals, less what is held.
    A class the pack counts nothing for grows by its own prose instead."""
    cantrips = max(0, _count(next_level, CANTRIPS_KNOWN) - sheet_numbers.get(CANTRIPS_KNOWN, 0))
    counted = _count(next_level, SPELLS_KNOWN)
    if counted:
        return cantrips, max(0, counted - sheet_numbers.get(SPELLS_KNOWN, 0))
    return cantrips, _PREPARED_GROWTH.get(class_index, 0) if _casts(next_level) else 0


def verify(content: Content, class_ref: ContentRef, class_name: str, level_one: Record) -> None:
    """A caster whose pack list cannot fill its own count would refuse mid-creation, so the pool
    is measured at engine build."""
    for level, wanted in enumerate(known_at_level_one(class_ref.index, level_one)):
        offered = len(castable(content, class_name, level))
        if offered < wanted:
            raise ValueError(
                f"{class_ref} picks {wanted} level {level} spells from a list of {offered}"
            )


def _casts(record: Record) -> bool:
    return any(key.startswith("slot-") for key in record.facts)


def _count(record: Record, key: Slug) -> int:
    held = record.facts.get(key)
    return held if is_int_fact(held) else 0


def _level(record: Record) -> int:
    # A cantrip carries no level fact at all; every other spell names its own.
    held = record.facts.get("level")
    return held if is_int_fact(held) else 0


def _classes(record: Record) -> tuple[str, ...]:
    held = record.facts.get("classes")
    return tuple(name.strip() for name in held.split(",")) if isinstance(held, str) else ()
