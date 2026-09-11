import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.io import FileStore, Library, decode, routed
from aidm.core.model import AnyScenario
from aidm.core.views import Look
from aidm.engines.seam import AnyEngine

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
    saves: tuple[SaveOption, ...]

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
        cls,
        library: Library,
        store: FileStore,
        engines: Mapping[EngineId, AnyEngine],
        scenario_models: Mapping[EngineId, type[AnyScenario]],
    ) -> Self:
        scenarios = tuple(
            CatalogEntry(
                id=name,
                engine=scenario.engine,
                label=scenario.meta.title,
                detail=scenario.meta.premise,
                rules=engines[scenario.engine].title,
                look=engines[scenario.engine].look,
            )
            for name, scenario in library.read_scenarios(scenario_models)
        )
        characters = tuple(
            CatalogEntry(
                id=name,
                engine=engine,
                label=header.payload.name,
                detail=header.payload.brief,
                rules=engines[engine].title,
                look=engines[engine].look,
            )
            for name, engine, header in library.read_characters(engines)
        )
        titles = {(entry.id, entry.engine): entry.label for entry in characters}
        played_by = {entry.id: entry.engine for entry in scenarios}
        saves = tuple(
            option
            for slug in store.slugs()
            if (option := _save_option(slug, store, engines, titles, played_by)) is not None
        )
        return cls(scenarios=scenarios, characters=characters, saves=saves)


def _save_option(
    slug: str,
    store: FileStore,
    engines: Mapping[EngineId, AnyEngine],
    titles: Mapping[tuple[Slug, EngineId], str],
    played_by: Mapping[Slug, EngineId],
) -> SaveOption | None:
    try:
        raw = store.read(slug)
        if raw is None:
            return None
        value = decode(raw)
        engine = routed(value, engines)
        state = engine.restore(value)
    except Refusal as unreadable:
        # Skip rather than raise: one save the app could not resume must not hide the rest.
        LOGGER.warning("skipping save %r: %s", slug, unreadable)
        return None
    title = titles.get((state.character_id, state.engine))
    if played_by.get(state.scenario_id) != state.engine or title is None:
        LOGGER.warning("skipping save %r: its scenario or character is gone", slug)
        return None
    target = LaunchTarget(scenario_id=state.scenario_id, character_id=state.character_id)
    if slug != target.slug:
        LOGGER.warning("skipping save %r: filed under another name", slug)
        return None
    return SaveOption(
        target=target,
        scenario_label=state.scenario.title,
        character_label=title,
        turn=len(state.exchanges()),
        where=state.log[-1].title,
        rules=engine.title,
    )
