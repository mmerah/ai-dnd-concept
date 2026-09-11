from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field

from aidm.core.entities import Mutable, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.prompt import Pairs
from aidm.engines.base import PLAYER_ID, Gauge, Sheeted
from aidm.engines.rooms.world import Dweller, MapDraft, Prop, RoomWorld

type Ability = Literal["brute", "skulker", "erudite"]
type AbilityScores = dict[Ability, Annotated[int, Field(ge=0)]]
type Boost = Literal["health", "inventory"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class GoonSheet(Mutable):
    """The three ability scores a goon rolls with."""

    abilities: AbilityScores = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)

    def rows(self, hp: Gauge) -> Pairs:
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Health", str(hp)),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )


class Npc(Sheeted[GoonSheet], Dweller):
    """A non-player character, friend or foe."""

    # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
    hp: Gauge

    def rows(self) -> Pairs:
        if self.hired:
            return self.require_sheet().rows(self.hp)
        return (("Health", f"{self.hp} (its Difficulty Score)"),)


class Goon(Sheeted[GoonSheet]):
    hp: Gauge = Field(default_factory=lambda: Gauge(current=HP_START, maximum=HP_START))
    # The starting items by name; `new_game` files them as `Prop`s on the player.
    kit: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    def rows(self) -> Pairs:
        return self.require_sheet().rows(self.hp)

    def unpack_kit(self, taken: Iterable[str]) -> tuple[Prop, ...]:
        made = list(taken)
        items: list[Prop] = []
        for name in self.kit:
            item_id = slug(name, made)
            made.append(item_id)
            items.append(Prop(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)


class TunnelGoonsWorld(RoomWorld[Npc, Goon]):
    def sheet_rows(self) -> Pairs:
        carried = len(list(self.carried(self.player.id)))
        return tuple(
            (label, f"{carried}/{self.player.require_sheet().inventory}")
            if label == "Inventory"
            else (label, value)
            for label, value in self.player.rows()
        )

    def rest(self) -> list[Fact]:
        player = self.player
        members = self.members()
        facts = player.hp.change(player, player.hp.shortfall, "Health", "resting")
        for member in members:
            facts.extend(member.hp.change(member, member.hp.shortfall, "Health", "resting"))
        trace = f"{'the party' if members else 'the player'} rests at {self.current.mention}"
        facts.append(player.fact(trace, card=f"Rested — Health {player.hp}"))
        return facts

    def next_to_level(self, actor: Goon | Npc) -> Npc | None:
        members = [member for member in self.members() if member.hired]
        order = [self.player.id, *(member.id for member in members)]
        index = order.index(actor.id)
        return members[index] if index < len(members) else None


TunnelGoonsGame = Game[TunnelGoonsWorld]

TunnelGoonsScenario = Scenario[MapDraft[Npc]]

TunnelGoonsCharacter = Character[Goon]
