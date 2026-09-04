from random import Random
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Refusal, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.play import PendingDecision, PendingOption
from aidm.engines.breathless.world import CARRY, BreathlessGame, Die, Item, Skill, Survivor, stepped
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal

SWAP = "swap-"


class DropItem(Frozen):
    """Take an item out of the player's backpack for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")


type WorldChange = Reveal | Enter | Leave | Kill | DropItem


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


def outcome(face: int) -> str:
    if face <= 2:
        return "fail"
    if face <= 4:
        return "success-but"
    return "success"


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


def take_loot(player: Survivor, item: str, granted: Die, choice: str) -> Fact:
    if choice == "take":
        if len(player.items) >= CARRY:
            raise Refusal("the backpack is full; swap for something carried instead")
        key = EntityId(slug(item, player.items))
        player.items[key] = Item(name=item, die=granted)
        card = f"Took {item} (d{granted})"
    elif choice == "med-kit":
        if granted < 10:
            raise Refusal("only a d10 find or better can be a med kit")
        if player.med_kit:
            raise Refusal("the player already holds a med kit")
        player.med_kit = True
        card = "Took a med kit"
    elif choice.startswith(SWAP) and EntityId(choice.removeprefix(SWAP)) in player.items:
        old = player.items.pop(EntityId(choice.removeprefix(SWAP)))
        key = EntityId(slug(item, player.items))
        player.items[key] = Item(name=item, die=granted)
        card = f"Swapped {old.name} for {item} (d{granted})"
    else:
        raise Refusal(f"{choice!r} is not a valid loot choice")
    return player.fact("loot_taken", card, card=card)


def roll_loot(draft: BreathlessGame, item: str, rng: Random) -> list[Fact]:
    player = draft.payload.player
    before = player.loot
    rolled, dice_fact = roll((before,), f"scavenging — {item}", rng)
    face = rolled[0]
    player.loot = stepped(before)

    found: Die | None = None
    if face <= 2:
        draft.note("The scavenge turns up trouble right here; nothing is found.")
    elif face <= 4:
        draft.note("The scavenge finds nothing, and trouble is coming.")
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
    fact = player.fact("loot_checked", trace, card=card, dice=(event,))
    facts = [dice_fact, fact]

    if found is not None:
        draft.pending = PendingDecision(
            kind="loot",
            prompt=f"You found {item} (d{found}). Take it?",
            options=loot_options(player, item, found),
            allows_text=False,
        )
    return facts
