from collections.abc import Mapping

from pydantic import JsonValue

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.engine import CharacterCreation
from aidm.engines.packs import pack_step
from aidm.state.base import PLAYER_ID, Entity, EntityId, Trait, text_slug
from aidm.state.creation import (
    AnyStep,
    CreationOption,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)

from .mechanics import SkillDie, raised
from .pack import KitItem, Origin, Pack, SkillGrant, Specialty


class TwentyfourxxCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        steps: list[AnyStep] = [
            first,
            CreationStep(
                id="specialty",
                prompt="Choose a specialty",
                options=_options(pack.specialties),
            ),
        ]
        specialty = _picked_entry(pack.specialties, picks, "specialty")
        if specialty is not None and specialty.choices:
            steps.append(
                CreationStep(
                    id="training",
                    prompt="Choose their training",
                    options=_options(specialty.choices),
                )
            )
        steps.append(
            CreationStep(id="origin", prompt="Choose an origin", options=_options(pack.origins))
        )
        origin = _picked_entry(pack.origins, picks, "origin")
        if origin is not None and origin.invents:
            steps.append(
                TextStep(
                    id="traits",
                    prompt=_count_prompt("trait", origin.invents, verb="Invent"),
                    count=origin.invents,
                    hint=", ".join(option.label for option in origin.traits),
                )
            )
        if origin is not None and origin.increases:
            steps.append(
                CreationStep(
                    id="skills",
                    prompt=_count_prompt("further skill", origin.increases),
                    options=pack.skills,
                    choose=origin.increases,
                    repeats=True,
                )
            )
        return tuple(steps)

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        specialty = _find(pack.specialties, picked(picks, "specialty")[0])
        origin = _find(pack.origins, picked(picks, "origin")[0])

        skills: dict[str, SkillDie] = {}
        for skill in specialty.skills:
            skills[skill] = raised(skills.get(skill))
        for grant_id in picked(picks, "training"):
            grant = _find(specialty.choices, grant_id)
            for skill in grant.skills:
                held = skills.get(skill)
                skills[skill] = grant.die if held is None else max(held, grant.die)
        for skill_id in picked(picks, "skills"):
            label = _find(pack.skills, skill_id).label
            skills[label] = raised(skills.get(label))
        skills_json: dict[str, JsonValue] = {skill: die for skill, die in skills.items()}

        traits: list[Trait] = []
        for written in picked(picks, "traits"):
            taken = [trait.id for trait in traits]
            traits.append(Trait(id=text_slug(written, taken), name=written))
        items = tuple(_carried(entry) for entry in (*pack.starting_kit, *specialty.kit))

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=tuple(traits), items=items),
            overlay=CharacterOverlay(
                character={
                    "specialty": specialty.label,
                    "origin": origin.label,
                    "skills": skills_json,
                }
            ),
        )


BULKY = Trait(
    id="bulky", name="Bulky", text="Heavy or awkward to lug; more than one may hinder at times."
)


def _carried(entry: KitItem) -> Entity:
    return Entity(
        id=EntityId(entry.id),
        kind="item",
        name=entry.label,
        brief=entry.detail or entry.label,
        known=True,
        parent_id=PLAYER_ID,
        traits=[BULKY] if entry.bulky else [],
    )


def _options(
    entries: tuple[Specialty, ...] | tuple[Origin, ...] | tuple[SkillGrant, ...],
) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _find[T: Specialty | Origin | SkillGrant | CreationOption](
    entries: tuple[T, ...], chosen: str
) -> T:
    return next(entry for entry in entries if entry.id == chosen)


def _picked_entry[T: Specialty | Origin](
    entries: tuple[T, ...], picks: Picks, step: str
) -> T | None:
    chosen = picked(picks, step)
    if not chosen:
        return None
    return next((entry for entry in entries if entry.id == chosen[0]), None)


def _count_prompt(what: str, count: int, verb: str = "Choose") -> str:
    return f"{verb} one {what}" if count == 1 else f"{verb} {count} {what}s"
