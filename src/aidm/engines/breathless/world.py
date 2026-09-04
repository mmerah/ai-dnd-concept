from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.core.entities import EntityId, Mutable, Refusal, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import PendingOption
from aidm.core.views import Rows
from aidm.engines.base import Counter, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
SKILL_SPREAD = [4, 4, 4, 6, 8, 10]
STRESS_MAX = 4  # vulnerable at 4
CARRY = 3  # items beside the med kit
LOOT_START: Die = 12
STUNT_DIE: Die = 12
STARTING_ITEM: Die = 10
MED_KIT_CLEARS = 2
STARTING_DICE: tuple[Die, ...] = (10, 8, 6)  # the three rated skills, best first
SWAP = "swap-"


class Item(Mutable):
    name: str
    die: Die


class Survivor(Person):
    pronouns: str = ""
    job: str = ""
    skills: dict[Skill, Die] = Field(min_length=6, max_length=6)  # as created
    worn: dict[Skill, Die] = Field(min_length=6, max_length=6)  # where each stands now
    items: dict[EntityId, Item] = Field(default_factory=dict)  # the backpack
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=lambda: Counter(current=0, maximum=STRESS_MAX))
    stunted: bool = False

    @model_validator(mode="after")
    def _rated_spread(self) -> Self:
        if sorted(self.skills.values()) != SKILL_SPREAD:
            raise ValueError("skills as created: three d4, one d6, one d8, one d10")
        return self

    @property
    def vulnerable(self) -> bool:
        return self.stress.current >= STRESS_MAX

    def rows(self) -> Rows:
        skills = ", ".join(
            f"{skill.capitalize()} d{self.worn[skill]}"
            + ("" if self.worn[skill] == self.skills[skill] else f" (rated d{self.skills[skill]})")
            for skill in SKILLS
        )
        return tuple(
            (label, value)
            for label, value in (
                ("Pronouns", self.pronouns),
                ("Job", self.job),
                ("Skills", skills),
                ("Loot die", f"d{self.loot}"),
                ("Stress", str(self.stress) + (", vulnerable" if self.vulnerable else "")),
                ("Stunt", "spent" if self.stunted else ""),
                ("Med kit", "yes" if self.med_kit else ""),
            )
            if value
        )

    def require_item(self, item_id: EntityId) -> Item:
        item = self.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among the player's items")
        return item

    def drop_item(self, item_id: EntityId) -> list[Fact]:
        item = self.require_item(item_id)
        del self.items[item_id]
        trace = f"{self.label} drops {item.name}"
        return [self.fact("item_dropped", trace, card=f"Dropped {item.name}")]

    def loot_options(self, item: str, granted: Die) -> tuple[PendingOption, ...]:
        base: dict[str, JsonValue] = {"item": item, "granted": granted}
        options: list[PendingOption] = []
        if len(self.items) < CARRY:
            take = {**base, "choice": "take"}
            options.append(PendingOption(id="take", label="Take it", name="loot_check", args=take))
        else:
            for key, carried in self.items.items():
                swap = {**base, "choice": f"{SWAP}{key}"}
                options.append(
                    PendingOption(
                        id=f"{SWAP}{key}",
                        label=f"Swap for {carried.name}",
                        name="loot_check",
                        args=swap,
                    )
                )
        if granted >= 10 and not self.med_kit:
            med_kit = {**base, "choice": "med-kit"}
            options.append(
                PendingOption(
                    id="med-kit", label="Take a med kit instead", name="loot_check", args=med_kit
                )
            )
        return tuple(options)

    def take_loot(self, item: str, granted: Die, choice: str) -> Fact:
        if choice == "take":
            if len(self.items) >= CARRY:
                raise Refusal("the backpack is full; swap for something carried instead")
            self.items[EntityId(slug(item, self.items))] = Item(name=item, die=granted)
            card = f"Took {item} (d{granted})"
        elif choice == "med-kit":
            if granted < 10:
                raise Refusal("only a d10 find or better can be a med kit")
            if self.med_kit:
                raise Refusal("the player already holds a med kit")
            self.med_kit = True
            card = "Took a med kit"
        elif choice.startswith(SWAP) and EntityId(choice.removeprefix(SWAP)) in self.items:
            old = self.items.pop(EntityId(choice.removeprefix(SWAP)))
            self.items[EntityId(slug(item, self.items))] = Item(name=item, die=granted)
            card = f"Swapped {old.name} for {item} (d{granted})"
        else:
            raise Refusal(f"{choice!r} is not a valid loot choice")
        return self.fact("loot_taken", card, card=card)


BreathlessWorld = SceneWorld[Person, Survivor]


class BreathlessGame(Game[BreathlessWorld]):
    pass


class BreathlessScenario(Scenario[SceneCanon[Person]]):
    pass


class BreathlessCharacter(Character[Survivor]):
    pass


def stepped(die: Die) -> Die:
    return LADDER[max(LADDER.index(die) - 1, 0)]
