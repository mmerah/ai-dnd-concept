from typing import Annotated, ClassVar, Literal

from pydantic import Field, TypeAdapter

from aidm.base import EntityId, Frozen, Slug

from .actions import (
    CORE_ACTION_TYPES,
    CoreAction,
    Discover,
    DropItem,
    GainImprovisedItem,
    GiveItem,
    Move,
    TakeItem,
)
from .state import StoryApproach, StoryCondition


class HelpfulActorTag(Frozen):
    source: Literal["actor_tag"] = "actor_tag"
    id: Slug = Field(description="Exact id of an active edge or bond on the acting character.")


class HelpfulGear(Frozen):
    source: Literal["gear"] = "gear"
    item_id: EntityId = Field(
        description="Exact id of a carried item whose shown gear benefit directly helps."
    )


type HelpfulRef = Annotated[
    HelpfulActorTag | HelpfulGear,
    Field(discriminator="source"),
]


class HinderingBurden(Frozen):
    source: Literal["burden"] = "burden"
    id: Slug = Field(description="Exact id of an active burden on the acting character.")


class HinderingCondition(Frozen):
    source: Literal["condition"] = "condition"
    id: Slug = Field(description="Exact id of an active condition on the acting character.")


type HinderingRef = Annotated[
    HinderingBurden | HinderingCondition,
    Field(discriminator="source"),
]


class StoryAction(Frozen):
    GUIDANCE: ClassVar[str] = ""


class Risk(StoryAction):
    """Resolve an uncertain action whose result matters."""

    GUIDANCE: ClassVar[str] = """Use only when success is uncertain and both success and failure \
would change the fiction. Fill every outcome branch that has a distinct consequence because the \
engine, not you, decides the outcome. Put effects that happen regardless of outcome after `risk`, \
not redundantly in all three branches. A setback automatically marks player growth."""

    action: Literal["risk"] = "risk"
    actor_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor taking the risk; omit for the player.",
    )
    approach: StoryApproach = Field(
        description="How the actor acts: bold, subtle, clever, or empathetic."
    )
    difficulty: int = Field(
        ge=0,
        le=2,
        description="0 risky, 1 demanding, or 2 extreme.",
    )
    helpful: HelpfulRef | None = Field(
        default=None,
        description="At most one directly relevant active edge, bond, or carried gear benefit.",
    )
    hindering: HinderingRef | None = Field(
        default=None,
        description="At most one directly relevant active burden or condition.",
    )
    on_strong: list["StoryConsequence"] = Field(
        default_factory=list,
        description="Consequences applied only on a strong outcome.",
    )
    on_mixed: list["StoryConsequence"] = Field(
        default_factory=list,
        description="Consequences applied only on a mixed outcome.",
    )
    on_setback: list["StoryConsequence"] = Field(
        default_factory=list,
        description="Consequences applied only on a setback.",
    )


class TakeStress(StoryAction):
    """Increase an actor's pressure and possibly take them out."""

    GUIDANCE: ClassVar[str] = """Use for harm, exhaustion, fear, or pressure that pushes an actor \
toward defeat. Reaching maximum stress takes them out. Put uncertain harm in the appropriate \
`risk` branch."""

    action: Literal["take_stress"] = "take_stress"
    amount: int = Field(gt=0, description="Positive stress gained.")
    actor_id: EntityId | None = Field(
        default=None,
        description="Exact id of the affected actor; omit for the player.",
    )


class RecoverStress(StoryAction):
    """Reduce an actor's pressure and return a taken-out actor to action."""

    GUIDANCE: ClassVar[str] = """Use only when the fiction provides meaningful rest, safety, \
comfort, treatment, or another release from pressure. It is the only action that returns a \
taken-out actor once stress drops below maximum."""

    action: Literal["recover_stress"] = "recover_stress"
    amount: int = Field(gt=0, description="Positive stress recovered.")
    actor_id: EntityId | None = Field(
        default=None,
        description="Exact id of the affected actor; omit for the player.",
    )


class ApplyCondition(StoryAction):
    """Record a persistent injury, status, or other concrete fictional constraint."""

    GUIDANCE: ClassVar[str] = """Use when an injury or status should remain true after this \
turn and affect later action, such as `Twisted Ankle`, `Terrified`, or `Pinned Beneath Rubble`. \
Give it a stable slug id, concise name, and description of the concrete constraint. Put a \
resistible condition in a `risk` branch."""

    action: Literal["apply_condition"] = "apply_condition"
    condition: StoryCondition = Field(description="The persistent injury or status to record.")
    actor_id: EntityId | None = Field(
        default=None,
        description="Exact id of the affected actor; omit for the player.",
    )


class ClearCondition(StoryAction):
    """Remove a persistent injury or status that the fiction resolves."""

    GUIDANCE: ClassVar[str] = """Use when treatment, escape, recovery, or another established \
change ends an active condition. Copy its exact shown condition id."""

    action: Literal["clear_condition"] = "clear_condition"
    condition_id: Slug = Field(description="Exact id of the active condition to remove.")
    actor_id: EntityId | None = Field(
        default=None,
        description="Exact id of the affected actor; omit for the player.",
    )


type StoryConsequence = Annotated[
    Risk
    | TakeStress
    | RecoverStress
    | ApplyCondition
    | ClearCondition
    | Discover
    | Move
    | TakeItem
    | DropItem
    | GiveItem
    | GainImprovisedItem,
    Field(discriminator="action"),
]
STORY_ACTION_TYPES: tuple[type[StoryAction], ...] = (
    Risk,
    TakeStress,
    RecoverStress,
    ApplyCondition,
    ClearCondition,
)
STORY_CONSEQUENCE_TYPES: tuple[type[CoreAction] | type[StoryAction], ...] = (
    *CORE_ACTION_TYPES,
    *STORY_ACTION_TYPES,
)

Risk.model_rebuild(_types_namespace={"StoryConsequence": StoryConsequence})
STORY_CONSEQUENCE_ADAPTER: TypeAdapter[StoryConsequence] = TypeAdapter(StoryConsequence)
STORY_MECHANICS_ADAPTER: TypeAdapter[list[StoryConsequence]] = TypeAdapter(list[StoryConsequence])


class StoryDirection(Frozen):
    engine: Literal["story"] = "story"
    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: list[StoryConsequence] = Field(default_factory=list)


def branches(consequence: StoryConsequence) -> tuple[list[StoryConsequence], ...]:
    if isinstance(consequence, Risk):
        return consequence.on_strong, consequence.on_mixed, consequence.on_setback
    return ()


def flatten(consequences: list[StoryConsequence]) -> tuple[StoryConsequence, ...]:
    flattened: list[StoryConsequence] = []
    for consequence in consequences:
        flattened.append(consequence)
        for branch in branches(consequence):
            flattened.extend(flatten(branch))
    return tuple(flattened)
