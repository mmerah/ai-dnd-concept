from ..content.registry import COLLECTION_SPECS
from ..domain.models.entities import ActorEntity, Entity
from ..domain.models.state import GameState
from ..domain.models.stats import StatBlock
from ..utils.models import updated
from .ruleset import ArchetypeRules


def statted(entity: Entity, ruleset: ArchetypeRules) -> Entity:
    ref = entity.ref
    if ref is None:
        return entity
    if entity.kind != COLLECTION_SPECS[ref.collection].entity:
        raise ValueError(f"a {entity.kind} may not name a {ref.collection} record: {entity.id!r}")
    if not isinstance(entity, ActorEntity):
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
    entities = list(state.world.entities.values())
    unbacked = sorted(
        f"{e.id}: {e.ref}" for e in entities if e.ref is not None and not ruleset.provides(e.ref)
    )
    if unbacked:
        raise ValueError(f"the world references content nothing provides: {unbacked}")
    filled = {e.id: statted(e, ruleset) for e in entities}
    return updated(state, world=updated(state.world, entities=filled))
