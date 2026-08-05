import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from pydantic import TypeAdapter

from aidm.core.enginepack import EngineSpec
from aidm.core.packs import (
    ENCODING,
    CollectionName,
    LenientRecord,
    Manifest,
    Pack,
    lenient_format,
    validate_pack,
)

from . import project
from . import upstream as up

EDITION = "2014"
ENGINE_DIR = Path(__file__).parents[2] / "src" / "aidm" / "engines" / "dnd5e"
EQUIPMENT_COLLECTIONS: Mapping[
    CollectionName, tuple[str, Callable[[up.Equipment], LenientRecord]]
] = {
    "weapons": ("weapon", project.weapon),
    "armor": ("armor", project.armor),
    "gear": ("adventuring-gear", project.gear),
    "tools": ("tools", project.gear),
    "vehicles": ("mounts-and-vehicles", project.vehicle),
}


class PackageJson(up.Upstream):
    version: str


def build(checkout: Path) -> Pack:
    source = checkout / "src" / EDITION / "en"

    def read[T: up.Upstream](name: str, model: type[T]) -> list[T]:
        adapter: TypeAdapter[list[T]] = TypeAdapter(list[model])
        return adapter.validate_json((source / f"5e-SRD-{name}.json").read_text(encoding=ENCODING))

    equipment = read("Equipment", up.Equipment)
    features = read("Features", up.Feature)
    choices = {f.index: options for f in features if (options := project.subfeature_options(f))}
    records: Mapping[CollectionName, Mapping[str, LenientRecord]] = {
        "monsters": _keyed(project.monster(r) for r in read("Monsters", up.Monster)),
        **{
            name: _keyed(projected(r) for r in equipment if r.equipment_category.index == category)
            for name, (category, projected) in EQUIPMENT_COLLECTIONS.items()
        },
        "magic_items": _keyed(project.magic_item(r) for r in read("Magic-Items", up.MagicItem)),
        "spells": _keyed(project.spell(r) for r in read("Spells", up.Spell)),
        "skills": _keyed(project.skill(r) for r in read("Skills", up.Skill)),
        "conditions": _keyed(project.described(r) for r in read("Conditions", up.Described)),
        "alignments": _keyed(project.alignment(r) for r in read("Alignments", up.Alignment)),
        "languages": _keyed(project.language(r) for r in read("Languages", up.Language)),
        "classes": _keyed(project.klass(r) for r in read("Classes", up.Class)),
        "subclasses": _keyed(project.subclass(r) for r in read("Subclasses", up.Subclass)),
        "levels": _keyed(project.level(r, choices) for r in read("Levels", up.Level)),
        "features": _keyed(project.feature(r) for r in features),
        "races": _keyed(project.race(r) for r in read("Races", up.Race)),
        "subraces": _keyed(project.subrace(r) for r in read("Subraces", up.Subrace)),
        "traits": _keyed(project.trait(r) for r in read("Traits", up.Trait)),
        "backgrounds": _keyed(project.background(r) for r in read("Backgrounds", up.Background)),
        "feats": _keyed(project.feat(r) for r in read("Feats", up.Feat)),
        "proficiencies": _keyed(
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
    validate_pack(pack, lenient_format(_collections()))
    return pack


def _collections() -> tuple[CollectionName, ...]:
    """The engine's spec is the single list of what this pack may hold."""
    spec = EngineSpec.model_validate_json((ENGINE_DIR / "spec.json").read_text(encoding=ENCODING))
    return spec.collections


def _keyed(records: Iterable[LenientRecord]) -> dict[str, LenientRecord]:
    return {record.index: record for record in records}


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
