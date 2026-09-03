from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.loner3e.world import DIE_FACE

AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every character — a person, an object, a vehicle or a curse alike — has a one-line "
    "`concept` and any fitting `skills`, `frailties` or `gear`, and rolls with luck of its own. "
    "Living characters may carry a `goal`, a `motive` and a `nemesis`; objects, vehicles and "
    "curses do not. "
    "Every scene bears on the player's `goal`, or brings their `nemesis` nearer. "
    "Give a door or a storm the `skills` and `frailties` it resists with. "
    "Loner tags are freeform descriptions: use selected pack entries when they fit and invent "
    "scenario-specific tags when they are clearer. Only a pack tag carries a meaning the game "
    "master can look up, so an invented tag that does not say what it does needs one sentence "
    "in that character's `brief`: positions are judged from it."
)


class Pack(ScenePack):
    """One published table set the player can build a character from."""

    source: str
    license: str
    concepts: tuple[DecisionOption, ...] = Field(min_length=1)
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    frailties: tuple[DecisionOption, ...] = Field(min_length=1)
    gear: tuple[DecisionOption, ...] = Field(min_length=1)
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise Refusal("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != DIE_FACE:
                raise Refusal("a twist column is one d6: exactly six entries")
        return self
