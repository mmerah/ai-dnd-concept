from typing import Annotated, Literal

from pydantic import Field

from aidm.utils.models import EMPTY_FROZEN_MAP, FrozenMap

from ...utils.dice import DiceExpr
from ...utils.models import Ability, Frozen, Slug
from ..vocabulary import DamageType, MagicSchool
from .base import Record

MAX_SPELL_LEVEL = 9

# 0 is a cantrip, which costs no slot and scales off the caster's level instead.
type SpellLevel = Annotated[int, Field(ge=0, le=MAX_SPELL_LEVEL)]
# The level of a slot, which a cantrip never occupies.
type SlotLevel = Annotated[int, Field(ge=1, le=MAX_SPELL_LEVEL)]

SpellAttackType = Literal["melee", "ranged"]
SpellSaveOutcome = Literal["none", "half", "other"]


class SpellDamage(Frozen):
    damage_type: DamageType | None = None
    at_slot_level: FrozenMap[int, DiceExpr] = EMPTY_FROZEN_MAP
    at_character_level: FrozenMap[int, DiceExpr] = EMPTY_FROZEN_MAP


class SpellSave(Frozen):
    ability: Ability
    on_success: SpellSaveOutcome


class SpellRecord(Record):
    desc: str
    level: SpellLevel
    school: MagicSchool
    # A spell no class may cast is unreachable content, so at least one list must name it.
    classes: tuple[Slug, ...] = Field(min_length=1)
    # Subclasses whose expanded list adds this spell to a class that could not otherwise cast it.
    subclasses: tuple[Slug, ...] = ()
    casting_time: str
    range: str
    duration: str
    concentration: bool
    ritual: bool
    attack_type: SpellAttackType | None = None
    save: SpellSave | None = None
    damage: SpellDamage | None = None
    heal_at_slot_level: FrozenMap[int, DiceExpr] = EMPTY_FROZEN_MAP
