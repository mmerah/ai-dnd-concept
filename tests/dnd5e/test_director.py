import pytest
from fivee_test_support import initial_5e_game
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.agents.context import DirectorScene, build_director_scene
from aidm.domain.engine import EngineData
from aidm.domain.json import thaw_json
from aidm.domain.state import GameState
from aidm.utils.models import updated
from aidm_5e.domain.models.base import EntityId
from aidm_5e.domain.models.consequences import Damage, DropItem, RollCheck
from aidm_5e.domain.models.direction import Dnd5eDirection


def _context(state: GameState) -> RunContext[DirectorScene]:
    return RunContext(
        deps=build_director_scene(state),
        model=TestModel(),
        usage=RunUsage(),
    )


def test_unknown_and_absent_references_return_actionable_retries() -> None:
    engine, state = initial_5e_game()
    unknown = Dnd5eDirection(
        intent="Something impossible happens.",
        tone="uncertain",
        mechanics=[Damage(amount=1, target_id=EntityId("missing"))],
    )
    absent = Dnd5eDirection(
        intent="Kael harms someone in another room.",
        tone="tense",
        mechanics=[Damage(amount=1, target_id=EntityId("tomas"))],
    )

    with pytest.raises(ModelRetry, match="Use only ids you were shown"):
        engine.director.validate(_context(state), unknown)
    with pytest.raises(ModelRetry, match="Move them here first"):
        engine.director.validate(_context(state), absent)


def test_dry_run_checks_both_roll_branches() -> None:
    engine, state = initial_5e_game()
    (lantern,) = state.world.carried_by(state.player.id)
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
        engine.director.validate(_context(state), direction)


def test_corrupt_rules_data_fails_fast_instead_of_becoming_a_retry() -> None:
    engine, state = initial_5e_game()
    scene = build_director_scene(state)
    player = updated(
        scene.player,
        rules=EngineData(engine="dnd5e", schema_version=1, payload={}),
    )
    world = scene.canon.replacing(player)
    corrupt = updated(scene, player=player, canon=world)
    context = RunContext(deps=corrupt, model=TestModel(), usage=RunUsage())
    direction = Dnd5eDirection(intent="Kael waits.", tone="quiet")

    with pytest.raises(ValidationError):
        engine.director.validate(context, direction)


def test_direction_records_preserve_the_5e_envelope_and_mechanics() -> None:
    engine, _ = initial_5e_game()
    direction = Dnd5eDirection(
        intent="Kael endures a falling stone.",
        tone="dangerous",
        mechanics=[Damage(amount="1d4")],
    )

    record = engine.director.record(direction)

    assert (record.engine, record.schema_version) == ("dnd5e", 1)
    assert thaw_json(record.mechanics) == [{"action": "damage", "amount": "1d4", "target_id": None}]
