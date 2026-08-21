from collections.abc import Mapping

from aidm.content.model import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.engine import CharacterCreation
from aidm.engines.packs import pack_step
from aidm.state.model import (
    AnyStep,
    CreationOption,
    CreationStep,
    Picks,
    TextStep,
    check_picks,
    picked,
)

from .pack import Pack, PackEntry


class Loner3eCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        return (
            first,
            TextStep(
                id="concept",
                prompt="Their concept, in one line",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(
                id="skills", prompt="Choose two skills", options=_options(pack.skills), choose=2
            ),
            CreationStep(id="frailty", prompt="Choose a frailty", options=_options(pack.frailties)),
            CreationStep(
                id="gear", prompt="Choose two pieces of gear", options=_options(pack.gear), choose=2
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            overlay=CharacterOverlay(
                character={
                    "pack": picked(picks, "pack")[0],
                    "concept": picked(picks, "concept")[0],
                    "skills": [_label(pack.skills, skill) for skill in picked(picks, "skills")],
                    "frailties": [_label(pack.frailties, picked(picks, "frailty")[0])],
                    "gear": [_label(pack.gear, gear) for gear in picked(picks, "gear")],
                }
            ),
        )


def _options(entries: tuple[PackEntry, ...]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _label(entries: tuple[PackEntry, ...], chosen: str) -> str:
    return next(entry.label for entry in entries if entry.id == chosen)
