from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field

from aidm.core.entities import Slug, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.views import Rows
from aidm.engines.base import PLAYER_ID, Gauge, Sheet, Sheeted
from aidm.engines.rooms.world import Dweller, MapDraft, Prop, RoomWorld

type Ability = Literal["brute", "skulker", "erudite"]
type AbilityScores = dict[Ability, Annotated[int, Field(ge=0)]]
type Boost = Literal["health", "inventory"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class GoonSheet(Sheet):
    """The three ability scores a goon rolls with."""

    abilities: AbilityScores = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)

    def rows(self) -> Rows:
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Inventory", str(self.inventory)),
            ("Level", str(self.level)),
        )


class Adventurer(Sheeted[GoonSheet]):
    hp: Gauge

    def rows(self) -> Rows:
        return (("Health", str(self.hp)), *self.require_sheet().rows())

    def level(self, ability: Ability, boost: Boost) -> list[Fact]:
        sheet = self.require_sheet()
        sheet.abilities[ability] += 1
        if boost == "health":
            self.hp.maximum += 1
            self.hp.current += 1
        else:
            sheet.inventory += 1
        sheet.level += 1
        card = f"Level {sheet.level}: {ability.capitalize()} +1, {boost.capitalize()} +1"
        if self.id != PLAYER_ID:
            card = f"{self.name}: {card}"
        return [self.fact(card, card=card)]

    def level_decision(self) -> PendingDecision:
        prompt = f"Level up: {self.name} — raise one ability by 1, and Health or Inventory by 1."
        return PendingDecision(
            kind="level-up", prompt=prompt, options=level_options(self.id), allows_text=False
        )


class Npc(Adventurer, Dweller):
    """A non-player character, friend or foe."""

    def rows(self) -> Rows:
        if self.hired:
            return super().rows()
        # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
        return (("Health", f"{self.hp} (its Difficulty Score)"),)


class Goon(Adventurer):
    hp: Gauge = Field(default_factory=lambda: Gauge(current=HP_START, maximum=HP_START))
    # The starting items by name; `new_game` files them as `Prop`s on the player.
    kit: tuple[str, ...] = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)

    def unpack_kit(self, taken: Iterable[str]) -> tuple[Prop, ...]:
        made = list(taken)
        items: list[Prop] = []
        for name in self.kit:
            item_id = slug(name, made)
            made.append(item_id)
            items.append(Prop(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)


class TunnelGoonsWorld(RoomWorld[Npc, Goon]):
    def sheet_rows(self) -> Rows:
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
        facts = player.change(player.hp, player.hp.shortfall, "Health", "resting")
        for member in members:
            facts.extend(member.change(member.hp, member.hp.shortfall, "Health", "resting"))
        trace = f"{'the party' if members else 'the player'} rests at {self.current.mention}"
        facts.append(player.fact(trace, card=f"Rested — Health {player.hp}"))
        return facts

    def next_to_level(self, actor: Adventurer) -> Npc | None:
        members = [member for member in self.members() if member.hired]
        order = [self.player.id, *(member.id for member in members)]
        index = order.index(actor.id)
        return members[index] if index < len(members) else None


TunnelGoonsGame = Game[TunnelGoonsWorld]

TunnelGoonsScenario = Scenario[MapDraft[Npc]]

TunnelGoonsCharacter = Character[Goon]


def level_options(actor_id: Slug) -> tuple[PendingOption, ...]:
    return tuple(
        PendingOption(
            id=f"{ability}-{boost}",
            label=f"{ability.capitalize()} +1, {boost.capitalize()} +1",
            name="level_up",
            args={"ability": ability, "boost": boost, "actor_id": actor_id},
        )
        for ability in ABILITIES
        for boost in ("health", "inventory")
    )
