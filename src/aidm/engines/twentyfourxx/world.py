from collections.abc import Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import EntityId, Frozen, Mutable, Refusal, require_unique, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

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
HULL_ARMOR: EntityId = EntityId("hull-armor")


class Kit(Frozen):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)


class Item(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)
    upgraded: bool = False

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
        if self.upgraded:
            parts.append("upgraded")
        return ", ".join(parts)


class Sheet(Mutable):
    """What the rules roll for: the player's from creation, a hired member's from the worldsmith."""

    specialty: str
    origin: str = ""  # empty on a hired member: the worldsmith writes no origin
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    hindrances: list[str] = Field(default_factory=list)

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


class Crewmate(Person):
    """One type plays the player and the cast alike; only a sheet says who has dice."""

    sheet: Sheet | None = Field(
        default=None,
        description="Never written by you: code installs it when the player hires them.",
    )

    def dice(self) -> Sheet:
        if self.sheet is None:
            raise Refusal(f"{self.name} carries no dice")
        return self.sheet

    def require_item(self, item_id: EntityId) -> Item:
        item = self.dice().items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {self.name}'s items")
        return item

    def pay(self, cost: int) -> None:
        sheet = self.dice()
        if cost > sheet.credits:
            raise Refusal(f"{self.name} has only ₡{sheet.credits}, not ₡{cost}")
        sheet.credits -= cost

    def change_hindrances(self, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        sheet = self.dice()
        require_unique("gained hindrances", gained)
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
        trace = f"{self.label} — {card}"
        return [self.fact("hindrances_changed", trace, card=card)]

    def gain_item(self, name: str, *, bulky: bool, breaks: int, cost: int) -> list[Fact]:
        self.pay(cost)
        items = self.dice().items
        items[EntityId(slug(name, items))] = Item(name=name, bulky=bulky, breaks=breaks)
        suffix = f" (₡{cost})" if cost > 0 else ""
        card = f"Gained {name}{suffix}"
        trace = f"{self.label} gains {name}{suffix}"
        return [self.fact("item_gained", trace, card=card)]

    def drop_item(self, item_id: EntityId) -> list[Fact]:
        item = self.require_item(item_id)
        del self.dice().items[item_id]
        trace = f"{self.label} drops {item.name}"
        return [self.fact("item_dropped", trace, card=f"Dropped {item.name}")]

    def repair_item(self, item: Item, cost: int) -> list[Fact]:
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

    def rows(self) -> Rows:
        if self.sheet is None:
            return ()
        gear = ", ".join(
            item.name + (f" ({detail})" if (detail := item.detail()) else "")
            for item in self.sheet.items.values()
        )
        return (*self.sheet.rows(), *((("Gear", gear),) if gear else ()))

    def unwritten(self) -> str:
        parts = [
            part
            for part in (super().unwritten(), "a sheet" if self.sheet is not None else "")
            if part
        ]
        return ", ".join(parts)


class TwentyfourxxWorld(SceneWorld[Crewmate, Crewmate]):
    job: str = ""
    ship: dict[EntityId, Item] = Field(
        default_factory=lambda: {
            EntityId(slug(name, ())): Item(name=name) for name in SHIP_FUNCTIONS
        }
    )

    @model_validator(mode="after")
    def _player_carries_a_sheet(self) -> Self:
        if self.player.sheet is None:
            raise ValueError("the player carries no sheet")
        return self

    def sheeted_members(self) -> list[Crewmate]:
        return [member for member in self.members() if member.sheet is not None]

    def require_actor(self, actor_id: EntityId | None) -> Crewmate:
        if actor_id is None or actor_id == self.player.id:
            return self.player
        entity = self.require(actor_id)
        if entity.alive and entity.sheet is not None and entity.id in self.party:
            return entity
        raise Refusal(f"{entity.name} is not the player or a hired crew member")

    def require_hireable(self, entity_id: EntityId) -> Crewmate:
        member = self.require_here(entity_id, alive=True)
        if member.sheet is not None:
            raise Refusal(f"{member.name} already carries a sheet")
        return member

    def require_gear(self, actor: Crewmate, item_id: EntityId) -> Item:
        """The actor's item or a ship function: both break to defend and both are repaired."""
        item = actor.dice().items.get(item_id) or self.ship.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {actor.name}'s items or the ship's functions")
        return item

    def defend(self, actor_id: EntityId | None, item_id: EntityId, hindrance: str) -> list[Fact]:
        actor = self.require_actor(actor_id)
        item = self.require_gear(actor, item_id)
        if item.broken:
            raise Refusal(f"{item.name} is already broken")
        if item_id == HULL_ARMOR:
            if hindrance:
                raise Refusal("hull armor breaks harmlessly: leave `hindrance` empty")
            item.broken_times += 1
            trace = f"{actor.label} breaks the hull armor"
            return [actor.fact("item_broken", trace, card="Hull armor breaks")]
        if not hindrance:
            raise Refusal("name the hindrance the hit becomes")
        sheet = actor.dice()
        if hindrance in sheet.hindrances:
            raise Refusal(f"{hindrance!r} is already among {actor.name}'s hindrances")
        item.broken_times += 1
        sheet.hindrances.append(hindrance)
        card = f"{item.name} breaks — {hindrance}"
        trace = f"{actor.label} breaks {item.name} — {hindrance}"
        return [actor.fact("item_broken", trace, card=card)]

    def upgrade_ship(self, function_id: EntityId) -> list[Fact]:
        function = self.ship.get(function_id)
        if function is None:
            raise Refusal(f"{function_id!r} is not a ship function")
        if function.upgraded:
            raise Refusal(f"{function.name} is already upgraded")
        self.player.pay(UPGRADE_COST)
        function.upgraded = True
        trace = f"the ship's {function.name} is upgraded (₡{UPGRADE_COST})"
        card = f"{function.name} upgraded — ₡{UPGRADE_COST}"
        return [self.player.fact("ship_upgraded", trace, card=card)]

    def take_lead(self, member_id: EntityId) -> list[Fact]:
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
        return [member.fact("lead_taken", trace, card=f"{member.name} leads now")]


TwentyfourxxGame = Game[TwentyfourxxWorld]

TwentyfourxxScenario = Scenario[SceneCanon[Crewmate]]

TwentyfourxxCharacter = Character[Crewmate]


def raised(current: SkillDie | None) -> SkillDie:
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise Refusal("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]
