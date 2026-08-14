from collections.abc import Mapping

from pydantic import JsonValue

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.loader import Creation
from aidm.engines.packs import pack_step
from aidm.state.base import Trait
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks, picked

from .mechanics import SkillDie, raised
from .pack import Origin, Pack, SkillGrant, Specialty


class TwentyfourxxCreation(Creation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        steps = [
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
                CreationStep(
                    id="traits",
                    prompt=_count_prompt("trait", origin.invents),
                    options=origin.traits,
                    choose=origin.invents,
                )
            )
        if origin is not None and origin.increases:
            steps.append(
                CreationStep(
                    id="skills",
                    prompt=_count_prompt("further skill", origin.increases),
                    options=pack.skills,
                    choose=origin.increases,
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

        invented = tuple(_find(origin.traits, trait_id) for trait_id in picked(picks, "traits"))
        traits = tuple(
            Trait(id=option.id, name=option.label, text=option.detail)
            for option in (*pack.starting_kit, *specialty.kit, *invented)
        )

        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, traits=traits),
            overlay=CharacterOverlay(
                character={
                    "specialty": specialty.label,
                    "origin": origin.label,
                    "skills": skills_json,
                }
            ),
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


def _count_prompt(what: str, count: int) -> str:
    return f"Choose one {what}" if count == 1 else f"Choose {count} {what}s"
