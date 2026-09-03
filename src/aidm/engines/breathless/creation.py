import json
from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.base import Pack as ScenePack
from aidm.engines.base import pack_options
from aidm.engines.breathless.world import (
    SKILLS,
    BreathlessCharacterFile,
    BreathlessPayload,
    Die,
    Skill,
    player_survivor,
)

STARTING_DICE: tuple[Die, ...] = (10, 8, 6)  # the three rated skills, best first
_AUTHORING = (
    "BREATHLESS AUTHORING\n"
    "The cast carries no dice: an NPC is a name, a brief and whether the player has met them, "
    "nothing more. A threat is a brief the player's own roll meets, never a stat block. "
    "Use the pack's `locations`, `complications` and `missions` as the setting's vocabulary."
)


class Pack(ScenePack):
    """One published table set the player can build a survivor from."""

    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=6, max_length=6)
    jobs: tuple[str, ...]
    weapons: tuple[str, ...]
    long_range_weapons: tuple[str, ...]
    locations: tuple[str, ...]
    complications: tuple[str, ...] = Field(min_length=12, max_length=12)  # one d12
    missions: tuple[str, ...]

    @model_validator(mode="after")
    def _six_srd_skills(self) -> Self:
        if {one.id for one in self.skills} != set(SKILLS):
            raise Refusal("the six SRD skills, by id")
        return self


def creation_steps(packs: Mapping[str, Pack], picks: Picks) -> tuple[CreationStep, ...]:
    first = CreationStep(id="pack", prompt="Choose a table set", options=pack_options(packs))
    pack = packs.get(picked(picks, "pack"))
    if pack is None:
        return (first,)
    d10 = picked(picks, "skill-d10")
    d8 = picked(picks, "skill-d8")
    return (
        first,
        CreationStep(id="pronouns", prompt="Pronouns"),
        CreationStep(id="job", prompt="Job", hint=", ".join(pack.jobs[:3])),
        CreationStep(id="skill-d10", prompt="Skill at d10", options=pack.skills),
        CreationStep(id="skill-d8", prompt="Skill at d8", options=other_than(pack.skills, d10)),
        CreationStep(
            id="skill-d6",
            prompt="Skill at d6",
            options=other_than(other_than(pack.skills, d10), d8),
        ),
        CreationStep(id="item", prompt="Your one item", hint=", ".join(pack.weapons[:3])),
    )


def create_character(
    packs: Mapping[str, Pack], name: str, brief: str, picks: Picks
) -> BreathlessCharacterFile:
    check_picks(creation_steps(packs, picks), picks)
    payload = BreathlessPayload(
        pronouns=picked(picks, "pronouns"),
        job=picked(picks, "job"),
        skills={_skill(picked(picks, f"skill-d{die}")): die for die in STARTING_DICE},
        item=picked(picks, "item"),
    )
    return BreathlessCharacterFile(
        id=slug(name, ()), engine=EngineId("breathless"), name=name, brief=brief, payload=payload
    )


def preview_character(character: AnyCharacter) -> Rows:
    if not isinstance(character, BreathlessCharacterFile):
        raise Refusal("Breathless received an incompatible character")
    return (*player_survivor(character).rows(), ("Backpack", character.payload.item))


def guidance(packs: Mapping[str, Pack], selected_ids: Sequence[Slug]) -> str:
    """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
    selected = {
        one: packs[one].model_dump(mode="json", include={"locations", "complications", "missions"})
        for one in selected_ids
    }
    return f"{_AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"


def _skill(name: str) -> Skill:
    """`check_picks` has already held the answer to the pack's six ids, which are the SRD's."""
    return next(skill for skill in SKILLS if skill == name)
