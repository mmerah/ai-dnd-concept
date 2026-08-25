from abc import ABC
from collections.abc import Mapping
from random import Random
from typing import Self

from pydantic import Field, JsonValue

from aidm.engines.core import Advancement, Engine, pool
from aidm.state.entities import PLAYER_ID, Counter, EngineId, Entity, EntityId, Mutable, Slug
from aidm.state.facts import Fact, MechanicEvent
from aidm.state.model import Game, WorldState


def actor_sheets[S: Mutable](
    world: WorldState, player_rules: dict[str, JsonValue], sheet: type[S]
) -> dict[EntityId, S]:
    return {
        entity.id: sheet.model_validate(player_rules if entity.id == PLAYER_ID else {})
        for entity in world.of_kind("actor")
    }


def check_sheets(world: WorldState, sheets: Mapping[EntityId, object], engine: EngineId) -> None:
    if PLAYER_ID not in sheets:
        raise ValueError(f"the {engine} mechanics name no player")
    actors = {entity.id for entity in world.of_kind("actor")}
    if missing := sorted(actors - set(sheets)):
        raise ValueError(f"actors carry no character sheet: {missing}")
    if gone := sorted(set(sheets) - world.all_ids()):
        raise ValueError(f"mechanics name actors the world does not hold: {gone}")


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


def render_counters(counters: dict[Slug, Counter]) -> str:
    return ", ".join(f"{key} {pool(counters[key])}" for key in sorted(counters))


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""


class SheetMechanics[S: SheetBase](Mutable):
    sheets: dict[EntityId, S] = Field(default_factory=dict)
    # How many chapters the fiction has closed, game-wide: what advancement is owed against.
    completed: Counter = Counter(current=0)

    @classmethod
    def of_game(cls, state: Game) -> Self:
        mechanics = state.mechanics
        if not isinstance(mechanics, cls):
            # Both engines name their model `Mechanics`, so only the module tells them apart.
            raise ValueError(
                f"the state carries {type(mechanics).__module__} mechanics, not {cls.__module__}"
            )
        return mechanics


def complete_chapter(draft: Game, ending: str) -> list[Fact]:
    SheetMechanics.of_game(draft).completed.current += 1
    return [
        Fact(
            kind="chapter_completed",
            trace=ending,
            told=True,
            event=MechanicEvent(title=ending, icon="auto_stories"),
        )
    ]


class SheetAdvancement(Advancement):
    def earned(self, state: Game) -> int:
        return SheetMechanics.of_game(state).completed.current


class SheetEngine[S: SheetBase](Engine):
    """An engine whose mechanics are one sheet per actor; the shelf's shape."""

    sheet_type: type[S]
    # Narrows a class attribute the base only ever reads; `Engine` itself is not generic.
    mechanics_type: type[SheetMechanics[S]]  # pyright: ignore[reportIncompatibleVariableOverride]

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = self.sheet_type.model_validate(rules)

    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> SheetMechanics[S]:
        return self.mechanics_type(sheets=actor_sheets(world, player_rules, self.sheet_type))

    def validate(self, state: Game) -> None:
        check_sheets(state.world, self.mechanics_type.of_game(state).sheets, self.id)

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng
        mechanics = self.mechanics_type.of_game(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # The sheet lands first: the ledger this brings level is a counter on it.
        mechanics.sheets[entity.id] = self.sheet_type()
        if self.advancement is not None:
            # A newcomer starts level with the party: what closed before they joined is not owed.
            self.advancement.ledger(draft, entity.id).current = mechanics.completed.current
