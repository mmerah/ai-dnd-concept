from collections.abc import Callable, Iterable, Sequence
from copy import deepcopy
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, parse, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.io import ENCODING
from aidm.core.model import AnyCharacter, AnyScenario, ScenarioKind, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import DecisionOption, Exchange, PendingDecision, SceneRecord
from aidm.core.tools import MasterTool, NoArgs, master_tool, schema_text
from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Rows,
    Sections,
    render_history,
    sections,
)
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID, character_panel, here_panel, trail_panel
from aidm.engines.hub import (
    RETURN_BRIEF,
    Job,
    board_lines,
    board_rows,
    check_kind,
    job_closed,
    jobs_panel,
    ledger,
    master_tail,
)
from aidm.engines.seam import Engine
from aidm.engines.tunnelgoons.tools import (
    LEVEL_OPTIONS,
    ActionRoll,
    ChangeWorld,
    Kill,
    LevelUp,
    Move,
    MoveItem,
    Reveal,
    UnlockWay,
    WorldChange,
)
from aidm.engines.tunnelgoons.views import REPORT_IN, REPORT_ROW, lines_of, place_lines, ways_lines
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    STARTING_ITEMS,
    Goon,
    Item,
    Place,
    TunnelGoonsCharacterFile,
    TunnelGoonsGame,
    TunnelGoonsPayload,
    TunnelGoonsScenario,
    TunnelGoonsWorld,
    Visit,
)
from aidm.engines.tunnelgoons.worldsmith import (
    JOB_BRIEF,
    TAVERN_ASK,
    MapDraft,
    ReturnDraft,
    extension_refusal,
    hub_refusal,
    job_refusal,
    map_refusal,
    opening_canon,
)

STARTING_ITEM_LIST: tuple[str, ...] = (
    "Melee Weapon (specify)",
    "Ranged Weapon (specify)",
    "Piece of Armor (specify)",
    "Cloak (specify colour)",
    "Ration (specify)",
    "Torch",
    "Net",
    "Bear Trap",
    "Hammer",
    "Mirror",
    "Rope",
    "Manacles",
    "Flask",
    "Marbles",
    "Pitons",
    "Scissors",
    "Wire",
    "Flint Steel",
)
POINT_OPTIONS: tuple[DecisionOption, ...] = tuple(
    DecisionOption(id=str(points), label=str(points)) for points in range(ABILITY_POINTS + 1)
)


class TunnelGoonsEngine(Engine[TunnelGoonsGame]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    game = TunnelGoonsGame
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacterFile
    worldsmith: str

    def __init__(self) -> None:
        super().__init__()
        self.worldsmith = (self.directory / "worldsmith.md").read_text(encoding=ENCODING)

    def master_tools(self) -> tuple[MasterTool[TunnelGoonsGame], ...]:
        level_desc = (
            "Raise one ability and either Health or Inventory Score by 1 at an adventure's end. "
            "In a campaign, call it when the job's dungeon is done; the tavern then closes the "
            "job as finished."
        )
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool(
                "move",
                "Move through an unlocked way from the player's current place.",
                Move,
                self.move,
            ),
            master_tool(
                "unlock_way",
                "Unlock a locked way out of the player's current place.",
                UnlockWay,
                self.unlock_way,
            ),
            master_tool(
                "action_roll",
                "Roll 2d6 plus an ability and helpful items against a Difficulty Score or an npc.",
                ActionRoll,
                self.action_roll,
            ),
            master_tool(
                "rest",
                "Spend the night in a safe spot to heal the player's Health to full.",
                NoArgs,
                self.rest,
            ),
            master_tool("level_up", level_desc, LevelUp, self.level_up),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        ability_steps = tuple(
            CreationStep(
                id=ability,
                prompt=f"Points in {ability.capitalize()}",
                options=POINT_OPTIONS,
                hint=f"{ABILITY_POINTS} points across the three",
            )
            for ability in ABILITIES
        )
        item_steps = tuple(
            CreationStep(id=f"item-{n}", prompt=f"Item {n}", hint=", ".join(STARTING_ITEM_LIST))
            for n in range(1, STARTING_ITEMS + 1)
        )
        return (*ability_steps, *item_steps)

    def create_character(self, name: str, brief: str, picks: Picks) -> TunnelGoonsCharacterFile:
        check_picks(self.creation_steps(picks), picks)
        # The ability split is the sheet's own rule, so the picks are parsed as a boundary.
        payload = parse(
            TunnelGoonsPayload,
            {
                "brute": int(picked(picks, "brute")),
                "skulker": int(picked(picks, "skulker")),
                "erudite": int(picked(picks, "erudite")),
                "items": tuple(picked(picks, f"item-{n}") for n in range(1, STARTING_ITEMS + 1)),
            },
        )
        return TunnelGoonsCharacterFile(
            id=slug(name, ()), engine=self.id, name=name, brief=brief, payload=payload
        )

    def preview_character(self, character: AnyCharacter) -> Rows:
        own = self._own(character)
        goon = self.player_of(own, EntityId("nowhere"))
        return (*goon.rows(), ("Items", ", ".join(own.payload.items)))

    def player_of(self, character: AnyCharacter, place: EntityId) -> Goon:
        """The played character as the world holds them; `new_game` and the preview share it."""
        payload = self._own(character).payload
        return Goon(
            id=PLAYER_ID,
            name=character.name,
            brief=character.brief,
            known=True,
            place=place,
            brute=payload.brute,
            skulker=payload.skulker,
            erudite=payload.erudite,
        )

    def _own(self, character: AnyCharacter) -> TunnelGoonsCharacterFile:
        if not isinstance(character, TunnelGoonsCharacterFile):
            raise Refusal(f"{self.title} received an incompatible character")
        return character

    def starting_items(
        self, character: TunnelGoonsCharacterFile, taken: Iterable[str]
    ) -> tuple[Item, ...]:
        made = list(taken)
        items: list[Item] = []
        for name in character.payload.items:
            item_id = EntityId(slug(name, made))
            made.append(item_id)
            items.append(Item(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)

    def validate(self, state: TunnelGoonsGame) -> None:
        if state.packs:
            raise Refusal("Tunnel Goons has no table sets")
        check_kind(state.scenario.kind, state.payload.hub)

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> TunnelGoonsWorld:
        if not isinstance(scenario, TunnelGoonsScenario):
            raise Refusal(f"{self.title} received an incompatible scenario")
        if not isinstance(character, TunnelGoonsCharacterFile):
            raise Refusal(f"{self.title} received an incompatible character")
        canon = deepcopy(scenario.payload)
        player = self.player_of(character, canon.start)
        taken = (*canon.places, *canon.npcs, *canon.items)
        items = self.starting_items(character, taken)
        return TunnelGoonsWorld(
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

    def over(self, state: TunnelGoonsGame) -> str | None:
        return "You died." if not state.payload.player.alive else None

    def record(self, state: TunnelGoonsGame, exchange: Exchange) -> None:
        state.payload.visit.exchanges.append(exchange)

    def history(self, state: TunnelGoonsGame) -> tuple[Exchange, ...]:
        return state.payload.exchanges()

    def scenes(self, state: TunnelGoonsGame) -> tuple[SceneRecord, ...]:
        return state.payload.scenes()

    def master_sections(self, state: TunnelGoonsGame) -> Sections:
        """Every section stated, hidden canon included: the game master reads all of it."""
        world = state.payload
        place = world.current
        player = world.player
        return (
            ("CURRENT PLACE", f"{place.name}[{place.id}]\n{place.description}"),
            ("YOU PLAY FOR", world.line(player)),
            ("CARRYING", lines_of(world.line(item) for item in world.carried(player.id))),
            ("HERE WITH THE PLAYER", place_lines(world, known=True)),
            ("HIDDEN HERE (the player has not found these)", place_lines(world, known=False)),
            ("WAYS OUT", ways_lines(world)),
            *master_tail(world.hub, world.at_hub, world.board, world.closed_jobs(), None),
        )

    def narrator_view(self, state: TunnelGoonsGame) -> NarratorView:
        world = state.payload
        place = world.current
        here = tuple(
            sorted(
                (one for one in world.here() if one.known),
                key=lambda one: one.id != world.player.id,
            )
        )
        return NarratorView(
            place=place.id,
            title=place.name,
            focus=place.brief,
            situation=place.description,
            subjects=tuple(one.subject() for one in here),
            # A corpse may stay a subject in the room; it does not speak.
            speakers=tuple(one.subject().speaker() for one in here if one.alive),
        )

    def player_view(self, state: TunnelGoonsGame) -> PlayerView:
        world = state.payload
        player = world.player
        ways = world.ways.get(world.current.id, ())
        me = player.subject()
        return PlayerView(
            player=me,
            panels=(
                character_panel(world.sheet_rows(player)),
                here_panel(me, (one.subject() for one in world.at(world.current.id) if one.known)),
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
                    (
                        Panel(
                            title="Board",
                            rows=(REPORT_ROW,) if world.job_open else board_rows(world.board),
                        ),
                    )
                    if world.at_hub
                    else ()
                ),
                trail_panel(world.require_place(v.place).name for v in world.job_visits()),
                *jobs_panel(world.closed_jobs()),
            ),
            prompt=state.pending,
            over=self.over(state),
        )

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
            return self.build_scenario(title, premise, tuple(packs), written, source, kind)

        prompt = self.render_map(source, kind)
        return await self.compose(worldsmith, prompt, MapDraft, built, playable)

    def ready(self, state: TunnelGoonsGame) -> bool:
        world = state.payload
        return world.at_hub or world.frontier() == 0

    async def advance(
        self, draft: TunnelGoonsGame, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        return tuple(
            self.install_extension(draft, await self.write_extension(draft, intent, worldsmith))
        )

    def apply_change(self, world: TunnelGoonsWorld, change: WorldChange) -> list[Fact]:
        match change:
            case Reveal():
                return world.reveal_hidden(change.entity_id)
            case MoveItem():
                return world.move_item(change.item_id, change.to)
            case Kill():
                return world.kill(world.require_npc_here(change.entity_id))

    def change_world(self, draft: TunnelGoonsGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def move(self, draft: TunnelGoonsGame, args: Move, _rng: Random) -> list[Fact]:
        return draft.payload.move(args.to_id, args.with_ids)

    def unlock_way(self, draft: TunnelGoonsGame, args: UnlockWay, _rng: Random) -> list[Fact]:
        return draft.payload.unlock_way(args.to_id)

    def action_roll(self, draft: TunnelGoonsGame, args: ActionRoll, rng: Random) -> list[Fact]:
        world = draft.payload
        player = world.player
        items = world.carried_items(args.items)
        npc = world.require_npc_here(args.against) if args.against is not None else None
        facts = npc.reveal() if npc is not None else []
        ds = npc.hp.current if npc is not None else args.difficulty
        if ds is None:
            raise Refusal("give a difficulty, or an npc to roll against")

        penalty = 0
        if args.ability in ("brute", "skulker"):
            penalty = max(0, len(list(world.carried(player.id))) - player.inventory)
        rolled, dice_fact = roll((6, 6), f"{args.what} — {args.ability}", rng)
        total = sum(rolled) + player.ability(args.ability) + len(items) - penalty
        success = total >= ds
        margin = total - ds
        outcome = "success" if success else "failure"

        facts.append(dice_fact)
        trace = f"{args.what} — {args.ability} {total} vs DS {ds} -> {outcome}"
        card = f"{args.what} — {args.ability.capitalize()} {total} vs DS {ds} → {outcome}"
        event = DiceEvent(label="2d6", faces=(6, 6), rolled=rolled)
        facts.append(player.fact("action_rolled", trace, card=card, dice=(event,)))

        # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
        if not args.dangerous:
            return facts
        if npc is not None and success:
            facts.extend(npc.hp.change(npc, -margin, "Health", "the player's action"))
            if npc.hp.current == 0:
                facts.extend(world.kill(npc))
        elif not success:
            facts.extend(player.hp.change(player, margin, "Health", args.what))
            if player.hp.current == 0:
                facts.extend(world.kill(player))
        return facts

    def rest(self, draft: TunnelGoonsGame, _args: NoArgs, _rng: Random) -> list[Fact]:
        world = draft.payload
        player = world.player
        facts = player.hp.change(player, player.hp.shortfall, "Health", "resting")
        trace = f"the player rests at {world.current.label}"
        facts.append(player.fact("rested", trace, card=f"Rested — Health {player.hp}"))
        return facts

    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        if args.ability is None and args.boost is None:
            draft.pending = PendingDecision(
                kind="level-up",
                prompt="Level up: raise one ability by 1, and Health or Inventory by 1.",
                options=LEVEL_OPTIONS,
                allows_text=False,
            )
            return []
        if args.ability is None or args.boost is None:
            raise Refusal("level_up takes both an ability and a boost, or neither")
        world = draft.payload
        player = world.player
        match args.ability:
            case "brute":
                player.brute += 1
            case "skulker":
                player.skulker += 1
            case "erudite":
                player.erudite += 1
        if args.boost == "health":
            player.hp.maximum += 1
            player.hp.current += 1
        else:
            player.inventory += 1
        player.level += 1
        if (job := world.open_job()) is not None and job.started is not None:
            job.finished = True
        card = f"Level {player.level}: {args.ability.capitalize()} +1, {args.boost.capitalize()} +1"
        return [player.fact("levelled_up", card, card=card)]

    def render_map(self, source: str, kind: ScenarioKind) -> str:
        """One map serves both kinds; Tunnel Goons ships no packs to pick."""
        map_so_far = TAVERN_ASK if kind == "campaign" else "(no map yet — write the opening map)"
        return sections(
            (
                ("YOUR ROLE", self.worldsmith),
                ("SOURCE MATERIAL", source or "(none — write from the setting)"),
                ("MAP SO FAR", map_so_far),
                ("ANSWER WITH", schema_text(MapDraft)),
            )
        )

    def render_extension(self, world: TunnelGoonsWorld, intent: str, hub: Sections = ()) -> str:
        return sections(
            (
                ("YOUR ROLE", self.worldsmith),
                ("SOURCE MATERIAL", world.source or "(none — write from the setting)"),
                ("MAP SO FAR", self.map_so_far(world)),
                *hub,
                ("THE PLAYER", world.line(world.player)),
                ("WHAT THE PLAYER WANTS TO PURSUE", intent),
                ("ANSWER WITH", schema_text(MapDraft)),
            )
        )

    def render_job(self, world: TunnelGoonsWorld, intent: str) -> str:
        return self.render_extension(
            world,
            intent,
            (
                ("JOBS SO FAR", ledger(world.closed_jobs())),
                ("THE BOARD", board_lines(world.board)),
                ("THE HUB", JOB_BRIEF.format(title=world.current.name, place=world.hub)),
            ),
        )

    def render_return(self, world: TunnelGoonsWorld) -> str:
        job = world.open_job()
        verdict = "finished" if job is not None and job.finished else "left open"
        return sections(
            (
                ("YOUR ROLE", self.worldsmith),
                ("SOURCE MATERIAL", world.source or "(none — write from the setting)"),
                ("MAP SO FAR", self.map_so_far(world)),
                ("JOBS SO FAR", ledger(world.closed_jobs())),
                ("THIS JOB", render_history(world.scenes())),
                ("THE BOARD", board_lines(world.board)),
                ("THE VERDICT", verdict),
                ("THE PLAYER", world.line(world.player)),
                ("WHAT COMES NEXT", RETURN_BRIEF.format(title=world.current.name, place=world.hub)),
                ("ANSWER WITH", schema_text(ReturnDraft)),
            )
        )

    def map_so_far(self, world: TunnelGoonsWorld) -> str:
        seen: dict[EntityId, Place] = {}
        for visit in world.visits:
            seen.setdefault(visit.place, world.require_place(visit.place))
        lines: list[str] = []
        for place in seen.values():
            known_ways = ", ".join(
                world.require_place(one.to).name
                for one in world.ways.get(place.id, ())
                if one.known
            )
            lines.append(
                f"{place.name}[{place.id}] — {place.description}\n"
                f"  known ways out: {known_ways or '(none)'}"
            )
        return "\n".join(lines)

    async def write_extension(
        self, draft: TunnelGoonsGame, intent: str, worldsmith: WorldsmithAnswer
    ) -> MapDraft | ReturnDraft:
        world = draft.payload
        if world.at_hub and intent == REPORT_IN:
            if not world.job_open:
                raise Refusal("no job is open to report")
            return await worldsmith(self.render_return(world), ReturnDraft, lambda _written: None)
        if world.at_hub and world.job_open:
            raise Refusal("report the open job first")

        bar = job_refusal if world.at_hub else extension_refusal
        prompt = (
            self.render_job(world, intent) if world.at_hub else self.render_extension(world, intent)
        )
        return await worldsmith(prompt, MapDraft, lambda written: bar(written, world))

    def install_extension(
        self, draft: TunnelGoonsGame, written: MapDraft | ReturnDraft
    ) -> list[Fact]:
        world = draft.payload
        if isinstance(written, ReturnDraft):
            job = world.open_job()
            if job is None or job.started is None:
                raise Refusal("no job is open to report")
            job.debrief = written.debrief
            world.board = written.offers
            return [job_closed(job)]
        if world.at_hub:
            if (refused := job_refusal(written, world)) is not None:
                raise Refusal(refused)
            tavern = world.current
            world.attach(written, written.start, known=True)
            start = written.places[written.start]
            if (job := world.open_job()) is not None and job.started is None:
                world.jobs.pop()
            world.jobs.append(Job(title=start.name, place=written.start))
            trace = f"a way opens from {tavern.name} to {start.name}"
            card = f"A way opens: {start.name}"
            return [Fact(kind="job_taken", told=True, trace=trace, card=card)]
        if (refused := extension_refusal(written, world)) is not None:
            raise Refusal(refused)
        anchor = world.current.name
        world.attach(written, written.start, known=False)
        trace = f"a hidden region opens beyond {anchor}"
        return [Fact(kind="region_added", trace=trace, told=False)]

    def build_scenario(
        self,
        title: str,
        premise: str,
        packs: tuple[Slug, ...],
        written: MapDraft,
        source: str,
        kind: ScenarioKind,
    ) -> AnyScenario:
        bar = hub_refusal if kind == "campaign" else map_refusal
        if (refused := bar(written)) is not None:
            raise Refusal(refused)
        return TunnelGoonsScenario(
            meta=ScenarioMeta(
                title=title, premise=premise or written.places[written.start].description, kind=kind
            ),
            engine=self.id,
            packs=packs,
            payload=opening_canon(written, source, kind),
        )
