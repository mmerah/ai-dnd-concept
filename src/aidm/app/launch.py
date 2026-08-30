import logging
from collections.abc import Mapping

from aidm.config import Settings
from aidm.content.io import FileStore, read_characters, read_scenarios
from aidm.engines.core import Engine
from aidm.kernel.envelope import SaveEnvelope
from aidm.state.entities import EngineId, Frozen, Slug

LOGGER = logging.getLogger(__name__)


class CatalogEntry(Frozen):
    id: Slug
    title: str
    subtitle: str
    engines: tuple[EngineId, ...]


class LaunchTarget(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_id}/{self.character_id}"


class SaveOption(Frozen):
    target: LaunchTarget
    engine: EngineId
    scenario_title: str
    character_title: str
    turn: int


class LauncherCatalog(Frozen):
    engines: tuple[EngineId, ...]
    scenarios: tuple[CatalogEntry, ...]
    characters: tuple[CatalogEntry, ...]
    saves: tuple[SaveOption, ...]

    def scenario(self, scenario_id: Slug) -> CatalogEntry:
        found = next((entry for entry in self.scenarios if entry.id == scenario_id), None)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.characters if engine in entry.engines)


def launch_target(catalog: LauncherCatalog, scenario_id: Slug, character_id: Slug) -> LaunchTarget:
    engine = catalog.scenario(scenario_id).engines[0]
    if character_id not in {entry.id for entry in catalog.characters_for(engine)}:
        raise ValueError(f"character {character_id!r} has no {engine!r} rules written for it")
    return LaunchTarget(
        slug=f"{scenario_id}--{character_id}",
        scenario_id=scenario_id,
        character_id=character_id,
    )


def load_catalog(settings: Settings, engines: Mapping[EngineId, Engine]) -> LauncherCatalog:
    ids = tuple(engines)
    scenarios = tuple(
        CatalogEntry(
            id=name,
            title=scenario.meta.title,
            subtitle=scenario.meta.premise,
            engines=(scenario.engine,),
        )
        for name, scenario in read_scenarios(settings.scenarios_dir, engines)
    )
    characters = tuple(
        CatalogEntry(id=name, title=character.name, subtitle=character.brief, engines=written)
        for name, character, written in read_characters(settings.characters_dir, engines)
    )
    titles = {entry.id: entry.title for entry in characters}
    scenario_ids = {entry.id for entry in scenarios}
    files = FileStore(settings.saves_dir)
    saves: list[SaveOption] = []
    for slug in files.slugs():
        raw = files.load(slug)
        if raw is None:
            continue
        try:
            game = SaveEnvelope.model_validate_json(raw)
        except ValueError as unreadable:
            # Skip rather than raise: one save the app could not resume must not hide the rest.
            LOGGER.warning("skipping save %r: %s", slug, unreadable)
            continue
        if (
            game.engine not in ids
            or game.scenario_id not in scenario_ids
            or game.character_id not in titles
        ):
            LOGGER.warning("skipping save %r: its engine, scenario or character is gone", slug)
            continue
        saves.append(
            SaveOption(
                target=LaunchTarget(
                    slug=slug, scenario_id=game.scenario_id, character_id=game.character_id
                ),
                engine=game.engine,
                scenario_title=game.scenario.title,
                character_title=titles[game.character_id],
                turn=game.turn,
            )
        )
    return LauncherCatalog(
        engines=ids, scenarios=scenarios, characters=characters, saves=tuple(saves)
    )
