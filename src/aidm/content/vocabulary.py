"""Closed vocabularies prevent ambiguous bare slugs across collections."""

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
