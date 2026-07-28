"""Loading packs from disk, and looking records up in them."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import TypeAdapter, model_validator

from ..utils.models import Frozen
from .models import COLLECTIONS, Manifest, Pack, PackStamp
from .records import Collection, ContentRef, Record

ENCODING = "utf-8"

# `wrong_type` is a record of another class under the ref — the level that is a subclass level, the
# proficiency that is a skill rather than a save. It is a miss rather than a raise because asking
# for a subtype is how a caller *tests* which arm a record is.
MissReason = Literal["unknown_pack", "wrong_collection", "unknown_index", "wrong_type"]

# Collections are JSON arrays on disk — the authoring shape — and keyed by index once loaded. Read
# untyped so that one line covers every collection; `Pack` is what validates the records.
_RAW: TypeAdapter[list[dict[str, object]]] = TypeAdapter(list[dict[str, object]])


class ContentMiss(Frozen):
    """A ref nothing loaded provides. A value rather than a raise, because `pipeline` turns any
    raise into a dropped turn: a missing record must degrade visibly, not eat the player's move."""

    ref: ContentRef
    reason: MissReason

    @property
    def summary(self) -> str:
        return f"missing content {self.ref}: {self.reason}"


class Library(Frozen):
    """Every pack this game is playing, in the order it was loaded."""

    packs: tuple[Pack, ...] = ()

    @model_validator(mode="after")
    def _loadable_together(self) -> Self:
        """Pack load is an external boundary: a clash or a missing dependency must fail here."""
        ids = [p.manifest.id for p in self.packs]
        if clashing := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"two packs claim the same id: {clashing}")
        for pack in self.packs:
            if missing := sorted(set(pack.manifest.requires) - set(ids)):
                raise ValueError(f"pack {pack.manifest.id!r} requires {missing}, not loaded")
        return self

    @property
    def stamps(self) -> list[PackStamp]:
        return [p.manifest.stamp for p in self.packs]

    def get[R: Record](self, ref: ContentRef, kind: type[R]) -> R | ContentMiss:
        """The typed lookup: the record class names its own collection, so a caller cannot ask for
        a monster and receive the spell of that index."""
        if ref.collection != kind.COLLECTION:
            return ContentMiss(ref=ref, reason="wrong_collection")
        pack = self._pack(ref)
        if pack is None:
            return ContentMiss(ref=ref, reason="unknown_pack")
        record = pack.collection(ref.collection).get(ref.index)
        if record is None:
            return ContentMiss(ref=ref, reason="unknown_index")
        if not isinstance(record, kind):
            return ContentMiss(ref=ref, reason="wrong_type")
        return record

    def require[R: Record](self, ref: ContentRef, kind: type[R]) -> R:
        """The fail-loud lookup, for callers outside a turn — composing a world, reaching a level.
        Naming the intent here is what keeps them from translating misses back into raises."""
        found = self.get(ref, kind)
        if isinstance(found, ContentMiss):
            raise ValueError(found.summary)
        return found

    def resolves(self, ref: ContentRef) -> ContentMiss | None:
        """Why a ref does not resolve, or `None` if it does — what a load boundary needs before it
        trusts a ref it will not itself read, whatever class the record turns out to be."""
        pack = self._pack(ref)
        if pack is None:
            return ContentMiss(ref=ref, reason="unknown_pack")
        if ref.index not in pack.collection(ref.collection):
            return ContentMiss(ref=ref, reason="unknown_index")
        return None

    def _pack(self, ref: ContentRef) -> Pack | None:
        return next((p for p in self.packs if p.manifest.id == ref.pack), None)


def load(directories: Sequence[Path]) -> Library:
    return Library(packs=tuple(_read_pack(d) for d in directories))


def _read_pack(directory: Path) -> Pack:
    keyed: dict[Collection, dict[object, dict[str, object]]] = {}
    for name in COLLECTIONS:
        # No file is a pack that ships none of it — a gap its manifest declares. A record missing
        # its `index` keys to `None`, which `Pack` rejects by type.
        path = directory / f"{name}.json"
        records = _RAW.validate_json(_text(path)) if path.exists() else []
        keyed[name] = {record.get("index"): record for record in records}
    manifest = Manifest.model_validate_json(_text(directory / "manifest.json"))
    return Pack.model_validate({"manifest": manifest, **keyed})


def write_pack(directory: Path, pack: Pack) -> None:
    """Each record is dumped through its own class, so a subclass's projection survives; an adapter
    typed to the `Record` base would serialize the base's two fields and drop the rest."""
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / "manifest.json", pack.manifest.model_dump_json(indent=2))
    for name in COLLECTIONS:
        dumped = [record.model_dump(mode="json") for record in pack.collection(name).values()]
        _write(directory / f"{name}.json", json.dumps(dumped, indent=2, ensure_ascii=False))


def _text(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"pack file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _write(path: Path, body: str) -> None:
    path.write_text(body + "\n", encoding=ENCODING)
