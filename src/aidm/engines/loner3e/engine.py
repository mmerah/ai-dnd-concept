from collections.abc import Sequence
from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug
from aidm.core.facts import Fact
from aidm.core.model import AnyCharacter
from aidm.core.tools import MasterTool
from aidm.core.views import Rows
from aidm.engines.loner3e.creation import (
    Pack,
    create_character,
    creation_steps,
    guidance,
    preview_character,
)
from aidm.engines.loner3e.tools import close_conflicts, tools
from aidm.engines.loner3e.views import master_sections
from aidm.engines.loner3e.world import (
    Loner3eCharacterFile,
    Loner3eGame,
    Loner3eScenario,
    Loner3eSheet,
    Loner3eWorld,
    player_character,
)
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.world import SceneCanon, new_world

# Read by the next turn, which is usually the next offer click: the note must stand on its own.
GROWTH_NOTE = (
    "The job {title} is closed and was completed. The adventure's end applies: ask what the "
    "character learned if the player has not said, then write it once with `change_tags` and "
    "`drive`."
)


class Loner3eEngine(SceneEngine[Loner3eSheet, Loner3eSheet, Loner3eGame, Pack]):
    id = EngineId("loner3e")
    title = "LONER 3E"
    art_style = "Painterly illustration, muted colours, no text or lettering."
    directory = Path(__file__).parent
    game = Loner3eGame
    scenario = Loner3eScenario
    character = Loner3eCharacterFile
    cast = Loner3eSheet
    pack = Pack
    hub_phrase = "a guild hall or a ship, whoever keeps it and the regulars"
    finished_note = GROWTH_NOTE

    def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
        return tools(self.packs)

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return creation_steps(self.packs, picks)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return create_character(self.packs, name, brief, picks)

    def preview_character(self, character: AnyCharacter) -> Rows:
        return preview_character(character)

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        return guidance(self.packs, picks)

    def new_state(self, canon: SceneCanon[Loner3eSheet], character: AnyCharacter) -> Loner3eWorld:
        return new_world(Loner3eWorld, canon, player_character(character))

    def master_sections(self, state: Loner3eGame) -> Rows:
        return master_sections(self.packs, state)

    def leaving(self, state: Loner3eGame) -> tuple[Fact, ...]:
        return close_conflicts(state)
