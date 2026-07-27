"""Loading packs from disk, and looking records up in them."""

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import TypeAdapter, model_validator

from ..utils.models import Frozen
from .models import COLLECTIONS, Manifest, Pack, PackStamp
from .records import (
    AlignmentRecord,
    ArmorRecord,
    Collection,
    ConditionRecord,
    ContentRef,
    GearRecord,
    LanguageRecord,
    MagicItemRecord,
    MonsterRecord,
    Record,
    SkillRecord,
    SpellRecord,
    ToolRecord,
    VehicleRecord,
    WeaponRecord,
)

ENCODING = "utf-8"

MissReason = Literal["unknown_pack", "wrong_collection", "unknown_index"]

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
        clashing = sorted({i for i in ids if ids.count(i) > 1})
        if clashing:
            raise ValueError(f"two packs claim the same id: {clashing}")
        for pack in self.packs:
            missing = sorted(set(pack.manifest.requires) - set(ids))
            if missing:
                raise ValueError(f"pack {pack.manifest.id!r} requires {missing}, not loaded")
        return self

    @property
    def stamps(self) -> list[PackStamp]:
        return [p.manifest.stamp for p in self.packs]

    # Hand-written rather than generated: these are what stop a caller asking for a monster and
    # receiving the spell of that index, which is the whole point of the triple.
    def monster(self, ref: ContentRef) -> MonsterRecord | ContentMiss:
        return self._lookup(ref, "monsters", lambda p: p.monsters)

    def weapon(self, ref: ContentRef) -> WeaponRecord | ContentMiss:
        return self._lookup(ref, "weapons", lambda p: p.weapons)

    def armor(self, ref: ContentRef) -> ArmorRecord | ContentMiss:
        return self._lookup(ref, "armor", lambda p: p.armor)

    def gear(self, ref: ContentRef) -> GearRecord | ContentMiss:
        return self._lookup(ref, "gear", lambda p: p.gear)

    def tool(self, ref: ContentRef) -> ToolRecord | ContentMiss:
        return self._lookup(ref, "tools", lambda p: p.tools)

    def vehicle(self, ref: ContentRef) -> VehicleRecord | ContentMiss:
        return self._lookup(ref, "vehicles", lambda p: p.vehicles)

    def magic_item(self, ref: ContentRef) -> MagicItemRecord | ContentMiss:
        return self._lookup(ref, "magic_items", lambda p: p.magic_items)

    def spell(self, ref: ContentRef) -> SpellRecord | ContentMiss:
        return self._lookup(ref, "spells", lambda p: p.spells)

    def skill(self, ref: ContentRef) -> SkillRecord | ContentMiss:
        return self._lookup(ref, "skills", lambda p: p.skills)

    def condition(self, ref: ContentRef) -> ConditionRecord | ContentMiss:
        return self._lookup(ref, "conditions", lambda p: p.conditions)

    def alignment(self, ref: ContentRef) -> AlignmentRecord | ContentMiss:
        return self._lookup(ref, "alignments", lambda p: p.alignments)

    def language(self, ref: ContentRef) -> LanguageRecord | ContentMiss:
        return self._lookup(ref, "languages", lambda p: p.languages)

    def resolves(self, ref: ContentRef) -> ContentMiss | None:
        """Why a ref does not resolve, or `None` if it does — what a load boundary needs before it
        trusts a ref it will not itself read."""
        pack = self._pack(ref)
        if pack is None:
            return ContentMiss(ref=ref, reason="unknown_pack")
        if ref.index not in pack.collection(ref.collection):
            return ContentMiss(ref=ref, reason="unknown_index")
        return None

    def _lookup[R: Record](
        self, ref: ContentRef, collection: Collection, of: Callable[[Pack], Mapping[str, R]]
    ) -> R | ContentMiss:
        if ref.collection != collection:
            return ContentMiss(ref=ref, reason="wrong_collection")
        pack = self._pack(ref)
        if pack is None:
            return ContentMiss(ref=ref, reason="unknown_pack")
        record = of(pack).get(ref.index)
        return record if record is not None else ContentMiss(ref=ref, reason="unknown_index")

    def _pack(self, ref: ContentRef) -> Pack | None:
        return next((p for p in self.packs if p.manifest.id == ref.pack), None)


def load(directories: Sequence[Path]) -> Library:
    return Library(packs=tuple(_read_pack(d) for d in directories))


def _read_pack(directory: Path) -> Pack:
    keyed = {name: _keyed(_records(directory, name)) for name in COLLECTIONS}
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


def _records(directory: Path, name: Collection) -> list[dict[str, object]]:
    """A collection with no file is a pack that ships none of it — a gap its manifest declares."""
    path = directory / f"{name}.json"
    return _RAW.validate_json(_text(path)) if path.exists() else []


def _keyed(records: Sequence[dict[str, object]]) -> dict[object, dict[str, object]]:
    """A record missing its `index` produces a `None` key, which `Pack` rejects by type."""
    return {record.get("index"): record for record in records}


def _text(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"pack file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _write(path: Path, body: str) -> None:
    path.write_text(body + "\n", encoding=ENCODING)
