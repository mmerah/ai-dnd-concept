from abc import abstractmethod
from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import JsonValue

from aidm.engines.core import CharacterCreation
from aidm.state.creation import AnyStep, CreationOption, CreationStep, Picks, picked
from aidm.state.entities import Slug


class PackName(Protocol):
    name: str


def find_entry[T: CreationOption](entries: Sequence[T], chosen: str) -> T:
    return next(entry for entry in entries if entry.id == chosen)


def picked_entry[T: CreationOption](entries: Sequence[T], picks: Picks, step: Slug) -> T | None:
    chosen = picked(picks, step)[:1]
    return next((entry for entry in entries if entry.id in chosen), None)


def character_packs(chosen: Slug) -> list[JsonValue]:
    return ["srd"] if chosen == "srd" else ["srd", chosen]


class PackCreation[P: PackName](CharacterCreation):
    def __init__(self, packs: Mapping[str, P]) -> None:
        self.packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        options = tuple(
            CreationOption(id=one, label=one_pack.name) for one, one_pack in self.packs.items()
        )
        first = CreationStep(id="pack", prompt="Choose a character table set", options=options)
        pack = self.packs.get(chosen[0]) if (chosen := picked(picks, "pack")) else None
        return (first,) if pack is None else (first, *self.steps_for(pack, picks))

    @abstractmethod
    def steps_for(self, pack: P, picks: Picks) -> tuple[AnyStep, ...]: ...
