from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import Any, ClassVar

from aidm.core.entities import Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import AnyScenario, Game, Generation, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, lines_of, render_history, section_if
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView
from aidm.engines.base import character_panel, here_panel, party_panel, party_section, trail_panel
from aidm.engines.packs import Pack
from aidm.engines.rooms.tools import (
    ELSEWHERE,
    MEANWHILE,
    MOVE,
    MOVE_ITEM,
    MOVED_CARD,
    MOVES_OFFSCREEN,
    NOTHING_OFFSCREEN,
    UNLOCK_WAY,
    Meanwhile,
    Move,
    MoveItem,
    UnlockWay,
)
from aidm.engines.rooms.world import Dweller, MapProposal, RegionProposal, RoomWorld
from aidm.engines.rooms.worldsmith import MAP_ASK, OPENING_SECTIONS, check_extension
from aidm.engines.seam import WRITES_NO, Engine, Written

EXTEND: Slug = "extend"
MORE_MAP = DecisionOption(
    id=EXTEND, label="More map", detail="The map runs out here: say where you push on."
)
MAP_UNWRITTEN = Fact(
    told=True,
    trace="the map could not be written",
    card="The map could not be written. You are still where you were.",
)


class RoomEngine[N: Dweller, W: RoomWorld[Any, Any], K: Pack](Engine[W, K]):
    family_dir = Path(__file__).parent
    member: type[N]
    unwritten: ClassVar[dict[Slug, Fact]] = {EXTEND: MAP_UNWRITTEN}

    def family_sections(self, draft: Game[W]) -> Sections:
        world = draft.world
        return (
            ("MAP SO FAR", world.map_so_far()),
            *section_if("THE ARC SO FAR", world.arc),
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE PLAYER", world.line(world.player)),
        )

    def master_sections(self, state: Game[W]) -> Sections:
        world = state.world
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
            *self.packs.rules_section(state.pack_id),
            *(((ELSEWHERE, world.elsewhere_lines()),) if world.meanwhile_due else ()),
        )

    def narrator_view(self, state: Game[W]) -> NarratorView:
        world = state.world
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

    def player_view(self, state: Game[W]) -> PlayerView:
        world = state.world
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

    def master_tools(self) -> tuple[MasterTool[Game[W]], ...]:
        return (
            *super().master_tools(),
            master_tool("move_item", MOVE_ITEM, MoveItem, self.move_item),
            master_tool(
                "unlock_way", UNLOCK_WAY, UnlockWay, lambda d, a, _: d.world.unlock_way(a.to_id)
            ),
            master_tool("move", MOVE, Move, lambda d, a, _: d.world.move(a.to_id, a.with_ids)),
            master_tool("meanwhile", MEANWHILE, Meanwhile, self.meanwhile),
        )

    def move_item(self, draft: Game[W], args: MoveItem, _rng: Random) -> list[Fact]:
        return draft.world.move_item(args.item_id, args.to_id)

    def meanwhile(self, draft: Game[W], args: Meanwhile, _rng: Random) -> list[Fact]:
        """The ids resolve here; the world is handed what they name and changes its fields."""
        world = draft.world
        if not world.meanwhile_due:
            raise Refusal(NOTHING_OFFSCREEN)
        facts: list[Fact] = []
        if args.dweller_id is not None and args.dweller_to_id is not None:
            npc = world.require_dweller(args.dweller_id)
            facts.append(world.walk_offscreen(npc, world.offscreen_place(args.dweller_to_id)))
        if args.item_id is not None and args.item_to_id is not None:
            item = world.require_prop(args.item_id)
            facts.append(world.drift_item(item, world.offscreen_place(args.item_to_id)))
        if args.shut_from_id is not None and args.shut_to_id is not None:
            start = world.require_place(args.shut_from_id)
            facts.append(world.shut_way(start, world.require_place(args.shut_to_id)))
        facts.append(Fact(trace=MOVES_OFFSCREEN, told=True, card=MOVED_CARD))
        world.disarm()
        return facts

    def act(self, draft: Game[W], action: Slug, words: str) -> None:
        if action != EXTEND or draft.world.frontier():
            raise Refusal("the map still has ways to walk; the page was drawn before them")
        if not words:
            raise Refusal("say where you push on")
        draft.generation = Generation(operation=EXTEND, detail=words)

    async def write_next(
        self, draft: Game[W], intent: str, worldsmith: WorldsmithAnswer
    ) -> RegionProposal[N]:
        world = draft.world
        model = RegionProposal[self.member]
        prompt = self.render_request(
            draft, intent=intent, guidance=self.guidance(draft.pack_id, opening=False), answer=model
        )
        return await worldsmith(prompt, model, lambda answer: check_extension(answer, world))

    def install(self, draft: Game[W], extension: RegionProposal[N]) -> None:
        """Hidden, so nothing is told: the region reaches the player only as they walk it."""
        draft.world.attach(extension, extension.start)
        draft.log[-1].recap = extension.recap
        self.open_chapter(draft)

    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        pack_id: Slug,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: MapProposal[N]) -> AnyScenario:
            start = draft.places.get(draft.start)
            premise = "" if start is None else start.description
            return self.build_scenario(meta, pack_id, draft, source, premise)

        model = MapProposal[self.member]
        prompt = self.render_worldsmith(
            source,
            meta.scope,
            OPENING_SECTIONS,
            MAP_ASK,
            self.guidance(pack_id, opening=True),
            model,
        )
        return built(await worldsmith(prompt, model, lambda answer: check(built(answer))))

    async def advance(
        self, draft: Game[W], request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.operation == EXTEND:
            self.install(draft, await self.write_next(draft, request.detail, worldsmith))
            return Written((), None)
        raise ValueError(WRITES_NO.format(engine=self.id, operation=request.operation))
