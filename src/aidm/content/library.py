"""Loading packs from disk, and looking records up in what was loaded."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap
from .models import Manifest, Pack, PackStamp
from .records import Collection, ContentRef, Record, Slug
from .registry import COLLECTION_OF, COLLECTION_SPECS

ENCODING = "utf-8"

# `wrong_type` is a record of another class under the ref — the level that is a subclass level, the
# proficiency that is a skill rather than a save. It is a miss rather than a raise because asking
# for a subtype is how a caller *tests* which arm a record is.
MissReason = Literal["unknown_pack", "wrong_collection", "unknown_index", "wrong_type"]

# Collections are JSON arrays on disk — the authoring shape — and keyed by index once loaded. Read
# untyped so that one line covers every collection; `Pack` is what validates the records.
_RAW: TypeAdapter[list[dict[str, object]]] = TypeAdapter(list[dict[str, object]])


class ContentMiss(Frozen):
    """A ref nothing loaded provides. A value rather than a raise because `pipeline` turns any raise
    into a dropped turn: a missing record must degrade visibly, not eat the player's move."""

    ref: ContentRef
    reason: MissReason

    @property
    def summary(self) -> str:
        return f"missing content {self.ref}: {self.reason}"


class Content(Frozen):
    """Every loaded record under the ref that addresses it. Flat because `ContentRef` is already a
    record's identity, so a per-pack scan on every lookup would re-answer what the key answers;
    build one through `loaded`, which holds the checks a *set* of packs must pass."""

    stamps: tuple[PackStamp, ...] = ()
    records: FrozenMap[ContentRef, Record] = EMPTY_FROZEN_MAP

    def get[R: Record](self, ref: ContentRef, kind: type[R]) -> R | ContentMiss:
        """The typed lookup: the registry names each class's collection, so a caller cannot ask for
        a monster and get the spell of that index. A class in no collection raises, never misses."""
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
        """The fail-loud lookup, for callers outside a turn — composing a world, reaching a level.
        Naming the intent stops them translating misses back into raises."""
        found = self.get(ref, kind)
        if isinstance(found, ContentMiss):
            raise ValueError(found.summary)
        return found

    def resolves(self, ref: ContentRef) -> ContentMiss | None:
        """Why a ref does not resolve, or `None` if it does: what a load boundary needs before
        trusting a ref it will not itself read, whatever class the record turns out to be."""
        if not self.provides(ref.pack):
            return ContentMiss(ref=ref, reason="unknown_pack")
        if ref not in self.records:
            return ContentMiss(ref=ref, reason="unknown_index")
        return None

    def provides(self, pack: Slug) -> bool:
        return any(stamp.id == pack for stamp in self.stamps)


def loaded(packs: Sequence[Pack]) -> Content:
    """A clash of pack ids or a missing dependency fails here: the two things a *set* of packs can
    get wrong that no single pack can."""
    ids = [pack.manifest.id for pack in packs]
    if clashing := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"two packs claim the same id: {clashing}")
    for pack in packs:
        if missing := sorted(set(pack.manifest.requires) - set(ids)):
            raise ValueError(f"pack {pack.manifest.id!r} requires {missing}, not loaded")
    return Content(
        stamps=tuple(pack.manifest.stamp for pack in packs),
        records={ref: record for pack in packs for ref, record in pack.addressed().items()},
    )


def load(directories: Sequence[Path]) -> Content:
    return loaded([read_pack(d) for d in directories])


def read_pack(directory: Path) -> Pack:
    keyed: dict[Collection, dict[object, dict[str, object]]] = {}
    for name in COLLECTION_SPECS:
        # No file is a pack that ships none of it — a gap its manifest declares. A record missing
        # its `index` keys to `None`, which `Pack` rejects by type.
        path = directory / f"{name}.json"
        records = _RAW.validate_json(_text(path)) if path.exists() else []
        keyed[name] = {record.get("index"): record for record in records}
    manifest = Manifest.model_validate_json(_text(directory / "manifest.json"))
    return Pack.model_validate({"manifest": manifest, "records": keyed})


def write_pack(directory: Path, pack: Pack) -> None:
    """Each record is dumped through its own class, so a subclass's projection survives."""
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
