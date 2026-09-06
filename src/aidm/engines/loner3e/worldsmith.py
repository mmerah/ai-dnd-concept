from typing import Self

from pydantic import Field, model_validator

from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.loner3e.world import DIE_FACE

AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every character is a person, an object, a vehicle or a curse alike. Each one has a "
    "one-line `concept`, any fitting `tags` by kind, and luck of its own. The kinds are "
    "`skill`, `frailty` and `gear`. "
    "A living character can carry a `goal`, a `motive` and a `nemesis`. An object, a vehicle "
    "and a curse do not. "
    "Every scene bears on the player's `goal`, or brings their `nemesis` nearer. "
    "Give a door or a storm the `skill` and `frailty` tags it resists with. "
    "Loner tags are freeform descriptions. Use selected pack entries when they fit. Invent "
    "scenario-specific tags when they are clearer. Only a pack tag carries a meaning the game "
    "master can look up. An invented tag that does not say what it does needs one sentence in "
    "that character's `brief`. Positions are judged from it."
)


class Pack(ScenePack):
    concepts: tuple[DecisionOption, ...] = Field(min_length=1)
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    frailties: tuple[DecisionOption, ...] = Field(min_length=1)
    gear: tuple[DecisionOption, ...] = Field(min_length=1)
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != DIE_FACE:
                raise ValueError("a twist column is one d6: exactly six entries")
        return self
