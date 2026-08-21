import logging
from collections.abc import Mapping
from pathlib import Path
from re import fullmatch
from typing import Protocol

from pydantic import BaseModel

from aidm.content.io import ENCODING
from aidm.state.model import CreationOption, CreationStep

LOGGER = logging.getLogger(__name__)


class PackName(Protocol):
    name: str


def pack_step(packs: Mapping[str, PackName]) -> CreationStep:
    return CreationStep(
        id="pack",
        prompt="Choose a table set",
        options=tuple(
            CreationOption(id=pack_id, label=pack.name) for pack_id, pack in packs.items()
        ),
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
