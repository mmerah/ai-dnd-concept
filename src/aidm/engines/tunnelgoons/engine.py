from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, picked
from aidm.core.entities import EngineId, Refusal, slug
from aidm.core.facts import Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption, PendingDecision
from aidm.core.prompt import Pairs
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import DiceLook, Look
from aidm.engines.base import PLAYER_ID
from aidm.engines.hiring import Hiring, hiring
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
    Adventurer,
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


@dataclass(frozen=True, slots=True)
class Pool:
    faces: tuple[int, ...]
    label: str
    items: tuple[Prop, ...]
    npc: Npc | None
    difficulty: int
    penalty: int


class TunnelGoonsEngine(RoomEngine[Npc, Goon, TunnelGoonsGame]):
    id = EngineId("tunnelgoons")
    title = "TUNNEL GOONS"
    art_style = "Old-school fantasy illustration in black ink, cross-hatched, no text or lettering."
    look = Look(
        palette={
            "game-bg": "#191411",
            "game-surface": "#261e18",
            "game-surface-raised": "#34281f",
            "game-text": "#f4e7d5",
            "game-muted": "#c6b29c",
            "game-border": "#534030",
            "game-accent": "#eab078",
            "game-wash": "rgba(234, 176, 120, .08)",
            "game-radius": "8px",
        },
        dice=DiceLook(body="#3b4048", ink="#f3efe6", glow="#7fb069"),
    )
    directory = Path(__file__).parent
    game = TunnelGoonsGame
    scenario = TunnelGoonsScenario
    character = TunnelGoonsCharacter
    world = TunnelGoonsWorld
    member = Npc

    def world_of(self, state: TunnelGoonsGame) -> TunnelGoonsWorld:
        return state.payload

    def hiring(self) -> Hiring[TunnelGoonsGame, Npc]:
        return hiring(AbilitiesDraft, self.hire_prompt, self.install_sheet)

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
        return self.world_of(draft).rest()

    def hire_prompt(self, draft: TunnelGoonsGame, member: Npc, terms: str) -> str:
        return self.render_request(
            draft,
            intent=HIRING.format(name=member.name, brief=member.brief, terms=terms),
            guidance=HIRE_GUIDANCE,
            answer=AbilitiesDraft,
        )

    def install_sheet(self, member: Npc, answer: AbilitiesDraft) -> str:
        sheet = GoonSheet(abilities=dict(answer.abilities))
        member.take_sheet(sheet)
        return ", ".join(
            f"{ability.capitalize()} {sheet.abilities[ability]}" for ability in ABILITIES
        )

    def roll(self, draft: TunnelGoonsGame, args: Roll, rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        actor = world.require_actor(args.actor_id)
        sheet = actor.require_sheet()
        pool = _pool(world, actor, args)
        facts = pool.npc.reveal() if pool.npc else []
        rolled = roll(pool.faces, f"{args.what} — {pool.label}", rng)
        total = rolled.total + sheet.abilities[args.ability] + len(pool.items) - pool.penalty
        success = total >= pool.difficulty
        line = _line(world, actor, args, pool, total, success)
        facts += [rolled.fact, actor.fact(line, card=line, dice=(rolled.event,))]
        facts += _consequence(world, actor, args, pool, total, success)
        return facts

    def level_up(self, draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
        world = self.world_of(draft)
        # Both or neither, by `LevelUp`; `or` narrows both for the fall-through.
        if args.ability is None or args.boost is None:
            actor = world.require_actor(args.actor_id)
            draft.pending = _level_decision(actor)
            return []
        actor = world.require_actor(args.actor_id)
        facts = actor.level(args.ability, args.boost)
        following = world.next_to_level(actor)
        if following is not None:
            draft.pending = _level_decision(following)
        return facts


def _level_decision(actor: Adventurer) -> PendingDecision:
    prompt = f"Level up: {actor.name} — raise one ability by 1, and Health or Inventory by 1."
    return PendingDecision(
        kind="level-up", prompt=prompt, options=level_options(actor.id), allows_text=False
    )


def _pool(world: TunnelGoonsWorld, actor: Adventurer, args: Roll) -> Pool:
    items = world.carried_items(actor, args.items)
    npc = world.require_member_here(args.against) if args.against is not None else None
    if npc is actor:
        raise Refusal(f"{actor.name} cannot roll against themselves")
    difficulty = npc.hp.current if npc is not None else args.difficulty
    if difficulty is None:
        raise Refusal("give a difficulty, or an npc to roll against")
    penalty = 0
    if args.ability in ("brute", "skulker"):
        penalty = max(0, len(list(world.carried(actor.id))) - actor.require_sheet().inventory)
    return Pool(
        faces=(6, 6),
        label=args.ability,
        items=items,
        npc=npc,
        difficulty=difficulty,
        penalty=penalty,
    )


def _line(
    world: TunnelGoonsWorld, actor: Adventurer, args: Roll, pool: Pool, total: int, success: bool
) -> str:
    who = "" if actor is world.player else f"{actor.name}: "
    outcome = "success" if success else "failure"
    return (
        f"{args.what} — {who}{args.ability.capitalize()}"
        + (f" with {', '.join(item.name for item in pool.items)}" if pool.items else "")
        + (f" against {pool.npc.name}" if pool.npc is not None else "")
        + f", {total} vs DS {pool.difficulty} → {outcome}"
    )


def _consequence(
    world: TunnelGoonsWorld, actor: Adventurer, args: Roll, pool: Pool, total: int, success: bool
) -> list[Fact]:
    # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
    if not args.dangerous:
        return []
    margin = total - pool.difficulty
    facts: list[Fact] = []
    if pool.npc is not None and success:
        facts.extend(pool.npc.change(pool.npc.hp, -margin, "Health", f"{actor.name}'s action"))
        if pool.npc.hp.current == 0:
            facts.extend(world.kill(pool.npc.id))
    elif not success:
        facts.extend(actor.change(actor.hp, margin, "Health", args.what))
        if actor.hp.current == 0:
            facts.extend(world.kill(actor.id))
    return facts
