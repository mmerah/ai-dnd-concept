"""The closed vocabularies a record field is typed by.

Each is a whole SRD collection whose records carry nothing but a name and rulebook prose, so the
collection *is* its index set. Spelling them as `Literal`s rather than slugs is what stops a field
naming a collection it was never checked against: `light` is a Spell *and* a Weapon-Property,
`evocation` a Magic-School *and* a Subclass, so a bare slug says nothing about which was meant."""

from typing import Literal, get_args

DamageType = Literal[
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
]

MagicSchool = Literal[
    "abjuration",
    "conjuration",
    "divination",
    "enchantment",
    "illusion",
    "necromancy",
    "transmutation",
    "evocation",
]

# `exhaustion` is a 6-level track upstream and a flag here; nothing reads a level yet.
ConditionName = Literal[
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
]

CONDITION_NAMES: tuple[ConditionName, ...] = get_args(ConditionName)

AlignmentName = Literal[
    "lawful-good",
    "neutral-good",
    "chaotic-good",
    "lawful-neutral",
    "neutral",
    "chaotic-neutral",
    "lawful-evil",
    "neutral-evil",
    "chaotic-evil",
]

ALIGNMENT_NAMES: tuple[AlignmentName, ...] = get_args(AlignmentName)

LanguageName = Literal[
    "common",
    "dwarvish",
    "elvish",
    "giant",
    "gnomish",
    "goblin",
    "halfling",
    "orc",
    "abyssal",
    "celestial",
    "draconic",
    "deep-speech",
    "infernal",
    "primordial",
    "sylvan",
    "undercommon",
]

LANGUAGE_NAMES: tuple[LanguageName, ...] = get_args(LanguageName)

WeaponProperty = Literal[
    "ammunition",
    "finesse",
    "heavy",
    "light",
    "loading",
    "monk",
    "reach",
    "special",
    "thrown",
    "two-handed",
    "versatile",
]

# Both the broad kinds and the shelves within them; it is also what the 24 `equipment_category`
# choice nodes R7 flattens will point at.
EquipmentCategory = Literal[
    "weapon",
    "armor",
    "adventuring-gear",
    "ammunition",
    "tools",
    "mounts-and-vehicles",
    "simple-weapons",
    "martial-weapons",
    "melee-weapons",
    "ranged-weapons",
    "simple-melee-weapons",
    "simple-ranged-weapons",
    "martial-melee-weapons",
    "martial-ranged-weapons",
    "light-armor",
    "medium-armor",
    "heavy-armor",
    "shields",
    "standard-gear",
    "kits",
    "equipment-packs",
    "artisans-tools",
    "gaming-sets",
    "musical-instruments",
    "other-tools",
    "mounts-and-other-animals",
    "tack-harness-and-drawn-vehicles",
    "land-vehicles",
    "waterborne-vehicles",
    "arcane-foci",
    "druidic-foci",
    "holy-symbols",
    "wondrous-items",
    "rod",
    "potion",
    "ring",
    "scroll",
    "staff",
    "wand",
]
