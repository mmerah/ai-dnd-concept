from collections.abc import Mapping
from functools import partial
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.tools import MasterTool, master_tool
from aidm.engines.core import PLAYER_ID, entity_fact, keep_highest
from aidm.engines.scenes import NEXT_SCENE, NextScene, settle
from aidm.engines.twentyfourxx.creation import Pack
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Item,
    Npc,
    Operator,
    TwentyfourxxGame,
    TwentyfourxxWorld,
    raised,
)

CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)
SRD_PACK = "srd"
_PLAYER_DEAD = "the player is dead; they take no further part."


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class Kill(Frozen):
    """Record that someone here has died."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


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


# A plain alias, not `type`: the union must flatten so the discriminator sees every arm.
WorldChange = (
    Reveal | Enter | Leave | Kill | ChangeHindrances | GainItem | DropItem | RepairItem | Spend
)


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


def outcome(face: int) -> str:
    if face <= 2:
        return "disaster"
    if face <= 4:
        return "setback"
    return "success"


def apply_change(world: TwentyfourxxWorld, change: WorldChange) -> list[Fact]:
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    run = world.run
    match change:
        case Reveal():
            one = world.require(change.entity_id)
            if change.entity_id not in run.hidden:
                raise ValueError(f"{change.entity_id!r} is not hidden here")
            run.hidden.remove(one.id)
            run.present.append(one.id)
            return _reveal(world, one)
        case Enter():
            if change.entity_id == PLAYER_ID:
                raise ValueError("the player is in every scene; move the story on instead")
            one = world.require(change.entity_id)
            if one.id in run.present:
                raise ValueError(f"{one.name} is already here")
            if one.id in run.hidden:
                raise ValueError(f"{one.name} is hidden here; reveal them instead")
            run.present.append(one.id)
            seen = world.reveal(one)
            trace = f"{world.label(one)} arrives"
            return [*seen, entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives")]
        case Leave():
            if change.entity_id == PLAYER_ID:
                raise ValueError("the player is in every scene; move the story on instead")
            one = world.require_here(change.entity_id)
            run.present.remove(one.id)
            trace = f"{world.label(one)} leaves"
            return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]
        case Kill():
            return _kill(world, change.entity_id)
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
    return settle(draft.payload.world, args.job_done)


def attempt(
    packs: Mapping[str, Pack], draft: TwentyfourxxGame, args: Attempt, rng: Random
) -> list[Fact]:
    world = draft.payload.world
    player = world.player
    if not player.alive:
        raise ValueError(_PLAYER_DEAD)

    if args.skill:
        label = _resolve_skill(packs, player, args.skill)
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
    card = f"{args.what} — {_sentence(label)} {die_label} → {result}"
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
    if not player.alive:
        raise ValueError(_PLAYER_DEAD)
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


def job_done(
    packs: Mapping[str, Pack], draft: TwentyfourxxGame, args: JobDone, rng: Random
) -> list[Fact]:
    world = draft.payload.world
    player = world.player
    if not player.alive:
        raise ValueError(_PLAYER_DEAD)
    label = _resolve_skill(packs, player, args.skill)
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


def tools(packs: Mapping[str, Pack]) -> tuple[MasterTool[TwentyfourxxGame], ...]:
    return (
        master_tool(
            "change_world", CHANGE_WORLD, ChangeWorld, change_world, during_suspension=True
        ),
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
            partial(attempt, packs),
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
            partial(job_done, packs),
        ),
    )


def _resolve_skill(packs: Mapping[str, Pack], player: Operator, wanted: str) -> str:
    folded = wanted.casefold()
    for key in player.skills:
        if key.casefold() == folded:
            return key
    labels: list[str] = []
    for pack in packs.values():
        for option in pack.skills:
            if option.label.casefold() == folded:
                return option.label
            if option.label not in labels:
                labels.append(option.label)
    sheet = ", ".join(sorted(player.skills)) or "none"
    raise ValueError(
        f"{wanted!r} is not a skill on the sheet ({sheet}) or in the packs ({', '.join(labels)})"
    )


def _reveal(world: TwentyfourxxWorld, one: Operator | Npc) -> list[Fact]:
    """The discovery itself, distinct from the standalone `reveal` verb's card."""
    facts = world.reveal(one)
    if not facts:
        raise ValueError(f"the player has already met {one.name}")
    return [facts[0].model_copy(update={"card": _sentence(f"{one.name} discovered")})]


def _kill(world: TwentyfourxxWorld, entity_id: EntityId) -> list[Fact]:
    one = world.require_here(entity_id)
    if not one.alive:
        raise ValueError(f"{one.name} is already dead")
    facts = world.reveal(one)
    one.alive = False
    card = "You are dead" if one.id == PLAYER_ID else f"{one.name} is dead"
    trace = f"{world.label(one)} is dead"
    facts.append(entity_fact(one, "actor_killed", trace, card=card))
    return facts


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


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]
