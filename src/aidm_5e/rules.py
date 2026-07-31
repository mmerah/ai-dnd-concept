from random import Random

from aidm.domain.base import EntityId
from aidm.domain.engine import EngineData
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.events import Event, RuleEvent, RuleStatePatch
from aidm.domain.state import GameState

from .codecs import ACTOR_STATE_CODEC, GAME_STATE_CODEC, ITEM_STATE_CODEC
from .constants import ENGINE_ID, SCHEMA_VERSION
from .conversion import event_from_legacy, rules_for_legacy_entity, to_legacy_state
from .domain.models.direction import Dnd5eDirection
from .domain.models.entities import ActorEntity as LegacyActor
from .domain.models.entities import Entity as LegacyEntity
from .domain.models.entities import ItemEntity as LegacyItem
from .domain.reducer import apply as legacy_apply
from .engine.resolve import resolve as legacy_resolve
from .engine.ruleset import Ruleset
from .events import decode_dnd5e_event
from .utils.models import updated


class Dnd5eRules:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def resolve(
        self,
        direction: Dnd5eDirection,
        state: GameState,
        rng: Random,
    ) -> list[Event]:
        legacy = to_legacy_state(state)
        events = legacy_resolve(direction.mechanics, legacy, rng, self._ruleset)
        return [event_from_legacy(event) for event in events]

    def apply(self, state: GameState, event: RuleEvent) -> RuleStatePatch:
        typed = decode_dnd5e_event(event, ENGINE_ID, SCHEMA_VERSION)
        before = to_legacy_state(state)
        after = legacy_apply(before, [typed])
        changed: dict[EntityId, EngineData | None] = {}
        for legacy_id, entity in after.world.entities.items():
            previous = before.world.entities[legacy_id]
            if entity == previous:
                continue
            _require_rules_only_change(entity, previous)
            changed[EntityId(str(legacy_id))] = rules_for_legacy_entity(entity)
        return RuleStatePatch(entity_rules=changed)

    def validate_state(self, state: GameState) -> None:
        if state.engine != ENGINE_ID:
            raise ValueError(f"5e rules received a {state.engine!r} state")
        GAME_STATE_CODEC.decode(state.rules)
        to_legacy_state(state)
        for entity in state.world.entities.values():
            if isinstance(entity, ActorEntity):
                if entity.rules is None:
                    raise ValueError(f"5e actor {entity.id!r} has no rules data")
                actor = ACTOR_STATE_CODEC.decode(entity.rules)
                if actor.ref is not None and not self._ruleset.provides(actor.ref):
                    raise ValueError(f"5e actor {entity.id!r} has unknown ref {actor.ref}")
            elif isinstance(entity, ItemEntity):
                if entity.rules is None:
                    raise ValueError(f"5e item {entity.id!r} has no rules data")
                item = ITEM_STATE_CODEC.decode(entity.rules)
                if item.ref is not None and not self._ruleset.provides(item.ref):
                    raise ValueError(f"5e item {entity.id!r} has unknown ref {item.ref}")
            elif entity.rules is not None:
                raise ValueError(f"5e location {entity.id!r} must not have rules data")


def _require_rules_only_change(entity: LegacyEntity, previous: LegacyEntity) -> None:
    if isinstance(entity, LegacyActor) and isinstance(previous, LegacyActor):
        reverted = updated(
            entity, stats=previous.stats, progression=previous.progression, ref=previous.ref
        )
    elif isinstance(entity, LegacyItem) and isinstance(previous, LegacyItem):
        reverted = updated(entity, ref=previous.ref)
    else:
        reverted = entity
    if reverted != previous:
        raise ValueError(
            f"rule event changed a core-visible field of {entity.id!r}, "
            "which a rules-only patch cannot carry back to core"
        )
