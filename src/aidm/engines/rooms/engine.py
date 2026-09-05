from abc import abstractmethod
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from aidm.core.entities import Refusal, Slug, parse
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.views import (
    Action,
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Sections,
    lines_of,
    render_history,
)
from aidm.engines.base import Person, character_panel, here_panel, trail_panel
from aidm.engines.rooms.drafts import MapDraft
from aidm.engines.rooms.tools import Kill, Move, MoveItem, Reveal, SharedChange, UnlockWay
from aidm.engines.rooms.world import Dweller, Item, RoomCanon, RoomWorld
from aidm.engines.rooms.worldsmith import MAP_ASK, extension_refusal, map_refusal, worldsmith_prompt
from aidm.engines.seam import Engine

WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
MORE_MAP = Action(
    id="extend", label="More map", detail="The map runs out here: say where you push on."
)


class RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[P, G]):
    dweller: type[N]
    world_type: type[RoomWorld[N, P]]

    def world(self, state: G) -> RoomWorld[N, P]:
        return state.payload

    def map_draft(self) -> type[MapDraft[N]]:
        """Pydantic parametrizes the subscript at runtime, so the npc type reaches the schema."""
        return MapDraft[self.dweller]

    def validate(self, state: G) -> None:
        if state.packs:
            raise Refusal(f"{self.title} has no table sets")
        if state.generation is not None and state.generation.operation != MORE_MAP.id:
            raise Refusal(f"a room engine cannot write {state.generation.operation!r}")

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> RoomWorld[N, P]:
        self.check_scenario(scenario)
        canon: RoomCanon[N] = scenario.payload
        player = self.player_of(character)
        taken = (*canon.places, *canon.npcs, *canon.items)
        return self.world_type.begin(canon, player, self.starting_items(player, taken))

    def starting_items(self, player: P, taken: Iterable[str]) -> tuple[Item, ...]:
        return ()

    def master_sections(self, state: G) -> Sections:
        """Every section stated, hidden canon included: the game master reads all of it."""
        world = self.world(state)
        place = world.current
        player = world.player
        return (
            ("CURRENT PLACE", f"{place.tag}\n{place.description}"),
            ("YOU PLAY FOR", world.line(player)),
            ("CARRYING", lines_of(world.line(item) for item in world.carried(player.id))),
            ("HERE WITH THE PLAYER", world.place_lines(known=True)),
            ("HIDDEN HERE (the player has not found these)", world.place_lines(known=False)),
            ("WAYS OUT", world.ways_lines()),
        )

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world(state)
        place = world.current
        here = tuple(entity for entity in world.here() if entity.known)
        carrying = ", ".join(item.name for item in world.carried(world.player.id))
        return NarratorView(
            place=place.id,
            title=place.name,
            focus=place.brief,
            situation=place.description,
            subjects=tuple(entity.subject() for entity in here),
            # A corpse may stay a subject in the room; it does not speak.
            speakers=tuple(entity.id for entity in here if entity.alive),
            sheet=(*world.sheet_rows(), ("Carrying", carrying or "nothing")),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        ways = world.ways.get(world.current.id, ())
        me = player.subject()
        return PlayerView(
            player=me,
            panels=(
                character_panel(world.sheet_rows()),
                here_panel(
                    me, (entity.subject() for entity in world.at(world.current.id) if entity.known)
                ),
                Panel(
                    title="Carrying",
                    rows=tuple(
                        PanelRow(label=item.name, detail=item.brief, icon_id=item.id)
                        for item in world.carried(player.id)
                    ),
                ),
                Panel(
                    title="Ways out",
                    rows=tuple(
                        PanelRow(
                            label=world.require_place(way.to).name,
                            detail="locked" if way.locked else "",
                        )
                        for way in ways
                        if way.known
                    ),
                ),
                trail_panel(world.require_place(v.place).name for v in world.visits),
            ),
            prompt=state.pending,
            action=MORE_MAP if world.frontier() == 0 else None,
            over=self.over(state),
        )

    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: Sequence[Slug],
        worldsmith: WorldsmithAnswer,
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario:
        def built(draft: MapDraft[N]) -> AnyScenario:
            return self.build_scenario(meta, tuple(packs), draft, source)

        prompt = self.render_map(source, meta.scope)
        return await self.compose(worldsmith, prompt, self.map_draft(), built, playable)

    def act(self, draft: G, action: Slug, words: str) -> None:
        if action != MORE_MAP.id or self.world(draft).frontier():
            raise Refusal("the map still has ways to walk; the page was drawn before them")
        if not words:
            raise Refusal("say where you push on")
        draft.generation = Generation(operation=MORE_MAP.id, brief=words)

    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        extension = await self.write_extension(draft, request.brief, worldsmith)
        self.install_extension(draft, extension)
        return (), None

    def shared_change(self, world: RoomWorld[N, P], change: SharedChange) -> list[Fact]:
        match change:
            case Reveal():
                return world.reveal_hidden(change.entity_id)
            case MoveItem():
                return world.move_item(change.item_id, change.to)
            case Kill():
                return world.kill(world.require_npc_here(change.entity_id))

    def move(self, draft: G, args: Move, _rng: Random) -> list[Fact]:
        return self.world(draft).move(args.to_id, args.with_ids)

    def unlock_way(self, draft: G, args: UnlockWay, _rng: Random) -> list[Fact]:
        return self.world(draft).unlock_way(args.to_id)

    def render_map(self, source: str, scope: str) -> str:
        """A room engine ships no packs to pick."""
        return worldsmith_prompt(
            WORLDSMITH,
            source=source,
            scope=scope,
            map_so_far="(no map yet)",
            history="(no scenes yet — write the opening)",
            player="(no player yet — the map is authored before anyone stands in it)",
            intent=MAP_ASK,
            guidance=self.guidance(),
            answer=self.map_draft(),
        )

    def render_extension(self, world: RoomWorld[N, P], intent: str, scope: str) -> str:
        return worldsmith_prompt(
            WORLDSMITH,
            source=world.source,
            scope=scope,
            map_so_far=world.map_so_far(),
            history=render_history(world.records()),
            player=world.line(world.player),
            intent=intent,
            guidance=self.guidance(),
            answer=self.map_draft(),
        )

    async def write_extension(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> MapDraft[N]:
        world = self.world(draft)
        prompt = self.render_extension(world, intent, draft.scenario.scope)
        return await worldsmith(
            prompt, self.map_draft(), lambda answer: extension_refusal(answer, world)
        )

    def install_extension(self, draft: G, extension: MapDraft[N]) -> None:
        """Hidden, so nothing is told: the region reaches the player only as they walk it."""
        self.world(draft).attach(extension, extension.start)

    def build_scenario(
        self, meta: ScenarioMeta, packs: tuple[Slug, ...], draft: MapDraft[N], source: str
    ) -> AnyScenario:
        if (refused := map_refusal(draft)) is not None:
            raise Refusal(refused)
        return self.scenario(
            meta=meta.with_premise(draft.places[draft.start].description),
            engine=self.id,
            packs=packs,
            payload=self.opening_canon(draft, source),
        )

    def opening_canon(self, draft: MapDraft[N], source: str) -> RoomCanon[N]:
        """Parametrized on the engine's npc, so the canon revalidates as its own people."""
        return parse(
            RoomCanon[self.dweller],
            {
                "places": draft.places,
                "ways": draft.ways,
                "npcs": draft.npcs,
                "items": draft.items,
                "start": draft.start,
                "source": source,
            },
        )

    @abstractmethod
    def guidance(self) -> str: ...
