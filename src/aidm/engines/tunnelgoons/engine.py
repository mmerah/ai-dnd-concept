from collections.abc import Iterable
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Refusal, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption, PendingDecision
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import Rows
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID
from aidm.engines.rooms.engine import RoomEngine
from aidm.engines.rooms.tools import Move, UnlockWay
from aidm.engines.rooms.world import Item
from aidm.engines.tunnelgoons.tools import LEVEL_OPTIONS, ActionRoll, ChangeWorld, LevelUp
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    ABILITY_POINTS,
    STARTING_ITEMS,
    Ability,
    Goon,
    Npc,
    TunnelGoonsCharacter,
    TunnelGoonsGame,
    TunnelGoonsScenario,
    TunnelGoonsWorld,
)
from aidm.engines.tunnelgoons.worldsmith import AUTHORING

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
            abilities=abilities,
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
        total = sum(rolled) + player.abilities[args.ability] + len(items) - penalty
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
        player.abilities[args.ability] += 1
        if args.boost == "health":
            player.hp.maximum += 1
            player.hp.current += 1
        else:
            player.inventory += 1
        player.level += 1
        if (job := world.walked_job()) is not None:
            job.finished = True
        card = f"Level {player.level}: {args.ability.capitalize()} +1, {args.boost.capitalize()} +1"
        return [player.fact("levelled_up", card, card=card)]
