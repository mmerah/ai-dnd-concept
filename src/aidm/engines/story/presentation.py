import json

from aidm.base import PLAYER_ID, ActorEntity, Entity
from aidm.world import EntityRules

from .access import actor_rules, item_rules
from .direction import STORY_MECHANICS_ADAPTER, StoryDirection
from .state import StoryActorState, StoryItemState


class StoryPresentation:
    def entity_state(self, entity: Entity, rules: EntityRules) -> str:
        if isinstance(entity, ActorEntity):
            return self._actor_state(entity, actor_rules(rules))
        return self._item_state(item_rules(rules))

    def trace_direction(self, direction: StoryDirection) -> str:
        return json.dumps(
            json.loads(STORY_MECHANICS_ADAPTER.dump_json(direction.mechanics)), indent=2
        )

    @staticmethod
    def _actor_state(actor: ActorEntity, state: StoryActorState) -> str:
        approaches = ", ".join(
            f"{name} {value:+d}" for name, value in state.approaches.model_dump().items()
        )
        tags = ", ".join(f"{tag.name}[id={tag.id}, {tag.kind}]" for tag in state.tags)
        conditions = ", ".join(
            f"{condition.name}[id={condition.id}]" for condition in state.conditions
        )
        growth = f", growth {state.growth_marks}/3" if actor.id == PLAYER_ID else ""
        status = "taken out" if state.taken_out else "active"
        return (
            f"{approaches}; "
            f"stress {state.stress}/{state.max_stress}{growth}; "
            f"status {status}; tags {tags or '(none)'}; "
            f"conditions {conditions or '(none)'}"
        )

    @staticmethod
    def _item_state(state: StoryItemState) -> str:
        gear = state.gear
        if gear is None:
            return "gear benefit: (none)"
        return f"gear benefit: {gear.name} — {gear.description}"
