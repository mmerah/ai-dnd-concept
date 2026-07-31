from dataclasses import dataclass

from aidm.agents.stages import director_stage, shared_stages
from aidm.application.game import GameApplication
from aidm.config import Settings
from aidm.domain.engine import EngineRef, EngineStamp
from aidm.engine_api.contracts import RulesEngine
from aidm.engine_api.registry import EngineRegistry
from aidm.pipeline import TurnOptions
from aidm.store import (
    FileSaves,
    FileTraces,
    read_named_character,
    read_named_scenario,
)
from aidm_5e.config import Dnd5eConfig
from aidm_5e.constants import DESCRIPTOR as DND5E_DESCRIPTOR
from aidm_5e.facade import Dnd5eEngine
from aidm_5e.factory import create_dnd5e_engine
from aidm_story.constants import DESCRIPTOR as STORY_DESCRIPTOR
from aidm_story.engine import StoryEngine, create_story_engine

from .advancement.fivee import Dnd5eAdvancementUi
from .advancement.story import StoryAdvancementUi
from .session_model import AdvancementUi


@dataclass(frozen=True, slots=True)
class Composition:
    config: Settings
    engines: EngineRegistry

    def installed_stamp(self, requested: EngineRef) -> EngineStamp:
        return self.engines.require(requested).stamp

    def advancement_ui(self, engine: RulesEngine) -> AdvancementUi:
        if isinstance(engine, StoryEngine):
            return StoryAdvancementUi()
        if isinstance(engine, Dnd5eEngine):
            return Dnd5eAdvancementUi()
        raise TypeError(f"no advancement UI for {type(engine).__name__}")

    def application(
        self,
        slug: str,
        scenario_name: str,
        character_name: str,
    ) -> GameApplication:
        config = self.config
        scenario = read_named_scenario(config.scenarios_dir, scenario_name)
        character = read_named_character(config.characters_dir, character_name)
        engine = self.engines.require(scenario.engine)
        return GameApplication(
            slug=slug,
            scenario=scenario,
            character=character,
            engine=engine,
            director=director_stage(engine, config),
            stages=shared_stages(config),
            saves=FileSaves(config.saves_dir),
            traces=FileTraces(config.saves_dir),
            options=TurnOptions(
                history_window=config.history_window,
                max_growth=config.max_growth,
            ),
        )


def create_composition(config: Settings) -> Composition:
    engines = EngineRegistry()
    engines.register(STORY_DESCRIPTOR, create_story_engine)
    dnd5e = Dnd5eConfig.model_validate({})
    engines.register(DND5E_DESCRIPTOR, lambda: create_dnd5e_engine(dnd5e.pack_paths))
    return Composition(config=config, engines=engines)
