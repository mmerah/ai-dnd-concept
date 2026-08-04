import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from ..values import EMPTY_FROZEN_MAP, ContentSlug, FrozenMap, Value
from .models import Manifest, Pack
from .records.base import Collection, ContentRef, Record
from .registry import COLLECTION_OF, COLLECTION_SPECS

ENCODING = "utf-8"

# A wrong subtype is a miss because callers probe discriminated-union arms.
MissReason = Literal["unknown_pack", "wrong_collection", "unknown_index", "wrong_type"]

_RAW: TypeAdapter[list[dict[str, object]]] = TypeAdapter(list[dict[str, object]])


class ContentMiss(Value):
    ref: ContentRef
    reason: MissReason

    @property
    def summary(self) -> str:
        return f"missing content {self.ref}: {self.reason}"


class Content(Value):
    packs: tuple[ContentSlug, ...] = ()
    records: FrozenMap[ContentRef, Record] = EMPTY_FROZEN_MAP

    def get[R: Record](self, ref: ContentRef, kind: type[R]) -> R | ContentMiss:
        if COLLECTION_OF[kind] != ref.collection:
            return ContentMiss(ref=ref, reason="wrong_collection")
        if not self.provides(ref.pack):
            return ContentMiss(ref=ref, reason="unknown_pack")
        record = self.records.get(ref)
        if record is None:
            return ContentMiss(ref=ref, reason="unknown_index")
        if not isinstance(record, kind):
            return ContentMiss(ref=ref, reason="wrong_type")
        return record

    def require[R: Record](self, ref: ContentRef, kind: type[R]) -> R:
        found = self.get(ref, kind)
        if isinstance(found, ContentMiss):
            raise ValueError(found.summary)
        return found

    def resolves(self, ref: ContentRef) -> ContentMiss | None:
        if not self.provides(ref.pack):
            return ContentMiss(ref=ref, reason="unknown_pack")
        if ref not in self.records:
            return ContentMiss(ref=ref, reason="unknown_index")
        return None

    def record(self, ref: ContentRef) -> Record | ContentMiss:
        missing = self.resolves(ref)
        return missing if missing is not None else self.records[ref]

    def provides(self, pack: ContentSlug) -> bool:
        return pack in self.packs


def loaded(packs: Sequence[Pack]) -> Content:
    ids = [pack.manifest.id for pack in packs]
    if clashing := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"two packs claim the same id: {clashing}")
    for pack in packs:
        if missing := sorted(set(pack.manifest.requires) - set(ids)):
            raise ValueError(f"pack {pack.manifest.id!r} requires {missing}, not loaded")
    return Content(
        packs=tuple(pack.manifest.id for pack in packs),
        records={ref: record for pack in packs for ref, record in pack.addressed().items()},
    )


def load(directories: Sequence[Path]) -> Content:
    return loaded([read_pack(d) for d in directories])


def read_pack(directory: Path) -> Pack:
    keyed: dict[Collection, dict[object, dict[str, object]]] = {}
    for name in COLLECTION_SPECS:
        path = directory / f"{name}.json"
        records = _RAW.validate_json(_text(path)) if path.exists() else []
        keyed[name] = {record.get("index"): record for record in records}
    manifest = Manifest.model_validate_json(_text(directory / "manifest.json"))
    return Pack.model_validate({"manifest": manifest, "records": keyed})


def write_pack(directory: Path, pack: Pack) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / "manifest.json", pack.manifest.model_dump_json(indent=2))
    for name in COLLECTION_SPECS:
        records = pack.records.get(name, {})
        dumped = [record.model_dump(mode="json") for record in records.values()]
        _write(directory / f"{name}.json", json.dumps(dumped, indent=2, ensure_ascii=False))


def _text(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"pack file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _write(path: Path, body: str) -> None:
    path.write_text(body + "\n", encoding=ENCODING)
