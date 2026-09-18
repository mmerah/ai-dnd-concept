from collections.abc import Mapping
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, picked
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.facts import Fact, roll
from aidm.core.model import AnyCharacter, AnyScenario, Commission, WorldsmithAnswer
from aidm.core.play import DecisionOption
from aidm.core.tools import NoArgs, tool
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Gauge
from aidm.engines.engine import Operation, Written
from aidm.engines.hiring import (
    HIRE,
    HIRE_UNWRITTEN,
    Hire,
    file_hire,
    hire_target,
    signed_on,
)
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.world import MapProposal
from aidm.engines.rooms.worldsmith import check_map
from aidm.engines.tunnelgoons.pack import (
    AUTHORING,
    HIRE_GUIDANCE,
    HIRING,
    AbilitiesProposal,
    TunnelGoonsBody,
    TunnelGoonsHead,
    TunnelGoonsPack,
)
from aidm.engines.tunnelgoons.tools import LevelUp, Roll
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    HP_START,
    STARTING_ITEMS,
    Ability,
    Goon,
    GoonSheet,
    TunnelGoonsCharacter,
    TunnelGoonsGame,
    TunnelGoonsScenario,
    TunnelGoonsWorld,
    level_up_decision,
)

POINT_OPTIONS: tuple[DecisionOption, ...] = tuple(
    DecisionOption(id=str(points), name=str(points)) for points in range(ABILITY_POINTS + 1)
)


class TunnelGoonsEngine(RoomEngine[Goon, TunnelGoonsWorld, TunnelGoonsPack]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    authoring = AUTHORING
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacter
    pack = TunnelGoonsPack
    head = TunnelGoonsHead
    body = TunnelGoonsBody
    world = TunnelGoonsWorld
    member = Goon

    def operations(self) -> Mapping[Slug, Operation[TunnelGoonsWorld]]:
        return {**super().operations(), HIRE: Operation(self.write_hire, HIRE_UNWRITTEN)}

    @tool
    def hire(self, draft: TunnelGoonsGame, args: Hire, _rng: Random) -> list[Fact]:
        """Call this when the player hires a character here to work. The player can also hire a
        character who already travels with the player. The worldsmith writes the sheet of that
        character at the end of the turn. Nothing more happens this turn. Give a sheet only to a
        character hired to work. Do not give a sheet to a character who only travels along."""
        return file_hire(draft, args.target_id, args.terms)

    async def write_hire(
        self, draft: TunnelGoonsGame, commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        member = hire_target(draft.world, commission)
        prompt = self.render_commission(
            draft,
            intent=HIRING.format(name=member.name, brief=member.brief, terms=commission.detail),
            guidance=HIRE_GUIDANCE,
            answer_model=AbilitiesProposal,
        )
        answer = await worldsmith(prompt, AbilitiesProposal, lambda _answer: None)
        summary = member.sign_on(answer.abilities)
        return signed_on(draft.world, member, summary)

    @tool
    def rest(self, draft: TunnelGoonsGame, _args: NoArgs, _rng: Random) -> list[Fact]:
        """The player and the party rest here for one night. Their Health goes to full."""
        return draft.world.rest()

    def creation_steps(self, pack_id: Slug, _picks: Picks) -> tuple[CreationStep, ...]:
        ability_steps = tuple(
            CreationStep(
                id=ability,
                name=f"Points in {ability.capitalize()}",
                options=POINT_OPTIONS,
                hint=f"{ABILITY_POINTS} points across the three",
            )
            for ability in ABILITIES
        )
        hint = ", ".join(name for pack in self.packs.played(pack_id) for name in pack.items)
        item_steps = tuple(
            CreationStep(id=f"item-{number}", name=f"Item {number}", hint=hint)
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
        # The player's `place` is never read: where they stand is `RoomWorld.current`.
        sheet = Goon(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            place=PLAYER_ID,
            hp=Gauge(current=HP_START, maximum=HP_START),
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
        draft: MapProposal[Goon] = scenario.opening
        check_map(draft)
        player = self.player_of(character)
        taken = (*draft.places, *draft.npcs, *draft.items)
        return self.world.opening(draft, player, player.unpack_kit(taken))

    @tool
    def roll(self, draft: TunnelGoonsGame, args: Roll, rng: Random) -> list[Fact]:
        """Call this for an uncertain action that has a real cost. The engine rolls 2d6, adds
        the ability and the items, and reads the total."""
        world = draft.world
        world.check_unnamed(args.what)
        actor = world.require_actor(args.actor_id)
        sheet = actor.require_sheet()
        items = world.carried_items(actor, args.item_ids)
        npc = world.require_member_here(args.target_id) if args.target_id is not None else None
        if npc is actor:
            raise Refusal(f"{actor.name} cannot roll against themselves")
        difficulty = npc.hp.current if npc is not None else args.difficulty
        if difficulty is None:
            raise ValueError("a roll names an npc or a difficulty, by `Roll._one_target`")
        penalty = 0
        if args.ability in ("brute", "skulker"):
            penalty = max(0, len(list(world.carried(actor.id))) - sheet.inventory)

        rolled = roll((6, 6), f"{args.what} — {args.ability}", rng)
        total = rolled.total + sheet.abilities[args.ability] + len(items) - penalty
        success = total >= difficulty
        outcome = "success" if success else "failure"
        led = actor.card_line(args.ability.capitalize(), leads=actor is world.player)
        line = (
            f"{args.what} — {led}"
            + (f" with {', '.join(item.name for item in items)}" if items else "")
            + (f" against {npc.name}" if npc is not None else "")
            + f", {total} vs DS {difficulty} → {outcome}"
        )
        facts = [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,))]

        # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
        if not args.dangerous:
            return facts
        margin = total - difficulty
        if npc is not None and success:
            facts.extend(npc.change(npc.hp, -margin, "Health", f"{actor.name}'s action"))
            if npc.hp.current == 0:
                facts.extend(world.kill(npc.id))
        elif not success:
            facts.extend(actor.change(actor.hp, margin, "Health", args.what))
            if actor.hp.current == 0:
                facts.extend(world.kill(actor.id))
        return facts

    @tool
    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        """Call this one time, when the whole adventure ends. The engine gives the choice to the
        player first, then to each living hired member in turn."""
        world = draft.world
        player = world.player
        actor = player if player.require_sheet().level == 1 else world.next_to_level(player)
        if actor is None:
            raise Refusal("the player and every hired member have already levelled up")
        # Both or neither, by `LevelUp`; `or` narrows both for the fall-through.
        if args.ability is None or args.boost is None:
            draft.pending = level_up_decision(actor)
            return []
        facts = actor.level(args.ability, args.boost)
        following = world.next_to_level(actor)
        if following is not None:
            draft.pending = level_up_decision(following)
        return facts
