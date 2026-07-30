from collections.abc import Mapping
from typing import Annotated, TypeGuard

from aidm.domain.base import Slug
from aidm.domain.events import RuleEvent
from aidm.domain.json import FrozenJson
from pydantic import Field, TypeAdapter

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

type Dnd5eRuleEvent = Annotated[
    DcRolled
    | AttackRolled
    | DiceRolled
    | HpChanged
    | ConditionChanged
    | LevelUpAvailable
    | FeatureUsed
    | FeatureActivated
    | SpellCast
    | SpellSlotSpent
    | Rested
    | LeveledUp,
    Field(discriminator="type"),
]
DND5E_EVENT_ADAPTER: TypeAdapter[Dnd5eRuleEvent] = TypeAdapter(Dnd5eRuleEvent)


def encode_dnd5e_event(
    event: Dnd5eRuleEvent,
    engine: Slug,
    schema_version: int,
) -> RuleEvent:
    return RuleEvent(
        engine=engine,
        schema_version=schema_version,
        name=event.type.replace("_", "-"),
        payload=event.model_dump(mode="json", exclude={"type"}),
    )


def _is_payload_mapping(
    value: FrozenJson,
) -> TypeGuard[Mapping[str, FrozenJson]]:
    return isinstance(value, Mapping)


def decode_dnd5e_event(
    event: RuleEvent,
    engine: Slug,
    schema_version: int,
) -> Dnd5eRuleEvent:
    if event.engine != engine:
        raise ValueError(f"5e event engine is {event.engine!r}, expected {engine!r}")
    if event.schema_version != schema_version:
        raise ValueError(f"5e event schema is {event.schema_version}, expected {schema_version}")
    if not _is_payload_mapping(event.payload):
        raise ValueError(f"5e event {event.name!r} payload must be an object")
    event_type = event.name.replace("-", "_")
    return DND5E_EVENT_ADAPTER.validate_python({"type": event_type, **event.payload})
