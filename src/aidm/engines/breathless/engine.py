from functools import partial
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.engines.breathless.creation import (
    Pack,
    create_character,
    creation_steps,
    pack_options,
    preview_character,
)
from aidm.engines.breathless.tools import tools
from aidm.engines.breathless.views import master_sections, player_view
from aidm.engines.breathless.world import (
    BreathlessCharacterFile,
    BreathlessGame,
    BreathlessScenarioFile,
    BreathlessState,
    player_survivor,
)
from aidm.engines.breathless.worldsmith import install_scene, render_opening, write_next
from aidm.engines.core import Authoring, Engine, Person, Transition, load_packs
from aidm.engines.scenes import (
    arrival_brief,
    build_scenario,
    check_game,
    history,
    known,
    narrator_view,
    new_world,
    opening_draft,
    player_over,
    record,
    way_open,
)

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> BreathlessState:
    if not isinstance(scenario, BreathlessScenarioFile):
        raise ValueError("Breathless received an incompatible scenario")
    if not isinstance(character, BreathlessCharacterFile):
        raise ValueError("Breathless received an incompatible character")
    return BreathlessState(world=new_world(scenario.payload.world, player_survivor(character)))


def build(user_packs: Path) -> Engine[BreathlessGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("breathless"),
        title="BREATHLESS",
        art_style=(
            "Grim survival-horror illustration: dim, desaturated, wet surfaces, "
            "no text or lettering."
        ),
        instructions=(ENGINE_DIR / "rules.md").read_text(encoding=ENCODING),
        packs=pack_options(packs),
        game=BreathlessGame,
        scenario=BreathlessScenarioFile,
        character=BreathlessCharacterFile,
        tools=tools(packs),
        creation_steps=partial(creation_steps, packs),
        create_character=partial(create_character, packs),
        preview_character=preview_character,
        validate=partial(check_game, packs),
        new_game=new_game,
        known=known,
        record=record,
        history=history,
        master_sections=master_sections,
        narrator_view=narrator_view,
        player_view=player_view,
        over=player_over,
        authoring=Authoring(
            answer=partial(opening_draft, Person),
            prompt=partial(render_opening, packs),
            build=partial(build_scenario, BreathlessScenarioFile, EngineId("breathless"), Person),
        ),
        transition=Transition(
            ready=way_open,
            write=partial(write_next, packs),
            install=install_scene,
            arrival_brief=arrival_brief,
        ),
    )
