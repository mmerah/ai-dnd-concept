from aidm.core.base import PLAYER_ID, Entity
from aidm.core.content import Rules

from .state import StoryActorState, StoryItemState, actor_state, item_state


class StoryPresentation:
    def entity_state(self, entity: Entity, rules: Rules) -> str:
        match entity.kind:
            case "actor":
                return self._actor_state(entity, actor_state(rules))
            case "item":
                return self._item_state(item_state(rules))
            case "location":
                return ""

    @staticmethod
    def _actor_state(actor: Entity, state: StoryActorState) -> str:
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
