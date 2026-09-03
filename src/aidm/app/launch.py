import logging
from collections.abc import Mapping
from dataclasses import dataclass

from aidm.config import Settings
from aidm.core.entities import EngineId, Refusal, Slug, parse
from aidm.core.io import FileStore, decode, read_characters, read_scenarios
from aidm.core.model import EngineHeader, ScenarioKind
from aidm.engines.seam import AnyEngine

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    id: Slug
    engine: EngineId
    title: str
    subtitle: str
    rules: str
    kind: ScenarioKind = "one-shot"


@dataclass(frozen=True, slots=True)
class LaunchTarget:
    scenario_id: Slug
    character_id: Slug

    @property
    def slug(self) -> str:
        return f"{self.scenario_id}--{self.character_id}"

    @property
    def path(self) -> str:
        return f"/game/{self.scenario_id}/{self.character_id}"


@dataclass(frozen=True, slots=True)
class SaveOption:
    target: LaunchTarget
    scenario_title: str
    character_title: str
    turn: int
    kind: ScenarioKind
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


def launch_target(catalog: LauncherCatalog, scenario_id: Slug, character_id: Slug) -> LaunchTarget:
    engine = catalog.scenario(scenario_id).engine
    if character_id not in {entry.id for entry in catalog.characters_for(engine)}:
        raise Refusal(f"no character {character_id!r} is written for the {engine!r} rules")
    return LaunchTarget(scenario_id=scenario_id, character_id=character_id)


def read_catalog(settings: Settings, engines: Mapping[EngineId, AnyEngine]) -> LauncherCatalog:
    scenario_models = {engine_id: engine.scenario for engine_id, engine in engines.items()}
    character_models = {engine_id: engine.character for engine_id, engine in engines.items()}
    scenarios = tuple(
        CatalogEntry(
            id=name,
            engine=scenario.engine,
            title=scenario.meta.title,
            subtitle=scenario.meta.premise,
            rules=engines[scenario.engine].title,
            kind=scenario.meta.kind,
        )
        for name, scenario in read_scenarios(settings.scenarios_dir, scenario_models)
    )
    characters = tuple(
        CatalogEntry(
            id=name,
            engine=engine,
            title=character.name,
            subtitle=character.brief,
            rules=engines[engine].title,
        )
        for name, engine, character in read_characters(settings.characters_dir, character_models)
    )
    titles = {(entry.id, entry.engine): entry.title for entry in characters}
    played_by = {entry.id: entry.engine for entry in scenarios}
    files = FileStore(settings.saves_dir)
    saves: list[SaveOption] = []
    for slug in files.slugs():
        try:
            raw = files.load(slug)
            if raw is None:
                continue
            header = parse(EngineHeader, decode(raw))
            engine = engines.get(header.engine)
            if engine is None:
                LOGGER.warning("skipping save %r: its engine %r is gone", slug, header.engine)
                continue
            state = engine.restore(raw)
        except Refusal as unreadable:
            # Skip rather than raise: one save the app could not resume must not hide the rest.
            LOGGER.warning("skipping save %r: %s", slug, unreadable)
            continue
        title = titles.get((state.character_id, state.engine))
        if played_by.get(state.scenario_id) != state.engine or title is None:
            LOGGER.warning("skipping save %r: its scenario or character is gone", slug)
            continue
        target = LaunchTarget(scenario_id=state.scenario_id, character_id=state.character_id)
        if slug != target.slug:
            LOGGER.warning("skipping save %r: filed under another name", slug)
            continue
        scenes = engine.scenes(state)
        saves.append(
            SaveOption(
                target=target,
                scenario_title=state.scenario.title,
                character_title=title,
                turn=state.turn,
                kind=state.scenario.kind,
                where=scenes[-1].title if scenes else "",
                rules=engine.title,
            )
        )
    return LauncherCatalog(scenarios=scenarios, characters=characters, saves=tuple(saves))
