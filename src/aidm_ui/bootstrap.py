from dataclasses import dataclass, field

from aidm.agents.stages import director_stage, shared_stages
from aidm.application.game import GameApplication
from aidm.config import Settings
from aidm.domain.base import EngineId, Slug
from aidm.engines import engine_for
from aidm.pipeline import TurnOptions
from aidm.store import FileSaves, FileTraces, load_character, load_scenario

from .advancement.fivee import Dnd5eAdvancementUi
from .advancement.story import StoryAdvancementUi
from .session_model import AdvancementUi


@dataclass(frozen=True, slots=True)
class Composition:
    config: Settings
    _advancement_uis: dict[EngineId, AdvancementUi] = field(
        default_factory=dict, init=False, repr=False
    )

    def advancement_ui(self, engine_id: EngineId) -> AdvancementUi:
        """Memoised: building the 5e engine compiles the whole content pack."""
        existing = self._advancement_uis.get(engine_id)
        if existing is None:
            existing = self._build_advancement_ui(engine_id)
            if existing.engine.id != engine_id:
                raise ValueError(
                    f"{engine_id!r} advancement UI is bound to {existing.engine.id!r}"
                )
            self._advancement_uis[engine_id] = existing
        return existing

    def _build_advancement_ui(self, engine_id: EngineId) -> AdvancementUi:
        match engine_id:
            case "story":
                engine = engine_for("story", self.config)
                return StoryAdvancementUi(engine)
            case "dnd5e":
                engine = engine_for("dnd5e", self.config)
                return Dnd5eAdvancementUi(engine)

    def application(
        self,
        slug: str,
        scenario_id: Slug,
        character_id: Slug,
        engine_id: EngineId,
    ) -> GameApplication:
        config = self.config
        engine = self.advancement_ui(engine_id).engine
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
