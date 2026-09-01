from pathlib import Path

from core_test_support import Call, opened_for, played
from pydantic import JsonValue

from aidm.core.entities import EngineId, EntityId
from aidm.engines.mazerats.state import ItemSheet, MazeRatsSheet
from aidm.kits.entities import Entity
from aidm.kits.rooms.boundary import frontier
from aidm.kits.rooms.state import Way
from aidm.kits.rooms.worldsmith import MapDraft

MAZE_RATS = EngineId("mazerats")


def _tool(name: str, **args: JsonValue) -> Call:
    return name, args


async def test_shipped_map_walks_a_loop_unlocks_a_way_and_records_journal(tmp_path: Path) -> None:
    table = opened_for(tmp_path, MAZE_RATS)

    for destination in ("echo-hall", "star-shrine", "glass-vault", "star-shrine", "moon-gate"):
        await played(table, f"I travel toward {destination}.", _tool("move", to_id=destination))

    state = table.state
    assert state.payload.world.current.id == EntityId("moon-gate")
    assert [visit.place for visit in state.payload.world.visits] == [
        "moon-gate",
        "echo-hall",
        "star-shrine",
        "glass-vault",
        "star-shrine",
        "moon-gate",
    ]
    assert state.turn == 5
    assert len(state.payload.world.exchanges()) == 5
    assert [exchange.prompt for exchange in state.payload.world.exchanges()] == [
        "I travel toward echo-hall.",
        "I travel toward star-shrine.",
        "I travel toward glass-vault.",
        "I travel toward star-shrine.",
        "I travel toward moon-gate.",
    ]

    await played(
        table,
        "I open the sealed way.",
        _tool("unlock_way", to_id="glass-vault"),
    )
    state = table.state
    assert state.payload.world.way("moon-gate", "glass-vault").locked is False

    await played(table, "I take the unlocked way.", _tool("move", to_id="glass-vault"))
    state = table.state
    assert state.payload.world.current.id == EntityId("glass-vault")
    assert state.turn == 7
    assert len(state.payload.world.exchanges()) == 7
    assert all(exchange.lines for exchange in state.payload.world.exchanges())


def _extension() -> MapDraft[MazeRatsSheet]:
    return MapDraft[MazeRatsSheet](
        cast={
            EntityId("ash-garden"): Entity[MazeRatsSheet](
                id=EntityId("ash-garden"),
                kind="place",
                name="The Ash Garden",
                brief="A garden of warm grey ash.",
            ),
            EntityId("bell-tower"): Entity[MazeRatsSheet](
                id=EntityId("bell-tower"),
                kind="place",
                name="The Bell Tower",
                brief="A leaning tower without a bell.",
            ),
            EntityId("ash-seed"): Entity[MazeRatsSheet](
                id=EntityId("ash-seed"),
                kind="item",
                name="an ash seed",
                brief="A seed that is warm to the touch.",
                carried_by=EntityId("ash-garden"),
                sheet=ItemSheet(),
            ),
        },
        ways={
            EntityId("ash-garden"): (Way(to=EntityId("bell-tower")),),
            EntityId("bell-tower"): (Way(to=EntityId("ash-garden")),),
        },
        start=EntityId("ash-garden"),
    )


async def test_exhausted_frontier_offers_extension_without_a_turn_or_arrival(
    tmp_path: Path,
) -> None:
    table = opened_for(tmp_path, MAZE_RATS)
    for destination in ("echo-hall", "star-shrine", "glass-vault"):
        await played(table, f"I travel toward {destination}.", _tool("move", to_id=destination))
    await played(table, "I return to the shrine.", _tool("move", to_id="star-shrine"))
    await played(table, "I return to the gate.", _tool("move", to_id="moon-gate"))
    await played(
        table,
        "I open the sealed way.",
        _tool("unlock_way", to_id="glass-vault"),
    )
    await played(table, "I take the unlocked way.", _tool("move", to_id="glass-vault"))

    before = table.state
    before_position = before.payload.world.current.id
    before_turn = before.turn
    before_history = before.payload.world.exchanges()
    before_prompts = len(table.spawner.prompts)
    assert frontier(before.payload.world) == 0
    assert table.service.transition_available()
    region = _extension()
    table.spawner.answers["worldsmith"] = [region.model_dump_json()]

    await table.service.play("I seek the rooms beyond the vault.", moving_on=True)

    state = table.state
    assert state.payload.world.current.id == before_position
    assert state.turn == before_turn
    assert state.payload.world.exchanges() == before_history
    assert frontier(state.payload.world) == 1
    assert state.payload.world.way("glass-vault", "ash-garden") == Way(to=EntityId("ash-garden"))
    assert state.payload.world.require(EntityId("ash-garden")).known is False
    assert [role for role, _ in table.spawner.prompts[before_prompts:]] == ["worldsmith"]
    assert all(
        "arrival" not in line.text.lower() for exchange in before_history for line in exchange.lines
    )
