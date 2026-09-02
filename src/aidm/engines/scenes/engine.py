from abc import abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aidm.core.entities import EntityId, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario, Game, ScenarioKind, WorldsmithAnswer
from aidm.core.play import DecisionOption, Exchange, SpokenLine
from aidm.core.views import NarratorView, Panel, PlayerView
from aidm.engines.core import Pack, Person, load_packs, pack_options
from aidm.engines.scenes.drafts import SceneDraft
from aidm.engines.scenes.views import narrator_view, player_view
from aidm.engines.scenes.world import (
    SceneCanon,
    SceneWorld,
    check_game,
    player_over,
    way_open,
)
from aidm.engines.scenes.worldsmith import (
    CROSSING,
    build_scenario,
    install_scene,
    opening_draft,
    render_opening,
    write_next,
)
from aidm.engines.seam import Engine, authored


class SceneEngine[C: Person, P: Person, G: Game[Any], K: Pack](Engine[G]):
    """The scene lifecycle, once; a subclass says what its rules add."""

    cast: type[C]
    pack: type[K]
    hub_phrase: str  # what CAMPAIGN_OPENING asks this engine's hub to be
    finished_note: str = ""  # the note a finished job leaves for the next turn
    crossing = CROSSING
    packs: dict[str, K]
    role: str

    def __init__(self, user_packs: Path) -> None:
        self.packs = load_packs((self.directory / "packs", user_packs), self.pack)
        self.role = (self.directory / "worldsmith.md").read_text(encoding=ENCODING)
        super().__init__()  # last: `master_tools` reads the packs

    def world(self, state: G) -> SceneWorld[C, P]:
        return state.payload.world  # the one place `G: Game[Any]` is narrowed to the scene world

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return pack_options(self.packs)

    def validate(self, state: G) -> None:
        check_game(self.packs, state)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> BaseModel:
        if not isinstance(scenario, self.scenario):
            raise ValueError(f"{self.title} received an incompatible scenario")
        if not isinstance(character, self.character):
            raise ValueError(f"{self.title} received an incompatible character")
        canon: SceneCanon[C] = scenario.payload.world
        return self.new_state(canon, character)

    def over(self, state: G) -> str | None:
        return player_over(state)

    def known(self, state: G, entity_id: EntityId) -> bool | None:
        world = self.world(state)
        if entity_id == world.player.id:
            return True
        one = world.cast.get(entity_id)
        return None if one is None else one.known

    def record(
        self, state: G, prompt: str, lines: tuple[SpokenLine, ...], facts: Sequence[Fact]
    ) -> tuple[str, ...]:
        world = self.world(state)
        return world.record_exchange(
            prompt,
            lines,
            facts,
            "" if state.pending is None else state.pending.prompt,
            someone_dead=any(not one.alive for one in world.here()),
        )

    def history(self, state: G) -> tuple[Exchange, ...]:
        return self.world(state).exchanges()

    def narrator_view(self, state: G) -> NarratorView:
        return narrator_view(state)

    def player_view(self, state: G) -> PlayerView:
        return player_view(state, self.panels(state))

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
        def built(written: SceneDraft[C]) -> AnyScenario:
            return build_scenario(
                self.scenario, self.id, title, premise, tuple(packs), written, source, kind
            )

        prompt = render_opening(
            self.cast,
            self.role,
            source,
            self.guidance(packs, campaign=kind == "campaign"),
            kind,
            self.hub_phrase,
        )
        return await authored(worldsmith, prompt, opening_draft(self.cast, kind), built, playable)

    def ready(self, state: G) -> bool:
        return way_open(state)

    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        world = self.world(draft)
        written = await write_next(
            world,
            intent,
            worldsmith,
            cast_type=self.cast,
            role=self.role,
            guidance=self.guidance(draft.packs, campaign=world.hub is not None),
        )
        # The engine's own closing reads the scene being left, so it runs before the install.
        return (
            *self.leaving(draft),
            *install_scene(draft, written, finished_note=self.finished_note),
        )

    def panels(self, state: G) -> tuple[Panel, ...]:
        return ()

    def leaving(self, state: G) -> tuple[Fact, ...]:
        return ()

    @abstractmethod
    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str: ...
    @abstractmethod
    def new_state(self, canon: SceneCanon[C], character: AnyCharacter) -> BaseModel: ...
