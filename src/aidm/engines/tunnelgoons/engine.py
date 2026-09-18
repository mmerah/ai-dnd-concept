from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import ClassVar

from aidm.core.creation import CreationStep, Picks, picked
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.facts import Fact, roll
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, lines_of, render_history, section_if
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView, Rows
from aidm.engines.base import (
    PLAYER_ID,
    character_panel,
    here_panel,
    party_panel,
    party_section,
    trail_panel,
)
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
from aidm.engines.rooms.world import MapProposal, RegionProposal
from aidm.engines.rooms.worldsmith import MAP_ASK, OPENING_SECTIONS, check_extension, check_map
from aidm.engines.seam import WRITES_NO, Engine, Written
from aidm.engines.tools import (
    HIRE,
    HIRE_PENDING,
    HIRE_TOOL,
    HIRE_UNWRITTEN,
    NO_HIRE_TARGET,
    SIGNED_ON,
    SIGNS_ON,
    Hire,
)
from aidm.engines.tunnelgoons.tools import (
    LEVEL_UP,
    REST,
    ROLL,
    LevelUp,
    Roll,
)
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    STARTING_ITEMS,
    Ability,
    Goon,
    GoonSheet,
    Npc,
    TunnelGoonsCharacter,
    TunnelGoonsGame,
    TunnelGoonsScenario,
    TunnelGoonsWorld,
    level_up_decision,
    sheet_of,
)
from aidm.engines.tunnelgoons.worldsmith import (
    AUTHORING,
    HIRE_GUIDANCE,
    HIRING,
    AbilitiesProposal,
    TunnelGoonsBody,
    TunnelGoonsHead,
    TunnelGoonsPack,
)

POINT_OPTIONS: tuple[DecisionOption, ...] = tuple(
    DecisionOption(id=str(points), label=str(points)) for points in range(ABILITY_POINTS + 1)
)
EXTEND: Slug = "extend"
MORE_MAP = DecisionOption(
    id=EXTEND, label="More map", detail="The map runs out here: say where you push on."
)
MAP_UNWRITTEN = Fact(
    told=True,
    trace="the map could not be written",
    card="The map could not be written. You are still where you were.",
)


class TunnelGoonsEngine(Engine[TunnelGoonsWorld, TunnelGoonsPack]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    authoring = AUTHORING
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    family_dir = Path(__file__).parents[1] / "rooms"
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacter
    pack = TunnelGoonsPack
    head = TunnelGoonsHead
    body = TunnelGoonsBody
    world = TunnelGoonsWorld
    unwritten: ClassVar[dict[Slug, Fact]] = {EXTEND: MAP_UNWRITTEN, HIRE: HIRE_UNWRITTEN}

    def hire(self, draft: TunnelGoonsGame, args: Hire, _rng: Random) -> list[Fact]:
        member = draft.world.require_hireable(args.target_id)
        draft.generation = Generation(operation=HIRE, detail=args.terms, target=member.id)
        trace = HIRE_PENDING.format(name=member.name, terms=args.terms)
        return [Fact(trace=trace)]

    async def write_hire(
        self, draft: TunnelGoonsGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.target is None:
            raise Refusal(NO_HIRE_TARGET)
        member = draft.world.require_hireable(request.target)
        prompt = self.render_request(
            draft,
            intent=HIRING.format(name=member.name, brief=member.brief, terms=request.detail),
            guidance=HIRE_GUIDANCE,
            answer=AbilitiesProposal,
        )
        answer = await worldsmith(prompt, AbilitiesProposal, lambda _answer: None)
        summary = member.sign_on(answer.abilities)
        world = draft.world
        facts = world.join(member) if member.id not in world.party else []
        trace = SIGNS_ON.format(who=member.mention, summary=summary)
        card = SIGNS_ON.format(who=member.name, summary=summary)
        facts.append(member.fact(trace, card=card))
        return Written(tuple(facts), SIGNED_ON.format(name=member.name))

    async def advance(
        self, draft: TunnelGoonsGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.operation == HIRE:
            return await self.write_hire(draft, request, worldsmith)
        if request.operation == EXTEND:
            self.install(draft, await self.write_next(draft, request.detail, worldsmith))
            return Written((), None)
        raise ValueError(WRITES_NO.format(engine=self.id, operation=request.operation))

    def master_tools(self) -> tuple[MasterTool[TunnelGoonsGame], ...]:
        return (
            *super().master_tools(),
            master_tool("move_item", MOVE_ITEM, MoveItem, self.move_item),
            master_tool(
                "unlock_way", UNLOCK_WAY, UnlockWay, lambda d, a, _: d.world.unlock_way(a.to_id)
            ),
            master_tool("move", MOVE, Move, lambda d, a, _: d.world.move(a.to_id, a.with_ids)),
            master_tool("meanwhile", MEANWHILE, Meanwhile, self.meanwhile),
            master_tool("hire", HIRE_TOOL, Hire, self.hire),
            master_tool("rest", REST, NoArgs, lambda d, _a, _: d.world.rest()),
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("level_up", LEVEL_UP, LevelUp, self.level_up),
        )

    def creation_steps(self, pack_id: Slug, _picks: Picks) -> tuple[CreationStep, ...]:
        ability_steps = tuple(
            CreationStep(
                id=ability,
                label=f"Points in {ability.capitalize()}",
                options=POINT_OPTIONS,
                hint=f"{ABILITY_POINTS} points across the three",
            )
            for ability in ABILITIES
        )
        hint = ", ".join(name for pack in self.packs.played(pack_id) for name in pack.items)
        item_steps = tuple(
            CreationStep(id=f"item-{number}", label=f"Item {number}", hint=hint)
            for number in range(1, STARTING_ITEMS + 1)
        )
        return (*ability_steps, *item_steps)

    def build_character(
        self, name: str, brief: str, _pack_id: Slug, picks: Picks
    ) -> TunnelGoonsCharacter:
        abilities: dict[Ability, int] = {
            ability: int(picked(picks, ability)) for ability in ABILITIES
        }
        if sum(abilities.values()) != ABILITY_POINTS:
            raise Refusal(f"the three abilities share exactly {ABILITY_POINTS} points")
        sheet = Goon(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            sheet=GoonSheet(abilities=abilities),
            kit=tuple(picked(picks, f"item-{number}") for number in range(1, STARTING_ITEMS + 1)),
        )
        sheet.unpack_kit(())
        return self.sheet_character(name, sheet)

    def player_of(self, character: AnyCharacter) -> Goon:
        return self.player_as(character, Goon)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Items", ", ".join(sheet.kit)))

    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> TunnelGoonsWorld:
        draft: MapProposal[Npc] = scenario.opening
        check_map(draft)
        player = self.player_of(character)
        taken = (*draft.places, *draft.npcs, *draft.items)
        return self.world.opening(draft, player, player.unpack_kit(taken))

    def family_sections(self, draft: TunnelGoonsGame) -> Sections:
        world = draft.world
        return (
            ("MAP SO FAR", world.map_so_far()),
            *section_if("THE ARC SO FAR", world.arc),
            ("SCENES SO FAR", render_history(draft.log)),
            ("THE PLAYER", world.line(world.player)),
        )

    def master_sections(self, state: TunnelGoonsGame) -> Sections:
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

    def narrator_view(self, state: TunnelGoonsGame) -> NarratorView:
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

    def player_view(self, state: TunnelGoonsGame) -> PlayerView:
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

    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        pack_id: Slug,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario:
        def built(draft: MapProposal[Npc]) -> AnyScenario:
            start = draft.places.get(draft.start)
            premise = "" if start is None else start.description
            return self.build_scenario(meta, pack_id, draft, source, premise)

        model = MapProposal[Npc]
        prompt = self.render_worldsmith(
            source,
            meta.scope,
            OPENING_SECTIONS,
            MAP_ASK,
            self.guidance(pack_id, opening=True),
            model,
        )
        return built(await worldsmith(prompt, model, lambda answer: check(built(answer))))

    def act(self, draft: TunnelGoonsGame, action: Slug, words: str) -> None:
        if action != EXTEND or draft.world.frontier():
            raise Refusal("the map still has ways to walk; the page was drawn before them")
        if not words:
            raise Refusal("say where you push on")
        draft.generation = Generation(operation=EXTEND, detail=words)

    def move_item(self, draft: TunnelGoonsGame, args: MoveItem, _rng: Random) -> list[Fact]:
        return draft.world.move_item(args.item_id, args.to_id)

    def meanwhile(self, draft: TunnelGoonsGame, args: Meanwhile, _rng: Random) -> list[Fact]:
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

    async def write_next(
        self, draft: TunnelGoonsGame, intent: str, worldsmith: WorldsmithAnswer
    ) -> RegionProposal[Npc]:
        world = draft.world
        model = RegionProposal[Npc]
        prompt = self.render_request(
            draft, intent=intent, guidance=self.guidance(draft.pack_id, opening=False), answer=model
        )
        return await worldsmith(prompt, model, lambda answer: check_extension(answer, world))

    def install(self, draft: TunnelGoonsGame, extension: RegionProposal[Npc]) -> None:
        """Hidden, so nothing is told: the region reaches the player only as they walk it."""
        draft.world.attach(extension, extension.start)
        draft.log[-1].recap = extension.recap
        self.open_chapter(draft)

    def roll(self, draft: TunnelGoonsGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.world
        world.check_unnamed(args.what)
        actor = world.require_actor(args.actor_id)
        sheet = sheet_of(actor)
        items = world.carried_items(actor, args.item_ids)
        npc = world.require_member_here(args.target_id) if args.target_id is not None else None
        if npc is actor:
            raise Refusal(f"{actor.name} cannot roll against themselves")
        ds = npc.hp.current if npc is not None else args.difficulty
        if ds is None:
            raise ValueError("a roll names an npc or a difficulty, by `Roll._one_target`")
        penalty = 0
        if args.ability in ("brute", "skulker"):
            penalty = max(0, len(list(world.carried(actor.id))) - sheet.inventory)

        rolled = roll((6, 6), f"{args.what} — {args.ability}", rng)
        total = rolled.total + sheet.abilities[args.ability] + len(items) - penalty
        success = total >= ds
        outcome = "success" if success else "failure"
        line = (
            f"{args.what} — {actor.card_line(args.ability.capitalize())}"
            + (f" with {', '.join(item.name for item in items)}" if items else "")
            + (f" against {npc.name}" if npc is not None else "")
            + f", {total} vs DS {ds} → {outcome}"
        )
        facts = [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,))]

        # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
        if not args.dangerous:
            return facts
        margin = total - ds
        if npc is not None and success:
            facts.extend(npc.change(npc.hp, -margin, "Health", f"{actor.name}'s action"))
            if npc.hp.current == 0:
                facts.extend(world.kill(npc.id))
        elif not success:
            facts.extend(actor.change(actor.hp, margin, "Health", args.what))
            if actor.hp.current == 0:
                facts.extend(world.kill(actor.id))
        return facts

    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        world = draft.world
        actor = world.require_actor(args.actor_id)
        if sheet_of(actor).level > 1:
            raise Refusal(f"{actor.name} has already levelled up")
        # Both or neither, by `LevelUp`; `or` narrows both for the fall-through.
        if args.ability is None or args.boost is None:
            draft.pending = level_up_decision(actor)
            return []
        facts = actor.level(args.ability, args.boost)
        following = world.next_to_level(actor)
        if following is not None:
            draft.pending = level_up_decision(following)
        return facts
