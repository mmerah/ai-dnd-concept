from pathlib import Path

from pydantic import BaseModel

from aidm.core.entities import Frozen, Slug, content_id, parse_json
from aidm.core.io import ENCODING, decode

SRD_PACK: Slug = "srd"


class ScenePack(Frozen):
    name: str
    source: str
    license: str

    def defined_ids(self) -> tuple[Slug, ...]:
        """The option ids this pack defines; two selected packs may not share one."""
        return ()


def read_packs[P: BaseModel](directory: Path, model: type[P]) -> dict[Slug, P]:
    packs: dict[Slug, P] = {}
    for path in sorted(directory.glob("*.json")):
        raw = path.read_text(encoding=ENCODING)
        decode(raw)
        packs[content_id(path.stem)] = parse_json(model, raw)
    return packs
