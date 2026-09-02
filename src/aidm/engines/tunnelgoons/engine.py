from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import Path

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, EntityId, Slug
from aidm.core.facts import Fact
from aidm.core.model import AnyCharacter, AnyScenario, ScenarioKind, WorldsmithAnswer
from aidm.core.play import Exchange, SpokenLine
from aidm.core.tools import MasterTool
from aidm.core.views import NarratorView, PlayerView, Rows
from aidm.engines.hub import check_kind
from aidm.engines.seam import Engine, authored
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
    MapDraft,
    build_scenario,
    install_extension,
    render_map,
    way_open,
    write_extension,
)


class TunnelGoonsEngine(Engine[TunnelGoonsGame]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    game = TunnelGoonsGame
    scenario = TunnelGoonsScenarioFile
    character = TunnelGoonsCharacterFile

    def master_tools(self) -> tuple[MasterTool[TunnelGoonsGame], ...]:
        return tools()

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        return creation_steps(picks)

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        return create_character(name, brief, picks)

    def preview_character(self, character: AnyCharacter) -> Rows:
        return preview_character(character)

    def validate(self, state: TunnelGoonsGame) -> None:
        if state.packs:
            raise ValueError("Tunnel Goons has no table sets")
        check_kind(state.scenario.kind, state.payload.world.hub)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> TunnelGoonsState:
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

    def over(self, state: TunnelGoonsGame) -> str | None:
        return player_over(state)

    def known(self, state: TunnelGoonsGame, entity_id: EntityId) -> bool | None:
        return known(state, entity_id)

    def record(
        self,
        state: TunnelGoonsGame,
        prompt: str,
        lines: tuple[SpokenLine, ...],
        facts: Sequence[Fact],
    ) -> tuple[str, ...]:
        return record(state, prompt, lines, facts)

    def history(self, state: TunnelGoonsGame) -> tuple[Exchange, ...]:
        return history(state)

    def master_sections(self, state: TunnelGoonsGame) -> Rows:
        return master_sections(state)

    def narrator_view(self, state: TunnelGoonsGame) -> NarratorView:
        return narrator_view(state)

    def player_view(self, state: TunnelGoonsGame) -> PlayerView:
        return player_view(state)

    async def author(
        self,
        title: str,
        premise: str,
        source: str,
        packs: Sequence[Slug],
        kind: ScenarioKind,
        worldsmith: WorldsmithAnswer,
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario:
        def built(written: MapDraft) -> AnyScenario:
            return build_scenario(title, premise, tuple(packs), written, source, kind)

        return await authored(
            worldsmith, render_map(source, packs, kind), MapDraft, built, playable
        )

    def ready(self, state: TunnelGoonsGame) -> bool:
        return way_open(state)

    async def advance(
        self, draft: TunnelGoonsGame, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        return install_extension(draft, await write_extension(draft, intent, worldsmith))
