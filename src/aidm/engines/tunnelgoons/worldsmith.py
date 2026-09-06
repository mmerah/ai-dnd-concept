from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen
from aidm.engines.tunnelgoons.world import ABILITY_POINTS, AbilityScores

AUTHORING = (
    "TUNNEL GOONS AUTHORING\n"
    "Every npc needs `hp`: its Difficulty Score and its Health at once, graded as the rules "
    "grade a Difficulty Score: 8 easy, 10 moderate, 12 hard."
)
HIRE_GUIDANCE = (
    "TUNNEL GOONS HIRING\n"
    f"{ABILITY_POINTS} points across three abilities: Brute is smacking things and feats of "
    "strength; Skulker is sneaking, aiming and balancing; Erudite is reading, perception and "
    "speaking. Answer with the abilities alone."
)
HIRING = (
    "The player has hired {name} ({brief}) on these terms: {terms}. Write their three "
    "abilities from ENGINE GUIDANCE, as fits who they are and what they were hired for."
)


class AbilitiesDraft(Frozen):
    abilities: AbilityScores = Field(
        min_length=3,
        max_length=3,
        description=(
            f"Points in brute, skulker and erudite: exactly {ABILITY_POINTS} across the three."
        ),
    )

    @model_validator(mode="after")
    def _points_spent(self) -> Self:
        total = sum(self.abilities.values())
        if total != ABILITY_POINTS:
            raise ValueError(
                f"the three abilities must share exactly {ABILITY_POINTS} points, not {total}"
            )
        return self
