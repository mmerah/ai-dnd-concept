"""Renderers for single context fragments. Pure string in, pure string out."""

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
from ..domain.models import (
    PLAYER_ID,
    ActorEntity,
    Direction,
    Entity,
    EntityId,
    Exchange,
    GameState,
    GrowthRequest,
    ItemEntity,
    LocationEntity,
    Progression,
    StatBlock,
    find,
)


def label(e: Entity) -> str:
    """Every entity is shown as `name[id=...]`, so any role can reference it by the id it must use.
    A prose-only role ignores the bracket; a role that emits ids reads it off directly."""
    return f"{e.name}[id={e.id}]"


def canon_without_player(state: GameState) -> list[Entity]:
    """Every list a role is shown subtracts the player: canon, but never a role's target."""
    return [e for e in state.world.entities.values() if e.id != PLAYER_ID]


def _item_holder(state: GameState, item_id: EntityId) -> ActorEntity | None:
    actors = (e for e in state.world.entities.values() if isinstance(e, ActorEntity))
    return next((e for e in actors if item_id in e.inventory), None)


def _place(entity: Entity, state: GameState) -> tuple[EntityId | None, str]:
    """Where to file an entity, and the suffix that says so. A carried item travels with its
    holder, so it stays in context once picked up rather than dropping to a bare name."""
    entities = state.world.entities
    match entity:
        case LocationEntity():
            return None, ""
        case ActorEntity():
            place = entities.get(entity.location_id)
            return entity.location_id, f" — at {place.name}" if place else ""
        case ItemEntity():
            if entity.location_id is not None:
                place = entities.get(entity.location_id)
                return entity.location_id, f" — at {place.name}" if place else ""
            holder = _item_holder(state, entity.id)
            if holder is None:
                raise ValueError(f"cannot place item {entity.id!r}: nobody holds it")
            if holder.id == PLAYER_ID:
                return holder.location_id, " — carried"
            return holder.location_id, f" — held by {holder.name}"


def briefs(items: Iterable[Entity], state: GameState) -> str:
    return (
        "\n".join(f"- {label(e)} — {e.kind}{_place(e, state)[1]} — {e.brief}" for e in items)
        or "- (none)"
    )


def present(state: GameState) -> list[Entity]:
    """Everything filed at the player's location; their own items show under CHARACTER."""
    where = state.player.location_id
    carried = set(state.player.inventory)
    return [
        e
        for e in canon_without_player(state)
        if e.id not in carried and _place(e, state)[0] == where
    ]


def here(state: GameState) -> str:
    return briefs((e for e in present(state) if e.known), state)


def statblocks(state: GameState, library: Library) -> str:
    """What the Director may act on for every actor standing here, and it alone — a typed slice,
    never the record: a goblin is ~2,100 bytes pretty-printed and an adult red dragon ~6,100, which
    would roughly double this role's whole input. Hit points are deliberately absent: `intent`
    reaches the Narrator, so a number read here could be restated where the player would see it.
    Conditions come from the entity, so an actor with no archetype behind it still shows them."""
    lines = [
        f"- {label(e)} — ac {e.stats.ac}{conditions(e.stats)}{_archetype(e.ref, library)}"
        for e in present(state)
        if isinstance(e, ActorEntity) and e.known
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
    record = library.monster(ref)
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


def elsewhere(state: GameState) -> str:
    """Known entities away from here; the current location and carried items show elsewhere."""
    here_ids = {e.id for e in present(state)}
    current = state.player.location_id
    carried = set(state.player.inventory)

    def shown(e: Entity) -> bool:
        return e.known and e.id not in here_ids and e.id != current and e.id not in carried

    return briefs((e for e in canon_without_player(state) if shown(e)), state)


def unrevealed(state: GameState) -> str:
    return briefs((e for e in canon_without_player(state) if not e.known), state)


def catalogue(state: GameState) -> str:
    return briefs(canon_without_player(state), state)


def _klass(progression: Progression, library: Library) -> str:
    """The player's class line: names from the pack, numbers from the snapshot. Only what a role
    could use — a proficiency list is applied by the rules, never chosen by the Director."""
    record = library.klass(progression.origin.class_ref)
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


def character(state: GameState, library: Library) -> str:
    """The player's own sheet, and the one place exact hit points are shown. Fail fast: standing
    outside canon, or holding an id no entity backs, would feed a role an unusable reference."""
    player = state.player
    where = find(state.world.entities, player.location_id)
    if where is None:
        raise ValueError(f"character is at unknown location {player.location_id!r}")
    stats = player.stats
    attributes = ", ".join(f"{k} {v}" for k, v in stats.attributes.model_dump().items())
    items = [find(state.world.entities, i) for i in player.inventory]
    missing = [i for i, e in zip(player.inventory, items, strict=True) if e is None]
    if missing:
        raise ValueError(f"character holds unknown item id(s) {missing!r}")
    inventory = "\n".join(f"- {label(e)} — {e.brief}" for e in items if e is not None) or "- (none)"
    lines = [
        f"{player.name} — hp {stats.hp}/{stats.max_hp} — ac {stats.ac}"
        f"{conditions(stats)} — at {label(where)}",
        *([] if player.progression is None else [_klass(player.progression, library)]),
        f"attributes: {attributes}",
        f"inventory:\n{inventory}",
    ]
    return "\n".join(lines)


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(state: GameState, direction: Direction) -> str:
    """Fail fast: a hidden, unknown, or absent speaker would put words in a stranger's mouth."""
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    entity = find(state.world.entities, direction.speaker_id)
    if entity is None or not entity.known or entity.id == PLAYER_ID:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    if _place(entity, state)[0] != state.player.location_id:
        raise ValueError(f"director named a speaker who is not here: {direction.speaker_id!r}")
    return f"{label(entity)} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    where = f"\nlocation: {item.location}" if item.location else ""
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}{where}"
