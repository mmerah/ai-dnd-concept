from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field

from aidm.core.entities import EntityId, slug
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Counter, Person
from aidm.engines.rooms.world import Dweller, Item, RoomCanon, RoomWorld

Ability = Literal["brute", "skulker", "erudite"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
Boost = Literal["health", "inventory"]
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class Npc(Dweller):
    """Every non-player character, friend or foe: the SRD gives them one shape."""

    # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
    hp: Counter

    def rows(self) -> Rows:
        return (("Health", f"{self.hp} (its Difficulty Score)"),)


class Goon(Person):
    """The played character: the only one with abilities, and the only one who rolls."""

    abilities: dict[Ability, Annotated[int, Field(ge=0)]] = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    hp: Counter = Field(default_factory=lambda: Counter(current=HP_START, maximum=HP_START))
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)
    # The starting items by name; `new_game` files them as `Item`s on the player.
    kit: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    def rows(self) -> Rows:
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Health", str(self.hp)),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )

    def starting_items(self, taken: Iterable[str]) -> tuple[Item, ...]:
        """The kit filed as `Item`s on the player, with ids clear of every id already taken."""
        made = list(taken)
        items: list[Item] = []
        for name in self.kit:
            item_id = EntityId(slug(name, made))
            made.append(item_id)
            items.append(Item(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)


class TunnelGoonsWorld(RoomWorld[Npc, Goon]):
    def sheet_rows(self) -> Rows:
        carried = len(list(self.carried(self.player.id)))
        return tuple(
            (label, f"{carried}/{self.player.inventory}")
            if label == "Inventory"
            else (label, value)
            for label, value in self.player.rows()
        )


class TunnelGoonsGame(Game[TunnelGoonsWorld]):
    pass


class TunnelGoonsScenario(Scenario[RoomCanon[Npc]]):
    pass


class TunnelGoonsCharacter(Character[Goon]):
    pass
