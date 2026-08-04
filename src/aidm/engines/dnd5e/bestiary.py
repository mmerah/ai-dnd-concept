from aidm.core.base import EntityId, Kind
from aidm.core.content import Rules
from aidm.core.packs import ContentRef

from .content.registry import COLLECTION_SPECS
from .ruleset import Ruleset
from .state import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eItemDefinition,
    Dnd5eItemState,
    StatBlock,
)


def statted_actor(actor_id: EntityId, rules: Rules, ruleset: Ruleset) -> Dnd5eActorState:
    authored = Dnd5eActorDefinition.model_validate(rules)
    stats, ref = authored.stats, authored.ref
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


def statted_item(item_id: EntityId, rules: Rules, ruleset: Ruleset) -> Dnd5eItemState:
    authored = Dnd5eItemDefinition.model_validate(rules)
    if authored.ref is not None:
        _require_backing(item_id, "item", authored.ref, ruleset)
    return Dnd5eItemState(ref=authored.ref)


def _require_backing(entity_id: EntityId, kind: Kind, ref: ContentRef, ruleset: Ruleset) -> None:
    spec = COLLECTION_SPECS.get(ref.collection)
    if spec is None or kind != spec.entity:
        raise ValueError(f"a {kind} may not name a {ref.collection} record: {entity_id!r}")
    if not ruleset.provides(ref):
        raise ValueError(f"{entity_id!r} names {ref}, which nothing provides")
