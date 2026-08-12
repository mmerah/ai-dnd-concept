import ast
import json
from pathlib import Path
from random import Random

import probe_engine
import pytest
from probe_engine import Mechanics, Strike
from pydantic import JsonValue, ValidationError

from aidm.state.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId
from aidm.state.world import GameState, ScenarioMeta, WorldState

SOURCE = Path(__file__).parent / "probe_engine.py"
AUTHORED = """
{
  "fighters": {
    "player": {
      "edge": 2,
      "heart": 1,
      "iron": 3,
      "debilities": ["wounded"],
      "momentum": 2,
      "tracks": {"vault-seal": {"name": "the vault seal", "rank": "dangerous"}}
    }
  }
}
"""
STRIKE = Strike(actor_id=EntityId("player"), stat="iron", track_id="vault-seal")
# What core must not own: an engine reaching for one of these has taken world state as mechanics.
FORBIDDEN = (
    "aidm.state.effects",
    "aidm.state.apply",
    "aidm.state.plan",
    "aidm.state.world",
    "aidm.engines",
    "aidm.content",
    "aidm.turn",
    "aidm.app",
    "aidm.ui",
)


def _loaded() -> Mechanics:
    return probe_engine.create(json.loads(AUTHORED))


def test_authored_json_becomes_mechanics_and_survives_a_round_trip() -> None:
    mechanics = _loaded()

    assert mechanics.fighters[EntityId("player")].ceiling == 9
    assert probe_engine.create(mechanics.model_dump(mode="json")) == mechanics


@pytest.mark.parametrize(
    "corruption",
    [
        {"momentum": 10},
        {"tracks": {"vault-seal": {"name": "seal", "rank": "dangerous", "ticks": 41}}},
        {"tracks": {"vault-seal": {"name": "seal", "rank": "dangerous", "resolved": True}}},
    ],
)
def test_mechanics_only_the_engine_can_judge_are_refused(corruption: dict[str, JsonValue]) -> None:
    fighter: dict[str, JsonValue] = {"edge": 2, "heart": 1, "iron": 3, "debilities": ["wounded"]}
    payload: JsonValue = {"fighters": {"player": fighter | corruption}}
    with pytest.raises(ValidationError):
        _ = probe_engine.create(payload)


def test_the_strike_is_deterministic_and_reaches_every_outcome() -> None:
    seen: set[str] = set()
    for seed in range(20):
        facts = probe_engine.resolve(_loaded(), STRIKE, Random(seed))
        assert facts == probe_engine.resolve(_loaded(), STRIKE, Random(seed))
        resolved = next(fact for fact in facts if fact.kind == "strike_resolved")
        seen.add(str(resolved.data["outcome"]))
    assert seen == {"strong", "weak", "miss"}


def test_an_entity_created_during_play_gains_mechanics_before_the_commit() -> None:
    mechanics = _loaded()
    actor = Entity(id=EntityId("mara"), kind="actor", name="Mara", brief="A wary novice.")
    item = Entity(id=EntityId("lantern"), kind="item", name="Lantern", brief="Guttering.")

    for entity in (actor, item):
        probe_engine.initialize(mechanics, entity)
    committed = probe_engine.commit(mechanics)

    assert EntityId("mara") in committed.fighters
    assert EntityId("lantern") not in committed.fighters
    assert probe_engine.render(committed, actor).startswith("Mara: edge 1")
    assert probe_engine.render(committed, item) == item.brief


def _probe_state() -> GameState:
    """A probe never ships a `spec.json` or joins `ENGINE_MODULES`; this state exists only so the
    test can drive `state.mechanics` the way a real engine's caller would."""
    cell = Entity(id=EntityId("cell"), kind="location", name="Cell", brief="A cell.", known=True)
    player = Entity(
        id=PLAYER_ID, kind="actor", name="Prisoner", brief="", known=True, parent_id=cell.id
    )
    return GameState(
        save_version=SAVE_VERSION,
        scenario_id="probe",
        character_id="probe",
        scenario=ScenarioMeta(title="Probe", premise="A test engine, not a shipped one."),
        engine=EngineId("probe"),
        world=WorldState(entities={cell.id: cell, player.id: player}),
        mechanics=_loaded().model_dump(mode="json"),
    )


def test_the_probes_mechanics_round_trip_through_gamestate_mechanics() -> None:
    """Core treats `state.mechanics` as opaque JSON: the probe is the only reader and the only
    validator of what it holds, all the way through a real draft/resolve/commit transaction."""
    state = _probe_state()

    draft = state.draft()
    mechanics = probe_engine.create(draft.mechanics)
    facts = probe_engine.resolve(mechanics, STRIKE, Random(0))
    draft.mechanics = probe_engine.commit(mechanics).model_dump(mode="json")
    committed = draft.committed()

    assert facts
    assert committed.mechanics == mechanics.model_dump(mode="json")
    assert probe_engine.create(committed.mechanics) == mechanics

    fighter: JsonValue = {"edge": 2, "heart": 1, "iron": 3, "momentum": 99}
    corrupted: JsonValue = {"fighters": {"player": fighter}}
    with pytest.raises(ValidationError):
        _ = probe_engine.create(corrupted)


def test_the_engine_reaches_for_nothing_core_must_own() -> None:
    """The counterexample: a third engine is written against ids, dice, and facts, nothing more."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

    assert not sorted(name for name in imported if name.startswith(FORBIDDEN))
    assert not sorted(
        name
        for name in dir(probe_engine)
        if not name.startswith("_")
        if any(word in name.lower() for word in ("advance", "offer", "delta", "content", "pack"))
    )
