import json

from aidm.domain.base import PLAYER_ID
from aidm.domain.direction import DirectionRecord
from aidm.domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from aidm.domain.events import RuleEvent
from aidm.domain.json import thaw_json

from .agents import views
from .codecs import ACTOR_STATE_CODEC, ITEM_STATE_CODEC
from .constants import ENGINE_ID, SCHEMA_VERSION
from .domain.models.events import (
    AttackRolled,
    ConditionChanged,
    DcRolled,
    DiceRolled,
    FeatureActivated,
    FeatureUsed,
    HpChanged,
    LeveledUp,
    LevelUpAvailable,
    Rested,
    SpellCast,
    SpellSlotSpent,
)
from .engine.ruleset import Ruleset
from .events import decode_dnd5e_event


class Dnd5ePresentation:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def entity_state(self, entity: Entity) -> str:
        match entity:
            case ActorEntity():
                if entity.rules is None:
                    raise ValueError(f"5e actor {entity.id!r} has no rules")
                state = ACTOR_STATE_CODEC.decode(entity.rules)
                if entity.id == PLAYER_ID:
                    sheet = views.player_state(state.stats, state.progression, self._ruleset)
                    advancement = views.level_up_state(state.progression)
                    return f"{sheet}\nadvancement: {advancement}"
                return views.actor_state(state.stats, state.ref, self._ruleset)
            case ItemEntity():
                if entity.rules is None:
                    raise ValueError(f"5e item {entity.id!r} has no rules")
                ref = ITEM_STATE_CODEC.decode(entity.rules).ref
                return views.item_state(ref, self._ruleset)
            case LocationEntity():
                return ""

    def narrator_event(self, event: RuleEvent) -> str | None:
        typed = decode_dnd5e_event(event, ENGINE_ID, SCHEMA_VERSION)
        match typed:
            case DcRolled(actor_name=name, success=success):
                return f"{name} {'succeeds' if success else 'fails'}"
            case AttackRolled(
                actor_name=actor,
                target_name=target,
                hit=hit,
            ):
                return f"{actor}'s attack {'hits' if hit else 'misses'} {target}"
            case DiceRolled():
                return None
            case HpChanged():
                return typed.summary
            case ConditionChanged():
                return typed.summary
            case LevelUpAvailable():
                return "an advancement is available to the player"
            case FeatureUsed(name=name):
                return f"used {name}"
            case FeatureActivated(name=name):
                return f"activated {name}"
            case SpellCast(name=name):
                return f"cast {name}"
            case SpellSlotSpent():
                return None
            case Rested():
                return typed.summary
            case LeveledUp():
                return typed.summary

    def trace_event(self, event: RuleEvent) -> str:
        return decode_dnd5e_event(event, ENGINE_ID, SCHEMA_VERSION).summary

    def trace_direction(self, direction: DirectionRecord) -> str:
        if direction.engine != ENGINE_ID or direction.schema_version != SCHEMA_VERSION:
            raise ValueError("direction record is not compatible with 5e")
        return json.dumps(thaw_json(direction.mechanics), indent=2)
