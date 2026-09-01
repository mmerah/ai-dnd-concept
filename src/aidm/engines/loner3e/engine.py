from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.engines.core import PLAYER_ID, Authoring, Engine, Transition, load_packs
from aidm.engines.hub import check_kind
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
    LonerWorld,
    history,
    known,
    player_character,
    player_over,
    record,
    settled,
)
from aidm.engines.loner3e.worldsmith import (
    SceneDraft,
    build_scenario,
    install_scene,
    render_opening,
    write_next,
)
from aidm.engines.scenes import SceneRun, arrival_brief

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> Loner3eState:
    """The player is added by code and never authored, so no scenario can claim their id."""
    if not isinstance(scenario, Loner3eScenarioFile):
        raise ValueError("Loner 3E received an incompatible scenario")
    if not isinstance(character, Loner3eCharacterFile):
        raise ValueError("Loner 3E received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    world = LonerWorld(
        cast={**canon.cast, PLAYER_ID: player_character(character)},
        runs=[
            SceneRun(
                scene=canon.opening,
                present=[PLAYER_ID, *canon.present],
                hidden=list(canon.hidden),
            )
        ],
        player_id=PLAYER_ID,
        source=canon.source,
    )
    return Loner3eState(world=world)


def check_packs(packs: Mapping[str, Pack], state: Loner3eGame) -> None:
    if not state.packs:
        raise ValueError("a Loner 3E game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, None)


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
        validate=partial(check_packs, packs),
        new_game=new_game,
        known=known,
        record=record,
        history=history,
        master_sections=partial(master_sections, packs),
        narrator_view=narrator_view,
        player_view=player_view,
        over=player_over,
        authoring=Authoring(
            answer=SceneDraft,
            prompt=partial(render_opening, packs),
            build=build_scenario,
        ),
        transition=Transition(
            ready=settled,
            write=partial(write_next, packs),
            install=install_scene,
            arrival_brief=arrival_brief,
        ),
    )
