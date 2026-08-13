from typing import Literal

from pydantic import Field

from aidm.state.base import EntityId, Frozen
from aidm.state.plan import Branched

from .mechanics import OracleEffect


class Question(Frozen):
    """A closed dramatic question, answered by Chance d6 against Risk d6."""

    act: Literal["question"] = "question"
    actor_id: EntityId = Field(
        description="Exact id of the actor the question is about: the player, or an actor here."
    )
    question: str = Field(
        min_length=1,
        description="The closed dramatic question the dice answer, phrased so that yes is what "
        "the actor wants.",
    )
    leverage: tuple[str, ...] = Field(
        default=(),
        max_length=3,
        description="Tags that make this easier, each copied exactly as it is written on the "
        "actor's sheet or on a trait in the scene. Empty when none applies; you cannot invent one.",
    )
    trouble: tuple[str, ...] = Field(
        default=(),
        max_length=3,
        description="Tags that make this harder, copied the same way. Empty when none applies.",
    )
    opponent_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor opposing this, set only when the question is one "
        "exchange of a conflict; the engine then takes luck off whichever side loses it.",
    )


class TurnPlan(Branched[OracleEffect]):
    action: Question | None = Field(
        default=None,
        description="The one question this turn resolves, or null when nothing is uncertain "
        "enough to ask.",
    )
