from collections.abc import Callable, Iterable, Mapping, Sequence

from pydantic import Field

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Frozen, Slug, slug
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.views import Rows
from aidm.engines.twentyfourxx.world import (
    Kit,
    SkillDie,
    TwentyfourxxCharacter,
    TwentyfourxxCharacterFile,
    player_operator,
    raised,
)

_AUTHORING = (
    "24XX AUTHORING\n"
    "The cast carries no dice: an NPC is a name, a brief and whether the player has met them, "
    "nothing more. A threat is a brief the player's own roll meets, never a stat block. The "
    "player is an operator on a job in a hard sci-fi future; write scenes as work sites, "
    "stations, ships and the people holding them."
)


class SkillChoice(Frozen):
    """One printed pick: Muscle's Hand-to-hand or Shooting; Psychic's both at d8 or one at d10."""

    id: Slug
    label: str
    skills: dict[str, SkillDie]


class Specialty(Frozen):
    id: Slug
    label: str
    detail: str
    skills: dict[str, SkillDie]  # the fixed ones, at d8
    choice: tuple[SkillChoice, ...] = ()  # Muscle, Psychic
    kit: tuple[Kit, ...] = ()
    kit_choice: tuple[Kit, ...] = ()  # Muscle: "a sword, firearm, or cyber-arm" -- pick one


class Origin(Frozen):
    id: Slug
    label: str
    detail: str
    increases: int = 0  # human 3, android 1
    invents: int = 0  # alien 2
    choice: tuple[DecisionOption, ...] = ()  # android: synth skin | case


class Pack(Frozen):
    name: str
    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=17, max_length=17)
    specialties: tuple[Specialty, ...]
    origins: tuple[Origin, ...]
    starting_kit: tuple[Kit, ...]  # the comm


def creation_steps(packs: Mapping[str, Pack], picks: Picks) -> tuple[CreationStep, ...]:
    first = CreationStep(id="pack", prompt="Choose a table set", options=pack_options(packs))
    pack = packs.get(picked(picks, "pack"))
    if pack is None:
        return (first,)
    steps = [
        first,
        CreationStep(id="specialty", prompt="Specialty", options=_options(pack.specialties)),
    ]
    specialty = _by_key(pack.specialties, lambda one: one.id, picked(picks, "specialty"))
    if specialty is None:
        return tuple(steps)
    if specialty.choice:
        steps.append(
            CreationStep(
                id="specialty-choice",
                prompt="Specialty skill",
                options=tuple(DecisionOption(id=c.id, label=c.label) for c in specialty.choice),
            )
        )
    if specialty.kit_choice:
        steps.append(
            CreationStep(
                id="weapon",
                prompt="Weapon",
                options=tuple(
                    DecisionOption(id=slug(kit.name, ()), label=kit.name)
                    for kit in specialty.kit_choice
                ),
            )
        )
    steps.append(CreationStep(id="origin", prompt="Origin", options=_options(pack.origins)))
    origin = _by_key(pack.origins, lambda one: one.id, picked(picks, "origin"))
    if origin is None:
        return tuple(steps)
    if origin.invents == 2:
        steps.append(CreationStep(id="trait-1", prompt="First trait", hint=origin.detail))
        steps.append(CreationStep(id="trait-2", prompt="Second trait", hint=origin.detail))
    if origin.choice:
        steps.append(CreationStep(id="body", prompt="Body", options=origin.choice))
    for number in range(1, origin.increases + 1):
        steps.append(
            CreationStep(id=f"increase-{number}", prompt="Skill increase", options=pack.skills)
        )
    return tuple(steps)


def create_character(
    packs: Mapping[str, Pack], name: str, brief: str, picks: Picks
) -> TwentyfourxxCharacterFile:
    check_picks(creation_steps(packs, picks), picks)
    pack = packs[picked(picks, "pack")]
    specialty = _require(pack.specialties, lambda one: one.id, picked(picks, "specialty"))
    origin = _require(pack.origins, lambda one: one.id, picked(picks, "origin"))

    skills: dict[str, SkillDie] = dict(specialty.skills)
    if specialty.choice:
        chosen = _require(specialty.choice, lambda c: c.id, picked(picks, "specialty-choice"))
        skills.update(chosen.skills)
    for number in range(1, origin.increases + 1):
        option = _require(pack.skills, lambda one: one.id, picked(picks, f"increase-{number}"))
        skills[option.label] = raised(skills.get(option.label))

    weapon: Kit | None = None
    if specialty.kit_choice:
        weapon = _require(
            specialty.kit_choice, lambda kit: slug(kit.name, ()), picked(picks, "weapon")
        )

    if origin.invents == 2:
        traits = (picked(picks, "trait-1"), picked(picks, "trait-2"))
    elif origin.choice:
        body = _require(origin.choice, lambda one: one.id, picked(picks, "body"))
        traits = (body.label,)
    else:
        traits = ()

    items = pack.starting_kit + specialty.kit + ((weapon,) if weapon is not None else ())

    payload = TwentyfourxxCharacter.model_validate(
        {
            "specialty": specialty.label,
            "origin": origin.label,
            "traits": traits,
            "skills": skills,
            "items": items,
        }
    )
    return TwentyfourxxCharacterFile(
        id=slug(name, ()),
        engine=EngineId("twentyfourxx"),
        name=name,
        brief=brief,
        payload=payload,
    )


def preview_character(character: AnyCharacter) -> Rows:
    if not isinstance(character, TwentyfourxxCharacterFile):
        raise ValueError("24XX received an incompatible character")
    names = ", ".join(kit.name for kit in character.payload.items)
    return (*player_operator(character).rows(), ("Gear", names))


def pack_options(packs: Mapping[str, Pack]) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=key, label=one.name) for key, one in packs.items())


def guidance(packs: Mapping[str, Pack], selected_ids: Sequence[Slug]) -> str:
    """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
    return _AUTHORING


def _options(items: Sequence[Specialty] | Sequence[Origin]) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=one.id, label=one.label, detail=one.detail) for one in items)


def _by_key[T](options: Iterable[T], key: Callable[[T], str], wanted: str) -> T | None:
    return next((one for one in options if key(one) == wanted), None)


def _require[T](options: Iterable[T], key: Callable[[T], str], wanted: str) -> T:
    found = _by_key(options, key, wanted)
    if found is None:
        raise ValueError(f"no option {wanted!r}")
    return found
