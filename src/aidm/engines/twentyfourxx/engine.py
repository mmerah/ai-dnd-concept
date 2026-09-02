from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.engines.core import PLAYER_ID, Authoring, Engine, Transition, load_packs
from aidm.engines.hub import check_kind
from aidm.engines.scenes import SceneRun, arrival_brief
from aidm.engines.twentyfourxx.creation import (
    Pack,
    create_character,
    creation_steps,
    pack_options,
    preview_character,
)
from aidm.engines.twentyfourxx.tools import tools
from aidm.engines.twentyfourxx.views import master_sections, narrator_view, player_view
from aidm.engines.twentyfourxx.world import (
    TwentyfourxxCharacterFile,
    TwentyfourxxGame,
    TwentyfourxxScenarioFile,
    TwentyfourxxState,
    TwentyfourxxWorld,
    history,
    known,
    player_operator,
    player_over,
    record,
    way_open,
)
from aidm.engines.twentyfourxx.worldsmith import (
    SceneDraft,
    build_scenario,
    install_scene,
    render_opening,
    write_next,
)

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> TwentyfourxxState:
    """The player is added by code and never authored, so no scenario can claim their id."""
    if not isinstance(scenario, TwentyfourxxScenarioFile):
        raise ValueError("24XX received an incompatible scenario")
    if not isinstance(character, TwentyfourxxCharacterFile):
        raise ValueError("24XX received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    world = TwentyfourxxWorld(
        cast=canon.cast,
        player=player_operator(character),
        runs=[
            SceneRun(scene=canon.opening, present=list(canon.present), hidden=list(canon.hidden))
        ],
        source=canon.source,
        hub=canon.hub,
        board=canon.board,
    )
    return TwentyfourxxState(world=world)


def check_game(packs: Mapping[str, Pack], state: TwentyfourxxGame) -> None:
    if not state.packs:
        raise ValueError("a 24XX game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, state.payload.world.hub)


def build(user_packs: Path) -> Engine[TwentyfourxxGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("twentyfourxx"),
        title="24XX",
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
            answer=SceneDraft,
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
