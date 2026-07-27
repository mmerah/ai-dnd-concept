"""Spells: the level, the save, and how the dice scale."""

from typing import Literal

from pydantic import Field

from ...utils.dice import DiceExpr
from ...utils.models import Ability, Frozen, FrozenMap
from ..vocabulary import DamageType, MagicSchool
from .base import Record

SpellAttackType = Literal["melee", "ranged"]
SpellSaveOutcome = Literal["none", "half", "other"]


class SpellDamage(Frozen):
    """`damage_type` is absent on the two records whose damage is not typed damage."""

    damage_type: DamageType | None = None
    at_slot_level: FrozenMap[int, DiceExpr] = Field(default_factory=dict, validate_default=True)
    at_character_level: FrozenMap[int, DiceExpr] = Field(
        default_factory=dict, validate_default=True
    )


class SpellSave(Frozen):
    ability: Ability
    on_success: SpellSaveOutcome


class SpellRecord(Record):
    desc: str
    level: int = Field(ge=0, le=9)
    school: MagicSchool
    casting_time: str
    range: str
    duration: str
    concentration: bool
    ritual: bool
    attack_type: SpellAttackType | None = None
    save: SpellSave | None = None
    damage: SpellDamage | None = None
    # `MOD` is the caster's modifier: substituted at resolve time, never at load.
    heal_at_slot_level: FrozenMap[int, DiceExpr] = Field(
        default_factory=dict, validate_default=True
    )
