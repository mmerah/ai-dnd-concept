from collections.abc import Iterable, Sequence
from typing import assert_never

from ..content.library import ContentMiss
from ..content.records.base import ContentRef, DamageRoll
from ..content.records.monsters import (
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
)
from ..domain.models.base import PLAYER_ID
from ..domain.models.direction import Direction
from ..domain.models.entities import ActorEntity, Entity, GrowthRequest, ItemEntity, LocationEntity
from ..domain.models.progression import MAX_LEVEL, Progression, feature_key, spell_key
from ..domain.models.state import Exchange
from ..domain.models.stats import StatBlock
from ..engine import features, spells
from ..engine.ruleset import NarrativeRules
from ..utils.models import Attributes
from .context import Scene


def label(e: Entity) -> str:
    return f"{e.name}[id={e.id}]"


def _kind(entity: Entity) -> str:
    return "npc" if isinstance(entity, ActorEntity) else entity.kind


def _placement(entity: Entity, scene: Scene) -> str:
    match entity:
        case LocationEntity():
            return ""
        case ActorEntity():
            place = scene.canon.get(entity.location_id)
            return f" — at {place.name}" if place else ""
        case ItemEntity():
            held_by = scene.state.world.container_of(entity)
            if isinstance(held_by, LocationEntity):
                return f" — at {held_by.name}"
            return " — carried" if held_by.id == PLAYER_ID else f" — held by {held_by.name}"


def briefs(items: Iterable[Entity], scene: Scene) -> str:
    return (
        "\n".join(f"- {label(e)} ({_kind(e)}){_placement(e, scene)} — {e.brief}" for e in items)
        or "- (none)"
    )


def here(scene: Scene) -> str:
    return briefs(scene.here, scene)


def elsewhere(scene: Scene) -> str:
    return briefs(scene.elsewhere, scene)


def unrevealed(scene: Scene) -> str:
    return briefs(scene.unrevealed, scene)


def catalogue(scene: Scene) -> str:
    return briefs(scene.shown, scene)


def statblocks(scene: Scene, rules: NarrativeRules) -> str:
    lines = [
        f"- {label(e)} (npc) — {_statline(e.stats)}{_archetype(e.ref, rules)}"
        for e in scene.here
        if isinstance(e, ActorEntity)
    ]
    return "\n".join(lines) or "- (none)"


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


def conditions(stats: StatBlock) -> str:
    return f" — under {', '.join(stats.conditions)}" if stats.conditions else ""


def _archetype(ref: ContentRef | None, rules: NarrativeRules) -> str:
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


def _klass(progression: Progression, rules: NarrativeRules) -> str:
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


def _spell_list(progression: Progression, rules: NarrativeRules) -> list[str]:
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
    rules: NarrativeRules,
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


def character(scene: Scene, rules: NarrativeRules) -> str:
    player = scene.state.player
    stats = player.stats
    # Stable ordering avoids prompt churn.
    inventory = (
        "\n".join(f"- {label(e)} — {e.brief}" for e in sorted(scene.carried, key=lambda e: e.name))
        or "- (none)"
    )
    progression = player.progression
    lines = [
        f"{player.name} — hp {stats.hp}/{stats.max_hp} — ac {stats.ac}"
        f"{conditions(stats)} — at {label(scene.where)}",
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
        f"inventory:\n{inventory}",
    ]
    return "\n".join(lines)


def narrator_character(scene: Scene) -> str:
    player = scene.state.player
    inventory = (
        "\n".join(
            f"- {item.name} — {item.brief}" for item in sorted(scene.carried, key=lambda e: e.name)
        )
        or "- (none)"
    )
    return f"{player.name} — at {scene.where.name}\ninventory:\n{inventory}"


def level_up_status(scene: Scene) -> str:
    current = scene.state.player.progression
    if current is None:
        return "unavailable — the player has no class"
    if current.level >= MAX_LEVEL:
        return f"unavailable — level {MAX_LEVEL} is the maximum"
    if current.level_up_available:
        return "already awarded — waiting for the player to complete it in the level-up UI"
    return (
        "not awarded — `level_up` unlocks the player's level-up UI when their achievements earn it"
    )


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(scene: Scene, direction: Direction) -> str:
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    entity = scene.canon.get(direction.speaker_id)
    if entity is None or not entity.known or entity.id == PLAYER_ID:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    if not scene.is_here(entity):
        raise ValueError(f"director named a speaker who is not here: {direction.speaker_id!r}")
    return f"{label(entity)} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    where = f"\nlocation: {item.location}" if item.location else ""
    kind = "an npc" if item.kind == "actor" else f"a {item.kind}"
    return f"{kind} named {item.name}\nbrief: {item.brief}{where}"
