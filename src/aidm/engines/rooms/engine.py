from collections.abc import Callable, Iterable
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
    PackSelection,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, lines_of, render_history, section_if
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView
from aidm.engines.base import (
    Person,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
from aidm.engines.rooms.tools import (
    MEANWHILE,
    MOVE,
    MOVE_ITEM,
    UNLOCK_WAY,
    Meanwhile,
    Move,
    MoveItem,
    UnlockWay,
)
from aidm.engines.rooms.world import Dweller, MapDraft, Prop, RegionDraft, RoomWorld
from aidm.engines.rooms.worldsmith import MAP_ASK, check_extension, check_map
from aidm.engines.seam import Engine, Request, Written

EXTEND: Slug = "extend"
MORE_MAP = DecisionOption(
    id=EXTEND, label="More map", detail="The map runs out here: say where you push on."
)
MAP_UNWRITTEN = Fact(
    told=True,
    trace="the map could not be written",
    card="The map could not be written. You are still where you were.",
)
ELSEWHERE = "ELSEWHERE (time has passed; you may move what the player cannot see)"


class RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[P, N, G]):
    world: type[RoomWorld[N, P]]
    family_dir = Path(__file__).parent
    guidance: str
    opening_sections = (
        ("MAP SO FAR", "(no map yet)"),
        ("SCENES SO FAR", "(no scenes yet — write the opening)"),
        ("THE PLAYER", "(no player yet — the map is authored before anyone stands in it)"),
    )

    def world_of(self, state: G) -> RoomWorld[N, P]:
        return state.payload

    def validate(self, state: G) -> None:
        super().validate(state)
        if state.packs is not None:
            raise Refusal(f"a {self.id!r} game plays no table set")

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> RoomWorld[N, P]:
        draft: MapDraft[N] = scenario.payload
        check_map(draft)
        player = self.player_of(character)
        taken = (*draft.places, *draft.npcs, *draft.items)
        return self.world.opening(
            draft, player, self.starting_items(player, taken), scenario.source
        )

    def starting_items(self, _player: P, _taken: Iterable[str]) -> tuple[Prop, ...]:
        return ()

    def family_sections(self, draft: G) -> Sections:
        world = self.world_of(draft)
        return (
            ("MAP SO FAR", world.map_so_far()),
            *section_if("THE ARC SO FAR", world.arc),
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE PLAYER", world.line(world.player)),
        )

    def master_sections(self, state: G) -> Sections:
        world = self.world_of(state)
        place = world.current
        player = world.player
        return (
            ("CURRENT PLACE", f"{place.tag}\n{place.description}"),
            ("YOU PLAY FOR", world.line(player)),
            ("CARRYING", lines_of(world.line(item) for item in world.carried(player.id))),
            ("HERE WITH THE PLAYER", world.place_lines(known=True)),
            *party_section(world.members()),
            ("HIDDEN HERE (the player has not found these)", world.place_lines(known=False)),
            *section_if("THE ARC (the player has not found this)", world.arc),
            ("WAYS OUT", world.ways_lines()),
            *(((ELSEWHERE, world.elsewhere_lines()),) if world.meanwhile_due else ()),
        )

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world_of(state)
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
        world = self.world_of(state)
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
                here_panel(other.subject() for other in world.others()),
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
        packs: PackSelection | None,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: MapDraft[N]) -> AnyScenario:
            start = draft.places.get(draft.start)
            premise = "" if start is None else start.description
            return self.build_scenario(meta, packs, draft, source, premise)

        prompt = self.render_opening(
            source,
            meta.scope,
            intent=MAP_ASK,
            guidance=self.guidance,
            answer=MapDraft[self.member],
        )
        return built(
            await worldsmith(prompt, MapDraft[self.member], lambda answer: check(built(answer)))
        )

    def act(self, draft: G, action: Slug, words: str) -> None:
        if action != EXTEND or self.world_of(draft).frontier():
            raise Refusal("the map still has ways to walk; the page was drawn before them")
        if not words:
            raise Refusal("say where you push on")
        draft.generation = Generation(operation=EXTEND, detail=words)

    async def extend(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        self.install(draft, await self.write_next(draft, request.detail, worldsmith))
        return Written((), None)

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        return {**super().worldsmith_requests(), EXTEND: Request(MAP_UNWRITTEN, self.extend)}

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (
            *super().master_tools(),
            master_tool("move_item", MOVE_ITEM, MoveItem, self.move_item),
            master_tool("unlock_way", UNLOCK_WAY, UnlockWay, self.unlock_way),
            master_tool("move", MOVE, Move, self.move),
            master_tool("meanwhile", MEANWHILE, Meanwhile, self.meanwhile),
        )

    def move_item(self, draft: G, args: MoveItem, _rng: Random) -> list[Fact]:
        return self.world_of(draft).move_item(args.item_id, args.to)

    def unlock_way(self, draft: G, args: UnlockWay, _rng: Random) -> list[Fact]:
        return self.world_of(draft).unlock_way(args.to_id)

    def move(self, draft: G, args: Move, _rng: Random) -> list[Fact]:
        return self.world_of(draft).move(args.to_id, args.with_ids)

    def meanwhile(self, draft: G, args: Meanwhile, _rng: Random) -> list[Fact]:
        return self.world_of(draft).meanwhile(
            dweller_id=args.dweller_id,
            dweller_to=args.dweller_to,
            item_id=args.item_id,
            item_to=args.item_to,
            shut_from=args.shut_from,
            shut_to=args.shut_to,
        )

    def tick(self, draft: G, *, counted: bool) -> None:
        world = self.world_of(draft)
        was_armed = world.meanwhile_due
        if not was_armed and not world.can_move_offscreen():
            return
        super().tick(draft, counted=counted)
        if was_armed and counted:
            world.disarm()  # the armed turn is spent; one chance, not several

    async def write_next(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> RegionDraft[N]:
        world = self.world_of(draft)
        prompt = self.render_request(
            draft, intent=intent, guidance=self.guidance, answer=RegionDraft[self.member]
        )
        return await worldsmith(
            prompt, RegionDraft[self.member], lambda answer: check_extension(answer, world)
        )

    def install(self, draft: G, extension: RegionDraft[N]) -> None:
        """Hidden, so nothing is told: the region reaches the player only as they walk it."""
        self.world_of(draft).attach(extension, extension.start)
        draft.log[-1].recap = extension.recap
        self.open_chapter(draft)
