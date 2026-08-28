from abc import ABC, abstractmethod
from collections.abc import Mapping
from random import Random
from typing import Self

from pydantic import Field, JsonValue, ValidationError, model_validator

from aidm.content.model import Scenario
from aidm.engines.core import (
    Advancement,
    Command,
    Engine,
    NoArgs,
    apply_action,
    command,
)
from aidm.state.entities import PLAYER_ID, Counter, Entity, EntityId, Mutable, Slug, require_unique
from aidm.state.facts import Fact, MechanicEvent
from aidm.state.model import Game, WorldState


def require_sheet[S](sheets: Mapping[EntityId, S], actor: Entity) -> S:
    sheet = sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


class SheetBase(Mutable, ABC):
    """One actor's mechanics, whatever this engine's rules make of them."""

    packs: tuple[Slug, ...] = ("srd",)

    @model_validator(mode="after")
    def _packs_include_srd(self) -> Self:
        require_unique("sheet pack ids", self.packs)
        if "srd" not in self.packs:
            raise ValueError("sheet packs must include 'srd'")
        return self

    @abstractmethod
    def rows(self) -> tuple[tuple[str, str], ...]:
        """Every view of this sheet: labels head the player's panel, and a prompt lowers them."""


class ItemBase(Mutable, ABC):
    @abstractmethod
    def rows(self) -> tuple[tuple[str, str], ...]:
        """The item's state as a prompt reads it; empty values are dropped."""


class SheetMechanics[S: SheetBase, I: ItemBase = ItemBase](Mutable):
    sheets: dict[EntityId, S] = Field(default_factory=dict)
    items: dict[EntityId, I] = Field(default_factory=dict)
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


class SheetAdvancement(Advancement):
    def earned(self, state: Game) -> int:
        return SheetMechanics.of_game(state).completed.current


def _validated[M: SheetBase | ItemBase](model: type[M], where: str, entity: Entity) -> M:
    try:
        return model.model_validate(entity.rules)
    except ValidationError as broken:
        first = broken.errors()[0]
        place = ".".join(str(part) for part in (where, entity.id, *first["loc"]))
        raise ValueError(f"{place}: {first['msg']}") from broken


class SheetEngine[S: SheetBase, I: ItemBase = ItemBase](Engine):
    sheet_type: type[S]
    item_type: type[I] | None = None
    # Narrows a class attribute the base only ever reads; `Engine` itself is not generic.
    mechanics_type: type[SheetMechanics[S, I]]  # pyright: ignore[reportIncompatibleVariableOverride]

    def overlay_rows(self, rules: dict[str, JsonValue]) -> tuple[tuple[str, str], ...]:
        return self.sheet_type.model_validate(rules).rows()

    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> SheetMechanics[S, I]:
        # Validated as one map so a bad overlay is refused at `sheets.<entity id>.<field>`.
        return self.mechanics_type.model_validate(
            {
                "sheets": {
                    entity.id: player_rules if entity.id == PLAYER_ID else entity.rules
                    for entity in world.entities
                    if entity.id == PLAYER_ID or self.uses_sheet(entity)
                },
                "items": {
                    entity.id: entity.rules
                    for entity in world.entities
                    if self.uses_item_sheet(entity)
                },
            }
        )

    def uses_sheet(self, entity: Entity) -> bool:
        return bool(entity.rules) and not self.uses_item_sheet(entity)

    def uses_item_sheet(self, entity: Entity) -> bool:
        return self.item_type is not None and entity.kind == "item" and bool(entity.rules)

    def check_scenario(self, scenario: Scenario) -> None:
        super().check_scenario(scenario)
        for entity in scenario.world.entities:
            if not entity.rules:
                continue
            if self.item_type is not None and self.uses_item_sheet(entity):
                _ = _validated(self.item_type, "items", entity)
                continue
            sheet = _validated(self.sheet_type, "sheets", entity)
            if missing := sorted(set(sheet.packs) - set(scenario.packs)):
                raise ValueError(
                    f"{entity.id!r} uses packs the scenario does not select: {missing}"
                )
            self.check_sheet(entity, sheet)

    def check_sheet(self, entity: Entity, sheet: S) -> None:
        del entity, sheet

    def validate(self, state: Game) -> None:
        mechanics = self.mechanics_type.of_game(state)
        self._check_items(state, mechanics.items)
        sheets = mechanics.sheets
        if state.player_id not in sheets:
            raise ValueError(f"the {self.id} mechanics name no player")
        required = {entity.id for entity in state.world.entities if self.uses_sheet(entity)}
        if missing := sorted(required - set(sheets)):
            raise ValueError(f"entities have no character sheet to play by: {missing}")
        if gone := sorted(set(sheets) - state.world.all_ids()):
            raise ValueError(f"mechanics name actors the world does not hold: {gone}")
        installed = set(self.pack_ids)
        if missing_packs := sorted(
            {pack for sheet in sheets.values() for pack in sheet.packs if pack not in installed}
        ):
            raise ValueError(f"sheets use packs that are not installed: {missing_packs}")

    def _check_items(self, state: Game, items: Mapping[EntityId, I]) -> None:
        required = {entity.id for entity in state.world.entities if self.uses_item_sheet(entity)}
        if missing := sorted(required - set(items)):
            raise ValueError(f"items have no item sheet to play by: {missing}")
        if gone := sorted(set(items) - state.world.all_ids()):
            raise ValueError(f"mechanics name items the world does not hold: {gone}")

    def meanings(self, sheet: S) -> tuple[tuple[str, str], ...]:
        del sheet
        return ()

    def describe(self, state: Game, entity: Entity) -> str:
        mechanics = self.mechanics_type.of_game(state)
        sheet = mechanics.sheets.get(entity.id)
        if sheet is not None:
            return _described(sheet.rows(), self.meanings(sheet))
        item = mechanics.items.get(entity.id)
        return "" if item is None else _described(item.rows(), ())

    def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
        return self.mechanics_type.of_game(state).sheets[state.player_id].rows()

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng
        mechanics = self.mechanics_type.of_game(draft)
        if self.item_type is not None and self.uses_item_sheet(entity):
            mechanics.items[entity.id] = self.item_type.model_validate(entity.rules)
            return
        if not self.uses_sheet(entity) or entity.id in mechanics.sheets:
            return
        # The sheet lands first: the ledger this brings level is a counter on it.
        mechanics.sheets[entity.id] = self.sheet_type.model_validate(entity.rules)
        # A newcomer starts level with the party: what closed before they joined is not owed.
        if self.advancement is not None:
            self.advancement.ledger(draft, entity.id).current = mechanics.completed.current


def _described(rows: tuple[tuple[str, str], ...], meanings: tuple[tuple[str, str], ...]) -> str:
    lines: list[str] = []
    for label, value in rows:
        if not value:
            continue
        lines.append(f"{label.lower()}: {value}")
        listed = value.split(", ")
        lines.extend(f"- {tag}: {detail}" for tag, detail in meanings if tag in listed)
    return "\n".join(lines)


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


def chapter_command(description: str, ending: str) -> Command:
    """Every engine closes a chapter the same way; only what it calls one differs."""
    return command(
        "complete_chapter",
        description,
        NoArgs,
        lambda deps, _args: apply_action(deps, lambda draft: complete_chapter(draft, ending)),
    )
