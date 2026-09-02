from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.engines.breathless.creation import Pack
from aidm.engines.breathless.world import (
    CARRY,
    LOOT_START,
    MED_KIT_CLEARS,
    STUNT_DIE,
    BreathlessGame,
    BreathlessWorld,
    Die,
    Item,
    Skill,
    Survivor,
    stepped,
)
from aidm.engines.core import CHANGE_WORLD, counter_fact, entity_fact, sentence
from aidm.engines.scenes.world import NEXT_SCENE, Enter, Kill, Leave, NextScene, Reveal

SRD_PACK: Slug = "srd"
SWAP = "swap-"
type WorldChange = Reveal | Enter | Leave | Kill | DropItem


class DropItem(Frozen):
    """Take an item out of the player's backpack for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Check(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
    skill: Skill | None = Field(
        default=None, description="Which of the six skills the action calls on."
    )
    item_id: CheckedEntityId | None = Field(
        default=None, description="Exact id of a carried item used instead of a skill."
    )
    stunt: bool = Field(
        default=False,
        description="True to attempt an extraordinary stunt at d12 instead of a skill or item.",
    )
    dangerous: bool = Field(
        default=False, description="True when a fail would plainly hurt the player."
    )

    @model_validator(mode="after")
    def _one_thing(self) -> Self:
        if sum((self.skill is not None, self.item_id is not None, self.stunt)) != 1:
            raise ValueError("roll one thing: a skill, an item, or a stunt")
        return self


class ChangeStress(Frozen):
    amount: int = Field(
        description="How much stress changes: positive for a complication's cost, negative to "
        "clear it."
    )
    why: str = Field(min_length=1, description="What causes the change, in a few words.")


class LootCheck(Frozen):
    item: str = Field(
        min_length=1,
        description="What is found if the roll finds anything; the die sets how good it is.",
    )
    granted: Die | None = Field(
        default=None, description="Leave null; the engine fills it when the player answers."
    )
    choice: str | None = Field(
        default=None, description="Leave null; the engine fills it when the player answers."
    )

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if (self.granted is None) != (self.choice is None):
            raise ValueError("granted and choice arrive together, or not at all")
        return self


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )
    die: Die = Field(description="Which die to roll, picked by the odds.")


@dataclass(frozen=True, slots=True)
class Complications:
    """The rules that read the table sets: catching breath draws from the SRD's table."""

    packs: Mapping[str, Pack]

    def catch_breath(self, draft: BreathlessGame, _args: NoArgs, rng: Random) -> list[Fact]:
        world = draft.payload.world
        player = world.player
        player.worn = dict(player.skills)
        player.loot = LOOT_START
        player.stunted = False

        rolled, dice_fact = roll((12,), "a new complication", rng)
        text = complications_of(self.packs)[rolled[0] - 1]
        draft.notes = (
            *draft.notes,
            f"Catching breath brings a new complication. The SRD's table suggests: {text} Bring it "
            "in through the story, or one that fits better.",
        )
        trace = f"{world.label(player)} catches their breath: skills and loot die restored"
        fact = entity_fact(
            player, "breath_caught", trace, card="Caught breath — skills and loot die restored"
        )
        return [dice_fact, fact]


def outcome(face: int) -> str:
    if face <= 2:
        return "fail"
    if face <= 4:
        return "success-but"
    return "success"


def apply_change(world: BreathlessWorld, change: WorldChange) -> list[Fact]:
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    match change:
        case Reveal():
            return world.reveal_hidden(change.entity_id)
        case Enter():
            return world.enter(change.entity_id)
        case Leave():
            return world.leave(change.entity_id)
        case Kill():
            return world.kill(change.entity_id)
        case DropItem():
            return _drop_item(world, change.item_id)


def change_world(draft: BreathlessGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
    return apply_change(draft.payload.world, args.change)


def next_scene(draft: BreathlessGame, args: NextScene, _rng: Random) -> tuple[Fact, ...]:
    return draft.payload.world.settle(args.job_done, args.pursuit)


def check(draft: BreathlessGame, args: Check, rng: Random) -> list[Fact]:
    player = draft.payload.world.player

    item: Item | None = None
    if args.skill is not None:
        die = player.worn[args.skill]
        label = args.skill
    elif args.item_id is not None:
        item = player.items.get(args.item_id)
        if item is None:
            raise ValueError(f"{args.item_id!r} is not among the player's items")
        die = item.die
        label = item.name
    else:
        if player.stunted:
            raise ValueError("the stunt is spent until the player catches their breath")
        die = STUNT_DIE
        label = "stunt"
        player.stunted = True

    rolled, dice_fact = roll((die,), f"{args.what} — {label}", rng)
    face = rolled[0]
    result = outcome(face)

    if args.skill is not None:
        player.worn[args.skill] = stepped(die)
    elif item is not None and args.item_id is not None:
        # SRD: "When reduced to a d4, the item either breaks, gets lost, or fades away".
        if stepped(die) == 4:
            del player.items[args.item_id]
        else:
            item.die = stepped(die)

    trace = f"{args.what} — {label} d{die} [{face}] -> {result}"
    card = f"{args.what} — {sentence(label)} d{die} → {result}"
    event = DiceEvent(label=f"d{die}", faces=(die,), rolled=rolled)
    facts = [
        dice_fact,
        entity_fact(player, "checked", trace, card=card, dice=(event,)),
    ]
    if item is not None and stepped(die) == 4:
        gone = f"{item.name} is gone"
        facts.append(entity_fact(player, "item_gone", gone, card=gone))

    if args.dangerous and result == "fail" and player.vulnerable:
        draft.notes = (
            *draft.notes,
            "The player is vulnerable and this dangerous check failed: rule whether they are "
            "taken out of the scene or dead. Death is `change_world` `kill` on the player.",
        )
    return facts


def complications_of(packs: Mapping[str, Pack]) -> tuple[str, ...]:
    """Always the SRD's own table: no other pack publishes one."""
    srd = packs.get(SRD_PACK)
    if srd is None:
        raise ValueError("the SRD table set with its complications is not installed")
    return srd.complications


def change_stress(draft: BreathlessGame, args: ChangeStress, _rng: Random) -> list[Fact]:
    if args.amount == 0:
        raise ValueError("change_stress needs a non-zero amount")
    player = draft.payload.world.player
    return counter_fact(player, player.stress, args.amount, "Stress", args.why, player.id)


def use_med_kit(draft: BreathlessGame, _args: NoArgs, _rng: Random) -> list[Fact]:
    player = draft.payload.world.player
    if not player.med_kit:
        raise ValueError("the player holds no med kit")
    player.med_kit = False
    facts = counter_fact(player, player.stress, -MED_KIT_CLEARS, "Stress", "the med kit", player.id)
    used = f"{player.name} uses the med kit"
    facts.append(entity_fact(player, "med_kit_used", used, card="Med kit used"))
    return facts


def loot_options(player: Survivor, item: str, granted: Die) -> tuple[PendingOption, ...]:
    base: dict[str, JsonValue] = {"item": item, "granted": granted}
    options: list[PendingOption] = []
    if len(player.items) < CARRY:
        take = {**base, "choice": "take"}
        options.append(PendingOption(id="take", label="Take it", name="loot_check", args=take))
    else:
        for key, carried in player.items.items():
            swap = {**base, "choice": f"{SWAP}{key}"}
            options.append(
                PendingOption(
                    id=f"{SWAP}{key}",
                    label=f"Swap for {carried.name}",
                    name="loot_check",
                    args=swap,
                )
            )
    if granted >= 10 and not player.med_kit:
        med_kit = {**base, "choice": "med-kit"}
        options.append(
            PendingOption(
                id="med-kit", label="Take a med kit instead", name="loot_check", args=med_kit
            )
        )
    return tuple(options)


def loot_check(draft: BreathlessGame, args: LootCheck, rng: Random) -> list[Fact]:
    player = draft.payload.world.player
    if args.granted is None or args.choice is None:
        return _roll_loot(draft, player, args.item, rng)
    return [_take_loot(player, args.item, args.granted, args.choice)]


def test_luck(_draft: BreathlessGame, args: TestLuck, rng: Random) -> tuple[Fact, ...]:
    rolled, dice_fact = roll((args.die,), args.question, rng)
    result = outcome(rolled[0])
    trace = f"{args.question} — d{args.die} [{rolled[0]}] -> {result}"
    return dice_fact, Fact(kind="luck_tested", trace=trace)


def tools(packs: Mapping[str, Pack]) -> tuple[MasterTool[BreathlessGame], ...]:
    complications = Complications(packs)
    return (
        master_tool("change_world", CHANGE_WORLD, ChangeWorld, change_world),
        master_tool(
            "next_scene",
            NEXT_SCENE,
            NextScene,
            next_scene,
        ),
        master_tool(
            "check",
            "Roll a check for an action with a real cost, on a skill, a carried item, or a stunt.",
            Check,
            check,
        ),
        master_tool(
            "catch_breath",
            "Let the player catch their breath: skills, loot die and the stunt reset, at the "
            "cost of a new complication.",
            NoArgs,
            complications.catch_breath,
        ),
        master_tool(
            "change_stress",
            "A complication costs the player stress; laying low somewhere secure clears an "
            "amount at your discretion. Never a stand-in for `use_med_kit`.",
            ChangeStress,
            change_stress,
        ),
        master_tool(
            "use_med_kit",
            "Spend the player's med kit to clear 2 stress.",
            NoArgs,
            use_med_kit,
        ),
        master_tool(
            "loot_check",
            "Scavenge for an item. Leave `granted` and `choice` null; the engine fills them once "
            "the player answers.",
            LootCheck,
            loot_check,
        ),
        master_tool(
            "test_luck",
            "Roll a die to answer a question about the world where nobody is acting.",
            TestLuck,
            test_luck,
        ),
    )


def _drop_item(world: BreathlessWorld, item_id: EntityId) -> list[Fact]:
    player = world.player
    item = player.items.get(item_id)
    if item is None:
        raise ValueError(f"{item_id!r} is not among the player's items")
    del player.items[item_id]
    trace = f"{world.label(player)} drops {item.name}"
    return [entity_fact(player, "item_dropped", trace, card=f"Dropped {item.name}")]


def _roll_loot(draft: BreathlessGame, player: Survivor, item: str, rng: Random) -> list[Fact]:
    before = player.loot
    rolled, dice_fact = roll((before,), f"scavenging — {item}", rng)
    face = rolled[0]
    player.loot = stepped(before)

    found: Die | None = None
    if face <= 2:
        draft.notes = (*draft.notes, "The scavenge turns up trouble right here; nothing is found.")
    elif face <= 4:
        draft.notes = (*draft.notes, "The scavenge finds nothing, and trouble is coming.")
    elif face <= 6:
        found = 6
    elif face <= 8:
        found = 8
    elif face <= 10:
        found = 10
    else:
        found = 12

    result = f"found {item} (d{found})" if found is not None else "nothing"
    trace = f"scavenging — loot d{before} [{face}] -> {found or 'nothing'}"
    card = f"Scavenge — d{before} → {result}"
    event = DiceEvent(label=f"d{before}", faces=(before,), rolled=rolled)
    fact = entity_fact(player, "loot_checked", trace, card=card, dice=(event,))
    facts = [dice_fact, fact]

    if found is not None:
        draft.pending = PendingDecision(
            kind="loot",
            prompt=f"You found {item} (d{found}). Take it?",
            options=loot_options(player, item, found),
            allows_text=False,
        )
    return facts


def _take_loot(player: Survivor, item: str, granted: Die, choice: str) -> Fact:
    if choice == "take":
        if len(player.items) >= CARRY:
            raise ValueError("the backpack is full; swap for something carried instead")
        key = EntityId(slug(item, player.items))
        player.items[key] = Item(name=item, die=granted)
        card = f"Took {item} (d{granted})"
    elif choice == "med-kit":
        if granted < 10:
            raise ValueError("only a d10 find or better can be a med kit")
        if player.med_kit:
            raise ValueError("the player already holds a med kit")
        player.med_kit = True
        card = "Took a med kit"
    elif choice.startswith(SWAP) and EntityId(choice.removeprefix(SWAP)) in player.items:
        old = player.items.pop(EntityId(choice.removeprefix(SWAP)))
        key = EntityId(slug(item, player.items))
        player.items[key] = Item(name=item, die=granted)
        card = f"Swapped {old.name} for {item} (d{granted})"
    else:
        raise ValueError(f"{choice!r} is not a valid loot choice")
    return entity_fact(player, "loot_taken", card, card=card)
