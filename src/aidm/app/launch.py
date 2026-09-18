import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.io import FileStore, Library, decode, routed
from aidm.core.model import AnyGame, ScenarioMeta
from aidm.core.views import Look
from aidm.engines.engine import AnyEngine

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    id: Slug
    engine: EngineId
    label: str
    detail: str
    rules: str
    look: Look


@dataclass(frozen=True, slots=True)
class PackEntry:
    id: Slug
    engine: EngineId
    label: str
    rules: str
    written: bool
    tables: str  # `Pack.summary()`: what the pack holds, counted


@dataclass(frozen=True, slots=True)
class LaunchTarget:
    scenario_id: Slug
    character_id: Slug

    @property
    def slug(self) -> str:
        return f"{self.scenario_id}--{self.character_id}"


@dataclass(frozen=True, slots=True)
class SaveOption:
    target: LaunchTarget
    scenario_label: str
    character_label: str
    turn: int
    where: str
    rules: str


@dataclass(frozen=True, slots=True)
class LauncherCatalog:
    scenarios: tuple[CatalogEntry, ...]
    characters: tuple[CatalogEntry, ...]
    packs: tuple[PackEntry, ...]
    saves: tuple[SaveOption, ...]
    # Only entries whose stem equals a rendered `LaunchTarget.slug` are ever looked up by slug.
    unresumable: tuple[str, ...]

    def scenario(self, scenario_id: Slug) -> CatalogEntry:
        found = next((entry for entry in self.scenarios if entry.id == scenario_id), None)
        if found is None:
            raise Refusal(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.characters if entry.engine == engine)

    def target(self, scenario_id: Slug, character_id: Slug) -> LaunchTarget:
        engine = self.scenario(scenario_id).engine
        if character_id not in {entry.id for entry in self.characters_for(engine)}:
            raise Refusal(f"no character {character_id!r} is written for the {engine!r} rules")
        return LaunchTarget(scenario_id=scenario_id, character_id=character_id)

    @classmethod
    def read(
        cls, library: Library, store: FileStore, engines: Mapping[EngineId, AnyEngine]
    ) -> Self:
        scenario_models = {engine_id: engine.scenario for engine_id, engine in engines.items()}
        on_disk = dict(library.read_scenarios(scenario_models))
        scenarios = tuple(
            CatalogEntry(
                id=name,
                engine=scenario.engine,
                label=scenario.meta.title,
                detail=scenario.meta.premise,
                rules=engines[scenario.engine].title,
                look=engines[scenario.engine].look,
            )
            for name, scenario in on_disk.items()
        )
        metas = {name: scenario.meta for name, scenario in on_disk.items()}
        characters = tuple(
            CatalogEntry(
                id=name,
                engine=engine,
                label=header.sheet.name,
                detail=header.sheet.brief,
                rules=engines[engine].title,
                look=engines[engine].look,
            )
            for name, engine, header in library.read_characters(engines)
        )
        packs = tuple(
            PackEntry(
                id=pack_id,
                engine=engine.id,
                label=pack.name,
                rules=engine.title,
                written=written,
                tables=pack.summary(),
            )
            for engine in engines.values()
            for written, shelf in ((False, engine.packs.shipped), (True, engine.packs.written))
            for pack_id, pack in shelf.items()
        )
        titles = {(entry.id, entry.engine): entry.label for entry in characters}
        played_by = {entry.id: entry.engine for entry in scenarios}
        saves: list[SaveOption] = []
        unresumable: list[str] = []
        for slug in store.slugs():
            try:
                option = _save_option(slug, store, engines, titles, played_by, metas)
            # Skipped, never deleted: one save the app cannot resume must not hide the rest.
            except Refusal as unreadable:
                LOGGER.warning("skipping save %r: %s", slug, unreadable)
                unresumable.append(slug)
            else:
                if option is not None:
                    saves.append(option)
        return cls(
            scenarios=scenarios,
            characters=characters,
            packs=packs,
            saves=tuple(saves),
            unresumable=tuple(unresumable),
        )


def check_resumes(state: AnyGame, target: LaunchTarget, meta: ScenarioMeta) -> None:
    """The one rule for resuming a save: it is this game, and its scenario has not moved on."""
    if (state.scenario_id, state.character_id) != (target.scenario_id, target.character_id):
        raise Refusal(
            f"save is {state.scenario_id!r}/{state.character_id!r}, "
            f"selected is {target.scenario_id!r}/{target.character_id!r}"
        )
    state.scenario.check_drift(meta)


def _save_option(
    slug: str,
    store: FileStore,
    engines: Mapping[EngineId, AnyEngine],
    titles: Mapping[tuple[Slug, EngineId], str],
    played_by: Mapping[Slug, EngineId],
    metas: Mapping[Slug, ScenarioMeta],
) -> SaveOption | None:
    raw = store.read(slug)
    if raw is None:
        # Vanished between `slugs()` and `read`: listing it would hide a Start that works.
        return None
    engine = routed(decode(raw), engines)
    state = engine.restore(raw)
    title = titles.get((state.character_id, state.engine))
    if played_by.get(state.scenario_id) != state.engine or title is None:
        raise Refusal("its scenario or character is gone")
    target = LaunchTarget(scenario_id=state.scenario_id, character_id=state.character_id)
    if slug != target.slug:
        raise Refusal("filed under another name")
    state.scenario.check_drift(metas[state.scenario_id])
    return SaveOption(
        target=target,
        scenario_label=state.scenario.title,
        character_label=title,
        turn=len(state.exchanges()),
        where=state.log[-1].title,
        rules=engine.title,
    )
