from abc import abstractmethod
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.entities import Refusal, Slug, parse
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Game,
    ScenarioKind,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Commission
from aidm.core.tools import MasterTool, Play, master_tool
from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Sections,
    lines_of,
    render_history,
)
from aidm.engines.base import Person, character_panel, here_panel, trail_panel
from aidm.engines.hub import RETURN_BRIEF, Campaign, Job, check_kind
from aidm.engines.rooms.drafts import ItemDraft, MapDraft, NpcDraft, ReturnDraft
from aidm.engines.rooms.tools import (
    Kill,
    Move,
    MoveItem,
    Reveal,
    RoomCommission,
    SharedChange,
    UnlockWay,
)
from aidm.engines.rooms.world import Dweller, Item, RoomCanon, RoomWorld
from aidm.engines.rooms.worldsmith import (
    COMMISSION_ASK,
    JOB_BRIEF,
    MAP_ASK,
    TAVERN_ASK,
    extension_refusal,
    hub_refusal,
    item_refusal,
    job_refusal,
    map_refusal,
    npc_refusal,
    return_refusal,
    worldsmith_prompt,
)
from aidm.engines.seam import COMMISSION, COMMISSION_BRIEF, Engine

REPORT_IN = "Report in."
REPORT_ROW = PanelRow(label="Report in", detail="Tell the tavern how it went.", intent=REPORT_IN)
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)


class RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[P, G]):
    """The room-crawl lifecycle, once; a subclass says what its rules add."""

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
        check_kind(state.scenario.kind, self.world(state).campaign)

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
            *(() if world.campaign is None else world.campaign.tail(at_hub=world.at_hub)),
        )

    def narrator_view(self, state: G) -> NarratorView:
        world = self.world(state)
        place = world.current
        here = tuple(entity for entity in world.here() if entity.known)
        return NarratorView(
            place=place.id,
            title=place.name,
            focus=place.brief,
            situation=place.description,
            subjects=tuple(entity.subject() for entity in here),
            # A corpse may stay a subject in the room; it does not speak.
            speakers=tuple(entity.subject().speaker() for entity in here if entity.alive),
        )

    def player_view(self, state: G) -> PlayerView:
        world = self.world(state)
        player = world.player
        campaign = world.campaign
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
                *(
                    ()
                    if campaign is None
                    else campaign.board_panel(
                        at_hub=world.at_hub,
                        reporting=REPORT_ROW if world.walked_job() is not None else None,
                    )
                ),
                trail_panel(world.require_place(v.place).name for v in world.job_visits()),
                *(() if campaign is None else campaign.jobs_panel()),
            ),
            prompt=state.pending,
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

        prompt = self.render_map(source, meta.kind)
        return await self.compose(worldsmith, prompt, self.map_draft(), built, playable)

    def ready(self, state: G) -> bool:
        world = self.world(state)
        return world.at_hub or world.frontier() == 0

    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        reopening = self.reopening(draft, intent)
        extension = await self.write_extension(draft, intent, worldsmith, reopening=reopening)
        return tuple(self.install_extension(draft, extension, reopening=reopening))

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

    def commission_tool(self) -> MasterTool[G]:
        return master_tool(
            COMMISSION,
            COMMISSION_BRIEF
            + " An npc standing at this place, an item lying here, or a region beyond the "
            "player's reach. Read HIDDEN HERE and WAYS OUT first: ask only for what the place "
            "lacks.",
            RoomCommission,
            self.ask_worldsmith,
        )

    def render_map(self, source: str, kind: ScenarioKind) -> str:
        """One map serves both kinds; a room engine ships no packs to pick."""
        return worldsmith_prompt(
            WORLDSMITH,
            source=source,
            map_so_far="(no map yet)",
            history="(no scenes yet — write the opening)",
            player="(no player yet — the map is authored before anyone stands in it)",
            intent=TAVERN_ASK if kind == "campaign" else MAP_ASK,
            guidance=self.guidance(),
            answer=self.map_draft(),
        )

    def render_extension(
        self,
        world: RoomWorld[N, P],
        intent: str,
        hub: Sections = (),
        *,
        answer: type[BaseModel] | None = None,
        asked: str = "",
    ) -> str:
        return worldsmith_prompt(
            WORLDSMITH,
            source=world.source,
            map_so_far=world.map_so_far(),
            history=render_history(world.scenes()),
            player=world.line(world.player),
            intent=intent,
            guidance=self.guidance(),
            answer=answer or self.map_draft(),
            hub=hub,
            asked=asked,
        )

    def render_commission(
        self, world: RoomWorld[N, P], asked: Commission, answer: type[BaseModel]
    ) -> str:
        return self.render_extension(
            world,
            "(nothing this write: the game master's ask above is the whole brief)",
            answer=answer,
            asked=COMMISSION_ASK.format(kind=asked.kind, brief=asked.brief),
        )

    def hub_sections(
        self, world: RoomWorld[N, P], *, returning: bool, reopening: Job | None
    ) -> Sections:
        campaign = world.campaign
        if campaign is None or not world.at_hub:
            return ()
        brief = RETURN_BRIEF if returning else JOB_BRIEF
        return campaign.hub_block(
            world.current.name, brief, world.records(), returning=returning, reopening=reopening
        )

    async def write_extension(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer, *, reopening: Job | None = None
    ) -> MapDraft[N] | ReturnDraft:
        world = self.world(draft)
        walked = world.walked_job()
        returning = world.at_hub and intent == REPORT_IN
        if returning and walked is None:
            raise Refusal("no job is open to report")
        if world.at_hub and walked is not None and not returning:
            raise Refusal("report the open job first")
        later = draft.on_order()
        asked = lines_of(f"- {c.kind}: {c.brief}" for c in later) if later else ""
        hub = self.hub_sections(world, returning=returning, reopening=reopening)
        if returning:
            prompt = self.render_extension(world, intent, hub, answer=ReturnDraft)
            return await worldsmith(
                prompt, ReturnDraft, lambda answer: return_refusal(answer, world)
            )
        prompt = self.render_extension(world, intent, hub, asked=asked)
        bar = job_refusal if world.at_hub else extension_refusal
        return await worldsmith(prompt, self.map_draft(), lambda answer: bar(answer, world, later))

    def install_extension(
        self, draft: G, extension: MapDraft[N] | ReturnDraft, *, reopening: Job | None = None
    ) -> list[Fact]:
        world = self.world(draft)
        if isinstance(extension, ReturnDraft):
            job = world.apply_return(
                debrief=extension.debrief,
                summary=extension.summary,
                recaps=extension.recaps,
                offers=extension.offers,
            )
            return [job.closed()]
        anchor = world.apply_extension(extension, extension.start, reopening=reopening)
        draft.commissions.clear()
        start = world.require_place(extension.start)
        if world.at_hub:
            trace = f"a way opens from {anchor.name} to {start.name}"
            return [
                Fact(kind="job_taken", told=True, trace=trace, card=f"A way opens: {start.name}")
            ]
        trace = f"a hidden region opens beyond {anchor.name}"
        return [Fact(kind="region_added", trace=trace, told=False)]

    async def fulfil(self, draft: G, asked: Commission, worldsmith: WorldsmithAnswer) -> Play[G]:
        world = self.world(draft)
        match asked.kind:
            case "npc":
                written: NpcDraft[N] | ItemDraft | MapDraft[N] = await worldsmith(
                    self.render_commission(world, asked, NpcDraft[self.dweller]),
                    NpcDraft[self.dweller],
                    lambda answer: npc_refusal(answer, world),
                )
            case "item":
                written = await worldsmith(
                    self.render_commission(world, asked, ItemDraft),
                    ItemDraft,
                    lambda answer: item_refusal(answer, world),
                )
            case "region":
                written = await worldsmith(
                    self.render_commission(world, asked, self.map_draft()),
                    self.map_draft(),
                    lambda answer: extension_refusal(answer, world),
                )
            case _:  # `RoomCommission.kind` bars every other kind at the tool; this is a bug
                raise ValueError(f"no worldsmith answer for a commissioned {asked.kind!r}")
        return lambda candidate, _rng: tuple(self.install_commission(candidate, asked, written))

    def install_commission(
        self, draft: G, asked: Commission, written: NpcDraft[N] | ItemDraft | MapDraft[N]
    ) -> list[Fact]:
        world = self.world(draft)
        if isinstance(written, NpcDraft):
            world.npcs[written.npc.id] = written.npc
            label = written.npc.label
        elif isinstance(written, ItemDraft):
            world.items[written.item.id] = written.item
            label = written.item.label
        else:
            world.attach(written, written.start, known=False)
            label = world.require_place(written.start).label
        draft.withdraw(asked)
        trace = f"the worldsmith wrote {label}; reveal it when the player finds it"
        return [Fact(kind="commissioned", trace=trace)]

    def build_scenario(
        self, meta: ScenarioMeta, packs: tuple[Slug, ...], draft: MapDraft[N], source: str
    ) -> AnyScenario:
        bar = hub_refusal if meta.kind == "campaign" else map_refusal
        if (refused := bar(draft)) is not None:
            raise Refusal(refused)
        return self.scenario(
            meta=meta.with_premise(draft.places[draft.start].description),
            engine=self.id,
            packs=packs,
            payload=self.opening_canon(draft, source, meta.kind),
        )

    def opening_canon(self, draft: MapDraft[N], source: str, kind: ScenarioKind) -> RoomCanon[N]:
        """Parametrized on the engine's npc, so the canon revalidates as its own people."""
        campaign = None
        if kind == "campaign":
            if draft.board is None:
                raise Refusal("a campaign's opening needs a board")
            campaign = Campaign(place=draft.start, board=draft.board)
        return parse(
            RoomCanon[self.dweller],
            {
                "places": draft.places,
                "ways": draft.ways,
                "npcs": draft.npcs,
                "items": draft.items,
                "start": draft.start,
                "source": source,
                "campaign": campaign,
            },
        )

    @abstractmethod
    def guidance(self) -> str: ...
