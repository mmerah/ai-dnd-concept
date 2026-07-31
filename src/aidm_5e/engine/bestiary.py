from aidm.domain.base import EntityId, Kind

from ..content.records.base import ContentRef
from ..content.registry import COLLECTION_SPECS
from ..domain.models.stats import StatBlock
from ..models import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eItemDefinition,
    Dnd5eItemState,
)
from .ruleset import ArchetypeRules


def statted_actor(
    actor_id: EntityId, authored: Dnd5eActorDefinition | None, ruleset: ArchetypeRules
) -> Dnd5eActorState:
    stats = None if authored is None else authored.stats
    ref = None if authored is None else authored.ref
    if ref is None:
        # Copy: the authored definition outlives the game, and a stat block is mutable now.
        return Dnd5eActorState(stats=StatBlock() if stats is None else stats.model_copy(deep=True))
    _require_backing(actor_id, "actor", ref, ruleset)
    if stats is not None:
        raise ValueError(f"actor {actor_id!r} names a record and also declares its own stats")
    archetype = ruleset.archetype(ref)
    if archetype is None:
        raise ValueError(f"{actor_id!r} names {ref}, which is no archetype")
    return Dnd5eActorState(stats=archetype.stats.model_copy(deep=True), ref=ref)


def statted_item(
    item_id: EntityId, authored: Dnd5eItemDefinition | None, ruleset: ArchetypeRules
) -> Dnd5eItemState:
    ref = None if authored is None else authored.ref
    if ref is not None:
        _require_backing(item_id, "item", ref, ruleset)
    return Dnd5eItemState(ref=ref)


def _require_backing(
    entity_id: EntityId, kind: Kind, ref: ContentRef, ruleset: ArchetypeRules
) -> None:
    if kind != COLLECTION_SPECS[ref.collection].entity:
        raise ValueError(f"a {kind} may not name a {ref.collection} record: {entity_id!r}")
    if not ruleset.provides(ref):
        raise ValueError(f"{entity_id!r} names {ref}, which nothing provides")
