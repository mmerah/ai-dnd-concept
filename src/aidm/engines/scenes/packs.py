from pathlib import Path

from pydantic import BaseModel

from aidm.core.entities import Frozen, Slug, content_id, parse
from aidm.core.io import ENCODING, decode

SRD_PACK: Slug = "srd"


class ScenePack(Frozen):
    name: str
    source: str
    license: str


def read_packs[P: BaseModel](directory: Path, model: type[P]) -> dict[Slug, P]:
    return {
        content_id(path.stem): parse(model, decode(path.read_text(encoding=ENCODING)))
        for path in sorted(directory.glob("*.json"))
    }
