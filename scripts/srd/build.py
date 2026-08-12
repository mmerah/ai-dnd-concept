import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from pydantic import TypeAdapter

from aidm.engines.dnd5e.content import pack_format
from aidm.state.packs import (
    ENCODING,
    CollectionName,
    Manifest,
    Pack,
    Record,
    validate_pack,
)

from . import project
from . import upstream as up
from .interpret import Interpreted

EDITION = "2014"
EQUIPMENT_COLLECTIONS: Mapping[
    CollectionName, tuple[str, Callable[[up.Equipment], Interpreted]]
] = {
    "armor": ("armor", project.armor),
    "gear": ("adventuring-gear", project.gear),
    "tools": ("tools", project.gear),
    "vehicles": ("mounts-and-vehicles", project.vehicle),
}


class PackageJson(up.Upstream):
    version: str


class EquipmentCategory(up.Named):
    equipment: list[up.Named] = []


def build(checkout: Path) -> Pack:
    source = checkout / "src" / EDITION / "en"

    def read[T: up.Upstream](name: str, model: type[T]) -> list[T]:
        adapter: TypeAdapter[list[T]] = TypeAdapter(list[model])
        return adapter.validate_json((source / f"5e-SRD-{name}.json").read_text(encoding=ENCODING))

    equipment = read("Equipment", up.Equipment)
    features = read("Features", up.Feature)
    languages = read("Languages", up.Language)
    classes = read("Classes", up.Class)
    subclasses = read("Subclasses", up.Subclass)
    levels = read("Levels", up.Level)
    choices = {f.index: found for f in features if (found := project.subfeature_options(f))[0]}
    archetypes = project.subclass_choices(subclasses, levels)
    collections = _item_collections(equipment)
    categories = {
        entry.index: [item.index for item in entry.equipment]
        for entry in read("Equipment-Categories", EquipmentCategory)
    }
    records: Mapping[CollectionName, Mapping[str, Record]] = {
        "monsters": _generic(project.monster(r) for r in read("Monsters", up.Monster)),
        "weapons": _generic(
            project.weapon(r) for r in equipment if r.equipment_category.index == "weapon"
        ),
        **{
            name: _generic(
                projected(r) for r in equipment if r.equipment_category.index == category
            )
            for name, (category, projected) in EQUIPMENT_COLLECTIONS.items()
        },
        "magic_items": _generic(project.magic_item(r) for r in read("Magic-Items", up.MagicItem)),
        "spells": _generic(project.spell(r) for r in read("Spells", up.Spell)),
        "skills": _generic(project.skill(r) for r in read("Skills", up.Skill)),
        "conditions": _keyed(project.described(r) for r in read("Conditions", up.Described)),
        "alignments": _keyed(project.alignment(r) for r in read("Alignments", up.Alignment)),
        "languages": _generic(project.language(r) for r in languages),
        "classes": _generic(project.klass(r) for r in classes),
        "equipment_options": _keyed(
            record
            for entry in classes
            for record in project.equipment_groups(entry, collections, categories)
        ),
        "subclasses": _generic(project.subclass(r) for r in subclasses),
        "levels": _generic(project.level(r, choices, archetypes) for r in levels),
        "features": _generic(project.feature(r) for r in features),
        "races": _generic(project.race(r) for r in read("Races", up.Race)),
        "subraces": _generic(project.subrace(r) for r in read("Subraces", up.Subrace)),
        "traits": _generic(project.trait(r) for r in read("Traits", up.Trait)),
        "backgrounds": _generic(
            project.background(r, languages) for r in read("Backgrounds", up.Background)
        ),
        "feats": _generic(project.feat(r) for r in read("Feats", up.Feat)),
        "proficiencies": _generic(
            project.proficiency(r) for r in read("Proficiencies", up.Proficiency)
        ),
    }
    pack = Pack.model_validate(
        {
            "manifest": Manifest(
                id=project.PACK_ID,
                name="5e SRD (2014)",
                version=_version(checkout),
                edition=EDITION,
                provides={name: len(entries) for name, entries in records.items()},
                source_commit=_commit(checkout),
            ),
            "records": records,
        }
    )
    # The engine's spec is the single list of what this pack may hold.
    validate_pack(pack, pack_format())
    return pack


def _keyed(records: Iterable[Record]) -> dict[str, Record]:
    return {record.index: record for record in records}


def _item_collections(equipment: Iterable[up.Equipment]) -> dict[str, CollectionName]:
    """Which pack collection each equipment index landed in, so a starting-equipment ref can name
    it. Magic items are their own upstream file and reach no starting-equipment list."""
    by_category = {
        "weapon": "weapons",
        **{category: name for name, (category, _) in EQUIPMENT_COLLECTIONS.items()},
    }
    return {
        record.index: collection
        for record in equipment
        if (collection := by_category.get(record.equipment_category.index)) is not None
    }


def _generic(records: Iterable[Interpreted]) -> dict[str, Record]:
    return {record.index: record.generic() for record in records}


def _version(checkout: Path) -> str:
    text = (checkout / "package.json").read_text(encoding=ENCODING)
    return PackageJson.model_validate_json(text).version


def _commit(checkout: Path) -> str:
    """The npm version alone lets content churn smuggle into a schema commit unnoticed."""
    found = subprocess.run(
        ("git", "-C", str(checkout), "rev-parse", "HEAD"),
        capture_output=True,
        check=True,
        text=True,
    )
    return found.stdout.strip()
