"""Archetypes become live entities here — the one place the static/mutable line is drawn.

An entity is an instance (this goblin, here, with 5 hp left); an archetype is every goblin. Numbers
the reducer touches are snapshotted at creation, so a pack bump cannot move a saved actor's hit
points; everything descriptive or procedural is read live through `entity.ref`."""

from typing import assert_never

from ..content import Collection
from ..domain.models import ActorEntity, Entity, GameState, Kind, StatBlock, updated
from .ruleset import ArchetypeRules


def statted(entity: Entity, ruleset: ArchetypeRules) -> Entity:
    """An authored entity filled in from what it names. Fail-loud, and composing a world is not a
    turn: a stat block of silent defaults would be worse than no game."""
    ref = entity.ref
    if ref is None:
        return entity
    if entity.kind != _named_by(ref.collection):
        raise ValueError(f"a {entity.kind} may not name a {ref.collection} record: {entity.id!r}")
    if not isinstance(entity, ActorEntity):
        # Nothing reads an item's record at composition; that it exists is the whole check.
        if not ruleset.provides(ref):
            raise ValueError(f"{entity.id!r} names {ref}, which nothing provides")
        return entity
    if entity.stats != StatBlock():
        raise ValueError(f"actor {entity.id!r} names a record and also declares its own stats")
    archetype = ruleset.archetype(ref)
    if archetype is None:
        raise ValueError(f"{entity.id!r} names {ref}, which is no archetype")
    return updated(entity, stats=archetype.stats)


def statted_world(state: GameState, ruleset: ArchetypeRules) -> GameState:
    """Every entity of a composed world, filled from what it names. Run after composition rather
    than on the scenario definition, so a character's starting item meets the same check as authored
    canon. Unbacked refs are collected first: a load error naming one of six is a worse error."""
    entities = list(state.world.entities.values())
    unbacked = sorted(
        f"{e.id}: {e.ref}" for e in entities if e.ref is not None and not ruleset.provides(e.ref)
    )
    if unbacked:
        raise ValueError(f"the world references content nothing provides: {unbacked}")
    filled = {e.id: statted(e, ruleset) for e in entities}
    return updated(state, world=updated(state.world, entities=filled))


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
