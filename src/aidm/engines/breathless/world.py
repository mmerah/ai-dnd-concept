from collections.abc import Mapping
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from aidm.core.entities import EntityId, Mutable, Refusal, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import PendingOption
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Counter, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
SKILL_SPREAD = [4, 4, 4, 6, 8, 10]
STRESS_MAX = 4
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


class SurvivorSheet(Mutable):
    """What Breathless rolls for: the player's sheet from creation, a hired survivor's from
    the worldsmith."""

    pronouns: str = ""
    job: str = ""
    skills: dict[Skill, Die] = Field(min_length=6, max_length=6)
    # where each stands now; `skills` is as created
    worn: dict[Skill, Die] = Field(min_length=6, max_length=6)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=lambda: Counter(current=0, maximum=STRESS_MAX))
    stunted: bool = False

    @model_validator(mode="after")
    def _rated_spread(self) -> Self:
        check_spread(self.skills)
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


class Survivor(Person):
    """One type plays the player and the cast alike; only a sheet says who has dice."""

    sheet: SurvivorSheet | None = Field(
        default=None,
        description="Never written by you: code installs it when the player hires them.",
    )

    def dice(self) -> SurvivorSheet:
        if self.sheet is None:
            raise Refusal(f"{self.name} carries no dice")
        return self.sheet

    def require_item(self, item_id: EntityId) -> Item:
        item = self.dice().items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {self.name}'s items")
        return item

    def drop_item(self, item_id: EntityId) -> list[Fact]:
        item = self.require_item(item_id)
        del self.dice().items[item_id]
        trace = f"{self.label} drops {item.name}"
        return [self.fact("item_dropped", trace, card=f"Dropped {item.name}")]

    def change_stress(self, amount: int, why: str) -> list[Fact]:
        if amount == 0:
            raise Refusal("change_stress needs a non-zero amount")
        return self.dice().stress.change(self, amount, "Stress", why)

    def use_med_kit(self) -> list[Fact]:
        sheet = self.dice()
        if not sheet.med_kit:
            raise Refusal(f"{self.name} holds no med kit")
        sheet.med_kit = False
        facts = sheet.stress.change(self, -MED_KIT_CLEARS, "Stress", "the med kit")
        used = f"{self.name} uses the med kit"
        facts.append(self.fact("med_kit_used", used, card="Med kit used"))
        return facts

    def take_loot(self, item: str, granted: Die, choice: str) -> Fact:
        sheet = self.dice()
        if choice == "take":
            if len(sheet.items) >= CARRY:
                raise Refusal("the backpack is full; swap for something carried instead")
            sheet.items[EntityId(slug(item, sheet.items))] = Item(name=item, die=granted)
            card = f"Took {item} (d{granted})"
        elif choice == "med-kit":
            if granted < 10:
                raise Refusal("only a d10 find or better can be a med kit")
            if sheet.med_kit:
                raise Refusal(f"{self.name} already holds a med kit")
            sheet.med_kit = True
            card = "Took a med kit"
        elif choice.startswith(SWAP) and EntityId(choice.removeprefix(SWAP)) in sheet.items:
            old = sheet.items.pop(EntityId(choice.removeprefix(SWAP)))
            sheet.items[EntityId(slug(item, sheet.items))] = Item(name=item, die=granted)
            card = f"Swapped {old.name} for {item} (d{granted})"
        else:
            raise Refusal(f"{choice!r} is not a valid loot choice")
        return self.fact("loot_taken", card, card=card)

    def rows(self) -> Rows:
        return self.sheet.rows() if self.sheet is not None else ()

    def line(self, *, rows: Rows | None = None, detail: str = "") -> str:
        # the player's backpack is the BACKPACK section
        if self.sheet is not None and self.id != PLAYER_ID:
            items = ", ".join(
                f"{item.name}[{key}] d{item.die}" for key, item in self.sheet.items.items()
            )
            detail = f"backpack: {items or '(empty)'}"
            if self.sheet.med_kit:
                detail += ", med kit"
        return super().line(rows=rows, detail=detail)

    def unwritten(self) -> str:
        parts = [
            part
            for part in (super().unwritten(), "a sheet" if self.sheet is not None else "")
            if part
        ]
        return ", ".join(parts)


class BreathlessWorld(SceneWorld[Survivor, Survivor]):
    @model_validator(mode="after")
    def _player_carries_a_sheet(self) -> Self:
        if self.player.sheet is None:
            raise ValueError("the player carries no sheet")
        return self

    def require_actor(self, actor_id: EntityId | None) -> Survivor:
        if actor_id is None or actor_id == self.player.id:
            return self.player
        entity = self.require(actor_id)
        if entity.alive and entity.sheet is not None and entity.id in self.party:
            return entity
        raise Refusal(f"{entity.name} is not the player or a hired survivor")

    def require_hireable(self, entity_id: EntityId) -> Survivor:
        member = self.require_here(entity_id, alive=True)
        if member.sheet is not None:
            raise Refusal(f"{member.name} already carries a sheet")
        return member


BreathlessGame = Game[BreathlessWorld]

BreathlessScenario = Scenario[SceneCanon[Survivor]]

BreathlessCharacter = Character[Survivor]


def stepped(die: Die) -> Die:
    return LADDER[max(LADDER.index(die) - 1, 0)]


def check_spread(skills: Mapping[Skill, Die]) -> None:
    if sorted(skills.values()) != SKILL_SPREAD:
        raise ValueError("skills as created: three d4, one d6, one d8, one d10")
