"""What every projector needs: abilities, distances, refs, damage and usage."""

import re
from collections.abc import Sequence

from aidm.content.records.base import Collection, DamageRoll
from aidm.content.records.monsters import (
    AtWill,
    PerDay,
    RechargeAfterRest,
    RechargeOnRoll,
    Usage,
)
from aidm.utils.models import Ability

from .upstream.base import Damage
from .upstream.monsters import UpstreamUsage

# The database spells abilities two ways — `str` in Ability-Scores and Skills, `strength` in
# Monsters. This map is the single place the abbreviation is resolved.
ABILITY_BY_ABBREVIATION: dict[str, Ability] = {
    "str": "strength",
    "dex": "dexterity",
    "con": "constitution",
    "int": "intelligence",
    "wis": "wisdom",
    "cha": "charisma",
}

# A `choose` between damage options is the one-handed grip on 15 of 16 monster entries, where the
# options differ only in dice. The djinni's scimitar is a genuine lightning-or-thunder choice with
# nothing to distinguish the two, so taking the first is arbitrary — named here rather than hidden
# inside a rule that would silently swallow the next one upstream introduces. Keyed by collection
# and index, because a bare index is not an identity: `djinni` could equally be a weapon.
AMBIGUOUS_DAMAGE_CHOICE = {"monsters/djinni"}

PACK_ID = "srd-2014"

_FEET = re.compile(r"^(\d+) ft\.")
_INDEX_IN_URL = re.compile(r"/([a-z0-9-]+)$")


def ability(abbreviation: str) -> Ability:
    spelled = ABILITY_BY_ABBREVIATION.get(abbreviation)
    if spelled is None:
        raise ValueError(f"unknown ability abbreviation {abbreviation!r}")
    return spelled


def feet(value: str) -> int:
    """'60 ft. (blind beyond this radius)' -> 60. The parenthetical is a rule `engine/` cannot
    apply; the distance is one it can."""
    match = _FEET.match(value)
    if match is None:
        raise ValueError(f"cannot read a distance from {value!r}")
    return int(match[1])


def index_of(url: str) -> str:
    """`Monsters.spellcasting.spells[]` carries `{name, level, url}` and no `index` at all, so the
    url is the only thing a ref can be built from."""
    match = _INDEX_IN_URL.search(url)
    if match is None:
        raise ValueError(f"cannot read an index from {url!r}")
    return match[1]


def owner_of(collection: Collection, index: str) -> str:
    """Who a damage entry belongs to, addressed the way a `ContentRef` is: an allowlist keyed by a
    bare index would silently cover a record of that index in any other collection."""
    return f"{collection}/{index}"


def damage_roll(damage: Damage, owner: str) -> DamageRoll:
    if damage.options is not None:
        chosen = damage.options.options
        types = {o.damage_type.index for o in chosen if o.damage_type is not None}
        if len(types) > 1 and owner not in AMBIGUOUS_DAMAGE_CHOICE:
            raise ValueError(f"{owner!r} chooses between damage types {sorted(types)}")
        return damage_roll(chosen[0], owner)
    if damage.damage_dice is None or damage.damage_type is None:
        raise ValueError(f"damage entry carries neither dice nor options: {damage!r}")
    return DamageRoll(dice=damage.damage_dice, damage_type=damage.damage_type.index)


def damages(entries: Sequence[Damage], owner: str) -> tuple[DamageRoll, ...]:
    return tuple(damage_roll(d, owner) for d in entries)


def usage(entry: UpstreamUsage | None) -> Usage | None:
    if entry is None:
        return None
    match entry.type:
        case "recharge on roll" if entry.dice is not None and entry.min_value is not None:
            return RechargeOnRoll(dice=entry.dice, min_value=entry.min_value)
        case "per day" if entry.times is not None:
            return PerDay(times=entry.times)
        case "at will":
            return AtWill()
        case "recharge after rest":
            return RechargeAfterRest(rest_types=tuple(entry.rest_types))
        case _:
            raise ValueError(f"unreadable usage {entry!r}")
