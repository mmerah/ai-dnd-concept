import json

from aidm.domain.base import PLAYER_ID
from aidm.domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity

from .agents import views
from .domain.models.direction import MECHANICS_ADAPTER, Dnd5eDirection
from .domain.models.facts import (
    AttackRolled,
    ConditionChanged,
    DcRolled,
    DiceRolled,
    Dnd5eFact,
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
from .models import Dnd5eState


class Dnd5ePresentation:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def entity_state(self, entity: Entity, state: Dnd5eState) -> str:
        match entity:
            case ActorEntity():
                actor = state.actor(entity.id)
                if entity.id == PLAYER_ID:
                    sheet = views.player_state(actor.stats, actor.progression, self._ruleset)
                    advancement = views.level_up_state(actor.progression)
                    return f"{sheet}\nadvancement: {advancement}"
                return views.actor_state(actor.stats, actor.ref, self._ruleset)
            case ItemEntity():
                return views.item_state(state.item(entity.id).ref, self._ruleset)
            case LocationEntity():
                return ""

    def narrator_fact(self, fact: Dnd5eFact) -> str | None:
        match fact:
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
                return fact.summary
            case ConditionChanged():
                return fact.summary
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
                return fact.summary
            case LeveledUp():
                return fact.summary

    def trace_fact(self, fact: Dnd5eFact) -> str:
        return fact.summary

    def trace_direction(self, direction: Dnd5eDirection) -> str:
        return json.dumps(json.loads(MECHANICS_ADAPTER.dump_json(direction.mechanics)), indent=2)
