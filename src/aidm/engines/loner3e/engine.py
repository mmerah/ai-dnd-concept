from functools import partial
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.engines.core import Authoring, Engine, Transition, load_packs
from aidm.engines.loner3e.creation import (
    Pack,
    create_character,
    creation_steps,
    pack_options,
    preview_character,
)
from aidm.engines.loner3e.tools import tools
from aidm.engines.loner3e.views import master_sections, narrator_view, player_view
from aidm.engines.loner3e.world import (
    Loner3eCharacterFile,
    Loner3eGame,
    Loner3eScenarioFile,
    Loner3eState,
    player_character,
)
from aidm.engines.loner3e.worldsmith import (
    build_scenario,
    install_scene,
    opening_draft,
    render_opening,
    write_next,
)
from aidm.engines.scenes import (
    arrival_brief,
    check_game,
    history,
    known,
    new_world,
    player_over,
    record,
    way_open,
)

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> Loner3eState:
    if not isinstance(scenario, Loner3eScenarioFile):
        raise ValueError("Loner 3E received an incompatible scenario")
    if not isinstance(character, Loner3eCharacterFile):
        raise ValueError("Loner 3E received an incompatible character")
    return Loner3eState(world=new_world(scenario.payload.world, player_character(character)))


def build(user_packs: Path) -> Engine[Loner3eGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("loner3e"),
        title="LONER 3E",
        instructions=(ENGINE_DIR / "rules.md").read_text(encoding=ENCODING),
        packs=pack_options(packs),
        game=Loner3eGame,
        scenario=Loner3eScenarioFile,
        character=Loner3eCharacterFile,
        tools=tools(packs),
        creation_steps=partial(creation_steps, packs),
        create_character=partial(create_character, packs),
        preview_character=preview_character,
        validate=partial(check_game, packs),
        new_game=new_game,
        known=known,
        record=record,
        history=history,
        master_sections=partial(master_sections, packs),
        narrator_view=narrator_view,
        player_view=player_view,
        over=player_over,
        authoring=Authoring(
            answer=opening_draft,
            prompt=partial(render_opening, packs),
            build=build_scenario,
        ),
        transition=Transition(
            ready=way_open,
            write=partial(write_next, packs),
            install=install_scene,
            arrival_brief=arrival_brief,
        ),
    )
