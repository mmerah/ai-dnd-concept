"""Spells, skills, and the three vocabularies that ship a payload."""

from aidm.engines.dnd5e.content.records.rules import (
    AlignmentRecord,
    ConditionRecord,
    LanguageRecord,
    SkillRecord,
)
from aidm.engines.dnd5e.content.records.spells import (
    SpellDamage,
    SpellRecord,
    SpellSave,
)

from .common import ability
from .upstream.rules import Alignment, Condition, Language, Skill, Spell, SpellDc, SpellScaling


def _spell_save(dc: SpellDc | None) -> SpellSave | None:
    if dc is None:
        return None
    return SpellSave(ability=ability(dc.dc_type.index), on_success=dc.dc_success)


def _spell_damage(scaling: SpellScaling | None) -> SpellDamage | None:
    if scaling is None:
        return None
    return SpellDamage(
        damage_type=None if scaling.damage_type is None else scaling.damage_type.index,
        at_slot_level=scaling.damage_at_slot_level,
        at_character_level=scaling.damage_at_character_level,
    )


def spell(record: Spell) -> SpellRecord:
    return SpellRecord(
        index=record.index,
        name=record.name,
        desc="\n\n".join(record.desc),
        level=record.level,
        school=record.school.index,
        classes=tuple(c.index for c in record.classes),
        subclasses=tuple(s.index for s in record.subclasses),
        casting_time=record.casting_time,
        range=record.range,
        duration=record.duration,
        concentration=record.concentration,
        ritual=record.ritual,
        attack_type=record.attack_type,
        save=_spell_save(record.dc),
        damage=_spell_damage(record.damage),
        heal_at_slot_level=record.heal_at_slot_level,
    )


def skill(record: Skill) -> SkillRecord:
    return SkillRecord(
        index=record.index, name=record.name, ability=ability(record.ability_score.index)
    )


def condition(record: Condition) -> ConditionRecord:
    return ConditionRecord(index=record.index, name=record.name, desc="\n".join(record.desc))


def alignment(record: Alignment) -> AlignmentRecord:
    return AlignmentRecord(
        index=record.index,
        name=record.name,
        abbreviation=record.abbreviation,
        desc=record.desc,
    )


def language(record: Language) -> LanguageRecord:
    return LanguageRecord(
        index=record.index,
        name=record.name,
        script=record.script,
        typical_speakers=tuple(record.typical_speakers),
    )
