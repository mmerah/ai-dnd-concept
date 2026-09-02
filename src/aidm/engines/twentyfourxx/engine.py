from functools import partial
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
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
from aidm.engines.twentyfourxx.creation import (
    Pack,
    create_character,
    creation_steps,
    pack_options,
    preview_character,
)
from aidm.engines.twentyfourxx.tools import tools
from aidm.engines.twentyfourxx.views import master_sections, player_view
from aidm.engines.twentyfourxx.world import (
    TwentyfourxxCharacterFile,
    TwentyfourxxGame,
    TwentyfourxxScenarioFile,
    TwentyfourxxState,
    player_operator,
)
from aidm.engines.twentyfourxx.worldsmith import install_scene, render_opening, write_next

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> TwentyfourxxState:
    if not isinstance(scenario, TwentyfourxxScenarioFile):
        raise ValueError("24XX received an incompatible scenario")
    if not isinstance(character, TwentyfourxxCharacterFile):
        raise ValueError("24XX received an incompatible character")
    return TwentyfourxxState(world=new_world(scenario.payload.world, player_operator(character)))


def build(user_packs: Path) -> Engine[TwentyfourxxGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("twentyfourxx"),
        title="24XX",
        art_style=(
            "Clean science-fiction illustration: hard light, neon on steel, lived-in "
            "technology, no text or lettering."
        ),
        instructions=(ENGINE_DIR / "rules.md").read_text(encoding=ENCODING),
        packs=pack_options(packs),
        game=TwentyfourxxGame,
        scenario=TwentyfourxxScenarioFile,
        character=TwentyfourxxCharacterFile,
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
            build=partial(
                build_scenario, TwentyfourxxScenarioFile, EngineId("twentyfourxx"), Person
            ),
        ),
        transition=Transition(
            ready=way_open,
            write=partial(write_next, packs),
            install=install_scene,
            arrival_brief=arrival_brief,
        ),
    )
