"""Reading a checkout, and assembling the pack it becomes."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import TypeAdapter

from aidm.core.packs import ContentRef, Manifest, Pack, Record, validate_pack
from aidm.engines.dnd5e.content.records.base import Collection
from aidm.engines.dnd5e.content.records.character import RecordOption
from aidm.engines.dnd5e.content.registry import PACK_FORMAT

from . import character as char
from .common import PACK_ID
from .corrections import corrected
from .equipment import armor, gear, magic_item, tool, vehicle, weapon
from .monsters import monster
from .rules import alignment, condition, language, skill, spell
from .upstream.base import Upstream
from .upstream.character import (
    Background,
    Class,
    Feat,
    Feature,
    Level,
    Race,
    Subclass,
    Subrace,
    Trait,
    UpstreamProficiency,
)
from .upstream.equipment import Equipment, EquipmentCategoryRecord, MagicItem
from .upstream.monsters import Monster
from .upstream.rules import Alignment, Condition, Language, Skill, Spell

EDITION = "2014"
ENCODING = "utf-8"


class PackageJson(Upstream):
    version: str


def build(checkout: Path) -> Pack:
    source = checkout / "src" / EDITION / "en"

    def read[T: Upstream](name: str, model: type[T]) -> list[T]:
        adapter: TypeAdapter[list[T]] = TypeAdapter(list[model])
        return adapter.validate_json((source / f"5e-SRD-{name}.json").read_text(encoding=ENCODING))

    equipment = read("Equipment", Equipment)
    languages = read("Languages", Language)
    levels = read("Levels", Level)
    subclass_levels = _subclass_levels(levels)
    categories = {
        c.index: [e.index for e in c.equipment]
        for c in read("Equipment-Categories", EquipmentCategoryRecord)
    }
    collections: dict[Collection, Mapping[str, Record]] = {
        "monsters": _keyed(monster(m) for m in read("Monsters", Monster)),
        "weapons": _keyed(_of(equipment, "weapon", weapon)),
        "armor": _keyed(_of(equipment, "armor", armor)),
        "gear": _keyed(_of(equipment, "adventuring-gear", gear)),
        "tools": _keyed(_of(equipment, "tools", tool)),
        "vehicles": _keyed(_of(equipment, "mounts-and-vehicles", vehicle)),
        "magic_items": _keyed(magic_item(m) for m in read("Magic-Items", MagicItem)),
        "spells": _keyed(spell(s) for s in read("Spells", Spell)),
        "skills": _keyed(skill(s) for s in read("Skills", Skill)),
        "conditions": _keyed(condition(c) for c in read("Conditions", Condition)),
        "alignments": _keyed(alignment(a) for a in read("Alignments", Alignment)),
        "languages": _keyed(language(x) for x in languages),
        "classes": _keyed(char.klass(c, subclass_levels) for c in read("Classes", Class)),
        "subclasses": _keyed(char.subclass(s) for s in read("Subclasses", Subclass)),
        "levels": _keyed(char.level(x) for x in levels),
        "features": _keyed(char.feature(f) for f in read("Features", Feature)),
        "races": _keyed(char.race(r) for r in read("Races", Race)),
        "subraces": _keyed(char.subrace(s) for s in read("Subraces", Subrace)),
        "traits": _keyed(char.trait(t) for t in read("Traits", Trait)),
        "backgrounds": _keyed(
            char.background(b, _language_options(languages))
            for b in read("Backgrounds", Background)
        ),
        "feats": _keyed(char.feat(f) for f in read("Feats", Feat)),
        "proficiencies": _keyed(
            char.proficiency(p, categories) for p in read("Proficiencies", UpstreamProficiency)
        ),
    }
    projected = corrected(collections)
    manifest = Manifest(
        id=PACK_ID,
        name="5e SRD (2014)",
        version=_version(checkout),
        edition=EDITION,
        provides={name: len(records) for name, records in projected.items()},
    )
    pack = Pack.model_validate({"manifest": manifest, "records": projected})
    validate_pack(pack, PACK_FORMAT)
    return pack


def _subclass_levels(levels: Sequence[Level]) -> dict[str, int]:
    """The level at which each subclass first grants something, which is the level it is chosen at:
    Life Domain at 1, Champion at 3."""
    first: dict[str, int] = {}
    for record in levels:
        if record.subclass is not None:
            index = record.subclass.index
            first[index] = min(record.level, first.get(index, record.level))
    return first


def _language_options(languages: Sequence[Language]) -> list[RecordOption]:
    """The Acolyte's language choice is a `resource_list` — a collection named by url and never
    listed, so its members have to be handed to the flattener."""
    return [
        RecordOption(
            label=x.name, ref=ContentRef(pack=PACK_ID, collection="languages", index=x.index)
        )
        for x in languages
    ]


def _of[R](
    equipment: Sequence[Equipment], category: str, project: Callable[[Equipment], R]
) -> list[R]:
    """One upstream type covers 237 records; `equipment_category` is what splits them into the five
    non-optional models the engine reads."""
    return [project(e) for e in equipment if e.equipment_category.index == category]


def _keyed[R: Record](records: Iterable[R]) -> dict[str, R]:
    return {record.index: record for record in records}


def _version(checkout: Path) -> str:
    text = (checkout / "package.json").read_text(encoding=ENCODING)
    return PackageJson.model_validate_json(text).version
