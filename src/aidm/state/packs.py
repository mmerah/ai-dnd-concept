import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self, TypeGuard

from pydantic import (
    AfterValidator,
    Field,
    JsonValue,
    NonNegativeInt,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    WrapSerializer,
    model_validator,
)

from .base import Frozen, Slug

ENCODING = "utf-8"

MissReason = Literal["unknown_pack", "unknown_index"]

_RAW: TypeAdapter[list[dict[str, object]]] = TypeAdapter(list[dict[str, object]])


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _as_dict[K, V](mapping: Mapping[K, V], serialize: SerializerFunctionWrapHandler) -> object:
    return serialize(dict(mapping))


type FrozenMap[K, V] = Annotated[
    Mapping[K, V],
    AfterValidator(_immutable),
    WrapSerializer(_as_dict),
]

EMPTY_FROZEN_MAP = Field(default_factory=dict, validate_default=True)

# Upstream indexes run hyphens together ('...red---fire-damage'), so laxer than `Slug`.
CONTENT_SLUG_MAX_LENGTH = 64
ContentSlug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=CONTENT_SLUG_MAX_LENGTH)]
# A collection names a pack file and a spec, never a record, so 'magic_items' is legal.
CollectionName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]


class ContentRef(Frozen):
    """Uses a triple because indexes collide across collections and packs."""

    pack: ContentSlug
    collection: CollectionName
    index: ContentSlug

    def __str__(self) -> str:
        return f"{self.pack}/{self.collection}/{self.index}"

    def sibling(self, collection: CollectionName, index: ContentSlug) -> "ContentRef":
        return ContentRef(pack=self.pack, collection=collection, index=index)


class Record(Frozen):
    """`facts` carries every normalized mechanical value a record holds, keyed by slug. An
    int-valued fact in a collection the engine spec flags as projecting lands on the sheet of any
    entity that refs the record — a record reffed in multiplicity (a spell, a feature) must leave
    those keys out of its facts or they would collide. Every other fact renders beside the ref and
    in `read_content`, never touching a sheet. The engine spec names the facts every record in a
    collection must hold."""

    index: ContentSlug
    name: str
    text: str = ""
    tags: tuple[Slug, ...] = ()
    # A record that IS a choice names the legal picks; a bare index would be ambiguous.
    options: tuple[ContentRef, ...] = ()
    choose: int | None = None
    facts: FrozenMap[Slug, JsonValue] = EMPTY_FROZEN_MAP

    @model_validator(mode="after")
    def _choice_is_whole(self) -> Self:
        if (self.choose is None) != (not self.options):
            raise ValueError("options and choose are set together, or neither is")
        if self.choose is not None and not 1 <= self.choose <= len(self.options):
            raise ValueError(f"cannot choose {self.choose} of {len(self.options)} options")
        return self


type FactType = Literal["int", "slug", "str"]
type FactSchema = Mapping[Slug, FactType]


class Manifest(Frozen):
    id: ContentSlug
    name: str
    version: str
    edition: str
    requires: tuple[ContentSlug, ...] = ()
    provides: FrozenMap[CollectionName, NonNegativeInt]
    # A version string alone lets upstream content churn smuggle into a schema-only regeneration.
    source_commit: str | None = None


class Pack(Frozen):
    """Which collections a pack may hold is checked by `validate_pack`."""

    manifest: Manifest
    records: FrozenMap[CollectionName, FrozenMap[ContentSlug, Record]] = EMPTY_FROZEN_MAP

    def addressed(self) -> Mapping[ContentRef, Record]:
        return {
            ContentRef(pack=self.manifest.id, collection=name, index=index): record
            for name, records in self.records.items()
            for index, record in records.items()
        }


class ContentMiss(Frozen):
    ref: ContentRef
    reason: MissReason

    @property
    def summary(self) -> str:
        return f"missing content {self.ref}: {self.reason}"


@dataclass(frozen=True, slots=True)
class Content:
    packs: tuple[ContentSlug, ...]
    records: Mapping[ContentRef, Record]

    def record(self, ref: ContentRef) -> Record | ContentMiss:
        if not self.provides(ref.pack):
            return ContentMiss(ref=ref, reason="unknown_pack")
        found = self.records.get(ref)
        return ContentMiss(ref=ref, reason="unknown_index") if found is None else found

    def require(self, ref: ContentRef) -> Record:
        found = self.record(ref)
        if isinstance(found, ContentMiss):
            raise ValueError(found.summary)
        return found

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


def load(directories: Sequence[Path], collections: Mapping[CollectionName, FactSchema]) -> Content:
    return loaded([read_pack(d, collections) for d in directories])


def parse_ref(text: str) -> ContentRef:
    """A model names a record as one string, so a malformed one must read back as a refusal."""
    parts = text.split("/")
    if len(parts) != 3:
        raise ValueError(f"malformed ref {text!r}: write it as `pack/collection/index`")
    try:
        return ContentRef(pack=parts[0], collection=parts[1], index=parts[2])
    except ValidationError as invalid:
        raise ValueError(f"malformed ref {text!r}: {invalid.errors()[0]['msg']}") from invalid


def read_pack(directory: Path, collections: Mapping[CollectionName, FactSchema]) -> Pack:
    records = {
        name: {record.index: record for record in _read(directory / f"{name}.json")}
        for name in collections
    }
    pack = Pack(
        manifest=Manifest.model_validate_json(_text(directory / "manifest.json")),
        records=records,
    )
    validate_pack(pack, collections)
    return pack


def write_pack(directory: Path, pack: Pack) -> None:
    """Records keep the order they were read in, so a round trip is byte-identical."""
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / "manifest.json", pack.manifest.model_dump_json(indent=2))
    for name, records in pack.records.items():
        dumped = [
            record.model_dump(mode="json", exclude_defaults=True) for record in records.values()
        ]
        _write(directory / f"{name}.json", json.dumps(dumped, indent=2, ensure_ascii=False))


def validate_pack(pack: Pack, collections: Mapping[CollectionName, FactSchema]) -> None:
    """What a pack cannot check alone: which collections exist, and what each one may hold."""
    named = set(pack.records) | set(pack.manifest.provides)
    if unknown := sorted(named - set(collections)):
        raise ValueError(f"the format specifies no collection {unknown}")
    if undeclared := sorted(set(collections) - set(pack.manifest.provides)):
        raise ValueError(f"manifest declares no count for {undeclared}")
    for name, facts in collections.items():
        records = pack.records.get(name, {})
        if miskeyed := sorted(index for index, r in records.items() if index != r.index):
            raise ValueError(f"{name} keyed against the wrong index: {miskeyed}")
        declared = pack.manifest.provides[name]
        if declared != len(records):
            raise ValueError(f"manifest promises {declared} {name}, the pack ships {len(records)}")
        for key, kind in facts.items():
            wrong = sorted(i for i, r in records.items() if not _fact_is(r.facts.get(key), kind))
            if wrong:
                raise ValueError(f"{name} records lack the required {kind} fact {key!r}: {wrong}")


_SLUG: TypeAdapter[str] = TypeAdapter(Slug)


def is_int_fact(value: JsonValue | None) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def is_ladder_fact(value: JsonValue) -> TypeGuard[list[list[JsonValue]]]:
    """A non-empty list of `[threshold, value]` rungs, judged by shape rather than a key-name
    convention. A ladder starting at 0 states its own base, so the compact render can drop to that
    rung; one starting elsewhere (a monster's `slots`) means nothing without every rung."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(rung, list) and len(rung) == 2 for rung in value)
    )


def fact_line(key: str, value: JsonValue, *, ladder_full: bool) -> str | None:
    """One rendering of a fact: a scalar `key=value`, a ladder's rung 0 or every rung, or a flat
    list joined. `None` for anything else (a dict, or a list holding one) — nothing reads those."""
    if is_ladder_fact(value):
        if ladder_full or value[0][0] != 0:
            return f"{key}=" + ", ".join(f"{threshold}:{rung}" for threshold, rung in value)
        return f"{key}={value[0][1]}"
    if isinstance(value, list):
        if not value or any(isinstance(item, list | dict) for item in value):
            return None
        return f"{key}=" + ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return None
    return f"{key}={value}"


def _fact_is(value: JsonValue | None, kind: FactType) -> bool:
    match kind:
        case "int":
            return is_int_fact(value)
        case "slug":
            try:
                _ = _SLUG.validate_python(value, strict=True)
            except ValidationError:
                return False
            return True
        case "str":
            return isinstance(value, str)


def _read(path: Path) -> list[Record]:
    raw = _RAW.validate_json(_text(path)) if path.exists() else []
    return [Record.model_validate(record) for record in raw]


def _text(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"pack file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _write(path: Path, body: str) -> None:
    path.write_text(body + "\n", encoding=ENCODING)
