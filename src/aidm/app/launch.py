import logging
from collections.abc import Mapping

from aidm.config import Settings
from aidm.core.entities import EngineId, Frozen, Slug
from aidm.core.io import FileStore, decoded, read_characters, read_scenarios
from aidm.core.model import SaveHeader, ScenarioKind
from aidm.engines.core import AnyEngine

LOGGER = logging.getLogger(__name__)


class CatalogEntry(Frozen):
    id: Slug
    engine: EngineId
    title: str
    subtitle: str
    kind: ScenarioKind = "one-shot"


class LaunchTarget(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_id}/{self.character_id}"


class SaveOption(Frozen):
    target: LaunchTarget
    scenario_title: str
    character_title: str
    turn: int
    kind: ScenarioKind


class LauncherCatalog(Frozen):
    scenarios: tuple[CatalogEntry, ...]
    characters: tuple[CatalogEntry, ...]
    saves: tuple[SaveOption, ...]

    def scenario(self, scenario_id: Slug) -> CatalogEntry:
        found = next((entry for entry in self.scenarios if entry.id == scenario_id), None)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.characters if entry.engine == engine)


def launch_target(catalog: LauncherCatalog, scenario_id: Slug, character_id: Slug) -> LaunchTarget:
    engine = catalog.scenario(scenario_id).engine
    if character_id not in {entry.id for entry in catalog.characters_for(engine)}:
        raise ValueError(f"no character {character_id!r} is written for the {engine!r} rules")
    return LaunchTarget(
        slug=f"{scenario_id}--{character_id}",
        scenario_id=scenario_id,
        character_id=character_id,
    )


def load_catalog(settings: Settings, engines: Mapping[EngineId, AnyEngine]) -> LauncherCatalog:
    scenario_models = {engine_id: engine.scenario for engine_id, engine in engines.items()}
    character_models = {engine_id: engine.character for engine_id, engine in engines.items()}
    scenarios = tuple(
        CatalogEntry(
            id=name,
            engine=scenario.engine,
            title=scenario.meta.title,
            subtitle=scenario.meta.premise,
            kind=scenario.meta.kind,
        )
        for name, scenario in read_scenarios(settings.scenarios_dir, scenario_models)
    )
    characters = tuple(
        CatalogEntry(id=name, engine=engine, title=character.name, subtitle=character.brief)
        for name, engine, character in read_characters(settings.characters_dir, character_models)
    )
    titles = {(entry.id, entry.engine): entry.title for entry in characters}
    played_by = {entry.id: entry.engine for entry in scenarios}
    files = FileStore(settings.saves_dir)
    saves: list[SaveOption] = []
    for slug in files.slugs():
        raw = files.load(slug)
        if raw is None:
            continue
        try:
            game = SaveHeader.model_validate(decoded(raw))
        except ValueError as unreadable:
            # Skip rather than raise: one save the app could not resume must not hide the rest.
            LOGGER.warning("skipping save %r: %s", slug, unreadable)
            continue
        title = titles.get((game.character_id, game.engine))
        if played_by.get(game.scenario_id) != game.engine or title is None:
            LOGGER.warning("skipping save %r: its engine, scenario or character is gone", slug)
            continue
        saves.append(
            SaveOption(
                target=LaunchTarget(
                    slug=slug, scenario_id=game.scenario_id, character_id=game.character_id
                ),
                scenario_title=game.scenario.title,
                character_title=title,
                turn=game.turn,
                kind=game.scenario.kind,
            )
        )
    return LauncherCatalog(scenarios=scenarios, characters=characters, saves=tuple(saves))
