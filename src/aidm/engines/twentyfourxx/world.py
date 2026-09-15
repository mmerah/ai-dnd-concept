from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import Field

from aidm.core.entities import Frozen, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Item, ItemSheet, Sheeted
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
SHIP_IDS: tuple[Slug, ...] = tuple(slug(name, ()) for name in SHIP_FUNCTIONS)
UPGRADE_COST = 10


class Kit(Frozen):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)
    harmless: bool = False  # SRD: "break harmlessly for defense"


class Gear(Item):
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)
    upgraded: bool = False
    harmless: bool = False

    @property
    def broken(self) -> bool:
        return self.broken_times >= self.breaks

    @property
    def broken_message(self) -> str:
        return f"{self.name} is already broken"

    @property
    def harmless_message(self) -> str:
        """Raised before the roll and inside the break, so the two must stay the same sentence."""
        return f"{self.name} breaks harmlessly: leave `hindrance` empty"

    def notes(self) -> str:
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


class CrewSheet(ItemSheet[Gear]):
    """The dice a crew member rolls."""

    specialty: str
    origin: str = ""  # empty on a hired member: the worldsmith writes no origin
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
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


class Crewmate(Sheeted[CrewSheet]):
    def sign_on(
        self,
        specialty: str,
        skills: Mapping[str, SkillDie],
        items: dict[Slug, Gear],
        hindrances: Sequence[str],
    ) -> str:
        self.sheet = CrewSheet(
            specialty=specialty,
            skills=dict(skills),
            credits=0,
            items=items,
            hindrances=list(hindrances),
        )
        return specialty

    def pay(self, cost: int) -> None:
        sheet = self.require_sheet()
        if cost > sheet.credits:
            raise Refusal(f"{self.name} has only ₡{sheet.credits}, not ₡{cost}")
        sheet.credits -= cost

    def change_hindrances(self, gained: Sequence[str], lost: Sequence[str]) -> list[Fact]:
        sheet = self.require_sheet()
        sheet.hindrances = self.changed_tags("hindrance", sheet.hindrances, gained, lost)
        parts: list[str] = []
        if gained:
            parts.append(f"Hindered: {', '.join(gained)}")
        if lost:
            parts.append(f"Recovered: {', '.join(lost)}")
        card = " / ".join(parts)
        trace = f"{self.mention} — {card}"
        return [self.fact(trace, card=self.card_line(card))]

    def gain_item(self, name: str, *, bulky: bool, breaks: int, cost: int) -> list[Fact]:
        self.pay(cost)
        items = self.require_sheet().items
        items[slug(name, [*items, *SHIP_IDS])] = Gear(name=name, bulky=bulky, breaks=breaks)
        suffix = f" (₡{cost})" if cost > 0 else ""
        card = f"Gained {name}{suffix}"
        trace = f"{self.mention} gains {name}{suffix}"
        return [self.fact(trace, card=self.card_line(card))]

    def repair_item(self, item: Gear, cost: int) -> list[Fact]:
        if item.broken_times == 0:
            raise Refusal(f"{item.name} is not broken")
        self.pay(cost)
        item.broken_times = 0
        trace = f"{self.mention} repairs {item.name}"
        return [self.fact(trace, card=self.card_line(f"Repaired {item.name}"))]

    def spend(self, amount: int, why: str) -> list[Fact]:
        self.pay(amount)
        trace = f"{self.mention} spends ₡{amount} — {why}"
        return [self.fact(trace, card=self.card_line(f"₡{amount} spent — {why}"))]

    def hinder(self, name: str) -> list[Fact]:
        sheet = self.require_sheet()
        if name in sheet.hindrances:
            return []
        sheet.hindrances.append(name)
        return [
            self.fact(
                f"{self.mention} is hindered — {name}", card=self.card_line(f"Hindered: {name}")
            )
        ]

    def raise_skill(self, label: str) -> list[Fact]:
        sheet = self.require_sheet()
        try:
            new_die = raised(sheet.skills.get(label))
        except Refusal as maxed:
            raise Refusal(
                f"{self.name}'s {label} is already at d12; raise another skill for them"
            ) from maxed
        sheet.skills[label] = new_die
        trace = f"{self.mention} — {label} rises to d{new_die}"
        return [self.fact(trace, card=self.card_line(f"Job done: {label} d{new_die}"))]

    def earn(self, credits: int, event: DiceEvent) -> list[Fact]:
        sheet = self.require_sheet()
        sheet.credits += credits
        return [
            self.fact(
                f"{self.mention} earns ₡{credits} → ₡{sheet.credits}",
                card=self.card_line(f"+₡{credits} → ₡{sheet.credits}"),
                dice=(event,),
            )
        ]

    def carried(self) -> str:
        if self.sheet is None:
            return ""
        return ", ".join(
            f"{item.name}[{key}]" + (f" ({notes})" if (notes := item.notes()) else "")
            for key, item in self.sheet.items.items()
        )


class TwentyfourxxWorld(SceneWorld[Crewmate]):
    job: str = ""
    ship: dict[Slug, Gear] = Field(
        default_factory=lambda: {
            key: Gear(name=name, harmless=name == "Hull armor")
            for key, name in zip(SHIP_IDS, SHIP_FUNCTIONS, strict=True)
        }
    )

    def sheet_rows(self) -> Rows:
        """The narrator and the page read the kit here; the master has its GEAR section."""
        gear = ", ".join(
            item.name + (f" ({notes})" if (notes := item.notes()) else "")
            for item in self.player.require_sheet().items.values()
        )
        rows = self.player.rows()
        return (*rows, ("Gear", gear)) if gear else rows

    def sheeted_members(self) -> list[Crewmate]:
        return [member for member in self.members() if member.hired]

    def require_gear(self, actor: Crewmate, item_id: Slug) -> Gear:
        """The actor's item or a ship function: both break to defend and both are repaired."""
        item = actor.require_sheet().items.get(item_id) or self.ship.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {actor.name}'s items or the ship's functions")
        return item

    def defend(self, actor_id: Slug | None, item_id: Slug, hindrance: str) -> list[Fact]:
        actor = self.require_actor(actor_id)
        item = self.require_gear(actor, item_id)
        if item.broken:
            raise Refusal(item.broken_message)
        return self._break(actor, item, hindrance)

    def take_hit(
        self,
        actor: Crewmate,
        item_id: Slug | None,
        risk: str,
        hindrance: str,
        *,
        disaster: bool,
        deadly: bool,
    ) -> list[Fact]:
        if not disaster and not deadly:
            return []
        if item_id is not None:
            item = self.require_gear(actor, item_id)
            return self._break(actor, item, hindrance)
        if disaster:
            return self.kill(actor.id) if deadly else actor.hinder(risk)
        return actor.hinder(MAIMED)

    def check_defenses(self, claims: Sequence[tuple[Crewmate, Slug, str]]) -> None:
        resolved = [
            (actor, self.require_gear(actor, item_id), hindrance)
            for actor, item_id, hindrance in claims
        ]
        # By identity: two actors can claim the same ship function, and Gear is unhashable.
        claimed = Counter(id(item) for _, item, _ in resolved)
        for actor, item, hindrance in resolved:
            if item.breaks - item.broken_times < claimed[id(item)]:
                raise Refusal(item.broken_message)
            if item.harmless:
                if hindrance:
                    raise Refusal(item.harmless_message)
                continue
            if not hindrance:
                raise Refusal(f"name the hindrance {item.name} leaves behind")
            if hindrance in actor.require_sheet().hindrances:
                raise Refusal(f"{actor.name} already carries the hindrance {hindrance!r}")

    def _break(self, actor: Crewmate, item: Gear, hindrance: str) -> list[Fact]:
        if item.harmless:
            if hindrance:
                raise Refusal(item.harmless_message)
            item.broken_times += 1
            trace = f"{actor.mention} breaks {item.name}, harmlessly"
            return [actor.fact(trace, card=actor.card_line(f"{item.name} breaks"))]
        if not hindrance:
            raise Refusal("name the hindrance the hit becomes")
        sheet = actor.require_sheet()
        sheet.hindrances = actor.changed_tags("hindrance", sheet.hindrances, (hindrance,), ())
        item.broken_times += 1
        card = actor.card_line(f"{item.name} breaks — {hindrance}")
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
        """The new lead keeps their id; the dead lead is filed in the cast under theirs."""
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

    def take_job(self, terms: str) -> list[Fact]:
        if self.job:
            raise Refusal(f"a job is open: {self.job}")
        self.job = terms
        return [self.player.fact(f"the job is taken: {terms}", card=f"Job taken\n{terms}")]

    def close_job(self) -> None:
        self.job = ""


TwentyfourxxGame = Game[TwentyfourxxWorld]

TwentyfourxxScenario = Scenario[SceneDraft[Crewmate]]

TwentyfourxxCharacter = Character[Crewmate]


def raised(current: SkillDie | None) -> SkillDie:
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise Refusal("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]
