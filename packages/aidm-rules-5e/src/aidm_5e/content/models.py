from collections.abc import Mapping
from typing import Self

from aidm.utils.models import EMPTY_FROZEN_MAP, FrozenMap
from pydantic import NonNegativeInt, SerializeAsAny, TypeAdapter, model_validator

from ..utils.models import Frozen, Slug
from .records.base import Collection, ContentRef, Record
from .registry import COLLECTION_SPECS

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
    provides: FrozenMap[Collection, NonNegativeInt]

    @property
    def stamp(self) -> PackStamp:
        return PackStamp(id=self.id, version=self.version)


class Pack(Frozen):
    """`SerializeAsAny` preserves concrete record fields when dumping."""

    manifest: Manifest
    records: FrozenMap[Collection, FrozenMap[Slug, SerializeAsAny[Record]]] = EMPTY_FROZEN_MAP

    @model_validator(mode="before")
    @classmethod
    def _routed(cls, data: object) -> object:
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
        return {
            ContentRef(pack=self.manifest.id, collection=name, index=index): record
            for name, records in self.records.items()
            for index, record in records.items()
        }
