from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Mutable, Refusal, slug
from aidm.core.facts import Fact
from aidm.core.model import Character, Game, Scenario
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.views import Rows
from aidm.engines.base import NO_DICE, PLAYER_ID, Gauge, joined
from aidm.engines.rooms.world import Dweller, MapProposal, Prop, RoomWorld

type Ability = Literal["brute", "skulker", "erudite"]
type AbilityScores = dict[Ability, Annotated[int, Field(ge=0)]]
type Boost = Literal["health", "inventory"]
ABILITIES: tuple[Ability, ...] = ("brute", "skulker", "erudite")
HP_START = 10
INVENTORY_START = 8
ABILITY_POINTS = 3
STARTING_ITEMS = 3


class GoonSheet(Mutable):
    abilities: AbilityScores = Field(
        default_factory=lambda: dict.fromkeys(ABILITIES, 0), min_length=3, max_length=3
    )
    inventory: int = Field(default=INVENTORY_START, ge=0)
    level: int = Field(default=1, ge=1)

    def rows(self, *, carried: int | None = None) -> Rows:
        held = str(self.inventory) if carried is None else f"{carried}/{self.inventory}"
        return (
            *((ability.capitalize(), str(self.abilities[ability])) for ability in ABILITIES),
            ("Inventory", held),
            ("Level", str(self.level)),
        )

    def level_up(self, ability: Ability, boost: Boost, hp: Gauge) -> str:
        self.abilities[ability] += 1
        if boost == "health":
            hp.maximum += 1
            hp.current += 1
        else:
            self.inventory += 1
        self.level += 1
        return f"Level {self.level}: {ability.capitalize()} +1, {boost.capitalize()} +1"


class Goon(Dweller):
    """A character on the map, friend or enemy. Only a hired goon has dice. The player is one."""

    hp: Gauge
    sheet: GoonSheet | None = Field(default=None, description="Leave empty.")
    # The player's starting items by name; `new_game` files them as `Prop`s. Empty on an npc.
    kit: tuple[str, ...] = Field(default=(), description="Leave empty.")

    @property
    def hired(self) -> bool:
        return self.sheet is not None

    def require_sheet(self) -> GoonSheet:
        if self.sheet is None:
            raise Refusal(NO_DICE.format(name=self.name))
        return self.sheet

    def sign_on(self, abilities: AbilityScores) -> str:
        sheet = self.sheet = GoonSheet(abilities=dict(abilities))
        return ", ".join(
            f"{ability.capitalize()} {sheet.abilities[ability]}" for ability in ABILITIES
        )

    def rows(self, *, carried: int | None = None) -> Rows:
        if self.sheet is None:
            # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
            return (("Health", f"{self.hp} (its Difficulty Score)"),)
        return (("Health", str(self.hp)), *self.sheet.rows(carried=carried))

    def level(self, ability: Ability, boost: Boost) -> list[Fact]:
        card = self.card_line(self.require_sheet().level_up(ability, boost, self.hp))
        return [self.fact(card, card=card)]

    def required(self) -> str:
        return joined(
            super().required(),
            "no sheet" if self.sheet is not None else "",
            "no kit" if self.kit else "",
            "health above zero" if self.hp.current == 0 else "",
        )

    def unpack_kit(self, taken: Iterable[str]) -> tuple[Prop, ...]:
        made = [PLAYER_ID, *taken]
        items: list[Prop] = []
        for name in self.kit:
            item_id = slug(name, made)
            made.append(item_id)
            items.append(Prop(id=item_id, name=name, brief="", known=True, on=PLAYER_ID))
        return tuple(items)


class TunnelGoonsWorld(RoomWorld[Goon]):
    tempo = 4

    @model_validator(mode="after")
    def _player_carries_a_sheet(self) -> Self:
        if self.player.sheet is None:
            raise ValueError("the player carries no sheet")
        return self

    def sheet_rows(self) -> Rows:
        return self.player.rows(carried=len(list(self.carried(self.player.id))))

    def rest(self) -> list[Fact]:
        player = self.player
        members = self.members()
        facts = player.change(player.hp, player.hp.shortfall, "Health", "resting")
        for member in members:
            facts.extend(member.change(member.hp, member.hp.shortfall, "Health", "resting"))
        trace = f"{'the party' if members else 'the player'} rests at {self.current.mention}"
        facts.append(player.fact(trace, card=f"Rested — Health {player.hp}"))
        return facts

    def next_to_level(self, actor: Goon) -> Goon | None:
        members = [member for member in self.members() if member.hired]
        order = [self.player.id, *(member.id for member in members)]
        index = order.index(actor.id)
        return next(
            (member for member in members[index:] if member.require_sheet().level == 1), None
        )


TunnelGoonsGame = Game[TunnelGoonsWorld]

TunnelGoonsScenario = Scenario[MapProposal[Goon]]

TunnelGoonsCharacter = Character[Goon]


def level_up_decision(actor: Goon) -> PendingDecision:
    prompt = f"Level up: {actor.name}. Raise one ability by 1. Raise Health or Inventory by 1."
    options = tuple(
        PendingOption(
            id=f"{ability}-{boost}",
            name=f"{ability.capitalize()} +1, {boost.capitalize()} +1",
            tool_name="level_up",
            args={"ability": ability, "boost": boost},
        )
        for ability in ABILITIES
        for boost in ("health", "inventory")
    )
    return PendingDecision(kind="level-up", prompt=prompt, options=options, allows_text=False)
