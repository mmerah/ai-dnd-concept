from collections.abc import Mapping

from aidm.content.authored import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.loader import Creation
from aidm.engines.packs import pack_step
from aidm.state.creation import CreationOption, CreationStep, Picks, check_picks, picked

from .pack import Pack, PackEntry


class Loner3eCreation(Creation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        return (
            first,
            CreationStep(id="concept", prompt="Choose a concept", options=_options(pack.concepts)),
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
                    "concept": _label(pack.concepts, picked(picks, "concept")[0]),
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
