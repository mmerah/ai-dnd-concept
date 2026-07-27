"""Reading a checkout, and assembling the pack it becomes."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import TypeAdapter

from aidm.content import Manifest, Pack
from aidm.content.records import Collection, Record

from .common import PACK_ID
from .equipment import armor, gear, magic_item, tool, vehicle, weapon
from .monsters import monster
from .rules import alignment, condition, language, skill, spell
from .upstream import (
    Alignment,
    Condition,
    Equipment,
    Language,
    MagicItem,
    Monster,
    Skill,
    Spell,
    Upstream,
)

EDITION = "2014"
ENCODING = "utf-8"

_MONSTERS: TypeAdapter[list[Monster]] = TypeAdapter(list[Monster])
_EQUIPMENT: TypeAdapter[list[Equipment]] = TypeAdapter(list[Equipment])
_MAGIC_ITEMS: TypeAdapter[list[MagicItem]] = TypeAdapter(list[MagicItem])
_SPELLS: TypeAdapter[list[Spell]] = TypeAdapter(list[Spell])
_SKILLS: TypeAdapter[list[Skill]] = TypeAdapter(list[Skill])
_CONDITIONS: TypeAdapter[list[Condition]] = TypeAdapter(list[Condition])
_ALIGNMENTS: TypeAdapter[list[Alignment]] = TypeAdapter(list[Alignment])
_LANGUAGES: TypeAdapter[list[Language]] = TypeAdapter(list[Language])


class PackageJson(Upstream):
    version: str


def build(checkout: Path) -> Pack:
    source = checkout / "src" / EDITION / "en"

    def text(name: str) -> str:
        return (source / f"5e-SRD-{name}.json").read_text(encoding=ENCODING)

    equipment = _EQUIPMENT.validate_json(text("Equipment"))
    collections: dict[Collection, Mapping[str, Record]] = {
        "monsters": _keyed(monster(m) for m in _MONSTERS.validate_json(text("Monsters"))),
        "weapons": _keyed(_of(equipment, "weapon", weapon)),
        "armor": _keyed(_of(equipment, "armor", armor)),
        "gear": _keyed(_of(equipment, "adventuring-gear", gear)),
        "tools": _keyed(_of(equipment, "tools", tool)),
        "vehicles": _keyed(_of(equipment, "mounts-and-vehicles", vehicle)),
        "magic_items": _keyed(
            magic_item(m) for m in _MAGIC_ITEMS.validate_json(text("Magic-Items"))
        ),
        "spells": _keyed(spell(s) for s in _SPELLS.validate_json(text("Spells"))),
        "skills": _keyed(skill(s) for s in _SKILLS.validate_json(text("Skills"))),
        "conditions": _keyed(condition(c) for c in _CONDITIONS.validate_json(text("Conditions"))),
        "alignments": _keyed(alignment(a) for a in _ALIGNMENTS.validate_json(text("Alignments"))),
        "languages": _keyed(language(x) for x in _LANGUAGES.validate_json(text("Languages"))),
    }
    manifest = Manifest(
        id=PACK_ID,
        name="5e SRD (2014)",
        version=_version(checkout),
        edition=EDITION,
        provides={name: len(records) for name, records in collections.items()},
    )
    return Pack.model_validate({"manifest": manifest, **collections})


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
