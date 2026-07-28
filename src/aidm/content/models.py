"""A pack: a manifest and the records it provides — the shape an author writes and the importer
writes back. The record models themselves live in `records/`, one module per family; which
collections exist and how each is validated lives in `registry.py`."""

from collections.abc import Mapping
from typing import Self

from pydantic import NonNegativeInt, SerializeAsAny, TypeAdapter, model_validator

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap
from .records import Collection, ContentRef, Record, Slug
from .registry import COLLECTION_SPECS

# An `object` body is what lets one routing step accept an authored dict, a dumped dict and a live
# record; the `Collection` key is what refuses a collection no spec can route.
type _Routable = Mapping[Collection, Mapping[str, object]]
_ROUTABLE: TypeAdapter[_Routable] = TypeAdapter(_Routable)
_FIELDS: TypeAdapter[Mapping[str, object]] = TypeAdapter(Mapping[str, object])


class PackStamp(Frozen):
    id: Slug
    version: str


class Manifest(Frozen):
    id: Slug
    name: str
    version: str
    edition: str
    requires: tuple[Slug, ...] = ()
    # Checked against the records by `Pack`: `extra="ignore"` cannot see a truncated collection.
    provides: FrozenMap[Collection, NonNegativeInt]

    @property
    def stamp(self) -> PackStamp:
        return PackStamp(id=self.id, version=self.version)


class Pack(Frozen):
    """One loaded pack, its records keyed by collection and then by index.

    `SerializeAsAny` is what keeps a dump lossless: the field is declared `Record`, so pydantic
    would otherwise serialize a monster as the base's two fields — silently, no warning — and
    `updated(pack, ...)` would drop the other twenty."""

    manifest: Manifest
    records: FrozenMap[Collection, FrozenMap[Slug, SerializeAsAny[Record]]] = EMPTY_FROZEN_MAP

    @model_validator(mode="before")
    @classmethod
    def _routed(cls, data: object) -> object:
        """Each collection through its own spec, so `monsters.json` cannot hold a spell and a record
        keeps the fields its own class declares. Without this, validating a dumped pack would check
        every record against the bare `Record` base."""
        if not isinstance(data, Mapping):
            return data
        fields = _FIELDS.validate_python(data)
        held = fields.get("records")
        if held is None:
            return fields
        routed = {
            name: {i: COLLECTION_SPECS[name].adapter.validate_python(b) for i, b in bodies.items()}
            for name, bodies in _ROUTABLE.validate_python(held).items()
        }
        return {**fields, "records": routed}

    @model_validator(mode="after")
    def _matches_its_manifest(self) -> Self:
        """Fails here rather than mid-turn: a mis-keyed collection, or a file truncated since the
        manifest was written. Counting every collection is what makes a 0 a *stated gap* a character
        creator can show up front, rather than an omission."""
        if undeclared := sorted(set(COLLECTION_SPECS) - set(self.manifest.provides)):
            raise ValueError(f"manifest declares no count for {undeclared}")
        for name, declared in self.manifest.provides.items():
            records = self.records.get(name, {})
            if wrong := sorted(index for index, r in records.items() if index != r.index):
                raise ValueError(f"{name} keyed against the wrong index: {wrong}")
            if declared != len(records):
                raise ValueError(
                    f"manifest promises {declared} {name}, the pack ships {len(records)}"
                )
        return self

    def addressed(self) -> Mapping[ContentRef, Record]:
        """Every record under the ref that addresses it: the pack's own id is what makes a ref
        absolute, and so what lets one flat index hold every loaded pack."""
        return {
            ContentRef(pack=self.manifest.id, collection=name, index=index): record
            for name, records in self.records.items()
            for index, record in records.items()
        }
