from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.tools import MasterTool, master_tool
from aidm.engines.core import CHANGE_WORLD, entity_fact, keep_highest, sentence
from aidm.engines.scenes.world import NEXT_SCENE, Enter, Kill, Leave, NextScene, Reveal
from aidm.engines.twentyfourxx.creation import Pack
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Item,
    Operator,
    TwentyfourxxGame,
    TwentyfourxxWorld,
    raised,
)

type WorldChange = (
    Reveal | Enter | Leave | Kill | ChangeHindrances | GainItem | DropItem | RepairItem | Spend
)


class ChangeHindrances(Frozen):
    """Record hindrances the player picks up, sheds, or both at once."""

    verb: Literal["change_hindrances"]
    gained: tuple[str, ...] = Field(
        default=(), description="Hindrances the player now carries, that they did not before."
    )
    lost: tuple[str, ...] = Field(
        default=(), description="Hindrances the player no longer carries."
    )

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("change_hindrances needs a gained or a lost hindrance")
        return self


class GainItem(Frozen):
    """Add an item to the player's kit, spending credits when it costs any."""

    verb: Literal["gain_item"]
    name: str = Field(min_length=1, description="The item's name.")
    bulky: bool = Field(default=False, description="True when the item takes real space to carry.")
    breaks: int = Field(
        default=1, ge=1, description="How many times the item can break before it is ruined."
    )
    cost: int = Field(
        default=0,
        ge=0,
        description="Credits spent for the item; `cost` 0 only for a thing found or given.",
    )


class DropItem(Frozen):
    """Take an item out of the player's kit for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")


class RepairItem(Frozen):
    """Fix a broken item, spending credits when the repair costs any."""

    verb: Literal["repair_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")
    cost: int = Field(default=0, ge=0, description="Credits spent on the repair.")


class Spend(Frozen):
    """Pay credits for anything that is not an item or a repair: bribes, care, passage."""

    verb: Literal["spend"]
    amount: int = Field(gt=0, description="Credits spent.")
    why: str = Field(min_length=1, description="What the credits pay for, in a few words.")


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Attempt(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
    skill: str = Field(default="", description="Which skill to roll; empty rolls the plain d6.")
    helped: str = Field(default="", description="Why circumstances help, when they do.")
    hindered: str = Field(default="", description="Why the player is hindered, when they are.")
    risking_death: bool = Field(
        default=False,
        description="True when a disaster kills the player and a setback maims them; say it "
        "before the roll.",
    )


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Defend(Frozen):
    item_id: CheckedEntityId = Field(
        description="Exact id of the item the player breaks to defend."
    )
    hindrance: str = Field(
        min_length=1, description="What the harm the player takes becomes, as a hindrance."
    )


class JobDone(Frozen):
    skill: str = Field(
        min_length=1, description="The skill the job called on, named by the player, to raise."
    )


@dataclass(frozen=True, slots=True)
class Skills:
    """The rules that read the table sets: a skill the master names is matched against them."""

    packs: Mapping[str, Pack]

    def attempt(self, draft: TwentyfourxxGame, args: Attempt, rng: Random) -> list[Fact]:
        world = draft.payload.world
        player = world.player

        if args.skill:
            label = self._resolve_skill(player, args.skill)
            die = player.die(label)
        else:
            label = "unskilled"
            die = DEFAULT_DIE
        if args.hindered:
            die = HINDERED_DIE

        reason = f"{args.what} — {label}"
        die_label = f"d{die}+d{HELP_DIE}" if args.helped else f"d{die}"
        if args.helped:
            face, event, dice_fact = keep_highest((die, HELP_DIE), reason, rng, label=die_label)
        else:
            rolled, dice_fact = roll((die,), reason, rng)
            face = rolled[0]
            event = DiceEvent(label=die_label, faces=(die,), rolled=rolled)

        result = outcome(face)
        shown = ", ".join(str(one) for one in event.rolled)
        trace = f"{args.what} — {label} {die_label} [{shown}] -> {result}"
        card = f"{args.what} — {sentence(label)} {die_label} → {result}"
        qualifiers = "; ".join(
            part
            for part in (
                f"helped — {args.helped}" if args.helped else "",
                f"hindered — {args.hindered}" if args.hindered else "",
            )
            if part
        )
        if qualifiers:
            card = f"{card} ({qualifiers})"

        facts: list[Fact] = [
            dice_fact,
            entity_fact(player, "attempted", trace, card=card, dice=(event,)),
        ]

        if args.risking_death and result == "disaster":
            player.alive = False
            death_trace = f"{world.label(player)} is dead"
            facts.append(entity_fact(player, "actor_killed", death_trace, card="You are dead"))
        elif args.risking_death and result == "setback" and MAIMED not in player.hindrances:
            player.hindrances = (*player.hindrances, MAIMED)
            maimed_trace = f"{world.label(player)} is maimed"
            facts.append(entity_fact(player, "hindrances_changed", maimed_trace, card="Maimed"))

        return facts

    def job_done(self, draft: TwentyfourxxGame, args: JobDone, rng: Random) -> list[Fact]:
        world = draft.payload.world
        player = world.player
        label = self._resolve_skill(player, args.skill)
        new_die = raised(player.skills.get(label))
        player.skills[label] = new_die
        raise_trace = f"{world.label(player)} — {label} rises to d{new_die}"
        raise_fact = entity_fact(
            player, "skill_raised", raise_trace, card=f"Skill up: {label} d{new_die}"
        )

        rolled, dice_fact = roll((6,), "credits earned", rng)
        gained = rolled[0]
        player.credits += gained
        event = DiceEvent(label="d6", faces=(6,), rolled=rolled)
        credit_trace = f"{world.label(player)} earns ₡{gained} -> ₡{player.credits}"
        credit_fact = entity_fact(
            player,
            "credits_gained",
            credit_trace,
            card=f"+₡{gained} -> ₡{player.credits}",
            dice=(event,),
        )
        return [raise_fact, dice_fact, credit_fact]

    def _resolve_skill(self, player: Operator, wanted: str) -> str:
        folded = wanted.casefold()
        for key in player.skills:
            if key.casefold() == folded:
                return key
        labels: list[str] = []
        for pack in self.packs.values():
            for option in pack.skills:
                if option.label.casefold() == folded:
                    return option.label
                if option.label not in labels:
                    labels.append(option.label)
        sheet = ", ".join(sorted(player.skills)) or "none"
        raise ValueError(
            f"{wanted!r} is not a skill on the sheet ({sheet}) or in the packs "
            f"({', '.join(labels)})"
        )


def outcome(face: int) -> str:
    if face <= 2:
        return "disaster"
    if face <= 4:
        return "setback"
    return "success"


def apply_change(world: TwentyfourxxWorld, change: WorldChange) -> list[Fact]:
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
        case ChangeHindrances():
            return _change_hindrances(world, change)
        case GainItem():
            return _gain_item(world, change)
        case DropItem():
            return _drop_item(world, change.item_id)
        case RepairItem():
            return _repair_item(world, change)
        case Spend():
            return _spend(world, change)


def change_world(draft: TwentyfourxxGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
    return apply_change(draft.payload.world, args.change)


def next_scene(draft: TwentyfourxxGame, args: NextScene, _rng: Random) -> tuple[Fact, ...]:
    return draft.payload.world.settle(args.job_done, args.pursuit)


def test_luck(_draft: TwentyfourxxGame, args: TestLuck, rng: Random) -> tuple[Fact, ...]:
    rolled, dice_fact = roll((6,), args.question, rng)
    face = rolled[0]
    if face <= 2:
        result = "trouble now"
    elif face <= 4:
        result = "signs of it"
    else:
        result = "nothing"
    trace = f"{args.question} — d6 [{face}] -> {result}"
    return dice_fact, Fact(kind="luck_tested", trace=trace)


def defend(draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
    world = draft.payload.world
    player = world.player
    item = player.items.get(args.item_id)
    if item is None:
        raise ValueError(f"{args.item_id!r} is not among the player's items")
    if item.broken:
        raise ValueError(f"{item.name} is already broken")
    if args.hindrance in player.hindrances:
        raise ValueError(f"{args.hindrance!r} is already among the player's hindrances")
    item.broken_times += 1
    player.hindrances = (*player.hindrances, args.hindrance)
    card = f"{item.name} breaks — {args.hindrance}"
    trace = f"{world.label(player)} breaks {item.name} — {args.hindrance}"
    return [entity_fact(player, "item_broken", trace, card=card)]


def tools(packs: Mapping[str, Pack]) -> tuple[MasterTool[TwentyfourxxGame], ...]:
    skills = Skills(packs)
    return (
        master_tool("change_world", CHANGE_WORLD, ChangeWorld, change_world),
        master_tool(
            "next_scene",
            NEXT_SCENE,
            NextScene,
            next_scene,
        ),
        master_tool(
            "attempt",
            "Roll for something whose outcome matters. Name `helped` with why circumstances "
            "help — an ally who pitches in counts, named in it: the SRD gives them their own "
            "die, but here it is the d6 of circumstance, because an NPC carries no dice. Name "
            "`hindered` with why the player is hindered, when they are.",
            Attempt,
            skills.attempt,
        ),
        master_tool(
            "test_luck",
            "Roll a d6 to test the world's bad luck, where nobody is acting.",
            TestLuck,
            test_luck,
        ),
        master_tool(
            "defend",
            "Break a carried item to turn a hit into a hindrance instead of taking it outright; "
            "word the harm yourself.",
            Defend,
            defend,
        ),
        master_tool(
            "job_done",
            "Once per job, when the player's own words close out the job: raise the named "
            "skill and pay out its credits.",
            JobDone,
            skills.job_done,
        ),
    )


def _change_hindrances(world: TwentyfourxxWorld, change: ChangeHindrances) -> list[Fact]:
    player = world.player
    held = set(player.hindrances)
    for one in change.gained:
        if one in held:
            raise ValueError(f"{one!r} is already among the player's hindrances")
        held.add(one)
    for one in change.lost:
        if one not in player.hindrances:
            raise ValueError(f"{one!r} is not among the player's hindrances")
    hindrances = [one for one in player.hindrances if one not in change.lost]
    player.hindrances = (*hindrances, *change.gained)
    parts: list[str] = []
    if change.gained:
        parts.append(f"Hindered: {', '.join(change.gained)}")
    if change.lost:
        parts.append(f"Recovered: {', '.join(change.lost)}")
    card = " / ".join(parts)
    trace = f"{world.label(player)} — {card}"
    return [entity_fact(player, "hindrances_changed", trace, card=card)]


def _gain_item(world: TwentyfourxxWorld, change: GainItem) -> list[Fact]:
    player = world.player
    if change.cost > player.credits:
        raise ValueError(f"the player has only ₡{player.credits}, not ₡{change.cost}")
    player.credits -= change.cost
    key = EntityId(slug(change.name, player.items))
    player.items[key] = Item(name=change.name, bulky=change.bulky, breaks=change.breaks)
    suffix = f" (₡{change.cost})" if change.cost > 0 else ""
    card = f"Gained {change.name}{suffix}"
    trace = f"{world.label(player)} gains {change.name}{suffix}"
    return [entity_fact(player, "item_gained", trace, card=card)]


def _drop_item(world: TwentyfourxxWorld, item_id: EntityId) -> list[Fact]:
    player = world.player
    item = player.items.get(item_id)
    if item is None:
        raise ValueError(f"{item_id!r} is not among the player's items")
    del player.items[item_id]
    trace = f"{world.label(player)} drops {item.name}"
    return [entity_fact(player, "item_dropped", trace, card=f"Dropped {item.name}")]


def _repair_item(world: TwentyfourxxWorld, change: RepairItem) -> list[Fact]:
    player = world.player
    item = player.items.get(change.item_id)
    if item is None:
        raise ValueError(f"{change.item_id!r} is not among the player's items")
    if item.broken_times == 0:
        raise ValueError(f"{item.name} is not broken")
    if change.cost > player.credits:
        raise ValueError(f"the player has only ₡{player.credits}, not ₡{change.cost}")
    player.credits -= change.cost
    item.broken_times = 0
    card = f"Repaired {item.name}"
    trace = f"{world.label(player)} repairs {item.name}"
    return [entity_fact(player, "item_repaired", trace, card=card)]


def _spend(world: TwentyfourxxWorld, change: Spend) -> list[Fact]:
    player = world.player
    if change.amount > player.credits:
        raise ValueError(f"the player has only ₡{player.credits}, not ₡{change.amount}")
    player.credits -= change.amount
    card = f"₡{change.amount} spent — {change.why}"
    trace = f"{world.label(player)} spends ₡{change.amount} — {change.why}"
    return [entity_fact(player, "credits_spent", trace, card=card)]
