from collections.abc import Callable
from typing import cast

import pytest
from fivee_test_support import carried_by, initial_5e_game, player_of
from pydantic_ai import ModelRetry, NativeOutput, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.base import EntityId
from aidm.engine import Engine
from aidm.engines.dnd5e.direction import Attack, Damage, Dnd5eDirection, DropItem, RollCheck
from aidm.transition import Direction
from aidm.world import GameState


def _context(state: GameState) -> RunContext[GameState]:
    return RunContext(deps=state, model=TestModel(), usage=RunUsage())


def _propose(engine: Engine, state: GameState, proposal: Dnd5eDirection) -> None:
    """Drive the whole Director path: dump, check, and dry-run, as the model's own call would.

    `director_output` is built as a `NativeOutput` wrapping one output function; narrow to that
    concrete shape by hand, since the seam's declared type is the broader `OutputSpec` union."""
    native = cast(NativeOutput[Direction], engine.director_output)
    direct = cast(
        Callable[[RunContext[GameState], Dnd5eDirection], Direction],
        native.outputs,
    )
    _ = direct(_context(state), proposal)


def test_nested_faults_and_absent_references_return_actionable_retries() -> None:
    engine, state = initial_5e_game()
    unknown = Dnd5eDirection(
        intent="Something impossible happens.",
        tone="uncertain",
        mechanics=[
            RollCheck(
                ability="strength",
                dc=10,
                on_success=[Damage(amount=1, target_id=EntityId("missing_success"))],
                on_failure=[Damage(amount=1, target_id=EntityId("missing_failure"))],
            )
        ],
    )
    invalid = Dnd5eDirection(
        intent="Kael attacks himself.",
        tone="uncertain",
        mechanics=[RollCheck(ability="strength", dc=10, on_failure=[Attack(weapon="Longsword")])],
    )
    absent = Dnd5eDirection(
        intent="Kael harms someone in another room.",
        tone="tense",
        mechanics=[Damage(amount=1, target_id=EntityId("tomas"))],
    )

    with pytest.raises(ModelRetry, match="Use only ids you were shown") as retry:
        _propose(engine, state, unknown)
    assert "missing_success" in str(retry.value)
    assert "missing_failure" in str(retry.value)
    with pytest.raises(ModelRetry, match="attack must name at most one"):
        _propose(engine, state, invalid)
    with pytest.raises(ModelRetry, match="Move them here first"):
        _propose(engine, state, absent)


def test_dry_run_checks_both_roll_branches() -> None:
    engine, state = initial_5e_game()
    (lantern,) = carried_by(state, player_of(state).id)
    direction = Dnd5eDirection(
        intent="Kael may discard the same lantern twice.",
        tone="uncertain",
        mechanics=[
            RollCheck(
                ability="strength",
                dc=10,
                on_success=[
                    DropItem(item_id=EntityId(str(lantern.id))),
                    DropItem(item_id=EntityId(str(lantern.id))),
                ],
            )
        ],
    )

    with pytest.raises(ModelRetry, match="not carrying"):
        _propose(engine, state, direction)
