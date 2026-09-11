from abc import abstractmethod
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.prompt import Pairs, lines_of
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView
from aidm.engines.base import (
    JOIN_PARTY,
    LEAVE_PARTY,
    JoinParty,
    LeaveParty,
    Person,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
from aidm.engines.rooms.tools import (
    KILL,
    MOVE,
    MOVE_ITEM,
    REVEAL,
    UNLOCK_WAY,
    Kill,
    Move,
    MoveItem,
    Reveal,
    UnlockWay,
)
from aidm.engines.rooms.world import Dweller, MapDraft, Prop, RoomWorld
from aidm.engines.rooms.worldsmith import MAP_ASK, check_extension, check_map, map_sections
from aidm.engines.seam import Engine, Request, Written, compose

EXTEND: Slug = "extend"
MORE_MAP = DecisionOption(
    id=EXTEND, label="More map", detail="The map runs out here: say where you push on."
)
MAP_UNWRITTEN = Fact(
    told=True,
    trace="the map could not be written",
    card="The map could not be written. You are still where you were.",
)


class RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[P, G]):
    dweller: type[N]
    world_type: type[RoomWorld[N, P]]
    family_dir = Path(__file__).parent

    def world(self, state: G) -> RoomWorld[N, P]:
        return state.payload

    def map_draft(self) -> type[MapDraft[N]]:
        """Pydantic parametrizes the subscript at runtime, so the npc type reaches the schema."""
        return MapDraft[self.dweller]

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> RoomWorld[N, P]:
        draft: MapDraft[N] = scenario.payload
        check_map(draft)
        player = self.player_of(character)
        taken = (*draft.places, *draft.npcs, *draft.items)
        return self.world_type.opening(
            draft, player, self.starting_items(player, taken), scenario.source
        )

    def starting_items(self, _player: P, _taken: Iterable[str]) -> tuple[Prop, ...]:
        return ()

    def family_sections(self, draft: G | None) -> Pairs:
        return map_sections(
            None if draft is None else self.world(draft), () if draft is None else draft.log
        )

    def master_sections(self, state: G) -> Pairs:
        world = self.world(state)
        place = world.current
        player = world.player
        return (
            ("CURRENT PLACE", f"{place.tag}\n{place.description}"),
            ("YOU PLAY FOR", world.line(player)),
            ("CARRYING", lines_of(world.line(item) for item in world.carried(player.id))),
            ("HERE WITH THE PLAYER", world.place_lines(known=True)),
            *party_section(world.members()),
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
            party=(world.player.id, *world.party),
            sheet=(*world.sheet_rows(), ("Carrying", carrying or "nothing")),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        ways = world.ways.get(world.current.id, ())
        me = player.subject()
        return PlayerView(
            player=me,
            scene_title=world.current.name,
            situation=world.current.description,
            panels=(
                character_panel(world.sheet_rows()),
                *party_panel(world.members()),
                here_panel(
                    entity.subject()
                    for entity in world.at(world.current.id)
                    if entity.known and entity.id not in world.party
                ),
                Panel(
                    title="Carrying",
                    rows=tuple(item.subject().row() for item in world.carried(player.id)),
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
                trail_panel(world.require_place(place_id).name for place_id in world.visits),
            ),
            decision=state.pending,
            action=MORE_MAP if world.frontier() == 0 else None,
            over=self.over(state),
        )

    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: Sequence[Slug],
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: MapDraft[N]) -> AnyScenario:
            start = draft.places.get(draft.start)
            premise = "" if start is None else start.description
            return self.build_scenario(meta, tuple(packs), draft, source, premise)

        prompt = self.render_opening(
            source, meta.scope, intent=MAP_ASK, guidance=self.guidance(), answer=self.map_draft()
        )
        return await compose(worldsmith, prompt, self.map_draft(), built, check)

    def act(self, draft: G, action: Slug, words: str) -> None:
        if action != EXTEND or self.world(draft).frontier():
            raise Refusal("the map still has ways to walk; the page was drawn before them")
        if not words:
            raise Refusal("say where you push on")
        draft.generation = Generation(operation=EXTEND, detail=words)

    async def extend(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        self.install(draft, await self.write_next(draft, request.detail, worldsmith))
        return (), None

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        return {EXTEND: Request(MAP_UNWRITTEN, self.extend)}

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (
            *super().master_tools(),
            master_tool("reveal", REVEAL, Reveal, self.reveal),
            master_tool("move_item", MOVE_ITEM, MoveItem, self.move_item),
            master_tool("kill", KILL, Kill, self.kill),
            master_tool("join_party", JOIN_PARTY, JoinParty, self.join_party),
            master_tool("leave_party", LEAVE_PARTY, LeaveParty, self.leave_party),
            master_tool("unlock_way", UNLOCK_WAY, UnlockWay, self.unlock_way),
            master_tool("move", MOVE, Move, self.move),
        )

    def reveal(self, draft: G, args: Reveal, _rng: Random) -> list[Fact]:
        return self.world(draft).reveal_hidden(args.entity_id)

    def move_item(self, draft: G, args: MoveItem, _rng: Random) -> list[Fact]:
        return self.world(draft).move_item(args.item_id, args.to)

    def kill(self, draft: G, args: Kill, _rng: Random) -> list[Fact]:
        world = self.world(draft)
        return world.kill(world.require_member_here(args.entity_id))

    def join_party(self, draft: G, args: JoinParty, _rng: Random) -> list[Fact]:
        return self.world(draft).join_party(args.entity_id)

    def leave_party(self, draft: G, args: LeaveParty, _rng: Random) -> list[Fact]:
        return self.world(draft).leave_party(args.entity_id)

    def unlock_way(self, draft: G, args: UnlockWay, _rng: Random) -> list[Fact]:
        return self.world(draft).unlock_way(args.to_id)

    def move(self, draft: G, args: Move, _rng: Random) -> list[Fact]:
        facts = self.world(draft).move(args.to_id, args.with_ids)
        if not draft.log[-1].exchanges:
            draft.log.pop()
        self.open_chapter(draft)
        return facts

    async def write_next(self, draft: G, intent: str, worldsmith: WorldsmithAnswer) -> MapDraft[N]:
        world = self.world(draft)
        prompt = self.render_request(
            draft, intent=intent, guidance=self.guidance(), answer=self.map_draft()
        )
        return await worldsmith(
            prompt, self.map_draft(), lambda answer: check_extension(answer, world)
        )

    def install(self, draft: G, extension: MapDraft[N]) -> None:
        """Hidden, so nothing is told: the region reaches the player only as they walk it."""
        self.world(draft).attach(extension, extension.start)

    @abstractmethod
    def guidance(self) -> str: ...
