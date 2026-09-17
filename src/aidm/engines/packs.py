from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from aidm.core.entities import EngineId, Frozen, Refusal, Slug, content_id
from aidm.core.io import read_model
from aidm.core.model import PackSelection
from aidm.core.prompt import Sections, section_if, sections

SRD_PACK: Slug = "srd"
MAX_SUPPLEMENTS = 2  # two packs in play beside the source fill the worldsmith's command line


class Names(Frozen):
    female: tuple[str, ...] = ()
    male: tuple[str, ...] = ()
    neutral: tuple[str, ...] = ()
    surnames: tuple[str, ...] = ()
    nicknames: tuple[str, ...] = ()


class Location(Frozen):
    label: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    encounters: str = ""  # the SRD's "Possible encounters" line, names the worldsmith may use


class Pack(Frozen):
    """The setting kit every engine's pack carries; an engine adds its tables and its cast."""

    name: str = Field(min_length=1)
    source: str
    license: str
    setting: str = ""
    names: Names = Names()
    rules: str = ""  # special rules as prose, read by the master alone
    locations: tuple[Location, ...] = ()
    seeds: tuple[str, ...] = ()

    def defined_ids(self) -> tuple[Slug, ...]:
        """The option ids this pack defines; two selected packs may not share one."""
        return ()

    def sections(self, *, opening: bool) -> Sections:
        """Setting, names, locations always; seeds at the opening only; an engine adds its own."""
        name_lines = "\n".join(
            f"{kind}: {', '.join(values)}"
            for kind, values in (
                ("female", self.names.female),
                ("male", self.names.male),
                ("neutral", self.names.neutral),
                ("surnames", self.names.surnames),
                ("nicknames", self.names.nicknames),
            )
            if values
        )
        location_lines: list[str] = []
        for location in self.locations:
            location_lines.append(f"- {location.label} — {location.detail}")
            if location.encounters:
                location_lines.append(f"  encounters: {location.encounters}")
        seed_lines = "\n".join(f"- {seed}" for seed in self.seeds) if opening else ""
        return (
            *section_if("SETTING", self.setting),
            *section_if("NAMES", name_lines),
            *section_if("LOCATIONS", "\n".join(location_lines)),
            *section_if("ADVENTURE SEEDS", seed_lines),
        )


@dataclass(frozen=True, slots=True)
class PackSet[K: Pack]:
    engine: EngineId
    installed: Mapping[Slug, K]

    def srd(self) -> K:
        found = self.installed.get(SRD_PACK)
        if found is None:
            raise ValueError(f"the {self.engine!r} engine ships no {SRD_PACK!r} pack")
        return found

    def require(self, selection: PackSelection | None) -> PackSelection:
        if selection is None:
            raise Refusal(f"a {self.engine!r} game needs a table set")
        return selection

    def supplements(self) -> tuple[tuple[Slug, K], ...]:
        return tuple((key, pack) for key, pack in self.installed.items() if key != SRD_PACK)

    def chosen(self, selection: PackSelection | None) -> tuple[K, ...]:
        if selection is None:
            return ()
        installed = self.installed
        return tuple(installed[pack_id] for pack_id in selection.ids)

    def select(self, selection: PackSelection) -> PackSelection:
        installed = self.installed
        if missing := sorted(set(selection.ids) - set(installed)):
            raise Refusal(f"packs not installed for {self.engine!r}: {missing}")
        supplements = [pack_id for pack_id in selection.ids if pack_id != SRD_PACK]
        if len(supplements) > MAX_SUPPLEMENTS:
            raise Refusal(f"a game plays at most {MAX_SUPPLEMENTS} packs beside the SRD")
        defined: dict[Slug, Slug] = {}
        for pack_id in selection.ids:
            ids = set(installed[pack_id].defined_ids())
            if shared := sorted(ids & defined.keys()):
                raise Refusal(f"{pack_id!r} and {defined[shared[0]]!r} both define {shared[0]!r}")
            defined.update(dict.fromkeys(ids, pack_id))
        return selection

    def guidance(self, selection: PackSelection, *, opening: bool) -> str:
        blocks = [
            f"PACK: {pack.name}\n\n{sections(parts)}"
            for pack in self.chosen(selection)
            if (parts := pack.sections(opening=opening))
        ]
        return "\n\n".join(blocks)

    def rules_sections(self, selection: PackSelection | None) -> Sections:
        return tuple(
            (f"SPECIAL RULES: {pack.name}", pack.rules)
            for pack in self.chosen(selection)
            if pack.rules
        )


def read_packs[P: Pack](engine: EngineId, directory: Path, model: type[P]) -> PackSet[P]:
    installed = {
        content_id(path.stem): read_model(path, model) for path in sorted(directory.glob("*.json"))
    }
    return PackSet(engine, installed)
