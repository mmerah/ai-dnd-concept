import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch
from types import MappingProxyType

from pydantic import BaseModel, JsonValue

from aidm.content.io import ENCODING
from aidm.state.entities import Slug

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PackSources:
    """Every place one engine's content packs come from, composed by whoever holds them."""

    directories: tuple[Path, ...] = ()
    # Written by an authoring run and not on disk yet; a broken one is refused, never skipped.
    drafted: Mapping[Slug, JsonValue] = MappingProxyType({})

    def load[P: BaseModel](self, shipped: Path, model: type[P]) -> dict[str, P]:
        """Later sources win, so a scenario may ship what the installed packs lack."""
        packs = _from_files(shipped, self.directories, model)
        packs.update({name: _validated(name, body, model) for name, body in self.drafted.items()})
        if "srd" not in packs:
            raise ValueError("no usable srd content pack was found")
        return packs


# What an engine built with no caller behind it plays: the packs it ships with itself.
SHIPPED_PACKS = PackSources()


def _paths(shipped: Path, directories: Sequence[Path]) -> dict[str, Path]:
    if not (shipped / "srd.json").is_file():
        raise ValueError(f"engine pack directory {str(shipped)!r} has no srd.json")
    paths = {path.stem: path for path in sorted(shipped.glob("*.json"))}
    for directory in directories:
        if directory.is_dir():
            paths.update({path.stem: path for path in sorted(directory.glob("*.json"))})
    return paths


def _from_files[P: BaseModel](
    shipped: Path, directories: Sequence[Path], model: type[P]
) -> dict[str, P]:
    packs: dict[str, P] = {}
    for stem, path in _paths(shipped, directories).items():
        if fullmatch(r"[a-z0-9-]+", stem) is None:
            LOGGER.warning("skipping content pack %s: its name is not a slug", path)
            continue
        try:
            packs[stem] = model.model_validate_json(path.read_text(encoding=ENCODING))
        except (OSError, ValueError) as broken:
            LOGGER.warning("skipping content pack %s: %s", path, broken)
    return packs


def _validated[P: BaseModel](name: str, body: JsonValue, model: type[P]) -> P:
    try:
        return model.model_validate(body)
    except ValueError as broken:
        raise ValueError(f"content pack {name!r} is not playable here: {broken}") from broken
