"""Content records become live entities here — the one place the static/mutable line is drawn.

An entity is an instance (this goblin, here, with 5 hp left); a record is an archetype (all
goblins). Numbers the reducer touches are snapshotted at creation, so a pack bump cannot move a
saved actor's hit points; everything descriptive or procedural is read live through `entity.ref`."""

from typing import assert_never

from ..content import Collection, ContentMiss, Library, MonsterRecord
from ..domain.models import ActorEntity, Entity, GameState, Kind, StatBlock, updated


def stat_block(monster: MonsterRecord) -> StatBlock:
    """Fixed hit points, not `hit_points_roll`: a rolled value is unrecomputable, so the same
    scenario would load differently each time."""
    return StatBlock(
        attributes=monster.attributes,
        max_hp=monster.hit_points,
        hp=monster.hit_points,
        ac=monster.armor_class,
        condition_immunities=monster.condition_immunities,
        saving_throws=monster.saving_throws,
    )


def statted(entity: Entity, library: Library) -> Entity | ContentMiss:
    """An authored entity filled in from the record it names. A record nothing provides is a value
    the caller decides about; an entity contradicting its own ref is a broken invariant and raises.
    """
    ref = entity.ref
    if ref is None:
        return entity
    if entity.kind != _named_by(ref.collection):
        raise ValueError(f"a {entity.kind} may not name a {ref.collection} record: {entity.id!r}")
    if not isinstance(entity, ActorEntity):
        miss = library.resolves(ref)
        return entity if miss is None else miss
    if entity.stats != StatBlock():
        raise ValueError(f"actor {entity.id!r} names a record and also declares its own stats")
    monster = library.get(ref, MonsterRecord)
    if isinstance(monster, ContentMiss):
        return monster
    return updated(entity, stats=stat_block(monster))


def statted_world(state: GameState, library: Library) -> GameState:
    """Every entity of a composed world, filled from the record it names. Run after composition
    rather than on the scenario definition, so a character's starting item meets the same check as
    authored canon. Load fails fast: a stat block of silent defaults would be worse than no game."""
    filled = [statted(e, library) for e in state.world.entities.values()]
    if missed := [f.summary for f in filled if isinstance(f, ContentMiss)]:
        raise ValueError(f"the world references content nothing provides: {missed}")
    entities = {e.id: e for e in filled if not isinstance(e, ContentMiss)}
    return updated(state, world=updated(state.world, entities=entities))


def _named_by(collection: Collection) -> Kind | None:
    """The one kind of entity that may name this collection, or `None` where none may — a spell is
    cast, never stood next to. Exhaustive, so a new collection must answer the question."""
    match collection:
        case "monsters":
            return "actor"
        case "weapons" | "armor" | "gear" | "tools" | "vehicles" | "magic_items":
            return "item"
        case (
            "spells"
            | "skills"
            | "conditions"
            | "alignments"
            | "languages"
            | "classes"
            | "subclasses"
            | "levels"
            | "features"
            | "races"
            | "subraces"
            | "traits"
            | "backgrounds"
            | "feats"
            | "proficiencies"
        ):
            return None
        case _:
            assert_never(collection)
