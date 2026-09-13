import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue

from aidm.core.entities import EngineId, Frozen, Refusal, Slug, content_id
from aidm.core.io import read_model
from aidm.core.model import PackSelection

SRD_PACK: Slug = "srd"


class ScenePack(Frozen):
    name: str
    source: str
    license: str

    def defined_ids(self) -> tuple[Slug, ...]:
        """The option ids this pack defines; two selected packs may not share one."""
        return ()


@dataclass(frozen=True, slots=True)
class PackSet[K: ScenePack]:
    """Every pack installed for one engine, and what a game may select from them."""

    engine: EngineId
    installed: Mapping[Slug, K]

    def srd(self) -> K:
        return self.installed[SRD_PACK]

    def supplements(self) -> tuple[tuple[Slug, K], ...]:
        return tuple((key, pack) for key, pack in self.installed.items() if key != SRD_PACK)

    def require(self, selection: PackSelection | None) -> PackSelection:
        if selection is None:
            raise Refusal(f"a {self.engine!r} game needs a table set")
        return selection

    def chosen(self, selection: PackSelection | None) -> tuple[K, ...]:
        return tuple(self.installed[pack_id] for pack_id in self.require(selection).ids)

    def content(self, selection: PackSelection, dump: Callable[[K], JsonValue]) -> str:
        selected = {pack_id: dump(self.installed[pack_id]) for pack_id in selection.ids}
        return f"SELECTED PACK CONTENT\n{json.dumps(selected)}"

    def select(self, selection: PackSelection) -> PackSelection:
        if missing := sorted(set(selection.ids) - set(self.installed)):
            raise Refusal(f"packs not installed for {self.engine!r}: {missing}")
        if SRD_PACK not in selection.ids:
            raise Refusal(f"a {self.engine!r} game plays the {SRD_PACK!r} tables")
        defined: dict[Slug, Slug] = {}
        for pack_id in selection.ids:
            ids = set(self.installed[pack_id].defined_ids())
            if shared := sorted(ids & defined.keys()):
                raise Refusal(f"{pack_id!r} and {defined[shared[0]]!r} both define {shared[0]!r}")
            defined.update(dict.fromkeys(ids, pack_id))
        return selection


def read_packs[P: ScenePack](engine: EngineId, directory: Path, model: type[P]) -> PackSet[P]:
    packs = {
        content_id(path.stem): read_model(path, model) for path in sorted(directory.glob("*.json"))
    }
    if SRD_PACK not in packs:
        raise ValueError(f"the {engine!r} engine ships no {SRD_PACK!r} pack")
    return PackSet(engine, packs)
