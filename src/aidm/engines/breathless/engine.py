from collections.abc import Sequence
from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug
from aidm.core.model import AnyCharacter
from aidm.core.tools import MasterTool
from aidm.core.views import Panel, PanelRow, Rows
from aidm.engines.breathless.creation import (
    Pack,
    create_character,
    creation_steps,
    guidance,
    preview_character,
)
from aidm.engines.breathless.tools import tools
from aidm.engines.breathless.views import master_sections
from aidm.engines.breathless.world import (
    BreathlessCharacterFile,
    BreathlessGame,
    BreathlessScenarioFile,
    BreathlessState,
    Survivor,
    player_survivor,
)
from aidm.engines.core import Person
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.world import SceneCanon, new_world


class BreathlessEngine(SceneEngine[Person, Survivor, BreathlessGame, Pack]):
    id = EngineId("breathless")
    title = "BREATHLESS"
    art_style = (
        "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or lettering."
    )
    directory = Path(__file__).parent
    game = BreathlessGame
    scenario = BreathlessScenarioFile
    character = BreathlessCharacterFile
    cast = Person
    pack = Pack
    hub_phrase = "a camp or a safe house, whoever holds it and the regulars"

    def master_tools(self) -> tuple[MasterTool[BreathlessGame], ...]:
        return tools(self.packs)

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return creation_steps(self.packs, picks)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return create_character(self.packs, name, brief, picks)

    def preview_character(self, character: AnyCharacter) -> Rows:
        return preview_character(character)

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        return guidance(self.packs, picks)

    def new_state(self, canon: SceneCanon[Person], character: AnyCharacter) -> BreathlessState:
        return BreathlessState(world=new_world(canon, player_survivor(character)))

    def master_sections(self, state: BreathlessGame) -> Rows:
        return master_sections(state)

    def panels(self, state: BreathlessGame) -> tuple[Panel, ...]:
        player = self.world(state).player
        rows = [PanelRow(label=item.name, detail=f"d{item.die}") for item in player.items.values()]
        if player.med_kit:
            rows.append(PanelRow(label="Med kit", detail="held"))
        return (Panel(title="Backpack", rows=tuple(rows)),)
