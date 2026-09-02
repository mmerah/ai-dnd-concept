from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, require_unique
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.engines.core import counter_fact, entity_fact, pool
from aidm.engines.tunnelgoons.world import (
    ABILITIES,
    Ability,
    Boost,
    Goon,
    Item,
    Npc,
    Place,
    TunnelGoonsGame,
    TunnelWorld,
    Visit,
    Way,
)

CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)

_LEVEL_OPTIONS: tuple[PendingOption, ...] = tuple(
    PendingOption(
        id=f"{ability}-{boost}",
        label=f"{ability.capitalize()} +1, {boost.capitalize()} +1",
        name="level_up",
        args={"ability": ability, "boost": boost},
    )
    for ability in ABILITIES
    for boost in ("health", "inventory")
)
type WorldChange = Reveal | MoveItem | Kill


class Reveal(Frozen):
    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of something hidden here: an npc or an item."
    )


class MoveItem(Frozen):
    verb: Literal["move_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item here or carried.")
    to: CheckedEntityId = Field(description="Exact id of the player, an npc here, or this place.")


class Kill(Frozen):
    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of an npc here.")


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Move(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the place to move to.")
    with_ids: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of living NPCs here who come along."
    )


class UnlockWay(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the locked way's destination.")


class ActionRoll(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
    ability: Ability = Field(description="Which ability the action calls on.")
    items: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of items the player carries that plainly help; +1 each."
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Difficulty Score; the SRD's guidelines: 8 easy, 10 moderate, 12 hard. Null when "
            "`against` names an NPC."
        ),
    )
    against: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of an npc here; its Health is the Difficulty Score.",
    )
    dangerous: bool = Field(
        default=False,
        description=(
            "A fight, a trap, a fall: the margin becomes damage, to the NPC on a hit or to "
            "the player on a miss."
        ),
    )

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.difficulty is None) == (self.against is None):
            raise ValueError("give a difficulty, or an npc to roll against, not both/neither")
        return self


class LevelUp(Frozen):
    ability: Ability | None = Field(
        default=None, description="Which ability to raise by 1; null asks the player."
    )
    boost: Boost | None = Field(
        default=None, description="Health or Inventory to raise by 1; null asks the player."
    )


def apply_change(world: TunnelWorld, change: WorldChange) -> list[Fact]:
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    match change:
        case Reveal():
            return _reveal(world, change)
        case MoveItem():
            return _move_item(world, change)
        case Kill():
            return _kill(world, change)


def change_world(draft: TunnelGoonsGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
    return apply_change(draft.payload.world, args.change)


def move(draft: TunnelGoonsGame, args: Move, _rng: Random) -> list[Fact]:
    world = draft.payload.world
    here, destination, way = _here_and_way(world, args.to_id)
    if way is None:
        options = ", ".join(world.require_place(one.to).name for one in world.ways.get(here.id, ()))
        raise ValueError(
            f"no way leads from {here.name} to {destination.name}; ways out: {options or '(none)'}"
        )
    if way.locked:
        raise ValueError(f"the way to {destination.name} is locked and must be dealt with first")
    way.known = True
    back = world.way(destination.id, here.id)
    if back is not None:
        back.known = True
    facts = world.reveal(destination)
    require_unique("with_ids", args.with_ids)
    coming: list[Npc] = []
    for npc_id in args.with_ids:
        if npc_id == world.player.id:
            raise ValueError("the player already comes along")
        coming.append(world.require_npc_here(npc_id))
    world.player.place = destination.id
    for npc in coming:
        npc.place = destination.id
    world.visits.append(Visit(place=destination.id, job=world.visit.job))
    trace = f"the player arrives at {world.label(destination)}"
    if coming:
        names = " and ".join(npc.name for npc in coming)
        verb = "comes" if len(coming) == 1 else "come"
        trace += f", and {names} {verb} along"
    facts.append(entity_fact(destination, "arrived", trace, card=f"Arrived at {destination.name}"))
    return facts


def unlock_way(draft: TunnelGoonsGame, args: UnlockWay, _rng: Random) -> list[Fact]:
    world = draft.payload.world
    here, destination, way = _here_and_way(world, args.to_id)
    if way is None:
        raise ValueError(f"no way leads from {here.name} to {destination.name}")
    if not way.locked:
        raise ValueError(f"the way from {here.name} to {destination.name} is not locked")
    way.locked = False
    trace = f"the way from {world.label(here)} to {world.label(destination)} is unlocked"
    card = f"{destination.name} unlocked"
    return [entity_fact(here, "way_unlocked", trace, narrate=way.known and here.known, card=card)]


def action_roll(draft: TunnelGoonsGame, args: ActionRoll, rng: Random) -> list[Fact]:
    world = draft.payload.world
    player = world.player
    items = _carried_items(world, player, args.items)
    npc = world.require_npc_here(args.against) if args.against is not None else None
    facts = list(world.reveal(npc)) if npc is not None else []
    ds = npc.hp.current if npc is not None else args.difficulty
    if ds is None:
        raise ValueError("give a difficulty, or an npc to roll against")

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
    facts.append(entity_fact(player, "action_rolled", trace, card=card, dice=(event,)))

    # SRD: only a dangerous action turns the margin into damage; an npc's DS alone does not.
    if not args.dangerous:
        return facts
    if npc is not None and success:
        facts.extend(counter_fact(npc, npc.hp, -margin, "Health", "the player's action", player.id))
        if npc.hp.current == 0:
            npc.alive = False
            slain = f"{world.label(npc)} is slain"
            facts.append(entity_fact(npc, "npc_slain", slain, card=f"{npc.name} is slain"))
    elif not success:
        facts.extend(counter_fact(player, player.hp, margin, "Health", args.what, player.id))
        if player.hp.current == 0:
            player.alive = False
            dead = f"{world.label(player)} is dead"
            facts.append(entity_fact(player, "goon_killed", dead, card="You are dead"))
    return facts


def rest(draft: TunnelGoonsGame, _args: NoArgs, _rng: Random) -> list[Fact]:
    world = draft.payload.world
    player = world.player
    facts = counter_fact(
        player, player.hp, player.hp.maximum - player.hp.current, "Health", "resting", player.id
    )
    trace = f"the player rests at {world.label(world.current)}"
    facts.append(entity_fact(player, "rested", trace, card=f"Rested — Health {pool(player.hp)}"))
    return facts


def level_up(draft: TunnelGoonsGame, args: LevelUp, _rng: Random) -> list[Fact]:
    if args.ability is None and args.boost is None:
        draft.pending = PendingDecision(
            kind="level-up",
            prompt="Level up: raise one ability by 1, and Health or Inventory by 1.",
            options=_LEVEL_OPTIONS,
            allows_text=False,
        )
        return []
    if args.ability is None or args.boost is None:
        raise ValueError("level_up takes both an ability and a boost, or neither")
    world = draft.payload.world
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
    if world.job_open:
        world.job_done = True
    card = f"Level {player.level}: {args.ability.capitalize()} +1, {args.boost.capitalize()} +1"
    return [entity_fact(player, "levelled_up", card, card=card)]


def tools() -> tuple[MasterTool[TunnelGoonsGame], ...]:
    move_desc = "Move through an unlocked way from the player's current place."
    unlock_desc = "Unlock a locked way out of the player's current place."
    roll_desc = "Roll 2d6 plus an ability and helpful items against a Difficulty Score or an npc."
    rest_desc = "Spend the night in a safe spot to heal the player's Health to full."
    level_desc = (
        "Raise one ability and either Health or Inventory Score by 1 at an adventure's end. In a "
        "campaign, call it when the job's dungeon is done; the tavern then closes the job as "
        "finished."
    )
    return (
        master_tool("change_world", CHANGE_WORLD, ChangeWorld, change_world),
        master_tool("move", move_desc, Move, move),
        master_tool("unlock_way", unlock_desc, UnlockWay, unlock_way),
        master_tool("action_roll", roll_desc, ActionRoll, action_roll),
        master_tool("rest", rest_desc, NoArgs, rest),
        master_tool("level_up", level_desc, LevelUp, level_up),
    )


def _here_and_way(world: TunnelWorld, to_id: EntityId) -> tuple[Place, Place, Way | None]:
    here = world.current
    destination = world.require_place(to_id)
    return here, destination, world.way(here.id, destination.id)


def _reveal(world: TunnelWorld, change: Reveal) -> list[Fact]:
    one = world.require(change.entity_id)
    holders = {world.current.id, *(member.id for member in world.here())}
    location = one.place if isinstance(one, Npc) else one.on if isinstance(one, Item) else None
    if location not in holders:
        raise ValueError(f"{one.name} is not here with the player")
    found = "found" if isinstance(one, Item) else "discovered"
    if one.known:
        raise ValueError(f"the player has already {found} {one.name}")
    one.known = True
    trace = f"learned of {world.label(one)}"
    return [entity_fact(one, "entity_discovered", trace, card=f"{one.name} {found}")]


def _move_item(world: TunnelWorld, change: MoveItem) -> list[Fact]:
    item = world.require_item_here(change.item_id)
    to = change.to
    if to != world.player.id and to != world.current.id:
        npc = next((one for one in world.here() if one.id == to and one.alive), None)
        if npc is None:
            raise ValueError(
                f"{to!r} cannot hold {item.name}; give the player, a living npc here, or this place"
            )
    holder = world.require(to)
    if not holder.known:
        raise ValueError(f"the player has not met {holder.name}; reveal them first")
    if item.on == to:
        raise ValueError(f"{item.name} is already there")
    facts = world.reveal(item)
    item.on = to
    card = f"Took {item.name}" if to == world.player.id else f"{item.name} → {holder.name}"
    trace = f"{world.label(item)} moves to {world.label(holder)}"
    return [*facts, entity_fact(item, "entity_moved", trace, card=card)]


def _kill(world: TunnelWorld, change: Kill) -> list[Fact]:
    npc = world.require_npc_here(change.entity_id)
    facts = world.reveal(npc)
    npc.alive = False
    dropped = list(world.carried(npc.id))
    for item in dropped:
        item.on = world.current.id
    if dropped:
        facts.append(
            Fact(
                kind="items_dropped",
                trace=", ".join(world.label(item) for item in dropped) + " fell loose here",
            )
        )
    facts.append(
        entity_fact(npc, "actor_killed", f"{world.label(npc)} is dead", card=f"{npc.name} is dead")
    )
    return facts


def _carried_items(
    world: TunnelWorld, player: Goon, item_ids: tuple[EntityId, ...]
) -> tuple[Item, ...]:
    require_unique("items", item_ids)
    items: list[Item] = []
    for item_id in item_ids:
        item = world.items.get(item_id)
        if item is None or item.on != player.id:
            raise ValueError(f"{item_id!r} is not in the player's hands")
        items.append(item)
    return tuple(items)
