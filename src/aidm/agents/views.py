"""Renderers for single context fragments. A `Scene` bucket in, a string out: the buckets
answered every "can the player see this" question, and only `speaker` re-checks an id a role
named for itself."""

from collections.abc import Iterable, Sequence
from typing import assert_never

from ..content import (
    ContentMiss,
    ContentRef,
    DamageRoll,
    Library,
    MonsterAction,
    MonsterAttack,
    MonsterMultiattack,
    MonsterProcedure,
    MonsterRecord,
    MonsterSave,
)
from ..content.records import ClassRecord
from ..domain.models import (
    PLAYER_ID,
    ActorEntity,
    Direction,
    Entity,
    Exchange,
    GrowthRequest,
    ItemEntity,
    LocationEntity,
    Progression,
    StatBlock,
)
from .context import Scene


def label(e: Entity) -> str:
    """Every entity is shown as `name[id=...]`, so any role can reference it by the id it must use.
    A prose-only role ignores the bracket; a role that emits ids reads it off directly."""
    return f"{e.name}[id={e.id}]"


def _placement(entity: Entity, scene: Scene) -> str:
    """The suffix saying where a thing is."""
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
        "\n".join(f"- {label(e)} — {e.kind}{_placement(e, scene)} — {e.brief}" for e in items)
        or "- (none)"
    )


def here(scene: Scene) -> str:
    return briefs(scene.here, scene)


def elsewhere(scene: Scene) -> str:
    """Known entities away from here. The player's own location and items are named elsewhere in the
    prompt, which is why the partition keeps them out of this bucket."""
    return briefs(scene.elsewhere, scene)


def unrevealed(scene: Scene) -> str:
    """Everything the player has not learned of — here with them, elsewhere, carried, or the very
    room they stand in. All of it is a legal `discover` target, so none of it may be filtered."""
    return briefs(scene.unrevealed, scene)


def catalogue(scene: Scene) -> str:
    return briefs(scene.shown, scene)


def statblocks(scene: Scene, library: Library) -> str:
    """What the Director may act on for every actor standing here, and it alone — a typed slice,
    never the record: a goblin is ~2,100 bytes pretty-printed and an adult red dragon ~6,100, which
    would roughly double this role's whole input. Hit points are deliberately absent: `intent`
    reaches the Narrator, so a number read here could be restated where the player would see it.
    Conditions come from the entity, so an actor with no archetype behind it still shows them."""
    lines = [
        f"- {label(e)} — ac {e.stats.ac}{conditions(e.stats)}{_archetype(e.ref, library)}"
        for e in scene.here
        if isinstance(e, ActorEntity)
    ]
    return "\n".join(lines) or "- (none)"


def conditions(stats: StatBlock) -> str:
    """A condition nobody can read is a condition nobody can lift, so every view of an actor —
    the player's own sheet included — says which ones hold."""
    return f" — under {', '.join(stats.conditions)}" if stats.conditions else ""


def _archetype(ref: ContentRef | None, library: Library) -> str:
    """A miss is rendered, never skipped: a pack that lost a record must show in the trace. An
    actor naming no record has no archetype to show, which is not a miss."""
    if ref is None:
        return ""
    record = library.get(ref, MonsterRecord)
    if isinstance(record, ContentMiss):
        return f" — {record.summary}"
    return f"{_moves(record)}{_defences(record)}"


def _moves(record: MonsterRecord) -> str:
    """Only what the Director could turn into a consequence; a procedure it can only narrate is
    left to the prose it already has. Legendary actions, reactions and traits carry to-hits, DCs
    and damage of their own — a whole action economy the Director would otherwise never see."""
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
    """Exhaustive, so a new action shape must answer whether the Director can act on it rather
    than silently rendering as nothing."""
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
    """Resistances are what make a damage type worth choosing, and a condition immunity is the
    difference between `apply_condition` landing and doing nothing — so the two are never merged:
    `poison` is a damage type and `poisoned` a condition, and a role told "immune to poison,
    poisoned" cannot tell which is which. Damage entries are upstream prose containing their own
    commas ('bludgeoning, piercing, and slashing from nonmagical weapons'), so they are separated
    by something prose does not contain."""
    clauses = [
        f"{verb} {' / '.join(entries)}"
        for verb, entries in (
            ("resists", record.damage_resistances),
            ("immune to", record.damage_immunities),
            ("vulnerable to", record.damage_vulnerabilities),
        )
        if entries
    ]
    if record.condition_immunities:
        clauses.append(f"immune to the conditions {', '.join(record.condition_immunities)}")
    return "".join(f" — {clause}" for clause in clauses)


def _damage(rolls: Sequence[DamageRoll]) -> str:
    return ", ".join(f"{roll.dice} {roll.damage_type}" for roll in rolls)


def _klass(progression: Progression, library: Library) -> str:
    """The player's class line: names from the pack, numbers from the snapshot. Only what a role
    could use — a proficiency list is applied by the rules, never chosen by the Director."""
    record = library.get(progression.origin.class_ref, ClassRecord)
    if isinstance(record, ContentMiss):
        return record.summary
    subclass = progression.origin.subclass_ref
    parts = [
        f"level {progression.level} {record.name}"
        + ("" if subclass is None else f" ({subclass.index})"),
        f"proficiency +{progression.prof_bonus}",
    ]
    if record.spellcasting_ability is not None:
        parts.append(f"casts with {record.spellcasting_ability}")
    if progression.spell_slots:
        slots = ", ".join(f"level {n} x{count}" for n, count in progression.spell_slots.items())
        parts.append(f"spell slots {slots}")
    return " — ".join(parts)


def character(scene: Scene, library: Library) -> str:
    """The player's own sheet, and the one place exact hit points are shown."""
    player = scene.state.player
    stats = player.stats
    attributes = ", ".join(f"{k} {v}" for k, v in stats.attributes.model_dump().items())
    # Sorted, not acquisition-ordered: order is a rendering concern, and a stable list keeps the
    # prompt from churning as items are picked up.
    inventory = (
        "\n".join(f"- {label(e)} — {e.brief}" for e in sorted(scene.carried, key=lambda e: e.name))
        or "- (none)"
    )
    lines = [
        f"{player.name} — hp {stats.hp}/{stats.max_hp} — ac {stats.ac}"
        f"{conditions(stats)} — at {label(scene.where)}",
        *([] if player.progression is None else [_klass(player.progression, library)]),
        f"attributes: {attributes}",
        f"inventory:\n{inventory}",
    ]
    return "\n".join(lines)


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(scene: Scene, direction: Direction) -> str:
    """Fail fast: a hidden, unknown, or absent speaker would put words in a stranger's mouth."""
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
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}{where}"
