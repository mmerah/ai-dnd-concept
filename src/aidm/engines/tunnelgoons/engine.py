from collections.abc import Iterable
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Refusal, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter, Generation, WorldsmithAnswer
from aidm.core.play import DecisionOption, PendingDecision
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import Rows
from aidm.engines.base import (
    CHANGE_WORLD,
    HIRE,
    PLAYER_ID,
    SIGNED_ON,
    Hire,
    hire_request,
    hire_target,
)
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.tools import Move, UnlockWay
from aidm.engines.rooms.world import Item
from aidm.engines.tunnelgoons.tools import ActionRoll, ChangeWorld, LevelUp, level_options
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    STARTING_ITEMS,
    Abilities,
    Ability,
    Goon,
    Npc,
    TunnelGoonsCharacter,
    TunnelGoonsGame,
    TunnelGoonsScenario,
    TunnelGoonsWorld,
)
from aidm.engines.tunnelgoons.worldsmith import AUTHORING, HIRE_GUIDANCE, HIRING, AbilitiesDraft

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


class TunnelGoonsEngine(RoomEngine[Npc, Goon, TunnelGoonsGame]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    game = TunnelGoonsGame
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacter
    dweller = Npc
    world_type = TunnelGoonsWorld
    operations = (*RoomEngine.operations, HIRE)

    def master_tools(self) -> tuple[MasterTool[TunnelGoonsGame], ...]:
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
                "Roll 2d6 plus an ability and helpful items against a Difficulty Score or an "
                "npc; `actor_id` when a hired member acts instead of the player.",
                ActionRoll,
                self.action_roll,
            ),
            master_tool(
                "rest",
                "Spend the night in a safe spot to heal the player's and the party's Health to "
                "full.",
                NoArgs,
                self.rest,
            ),
            master_tool(
                "level_up",
                "Raise one ability and either Health or Inventory Score by 1, once, at the "
                "adventure's end: the player first, then each hired member in turn.",
                LevelUp,
                self.level_up,
            ),
            master_tool(
                "hire",
                "The player hires someone here to work: the worldsmith writes their sheet once "
                "this turn ends, and they join the party. Someone already travelling with the "
                "player may be hired too; a sheet is for someone hired to work, never for one "
                "who merely comes along.",
                Hire,
                self.hire,
            ),
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

    def create_character(self, name: str, brief: str, picks: Picks) -> TunnelGoonsCharacter:
        check_picks(self.creation_steps(picks), picks)
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
            sheet=Abilities(abilities=abilities),
            kit=tuple(picked(picks, f"item-{n}") for n in range(1, STARTING_ITEMS + 1)),
        )
        return TunnelGoonsCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Items", ", ".join(sheet.kit)))

    def starting_items(self, player: Goon, taken: Iterable[str]) -> tuple[Item, ...]:
        return player.starting_items(taken)

    def guidance(self) -> str:
        return AUTHORING

    def change_world(self, draft: TunnelGoonsGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.shared_change(draft.payload, args.change)

    def hire(self, draft: TunnelGoonsGame, args: Hire, _rng: Random) -> list[Fact]:
        world = draft.payload
        member = world.require_hireable(args.entity_id)
        draft.generation, fact = hire_request(member, args.terms)
        return [fact]

    def validate(self, state: TunnelGoonsGame) -> None:
        super().validate(state)
        generation = state.generation
        if generation is not None and generation.operation == HIRE:
            state.payload.require_hireable(hire_target(generation))

    async def advance(
        self, draft: TunnelGoonsGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        if request.operation != HIRE:
            return await super().advance(draft, request, worldsmith)
        world = draft.payload
        member = world.require_hireable(hire_target(request))
        prompt = self.render_extension(
            world,
            HIRING.format(name=member.name, brief=member.brief, terms=request.brief),
            draft.scenario.scope,
            guidance=HIRE_GUIDANCE,
            answer=AbilitiesDraft,
        )
        answer = await worldsmith(prompt, AbilitiesDraft, lambda _draft: None)
        sheet = member.sheet = Abilities(abilities=dict(answer.abilities))
        facts = world.join_party(member.id) if member.id not in world.party else []
        summary = ", ".join(
            f"{ability.capitalize()} {sheet.abilities[ability]}" for ability in ABILITIES
        )
        facts.append(
            member.fact(
                "hired",
                f"{member.label} signs on — {summary}",
                card=f"{member.name} signs on — {summary}",
            )
        )
        return tuple(facts), SIGNED_ON.format(name=member.name)

    def action_roll(self, draft: TunnelGoonsGame, args: ActionRoll, rng: Random) -> list[Fact]:
        world = draft.payload
        actor, sheet = world.require_actor(args.actor_id)
        items = world.carried_items(actor, args.items)
        npc = world.require_npc_here(args.against) if args.against is not None else None
        if npc is actor:
            raise Refusal(f"{actor.name} cannot roll against themselves")
        facts = npc.reveal() if npc is not None else []
        ds = npc.hp.current if npc is not None else args.difficulty
        if ds is None:
            raise Refusal("give a difficulty, or an npc to roll against")

        penalty = 0
        if args.ability in ("brute", "skulker"):
            penalty = max(0, len(list(world.carried(actor.id))) - sheet.inventory)
        rolled, dice_fact = roll((6, 6), f"{args.what} — {args.ability}", rng)
        total = sum(rolled) + sheet.abilities[args.ability] + len(items) - penalty
        success = total >= ds
        margin = total - ds
        outcome = "success" if success else "failure"

        facts.append(dice_fact)
        who = "" if actor is world.player else f"{actor.name}: "
        line = (
            f"{args.what} — {who}{args.ability.capitalize()}"
            + (f" with {', '.join(item.name for item in items)}" if items else "")
            + (f" against {npc.name}" if npc is not None else "")
            + f", {total} vs DS {ds} → {outcome}"
        )
        event = DiceEvent(label="2d6", faces=(6, 6), rolled=rolled)
        facts.append(actor.fact("action_rolled", line, card=line, dice=(event,)))

        # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
        if not args.dangerous:
            return facts
        if npc is not None and success:
            facts.extend(npc.hp.change(npc, -margin, "Health", f"{actor.name}'s action"))
            if npc.hp.current == 0:
                facts.extend(world.kill(npc))
        elif not success:
            facts.extend(actor.hp.change(actor, margin, "Health", args.what))
            if actor.hp.current == 0:
                facts.extend(world.kill(actor))
        return facts

    def rest(self, draft: TunnelGoonsGame, _args: NoArgs, _rng: Random) -> list[Fact]:
        world = draft.payload
        player = world.player
        members = world.members()
        facts = player.hp.change(player, player.hp.shortfall, "Health", "resting")
        for member in members:
            facts.extend(member.hp.change(member, member.hp.shortfall, "Health", "resting"))
        trace = f"{'the party' if members else 'the player'} rests at {world.current.label}"
        facts.append(player.fact("rested", trace, card=f"Rested — Health {player.hp}"))
        return facts

    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        world = draft.payload
        if args.ability is None and args.boost is None:
            actor, _ = world.require_actor(args.actor_id)
            draft.pending = _level_decision(actor)
            return []
        if args.ability is None or args.boost is None:
            raise Refusal("level_up takes both an ability and a boost, or neither")
        actor, sheet = world.require_actor(args.actor_id)
        sheet.abilities[args.ability] += 1
        if args.boost == "health":
            actor.hp.maximum += 1
            actor.hp.current += 1
        else:
            sheet.inventory += 1
        sheet.level += 1
        card = f"Level {sheet.level}: {args.ability.capitalize()} +1, {args.boost.capitalize()} +1"
        if actor is not world.player:
            card = f"{actor.name}: {card}"
        facts = [actor.fact("levelled_up", card, card=card)]
        following = world.next_to_level(actor)
        if following is not None:
            draft.pending = _level_decision(following)
        return facts


def _level_decision(actor: Goon | Npc) -> PendingDecision:
    prompt = f"Level up: {actor.name} — raise one ability by 1, and Health or Inventory by 1."
    return PendingDecision(
        kind="level-up", prompt=prompt, options=level_options(actor.id), allows_text=False
    )
