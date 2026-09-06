from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field

from aidm.core.entities import EntityId, Mutable, Refusal, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, UNKNOWN_ID, Counter, Person
from aidm.engines.rooms.world import Dweller, Item, RoomCanon, RoomWorld

Ability = Literal["brute", "skulker", "erudite"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
AbilityScores = dict[Ability, Annotated[int, Field(ge=0)]]
Boost = Literal["health", "inventory"]
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class Abilities(Mutable):
    """What a goon carries beside `hp`: the player's own, or a hired npc's."""

    abilities: AbilityScores = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)

    def rows(self, hp: Counter) -> Rows:
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Health", str(hp)),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )


class Npc(Dweller):
    """Every non-player character, friend or foe: the SRD gives them one shape."""

    # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
    hp: Counter
    sheet: Abilities | None = None

    def rows(self) -> Rows:
        if self.sheet is not None:
            return self.sheet.rows(self.hp)
        return (("Health", f"{self.hp} (its Difficulty Score)"),)


class Goon(Person):
    hp: Counter = Field(default_factory=lambda: Counter(current=HP_START, maximum=HP_START))
    sheet: Abilities
    # The starting items by name; `new_game` files them as `Item`s on the player.
    kit: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    def rows(self) -> Rows:
        return self.sheet.rows(self.hp)

    def starting_items(self, taken: Iterable[str]) -> tuple[Item, ...]:
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
            (label, f"{carried}/{self.player.sheet.inventory}")
            if label == "Inventory"
            else (label, value)
            for label, value in self.player.rows()
        )

    def require_actor(self, actor_id: EntityId | None) -> tuple[Goon | Npc, Abilities]:
        if actor_id is None or actor_id == self.player.id:
            return self.player, self.player.sheet
        npc = self.npcs.get(actor_id)
        if npc is None:
            raise Refusal(UNKNOWN_ID.format(entity_id=actor_id))
        if npc.alive and npc.sheet is not None and npc.id in self.party:
            return npc, npc.sheet
        raise Refusal(f"{npc.name} is not the player or a hired party member")

    def require_hireable(self, entity_id: EntityId) -> Npc:
        npc = self.require_npc_here(entity_id)
        if npc.sheet is not None:
            raise Refusal(f"{npc.name} already carries a sheet")
        return npc

    def rest(self) -> list[Fact]:
        player = self.player
        members = self.members()
        facts = player.hp.change(player, player.hp.shortfall, "Health", "resting")
        for member in members:
            facts.extend(member.hp.change(member, member.hp.shortfall, "Health", "resting"))
        trace = f"{'the party' if members else 'the player'} rests at {self.current.label}"
        facts.append(player.fact("rested", trace, card=f"Rested — Health {player.hp}"))
        return facts

    def next_to_level(self, actor: Goon | Npc) -> Npc | None:
        members = [member for member in self.members() if member.sheet is not None]
        order = [self.player.id, *(member.id for member in members)]
        index = order.index(actor.id)
        return members[index] if index < len(members) else None


TunnelGoonsGame = Game[TunnelGoonsWorld]

TunnelGoonsScenario = Scenario[RoomCanon[Npc]]

TunnelGoonsCharacter = Character[Goon]
