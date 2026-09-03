from collections.abc import Sequence
from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug
from aidm.core.model import AnyCharacter
from aidm.core.tools import MasterTool
from aidm.core.views import Panel, PanelRow, Rows
from aidm.engines.core import Person
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.world import SceneCanon, new_world
from aidm.engines.twentyfourxx.creation import (
    Pack,
    create_character,
    creation_steps,
    guidance,
    preview_character,
)
from aidm.engines.twentyfourxx.tools import tools
from aidm.engines.twentyfourxx.views import gear_detail, master_sections
from aidm.engines.twentyfourxx.world import (
    Operator,
    TwentyfourxxCharacterFile,
    TwentyfourxxGame,
    TwentyfourxxScenarioFile,
    TwentyfourxxWorld,
    player_operator,
)

BOARD_GUIDANCE = (
    "The SRD's job-finding setup is the board's range, not a recipe: 1–2 nothing, owe somebody to "
    "get in on a job; 3–4 found a job, but something seems off; 5–6 a choice between two jobs."
)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
JOB_DONE_NOTE = (
    "The job {title} is closed and was completed. The SRD's after-a-job step applies: call "
    "`after_job` once, with the skill the player names, else the skill the job called on."
)


class TwentyfourxxEngine(SceneEngine[Person, Operator, TwentyfourxxGame, Pack]):
    id = EngineId("twentyfourxx")
    title = "24XX"
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenarioFile
    character = TwentyfourxxCharacterFile
    cast = Person
    pack = Pack
    hub_phrase = "the fixer and the regulars"
    finished_note = JOB_DONE_NOTE

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return tools(self.packs)

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return creation_steps(self.packs, picks)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return create_character(self.packs, name, brief, picks)

    def preview_character(self, character: AnyCharacter) -> Rows:
        return preview_character(character)

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        told = guidance(self.packs, picks)
        return "\n\n".join((told, BOARD_GUIDANCE)) if campaign else told

    def new_state(self, canon: SceneCanon[Person], character: AnyCharacter) -> TwentyfourxxWorld:
        return new_world(TwentyfourxxWorld, canon, player_operator(character))

    def master_sections(self, state: TwentyfourxxGame) -> Rows:
        return master_sections(state)

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        rows = tuple(
            PanelRow(label=item.name, detail=gear_detail(item))
            for item in self.world(state).player.items.values()
        )
        return (Panel(title="Gear", rows=rows),)
