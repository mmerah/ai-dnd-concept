from dataclasses import dataclass, field

from aidm.agents.stages import director_stage, shared_stages
from aidm.application.game import GameApplication
from aidm.config import Settings
from aidm.domain.base import EngineId, Slug
from aidm.engines import Engine, engine_for
from aidm.pipeline import TurnOptions
from aidm.store import FileSaves, FileTraces, load_character, load_scenario
from aidm_5e.factory import Dnd5eEngine
from aidm_story.factory import StoryEngine

from .advancement.fivee import Dnd5eAdvancementUi
from .advancement.story import StoryAdvancementUi
from .session_model import AdvancementUi


@dataclass(frozen=True, slots=True)
class Composition:
    config: Settings
    engines: dict[EngineId, Engine] = field(default_factory=dict)

    def engine(self, engine_id: EngineId) -> Engine:
        """Memoised: building the 5e engine compiles the whole content pack."""
        existing = self.engines.get(engine_id)
        if existing is None:
            existing = self.engines.setdefault(engine_id, engine_for(engine_id, self.config))
        return existing

    def advancement_ui(self, engine: Engine) -> AdvancementUi:
        match engine:
            case StoryEngine():
                return StoryAdvancementUi()
            case Dnd5eEngine():
                return Dnd5eAdvancementUi()

    def application(
        self,
        slug: str,
        scenario_id: Slug,
        character_id: Slug,
        engine_id: EngineId,
    ) -> GameApplication:
        config = self.config
        engine = self.engine(engine_id)
        return GameApplication(
            slug=slug,
            scenario=load_scenario(config.scenarios_dir, scenario_id, engine_id),
            character=load_character(config.characters_dir, character_id, engine_id),
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
    return Composition(config=config)
