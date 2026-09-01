from typing import Annotated, Literal, get_args

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Counter, Frozen, Mutable, Slug, pool
from aidm.core.model import Character, Game, Scenario
from aidm.kits.rooms.state import RoomCanon, RoomWorld

MAX_LEVEL = 7
BASE_ARMOUR = 6
BASE_HEALTH = 4
HEALTH_PER_LEVEL = 2
ABILITY_MAX = 4
XP_FOR_LEVEL = (2, 6, 12, 20, 30, 42)  # index 0 is the XP that buys level 2

type Ability = Literal["strength", "dexterity", "will"]
type Path = Literal["briarborn", "fingersmith", "roofrunner", "shadowjack"]
type WeaponClass = Literal["light", "heavy", "ranged"]
type ArmourClass = Literal["light", "heavy"]
type CarryPosition = Literal["worn", "belt", "backpack", "hands"]
type Side = Literal["players", "enemies"]

ABILITIES: tuple[Ability, ...] = get_args(Ability.__value__)
PATHS: tuple[Path, ...] = get_args(Path.__value__)
WEAPON_CLASSES: tuple[WeaponClass, ...] = get_args(WeaponClass.__value__)


def _health() -> Counter:
    return Counter(current=BASE_HEALTH, maximum=BASE_HEALTH)


class ItemSheet(Mutable):
    """Only equipment categories that alter a Maze Rats procedure belong here."""

    kind: Literal["item"] = "item"
    weapon: WeaponClass | None = None
    armour: ArmourClass | None = None
    shield: bool = False
    medicine: bool = False
    position: CarryPosition = "backpack"

    @model_validator(mode="after")
    def _one_mechanical_role(self) -> "ItemSheet":
        if self.weapon is not None and self.armour is not None:
            raise ValueError("one item cannot be both a weapon and armour")
        if self.shield and (self.weapon is not None or self.armour is not None):
            raise ValueError("a shield is not also a weapon or armour")
        if self.medicine and (self.weapon is not None or self.armour is not None or self.shield):
            raise ValueError("medicine is not also a weapon, armour, or shield")
        if self.shield and self.position != "hands":
            raise ValueError("a shield must be carried in the hands")
        if self.armour is not None and self.position != "worn":
            raise ValueError("armour must be worn")
        return self

    def rows(self) -> tuple[tuple[str, str], ...]:
        category = (
            self.weapon
            or self.armour
            or ("shield" if self.shield else "medicine" if self.medicine else "ordinary")
        )
        return (("Category", category), ("Carry", self.position))


class InventoryItem(Frozen):
    """A starting item retained until the rooms world can materialize it."""

    id: CheckedEntityId
    name: str = Field(min_length=1)
    sheet: ItemSheet


class ActorSheet(Mutable):
    """The compact mechanical sheet used by player characters and monsters."""

    kind: Literal["actor"] = "actor"
    strength: int = Field(default=0, ge=0, le=ABILITY_MAX)
    dexterity: int = Field(default=0, ge=0, le=ABILITY_MAX)
    will: int = Field(default=0, ge=0, le=ABILITY_MAX)
    health: Counter = Field(default_factory=_health)
    # Innate armour above the base 6, so a monster's total lands in the SRD's 6-10 categories.
    armour: int = Field(default=0, ge=0, le=4)
    attack_bonus: int = Field(default=0, ge=0, le=4)
    level: int = Field(default=1, ge=1, le=MAX_LEVEL)
    xp: int = Field(default=0, ge=0)
    paths: tuple[Path, ...] = ()
    spell_slots: tuple[str | None, ...] = ()
    dosed: bool = False

    def ability(self, name: Ability) -> int:
        return getattr(self, name)

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("STR / DEX / WIL", f"{self.strength:+d} / {self.dexterity:+d} / {self.will:+d}"),
            ("Health", pool(self.health)),
            ("Armour", str(self.armour)),
            ("Attack bonus", f"{self.attack_bonus:+d}"),
            ("Level / XP", f"{self.level} / {self.xp}"),
            ("Paths", ", ".join(self.paths)),
            ("Spell slots", ", ".join(slot or "(empty)" for slot in self.spell_slots)),
        )


MazeRatsSheet = Annotated[ActorSheet | ItemSheet, Field(discriminator="kind")]
type MazeRatsWorld = RoomWorld[MazeRatsSheet]
type MazeRatsCanon = RoomCanon[MazeRatsSheet]


class CombatState(Mutable):
    """Transient combat bookkeeping; combat is discarded when it ends."""

    round: int = Field(default=1, ge=1)
    player_side: tuple[CheckedEntityId, ...] = ()
    enemy_side: tuple[CheckedEntityId, ...] = ()
    first_side: Side
    acting_side: Side
    acted: tuple[CheckedEntityId, ...] = ()
    ambusher: Side | None = None


class PendingAttack(Mutable):
    """A hit awaiting the target's shield decision."""

    attacker_id: CheckedEntityId
    target_id: CheckedEntityId
    weapon_id: CheckedEntityId | None = None
    damage: int = Field(ge=1)


class MazeRatsState(Mutable):
    engine: Literal["mazerats"] = "mazerats"
    world: MazeRatsWorld
    combat: CombatState | None = None
    pending_attack: PendingAttack | None = None
    pending_level_up: CheckedEntityId | None = None


class MazeRatsScenario(Mutable):
    engine: Literal["mazerats"] = "mazerats"
    world: MazeRatsCanon


class MazeRatsCharacter(Mutable):
    engine: Literal["mazerats"] = "mazerats"
    sheet: ActorSheet
    inventory: tuple[InventoryItem, ...] = ()
    pack: Slug | None = None


class MazeRatsGame(Game[MazeRatsState]):
    pass


class MazeRatsScenarioFile(Scenario[MazeRatsScenario]):
    pass


class MazeRatsCharacterFile(Character[MazeRatsCharacter]):
    pass
