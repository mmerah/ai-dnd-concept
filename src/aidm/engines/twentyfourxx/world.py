from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Mutable, Refusal, require_unique, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)
DEFAULT_DIE = 6  # a skill not on the sheet
HINDERED_DIE = 4
HELP_DIE = 6
STARTING_CREDITS = 2
MAIMED = "Maimed"


class Kit(Frozen):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)


class Item(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)

    @property
    def broken(self) -> bool:
        return self.broken_times >= self.breaks

    def detail(self) -> str:
        parts: list[str] = []
        if self.bulky:
            parts.append("bulky")
        if self.broken:
            parts.append("broken")
        elif self.breaks > 1 and self.broken_times > 0:
            parts.append(f"broken {self.broken_times}/{self.breaks}")
        return ", ".join(parts)


class Operator(Person):
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    hindrances: list[str] = Field(default_factory=list)  # the SRD's word: injuries and the like

    def die(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_DIE)

    def rows(self) -> Rows:
        skills = ", ".join(f"{skill} d{die}" for skill, die in self.skills.items())
        return tuple(
            (label, value)
            for label, value in (
                ("Specialty", self.specialty),
                ("Origin", self.origin),
                ("Traits", ", ".join(self.traits)),
                ("Skills", skills),
                ("Credits", f"₡{self.credits}"),
                ("Hindrances", ", ".join(self.hindrances)),
            )
            if value
        )

    def require_item(self, item_id: EntityId) -> Item:
        item = self.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among the player's items")
        return item

    def pay(self, cost: int) -> None:
        if cost > self.credits:
            raise Refusal(f"the player has only ₡{self.credits}, not ₡{cost}")
        self.credits -= cost

    def change_hindrances(self, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        require_unique("gained hindrances", gained)
        for hindrance in gained:
            if hindrance in self.hindrances:
                raise Refusal(f"{hindrance!r} is already among the player's hindrances")
        for hindrance in lost:
            if hindrance not in self.hindrances:
                raise Refusal(f"{hindrance!r} is not among the player's hindrances")
        for hindrance in lost:
            self.hindrances.remove(hindrance)
        self.hindrances.extend(gained)
        parts: list[str] = []
        if gained:
            parts.append(f"Hindered: {', '.join(gained)}")
        if lost:
            parts.append(f"Recovered: {', '.join(lost)}")
        card = " / ".join(parts)
        trace = f"{self.label} — {card}"
        return [self.fact("hindrances_changed", trace, card=card)]

    def gain_item(self, name: str, *, bulky: bool, breaks: int, cost: int) -> list[Fact]:
        self.pay(cost)
        self.items[EntityId(slug(name, self.items))] = Item(name=name, bulky=bulky, breaks=breaks)
        suffix = f" (₡{cost})" if cost > 0 else ""
        card = f"Gained {name}{suffix}"
        trace = f"{self.label} gains {name}{suffix}"
        return [self.fact("item_gained", trace, card=card)]

    def drop_item(self, item_id: EntityId) -> list[Fact]:
        item = self.require_item(item_id)
        del self.items[item_id]
        trace = f"{self.label} drops {item.name}"
        return [self.fact("item_dropped", trace, card=f"Dropped {item.name}")]

    def repair_item(self, item_id: EntityId, cost: int) -> list[Fact]:
        item = self.require_item(item_id)
        if item.broken_times == 0:
            raise Refusal(f"{item.name} is not broken")
        self.pay(cost)
        item.broken_times = 0
        trace = f"{self.label} repairs {item.name}"
        return [self.fact("item_repaired", trace, card=f"Repaired {item.name}")]

    def spend(self, amount: int, why: str) -> list[Fact]:
        self.pay(amount)
        trace = f"{self.label} spends ₡{amount} — {why}"
        return [self.fact("credits_spent", trace, card=f"₡{amount} spent — {why}")]


TwentyfourxxWorld = SceneWorld[Person, Operator]

TwentyfourxxGame = Game[TwentyfourxxWorld]

TwentyfourxxScenario = Scenario[SceneCanon[Person]]

TwentyfourxxCharacter = Character[Operator]


def raised(current: SkillDie | None) -> SkillDie:
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise Refusal("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]
