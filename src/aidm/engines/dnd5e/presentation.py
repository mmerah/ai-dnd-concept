import json
from collections.abc import Sequence
from typing import assert_never

from aidm.base import PLAYER_ID, ActorEntity, Entity
from aidm.content import Rules

from . import features, spells
from .access import actor_state, item_state
from .content.library import ContentMiss
from .content.records.base import ContentRef, DamageRoll
from .content.records.monsters import (
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
)
from .ruleset import Ruleset
from .state import MAX_LEVEL, Progression, StatBlock, feature_key, spell_key
from .values import Attributes


class Dnd5ePresentation:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def entity_state(self, entity: Entity, rules: Rules) -> str:
        if not isinstance(entity, ActorEntity):
            return item_summary(item_state(rules).ref, self._ruleset)
        actor = actor_state(rules)
        if entity.id != PLAYER_ID:
            return actor_summary(actor.stats, actor.ref, self._ruleset)
        sheet = player_state(actor.stats, actor.progression, self._ruleset)
        return f"{sheet}\nadvancement: {level_up_state(actor.progression)}"


def _attributes(stats: StatBlock) -> str:
    return ", ".join(f"{name} {score}" for name, score in stats.attributes.model_dump().items())


def _statline(stats: StatBlock) -> str:
    saving_throws = ", ".join(
        f"{ability} {bonus:+d}" for ability, bonus in stats.saving_throws.items()
    )
    saves = f" — saves {saving_throws}" if stats.saving_throws else ""
    immunities = (
        f" — immune to the conditions {', '.join(stats.condition_immunities)}"
        if stats.condition_immunities
        else ""
    )
    return (
        f"hp {stats.hp}/{stats.max_hp} — ac {stats.ac}{conditions(stats)}"
        f" — attributes {_attributes(stats)}{saves}{immunities}"
    )


def actor_summary(
    stats: StatBlock,
    ref: ContentRef | None,
    rules: Ruleset,
) -> str:
    return f"{_statline(stats)}{_archetype(ref, rules)}"


def item_summary(ref: ContentRef | None, rules: Ruleset) -> str:
    if ref is None:
        return "5e profile: (none)"
    record = rules.record(ref)
    if isinstance(record, ContentMiss):
        return record.summary
    fields = json.dumps(
        record.model_dump(mode="json", exclude={"index", "name"}),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return f"5e profile {ref}: {record.name} {fields}"


def conditions(stats: StatBlock) -> str:
    return f" — under {', '.join(stats.conditions)}" if stats.conditions else ""


def _archetype(ref: ContentRef | None, rules: Ruleset) -> str:
    if ref is None:
        return ""
    record = rules.monster(ref)
    if isinstance(record, ContentMiss):
        return f" — {record.summary}"
    return f"{_moves(record)}{_defences(record)}"


def _moves(record: MonsterRecord) -> str:
    groups = (
        ("", record.actions),
        ("legendary: ", record.legendary_actions),
        ("reaction: ", record.reactions),
        ("trait: ", record.traits),
    )
    return "".join(
        f" — {prefix}{'; '.join(rendered)}"
        for prefix, actions in groups
        if (rendered := [m for m in (_move(a) for a in actions) if m])
    )


def _move(action: MonsterAction) -> str:
    when = f" [{action.usage}]" if action.usage is not None else ""
    hurts = f" ({_damage(action.damage)})" if action.damage else ""
    match action:
        case MonsterAttack():
            return f"{action.name} {action.attack_bonus:+d}{hurts}{when}"
        case MonsterSave():
            saved = f", {action.on_success} on a save" if action.on_success != "none" else ""
            return f"{action.name} dc {action.dc} {action.save_ability}{hurts}{saved}{when}"
        case MonsterMultiattack():
            return f"{action.name}: {' or '.join(str(o) for o in action.options)}{when}"
        case MonsterProcedure():
            return ""
        case _:
            assert_never(action)


def _defences(record: MonsterRecord) -> str:
    """Use slashes because upstream damage prose contains commas."""
    clauses = [
        f"{verb} {' / '.join(entries)}"
        for verb, entries in (
            ("resists", record.damage_resistances),
            ("immune to", record.damage_immunities),
            ("vulnerable to", record.damage_vulnerabilities),
        )
        if entries
    ]
    return "".join(f" — {clause}" for clause in clauses)


def _damage(rolls: Sequence[DamageRoll]) -> str:
    return ", ".join(f"{roll.dice} {roll.damage_type}" for roll in rolls)


def _klass(progression: Progression, rules: Ruleset) -> str:
    record = rules.klass(progression.origin.class_ref)
    if isinstance(record, ContentMiss):
        return record.summary
    subclass = progression.origin.subclass_ref
    parts = [
        f"level {progression.level} {record.name}"
        + ("" if subclass is None else f" ({subclass.index})"),
        f"proficiency +{progression.prof_bonus}",
    ]
    if record.spellcasting is not None:
        parts.append(f"casts with {record.spellcasting.ability}")
    if progression.spell_slots:
        slots = ", ".join(
            f"level {n} {state.remaining}/{state.maximum} ({state.recharge} rest)"
            for n, state in sorted(progression.spell_slots.items())
        )
        parts.append(f"spell slots {slots}")
    return " — ".join(parts)


def _spell_list(progression: Progression, rules: Ruleset) -> list[str]:
    """Grouped by level and named only, because a caster's list runs to hundreds of entries."""
    casting = rules.character(progression.origin).spellcasting
    castable = () if casting is None else spells.repertoire(progression, casting, rules)
    if not castable:
        return []
    levels: dict[int, list[str]] = {}
    for spell in castable:
        levels.setdefault(spell.level, []).append(f"{spell.name}[id={spell_key(spell.ref)}]")
    lines = "\n".join(f"- level {level}: {', '.join(named)}" for level, named in levels.items())
    return [f"spells:\n{lines}"]


def _feature_list(
    progression: Progression,
    attributes: Attributes,
    rules: Ruleset,
) -> str:
    lines: list[str] = []
    for status in features.owned(progression, attributes, rules):
        profile, pool = status.profile, status.pool
        tags = [features.actionability(profile)]
        if pool is not None:
            state = pool.state
            tags += [f"{state.remaining}/{state.maximum} uses", f"{state.recharge} rest"]
        if features.directly_invokable(profile):
            depleted = pool is not None and pool.state.remaining == 0
            tags.append("depleted" if depleted else "usable")
        desc = " ".join(profile.desc.split())
        lines.append(
            f"- {profile.name}[id={feature_key(profile.ref)}] [{' — '.join(tags)}] — {desc}"
        )
    return "features:\n" + ("\n".join(lines) or "- (none)")


def player_state(
    stats: StatBlock,
    progression: Progression | None,
    rules: Ruleset,
) -> str:
    lines = [
        f"hp {stats.hp}/{stats.max_hp} — ac {stats.ac}{conditions(stats)}",
        *(
            []
            if progression is None
            else [
                _klass(progression, rules),
                _feature_list(progression, stats.attributes, rules),
                *_spell_list(progression, rules),
            ]
        ),
        f"attributes: {_attributes(stats)}",
    ]
    return "\n".join(lines)


def level_up_state(current: Progression | None) -> str:
    if current is None:
        return "unavailable — the player has no class"
    if current.level >= MAX_LEVEL:
        return f"unavailable — level {MAX_LEVEL} is the maximum"
    if current.level_up_available:
        return "already awarded — waiting for the player to complete it in the level-up UI"
    return (
        "not awarded — `level_up` unlocks the player's level-up UI when their achievements earn it"
    )
