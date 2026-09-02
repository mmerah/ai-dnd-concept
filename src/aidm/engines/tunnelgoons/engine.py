from copy import deepcopy
from pathlib import Path

from aidm.core.entities import EngineId
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario
from aidm.engines.core import Authoring, Engine, Transition
from aidm.engines.hub import check_kind
from aidm.engines.tunnelgoons.creation import create_character, creation_steps, preview_character
from aidm.engines.tunnelgoons.tools import tools
from aidm.engines.tunnelgoons.views import master_sections, narrator_view, player_view
from aidm.engines.tunnelgoons.world import (
    TunnelGoonsCharacterFile,
    TunnelGoonsGame,
    TunnelGoonsScenarioFile,
    TunnelGoonsState,
    TunnelWorld,
    Visit,
    history,
    known,
    player_goon,
    player_over,
    record,
    starting_items,
)
from aidm.engines.tunnelgoons.worldsmith import (
    build_scenario,
    install_extension,
    opening_draft,
    render_map,
    way_open,
    write_extension,
)

ENGINE_DIR = Path(__file__).parent


def new_game(scenario: AnyScenario, character: AnyCharacter) -> TunnelGoonsState:
    if not isinstance(scenario, TunnelGoonsScenarioFile):
        raise ValueError("Tunnel Goons received an incompatible scenario")
    if not isinstance(character, TunnelGoonsCharacterFile):
        raise ValueError("Tunnel Goons received an incompatible character")
    canon = deepcopy(scenario.payload.world)
    player = player_goon(character, canon.start)
    taken = (*canon.places, *canon.npcs, *canon.items)
    items = starting_items(character, taken)
    world = TunnelWorld(
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items={**canon.items, **{item.id: item for item in items}},
        player=player,
        visits=[Visit(place=canon.start)],
        source=canon.source,
        hub=canon.hub,
        board=canon.board,
    )
    return TunnelGoonsState(world=world)


def validate(state: TunnelGoonsGame) -> None:
    if state.packs:
        raise ValueError("Tunnel Goons has no table sets")
    check_kind(state.scenario.kind, state.payload.world.hub)


def build() -> Engine[TunnelGoonsGame]:
    return Engine(
        id=EngineId("tunnelgoons"),
        title="TUNNEL GOONS",
        art_style=(
            "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
        ),
        instructions=(ENGINE_DIR / "rules.md").read_text(encoding=ENCODING),
        packs=(),
        game=TunnelGoonsGame,
        scenario=TunnelGoonsScenarioFile,
        character=TunnelGoonsCharacterFile,
        tools=tools(),
        creation_steps=creation_steps,
        create_character=create_character,
        preview_character=preview_character,
        validate=validate,
        new_game=new_game,
        known=known,
        record=record,
        history=history,
        master_sections=master_sections,
        narrator_view=narrator_view,
        player_view=player_view,
        over=player_over,
        authoring=Authoring(
            answer=opening_draft,
            prompt=render_map,
            build=build_scenario,
        ),
        transition=Transition(
            ready=way_open,
            write=write_extension,
            install=install_extension,
            arrival_brief=None,
        ),
    )
