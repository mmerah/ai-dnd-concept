import json
from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, Slug, slug
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.core import Pack as ScenePack
from aidm.engines.core import pack_options
from aidm.engines.loner3e.world import (
    DIE_FACE,
    Loner3eCharacter,
    Loner3eCharacterFile,
    player_character,
)

_AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every character — a person, an object, a vehicle or a curse alike — has a one-line "
    "`concept` and any fitting `skills`, `frailties` or `gear`, and rolls with luck of its own. "
    "Living characters may carry a `goal`, a `motive` and a `nemesis`; objects, vehicles and "
    "curses do not. "
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
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != DIE_FACE:
                raise ValueError("a twist column is one d6: exactly six entries")
        return self


def creation_steps(packs: Mapping[str, Pack], picks: Picks) -> tuple[CreationStep, ...]:
    first = CreationStep(
        id="pack", prompt="Choose a character table set", options=pack_options(packs)
    )
    pack = packs.get(picked(picks, "pack"))
    if pack is None:
        return (first,)
    return (
        first,
        CreationStep(
            id="concept",
            prompt="Write a one-line concept",
            hint=", ".join(entry.label for entry in pack.concepts[:3]),
        ),
        CreationStep(id="goal", prompt="What does your character want?"),
        CreationStep(id="motive", prompt="Why do they want it?"),
        CreationStep(id="skill-1", prompt="Choose skill 1", options=pack.skills),
        CreationStep(
            id="skill-2",
            prompt="Choose skill 2",
            options=other_than(pack.skills, picked(picks, "skill-1")),
        ),
        CreationStep(id="frailty", prompt="Choose a frailty", options=pack.frailties),
        CreationStep(id="gear-1", prompt="Choose gear 1", options=pack.gear),
        CreationStep(
            id="gear-2",
            prompt="Choose gear 2",
            options=other_than(pack.gear, picked(picks, "gear-1")),
        ),
    )


def create_character(
    packs: Mapping[str, Pack], name: str, brief: str, picks: Picks
) -> Loner3eCharacterFile:
    check_picks(creation_steps(packs, picks), picks)
    chosen = picked(picks, "pack")
    pack = packs[chosen]
    payload = Loner3eCharacter(
        concept=picked(picks, "concept"),
        goal=picked(picks, "goal"),
        motive=picked(picks, "motive"),
        skills=tuple(
            find_entry(pack.skills, picked(picks, f"skill-{one}")).label for one in (1, 2)
        ),
        frailties=(find_entry(pack.frailties, picked(picks, "frailty")).label,),
        gear=tuple(find_entry(pack.gear, picked(picks, f"gear-{one}")).label for one in (1, 2)),
    )
    return Loner3eCharacterFile(
        id=slug(name, ()), engine=EngineId("loner3e"), name=name, brief=brief, payload=payload
    )


def preview_character(character: AnyCharacter) -> Rows:
    if not isinstance(character, Loner3eCharacterFile):
        raise ValueError("Loner 3E received an incompatible character")
    return player_character(character).rows()


def find_entry(entries: Sequence[DecisionOption], chosen: str) -> DecisionOption:
    return next(entry for entry in entries if entry.id == chosen)


def guidance(packs: Mapping[str, Pack], selected_ids: Sequence[Slug]) -> str:
    """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
    selected = {
        one: packs[one].model_dump(mode="json", exclude_defaults=True) for one in selected_ids
    }
    return f"{_AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"
