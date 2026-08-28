from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from textwrap import shorten

from pydantic import ValidationError

from aidm.config import Settings
from aidm.content.io import FileStore, SaveHeader, read_characters, read_scenarios
from aidm.engines.registry import ENGINES, engine_class
from aidm.state.entities import EngineId, Frozen, Slug
from aidm.state.model import Game


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in ENGINES)


def as_engine_id(value: str) -> EngineId:
    """Narrow a routed string, so an unknown engine cannot reach a filename downstream."""
    return engine_class(EngineId(value)).id


class EngineOption(Frozen):
    id: EngineId
    badge: tuple[str, str]


class CatalogEntry(Frozen):
    id: Slug
    title: str
    subtitle: str
    engines: tuple[EngineId, ...]


class SaveOption(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug
    engine: EngineId
    scenario_title: str
    character_title: str
    turn: int
    problem: str | None = None

    @property
    def resumable(self) -> bool:
        return self.problem is None


class UnreadableSave(Frozen):
    slug: str
    problem: str


def _one[T: EngineOption | CatalogEntry](options: Iterable[T], wanted: str) -> T | None:
    return next((option for option in options if option.id == wanted), None)


class LauncherCatalog(Frozen):
    engines: tuple[EngineOption, ...]
    scenarios: tuple[CatalogEntry, ...]
    characters: tuple[CatalogEntry, ...]
    saves: tuple[SaveOption, ...]
    unreadable: tuple[UnreadableSave, ...] = ()

    def badge(self, engine: EngineId) -> tuple[str, str]:
        found = _one(self.engines, engine)
        if found is None:
            raise ValueError(f"unknown engine {engine!r}")
        return found.badge

    def scenario(self, scenario_id: Slug) -> CatalogEntry:
        found = _one(self.scenarios, scenario_id)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CatalogEntry, ...]:
        """A character is playable under any engine it ships an overlay for."""
        return tuple(option for option in self.characters if engine in option.engines)

    def save(self, slug: str) -> SaveOption:
        found = next((option for option in self.saves if option.slug == slug), None)
        if found is None:
            raise ValueError(f"unknown save {slug!r}")
        return found


class LaunchTarget(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_id}/{self.character_id}"

    def __str__(self) -> str:
        return f"{self.scenario_id}/{self.character_id}"


@dataclass(slots=True)
class LauncherController:
    catalog: LauncherCatalog
    selected_scenario: Slug | None = None
    selected_character: Slug | None = None

    def __post_init__(self) -> None:
        if self.selected_scenario is None and self.catalog.scenarios:
            self.selected_scenario = self.catalog.scenarios[0].id
        self._select_character()

    @property
    def selected_engine(self) -> EngineId | None:
        """A scenario names its one engine, so nothing else chooses it."""
        if self.selected_scenario is None:
            return None
        return self.catalog.scenario(self.selected_scenario).engines[0]

    def choose_scenario(self, scenario_id: Slug) -> None:
        self.catalog.scenario(scenario_id)
        self.selected_scenario = scenario_id
        self._select_character()

    def choose_character(self, character_id: Slug) -> None:
        if character_id not in {option.id for option in self.compatible_characters()}:
            raise ValueError(
                f"character {character_id!r} has no {self.selected_engine!r} rules written for it"
            )
        self.selected_character = character_id

    def compatible_characters(self) -> tuple[CatalogEntry, ...]:
        if self.selected_engine is None:
            return ()
        return self.catalog.characters_for(self.selected_engine)

    def new_game(self) -> LaunchTarget:
        scenario, character = self.selected_scenario, self.selected_character
        if scenario is None or character is None:
            raise ValueError("choose a scenario and a character written for it")
        return LaunchTarget(
            slug=f"{scenario}--{character}",
            scenario_id=scenario,
            character_id=character,
        )

    def resume(self, slug: str) -> LaunchTarget:
        saved = self.catalog.save(slug)
        if saved.problem is not None:
            raise ValueError(saved.problem)
        return LaunchTarget(
            slug=saved.slug,
            scenario_id=saved.scenario_id,
            character_id=saved.character_id,
        )

    def _select_character(self) -> None:
        compatible = self.compatible_characters()
        if self.selected_character not in {option.id for option in compatible}:
            self.selected_character = compatible[0].id if compatible else None


def load_catalog(settings: Settings) -> LauncherCatalog:
    engine_options = tuple(EngineOption(id=engine.id, badge=engine.badge) for engine in ENGINES)
    ids = engine_ids()
    scenarios = tuple(
        CatalogEntry(
            id=name,
            title=scenario.meta.title,
            subtitle=scenario.meta.premise,
            engines=(scenario.engine,),
        )
        for name, scenario in read_scenarios(settings.scenarios_dir, ids)
    )
    characters = tuple(
        CatalogEntry(id=name, title=profile.name, subtitle=profile.brief, engines=engines)
        for name, profile, engines in read_characters(settings.characters_dir, ids)
    )
    files = FileStore(settings.saves_dir)
    saves: list[SaveOption] = []
    unreadable: list[UnreadableSave] = []
    for slug in files.slugs():
        try:
            raw = files.load(slug)
            if raw is None:
                continue
            saved = SaveHeader.model_validate_json(raw)
            # An installed engine's save must still parse whole, or /game would crash on resume.
            if saved.engine in ids:
                _ = Game.model_validate_json(raw)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=_short_reason(error)))
            continue
        saves.append(_save_option(slug, saved, scenarios, characters))
    return LauncherCatalog(
        engines=engine_options,
        scenarios=scenarios,
        characters=characters,
        saves=tuple(saves),
        unreadable=tuple(unreadable),
    )


def _save_option(
    slug: str,
    saved: SaveHeader,
    scenarios: Sequence[CatalogEntry],
    characters: Sequence[CatalogEntry],
) -> SaveOption:
    character = _one(characters, saved.character_id)
    return SaveOption(
        slug=slug,
        scenario_id=saved.scenario_id,
        character_id=saved.character_id,
        engine=saved.engine,
        scenario_title=saved.scenario.title,
        character_title=saved.character_id if character is None else character.title,
        turn=saved.turn,
        problem=_save_refusal(saved, scenarios, characters),
    )


def _save_refusal(
    saved: SaveHeader,
    scenarios: Sequence[CatalogEntry],
    characters: Sequence[CatalogEntry],
) -> str | None:
    """A save names its own origin, so the only question left is whether that origin still plays."""
    for purpose, wanted, offered in (
        ("scenario", saved.scenario_id, scenarios),
        ("character", saved.character_id, characters),
    ):
        found = _one(offered, wanted)
        if found is None:
            return f"{purpose} {wanted!r} is gone"
        if saved.engine not in found.engines:
            return f"{purpose} {wanted!r} no longer offers the {saved.engine!r} engine"
    return None


SHORT_REASON_WIDTH = 200


def _short_reason(error: Exception) -> str:
    """A rejected save shows a one-line reason; a full validation traceback is unreadable."""
    return shorten(str(error), width=SHORT_REASON_WIDTH, placeholder=" ...")
