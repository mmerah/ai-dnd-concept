from collections.abc import Mapping
from copy import deepcopy
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
from aidm.engines.breathless.views import master_sections, narrator_view, player_view
from aidm.engines.breathless.world import (
    BreathlessCharacterFile,
    BreathlessGame,
    BreathlessScenarioFile,
    BreathlessState,
    BreathlessWorld,
    history,
    known,
    player_over,
    player_survivor,
    record,
    settled,
)
from aidm.engines.breathless.worldsmith import (
    SceneDraft,
    build_scenario,
    install_scene,
    render_opening,
    write_next,
)
from aidm.engines.core import PLAYER_ID, Authoring, Engine, Transition, load_packs
from aidm.engines.hub import check_kind
from aidm.engines.scenes import SceneRun, arrival_brief

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> BreathlessState:
    """The player is added by code and never authored, so no scenario can claim their id."""
    if not isinstance(scenario, BreathlessScenarioFile):
        raise ValueError("Breathless received an incompatible scenario")
    if not isinstance(character, BreathlessCharacterFile):
        raise ValueError("Breathless received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    if PLAYER_ID in canon.cast:
        raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
    world = BreathlessWorld(
        cast=canon.cast,
        player=player_survivor(character),
        runs=[
            SceneRun(scene=canon.opening, present=list(canon.present), hidden=list(canon.hidden))
        ],
        source=canon.source,
    )
    return BreathlessState(world=world)


def check_packs(packs: Mapping[str, Pack], state: BreathlessGame) -> None:
    if not state.packs:
        raise ValueError("a Breathless game needs at least one table set")
    if missing := sorted(set(state.packs) - set(packs)):
        raise ValueError(f"the game names packs not installed: {missing}")
    check_kind(state.scenario.kind, None)


def build(user_packs: Path) -> Engine[BreathlessGame]:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("breathless"),
        title="BREATHLESS",
        instructions=(ENGINE_DIR / "rules.md").read_text(encoding=ENCODING),
        packs=pack_options(packs),
        game=BreathlessGame,
        scenario=BreathlessScenarioFile,
        character=BreathlessCharacterFile,
        tools=tools(packs),
        creation_steps=partial(creation_steps, packs),
        create_character=partial(create_character, packs),
        preview_character=preview_character,
        validate=partial(check_packs, packs),
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
            ready=settled,
            write=partial(write_next, packs),
            install=install_scene,
            arrival_brief=arrival_brief,
        ),
    )
