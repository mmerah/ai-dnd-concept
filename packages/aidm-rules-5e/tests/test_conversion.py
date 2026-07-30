from aidm.domain.events import ActorMoved, RuleEvent
from aidm_5e.conversion import event_from_legacy
from aidm_5e.domain.models.base import EntityId
from aidm_5e.domain.models.events import DiceRolled, Moved


def test_legacy_events_map_to_core_events_or_stamped_rule_events() -> None:
    moved = event_from_legacy(
        Moved(
            actor_id=EntityId("mara"),
            actor_name="Mara",
            location_id=EntityId("vault"),
            location_name="the vault",
        )
    )
    rolled = event_from_legacy(DiceRolled(dice="1d4", total=3))

    assert isinstance(moved, ActorMoved)
    assert (moved.actor_id, moved.location_id) == ("mara", "vault")
    assert isinstance(rolled, RuleEvent)
    assert (rolled.engine, rolled.schema_version, rolled.name) == (
        "dnd5e",
        1,
        "dice-rolled",
    )
