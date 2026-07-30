"""Spells, skills, and the vocabularies that ship a payload."""

from pydantic import Field

from aidm.content.records.spells import SpellAttackType, SpellSaveOutcome
from aidm.content.vocabulary import AlignmentName, ConditionName, LanguageName

from .base import ApiRef, DamageTypeRef, SchoolRef, Upstream


class SpellDc(Upstream):
    dc_type: ApiRef
    dc_success: SpellSaveOutcome


class SpellScaling(Upstream):
    damage_type: DamageTypeRef | None = None
    damage_at_slot_level: dict[int, str] = Field(default_factory=dict)
    damage_at_character_level: dict[int, str] = Field(default_factory=dict)


class Spell(Upstream):
    index: str
    name: str
    desc: list[str]
    level: int
    school: SchoolRef
    classes: list[ApiRef]
    subclasses: list[ApiRef] = Field(default_factory=list)
    casting_time: str
    range: str
    duration: str
    concentration: bool
    ritual: bool
    attack_type: SpellAttackType | None = None
    dc: SpellDc | None = None
    damage: SpellScaling | None = None
    heal_at_slot_level: dict[int, str] = Field(default_factory=dict)


class Skill(Upstream):
    index: str
    name: str
    ability_score: ApiRef


class Condition(Upstream):
    index: ConditionName
    name: str
    desc: list[str]


class Alignment(Upstream):
    index: AlignmentName
    name: str
    abbreviation: str
    desc: str


class Language(Upstream):
    index: LanguageName
    name: str
    script: str | None = None
    typical_speakers: list[str] = Field(default_factory=list)
