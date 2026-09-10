from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import Frozen, Mutable, Refusal, Slug, check_unique, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Pairs
from aidm.engines.base import Sheeted
from aidm.engines.hiring import ItemSheet
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)
DEFAULT_DIE = 6
HINDERED_DIE = 4
HELP_DIE = 6
STARTING_CREDITS = 2
MAIMED = "Maimed"
SHIP_FUNCTIONS: tuple[str, ...] = (
    "Comms",
    "Crafts",
    "Drive",
    "Equipment",
    "Hull armor",
    "Sensors",
    "Weapons",
)  # the SRD's seven, in its order
UPGRADE_COST = 10


class Kit(Frozen):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)
    harmless: bool = False  # SRD: "break harmlessly for defense"


class Gear(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)
    upgraded: bool = False
    harmless: bool = False

    @property
    def broken(self) -> bool:
        return self.broken_times >= self.breaks

    def detail(self) -> str:
        parts: list[str] = []
        if self.bulky:
            parts.append("bulky")
        if self.harmless:
            parts.append("breaks harmlessly")
        if self.broken:
            parts.append("broken")
        elif self.breaks > 1 and self.broken_times > 0:
            parts.append(f"broken {self.broken_times}/{self.breaks}")
        if self.upgraded:
            parts.append("upgraded")
        return ", ".join(parts)


class Sheet(ItemSheet[Gear]):
    """The dice a crew member rolls."""

    specialty: str
    origin: str = ""  # empty on a hired member: the worldsmith writes no origin
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    hindrances: list[str] = Field(default_factory=list)

    def die(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_DIE)

    def rows(self) -> Pairs:
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


class Crewmate(Sheeted[Sheet]):
    def require_item(self, item_id: Slug) -> Gear:
        return self.dice().require(item_id, self.name)

    def pay(self, cost: int) -> None:
        sheet = self.dice()
        if cost > sheet.credits:
            raise Refusal(f"{self.name} has only ₡{sheet.credits}, not ₡{cost}")
        sheet.credits -= cost

    def change_hindrances(self, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        sheet = self.dice()
        check_unique("gained hindrances", gained)
        for hindrance in gained:
            if hindrance in sheet.hindrances:
                raise Refusal(f"{hindrance!r} is already among {self.name}'s hindrances")
        for hindrance in lost:
            if hindrance not in sheet.hindrances:
                raise Refusal(f"{hindrance!r} is not among {self.name}'s hindrances")
        for hindrance in lost:
            sheet.hindrances.remove(hindrance)
        sheet.hindrances.extend(gained)
        parts: list[str] = []
        if gained:
            parts.append(f"Hindered: {', '.join(gained)}")
        if lost:
            parts.append(f"Recovered: {', '.join(lost)}")
        card = " / ".join(parts)
        trace = f"{self.mention} — {card}"
        return [self.fact(trace, card=card)]

    def gain_item(self, name: str, *, bulky: bool, breaks: int, cost: int) -> list[Fact]:
        self.pay(cost)
        items = self.dice().items
        items[slug(name, items)] = Gear(name=name, bulky=bulky, breaks=breaks)
        suffix = f" (₡{cost})" if cost > 0 else ""
        card = f"Gained {name}{suffix}"
        trace = f"{self.mention} gains {name}{suffix}"
        return [self.fact(trace, card=card)]

    def drop_item(self, item_id: Slug) -> list[Fact]:
        item = self.dice().drop(item_id, self.name)
        trace = f"{self.mention} drops {item.name}"
        return [self.fact(trace, card=f"Dropped {item.name}")]

    def repair_item(self, item: Gear, cost: int) -> list[Fact]:
        if item.broken_times == 0:
            raise Refusal(f"{item.name} is not broken")
        self.pay(cost)
        item.broken_times = 0
        trace = f"{self.mention} repairs {item.name}"
        return [self.fact(trace, card=f"Repaired {item.name}")]

    def spend(self, amount: int, why: str) -> list[Fact]:
        self.pay(amount)
        trace = f"{self.mention} spends ₡{amount} — {why}"
        return [self.fact(trace, card=f"₡{amount} spent — {why}")]

    def rows(self) -> Pairs:
        if self.sheet is None:
            return ()
        gear = ", ".join(
            item.name + (f" ({detail})" if (detail := item.detail()) else "")
            for item in self.sheet.items.values()
        )
        return (*self.sheet.rows(), *((("Gear", gear),) if gear else ()))


class TwentyfourxxWorld(SceneWorld[Crewmate]):
    job: str = ""
    ship: dict[Slug, Gear] = Field(
        default_factory=lambda: {
            slug(name, ()): Gear(name=name, harmless=name == "Hull armor")
            for name in SHIP_FUNCTIONS
        }
    )

    def sheeted_members(self) -> list[Crewmate]:
        return [member for member in self.members() if member.hired()]

    def require_gear(self, actor: Crewmate, item_id: Slug) -> Gear:
        """The actor's item or a ship function: both break to defend and both are repaired."""
        item = actor.dice().items.get(item_id) or self.ship.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {actor.name}'s items or the ship's functions")
        return item

    def defend(self, actor_id: Slug | None, item_id: Slug, hindrance: str) -> list[Fact]:
        actor = self.require_actor(actor_id)
        item = self.require_gear(actor, item_id)
        if item.broken:
            raise Refusal(f"{item.name} is already broken")
        if item.harmless:
            if hindrance:
                raise Refusal(f"{item.name} breaks harmlessly: leave `hindrance` empty")
            item.broken_times += 1
            trace = f"{actor.mention} breaks {item.name}, harmlessly"
            return [actor.fact(trace, card=f"{item.name} breaks")]
        if not hindrance:
            raise Refusal("name the hindrance the hit becomes")
        sheet = actor.dice()
        if hindrance in sheet.hindrances:
            raise Refusal(f"{hindrance!r} is already among {actor.name}'s hindrances")
        item.broken_times += 1
        sheet.hindrances.append(hindrance)
        card = f"{item.name} breaks — {hindrance}"
        trace = f"{actor.mention} breaks {item.name} — {hindrance}"
        return [actor.fact(trace, card=card)]

    def upgrade_ship(self, function_id: Slug) -> list[Fact]:
        function = self.ship.get(function_id)
        if function is None:
            raise Refusal(f"{function_id!r} is not a ship function")
        if function.upgraded:
            raise Refusal(f"{function.name} is already upgraded")
        self.player.pay(UPGRADE_COST)
        function.upgraded = True
        trace = f"the ship's {function.name} is upgraded (₡{UPGRADE_COST})"
        card = f"{function.name} upgraded — ₡{UPGRADE_COST}"
        return [self.player.fact(trace, card=card)]

    def take_lead(self, member_id: Slug) -> list[Fact]:
        """Decision 6: ids are kept. The new lead keeps theirs; the dead lead goes into the cast."""
        dead = self.player
        if dead.alive:
            raise Refusal(f"{dead.name} lives and leads")
        member = self.require_actor(member_id)
        if member is dead:
            raise Refusal(f"{dead.name} is dead and cannot lead")
        del self.cast[member.id]
        self.party.remove(member.id)
        self.run.here.remove(member.id)
        self.player = member
        self.cast[dead.id] = dead
        self.run.here.append(dead.id)
        trace = f"{member.tag} takes the lead; {dead.tag} is dead"
        return [member.fact(trace, card=f"{member.name} leads now")]


TwentyfourxxGame = Game[TwentyfourxxWorld]

TwentyfourxxScenario = Scenario[SceneDraft[Crewmate]]

TwentyfourxxCharacter = Character[Crewmate]


def raised(current: SkillDie | None) -> SkillDie:
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise Refusal("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]
