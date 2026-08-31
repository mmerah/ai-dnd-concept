import json
from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Frozen, Slug, slug
from aidm.core.model import Character
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.loner3e.state import DIE_FACE, ActorSheet, Loner3eCharacter

_AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every actor needs an `actor` sheet with a concept and any fitting skills, frailties, or "
    "gear. Anything that can resist without a will of its own takes an `item` sheet, which is "
    "luck alone. Loner tags are freeform descriptions: use selected pack entries when they fit "
    "and invent scenario-specific tags when they are clearer. Only a pack tag carries a meaning "
    "the game master can look up, so an invented tag that does not say what it does needs one "
    "sentence in that entity's `description`: positions are judged from it."
)


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
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


def create_character(packs: Mapping[str, Pack], name: str, brief: str, picks: Picks) -> Character:
    check_picks(creation_steps(packs, picks), picks)
    chosen = picked(picks, "pack")
    pack = packs[chosen]
    sheet = ActorSheet(
        concept=picked(picks, "concept"),
        skills=tuple(
            find_entry(pack.skills, picked(picks, f"skill-{one}")).label for one in (1, 2)
        ),
        frailties=(find_entry(pack.frailties, picked(picks, "frailty")).label,),
        gear=tuple(find_entry(pack.gear, picked(picks, f"gear-{one}")).label for one in (1, 2)),
    )
    return Character(
        id=slug(name, ()),
        engine=EngineId("loner3e"),
        name=name,
        brief=brief,
        payload=Loner3eCharacter(sheet=sheet, twist_pack=chosen),
    )


def preview_character(character: Character) -> Rows:
    return character.payload.sheet.rows()


def find_entry(entries: Sequence[DecisionOption], chosen: str) -> DecisionOption:
    return next(entry for entry in entries if entry.id == chosen)


def other_than(options: Sequence[DecisionOption], taken: str) -> tuple[DecisionOption, ...]:
    return tuple(option for option in options if option.id != taken)


def pack_options(packs: Mapping[str, Pack]) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=key, label=one.name) for key, one in packs.items())


def guidance(packs: Mapping[str, Pack], selected_ids: Sequence[Slug]) -> str:
    """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
    selected = {
        one: packs[one].model_dump(mode="json", exclude_defaults=True) for one in selected_ids
    }
    return f"{_AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"
