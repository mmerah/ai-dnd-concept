import logging
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path
from re import fullmatch
from typing import Protocol

from pydantic import BaseModel

from aidm.content.io import ENCODING
from aidm.engines.core import CharacterCreation
from aidm.state.creation import AnyStep, CreationOption, CreationStep, Picks, picked
from aidm.state.entities import Slug

LOGGER = logging.getLogger(__name__)


class PackName(Protocol):
    name: str


class PackChoice(Protocol):
    """Anything a pack offers the player: every table set entry is asked for the same three."""

    id: str
    label: str
    detail: str


def pack_options(entries: Sequence[PackChoice]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def pack_paths(shipped: Path, extra: Path | None) -> dict[str, Path]:
    """User packs merge over shipped ones by file stem, so one can replace a shipped table set."""
    paths = {path.stem: path for path in sorted(shipped.glob("*.json"))}
    if extra is not None and extra.is_dir():
        paths.update({path.stem: path for path in sorted(extra.glob("*.json"))})
    return paths


def load_packs[P: BaseModel](paths: Mapping[str, Path], model: type[P]) -> dict[str, P]:
    """A broken user pack is skipped with a log line: it must not block the way to the launcher."""
    packs: dict[str, P] = {}
    for stem, path in paths.items():
        if fullmatch(r"[a-z0-9-]+", stem) is None:
            LOGGER.warning("skipping content pack %s: its name is not a slug", path)
            continue
        try:
            packs[stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
        except (OSError, ValueError) as broken:
            LOGGER.warning("skipping content pack %s: %s", path, broken)
    if not packs:
        raise ValueError("no usable content pack was found")
    return packs


def find_entry[T: PackChoice](entries: Sequence[T], chosen: str) -> T:
    return next(entry for entry in entries if entry.id == chosen)


def picked_entry[T: PackChoice](entries: Sequence[T], picks: Picks, step: Slug) -> T | None:
    chosen = picked(picks, step)[:1]
    return next((entry for entry in entries if entry.id in chosen), None)


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
    def steps_for(self, pack: P, picks: Picks) -> tuple[AnyStep, ...]:
        """What this engine asks once a table set is chosen; the pack step itself is the base's."""
