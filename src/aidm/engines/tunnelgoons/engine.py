from collections.abc import Iterable
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Refusal, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption, PendingDecision
from aidm.core.prompt import Pairs
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.engines.base import PLAYER_ID
from aidm.engines.hiring import Hiring
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.world import Prop
from aidm.engines.tunnelgoons.tools import (
    LEVEL_UP,
    REST,
    ROLL,
    LevelUp,
    Roll,
    level_options,
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


class TunnelGoonsEngine(
    Hiring[Goon, Npc, TunnelGoonsGame, AbilitiesDraft],
    RoomEngine[Npc, Goon, TunnelGoonsGame],
):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    directory = Path(__file__).parent
    game = TunnelGoonsGame
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacter
    dweller = Npc
    world_type = TunnelGoonsWorld
    member = Npc
    hire_answer = AbilitiesDraft

    def master_tools(self) -> tuple[MasterTool[TunnelGoonsGame], ...]:
        return (
            *super().master_tools(),
            master_tool("rest", REST, NoArgs, self.rest),
            master_tool("roll", ROLL, Roll, self.roll),
            master_tool("level_up", LEVEL_UP, LevelUp, self.level_up),
        )

    def creation_steps(self, _picks: Picks) -> tuple[CreationStep, ...]:
        ability_steps = tuple(
            CreationStep(
                id=ability,
                label=f"Points in {ability.capitalize()}",
                options=POINT_OPTIONS,
                hint=f"{ABILITY_POINTS} points across the three",
            )
            for ability in ABILITIES
        )
        item_steps = tuple(
            CreationStep(id=f"item-{n}", label=f"Item {n}", hint=", ".join(STARTING_ITEM_LIST))
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
            sheet=GoonSheet(abilities=abilities),
            kit=tuple(picked(picks, f"item-{n}") for n in range(1, STARTING_ITEMS + 1)),
        )
        return TunnelGoonsCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def preview_character(self, character: AnyCharacter) -> Pairs:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Items", ", ".join(sheet.kit)))

    def starting_items(self, player: Goon, taken: Iterable[str]) -> tuple[Prop, ...]:
        return player.unpack_kit(taken)

    def guidance(self) -> str:
        return AUTHORING

    def rest(self, draft: TunnelGoonsGame, _args: NoArgs, _rng: Random) -> list[Fact]:
        return draft.payload.rest()

    def hire_prompt(self, draft: TunnelGoonsGame, member: Npc, terms: str) -> str:
        return self.render_request(
            draft,
            intent=HIRING.format(name=member.name, brief=member.brief, terms=terms),
            guidance=HIRE_GUIDANCE,
            answer=AbilitiesDraft,
        )

    def install_sheet(self, member: Npc, answer: AbilitiesDraft) -> str:
        sheet = member.sheet = GoonSheet(abilities=dict(answer.abilities))
        return ", ".join(
            f"{ability.capitalize()} {sheet.abilities[ability]}" for ability in ABILITIES
        )

    def roll(self, draft: TunnelGoonsGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_actor(args.actor_id)
        sheet = actor.require_sheet()
        items = world.carried_items(actor, args.items)
        npc = world.require_member_here(args.against) if args.against is not None else None
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
        facts.append(actor.fact(line, card=line, dice=(event,)))

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

    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        world = draft.payload
        if args.ability is None and args.boost is None:
            actor = world.require_actor(args.actor_id)
            draft.pending = _level_decision(actor)
            return []
        if args.ability is None or args.boost is None:
            raise Refusal("level_up takes both an ability and a boost, or neither")
        actor = world.require_actor(args.actor_id)
        sheet = actor.require_sheet()
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
        facts = [actor.fact(card, card=card)]
        following = world.next_to_level(actor)
        if following is not None:
            draft.pending = _level_decision(following)
        return facts


def _level_decision(actor: Goon | Npc) -> PendingDecision:
    prompt = f"Level up: {actor.name} — raise one ability by 1, and Health or Inventory by 1."
    return PendingDecision(
        kind="level-up", prompt=prompt, options=level_options(actor.id), allows_text=False
    )
