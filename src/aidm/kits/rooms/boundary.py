from collections.abc import Sequence

from pydantic import BaseModel

from aidm.core.facts import Fact, cards
from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.kits.rooms.state import RoomWorld


def frontier[S: BaseModel](world: RoomWorld[S]) -> int:
    """Count distinct unknown places reachable through ways out of known places."""
    return len(
        {
            way.to
            for from_id, ways in world.ways.items()
            if world.require(from_id).known
            for way in ways
            if not world.require(way.to).known
        }
    )


def history[S: BaseModel](world: RoomWorld[S]) -> tuple[Exchange, ...]:
    return world.exchanges()


def record[S: BaseModel](
    state: AnyGame,
    world: RoomWorld[S],
    prompt: str,
    lines: tuple[SpokenLine, ...],
    facts: Sequence[Fact],
) -> tuple[str, ...]:
    """Append the exchange to the current place; rooms have no scene-spent clock."""
    world.visit.exchanges.append(
        Exchange(
            prompt=prompt,
            lines=lines,
            facts=cards(facts),
            decision="" if state.pending is None else state.pending.prompt,
            scene=world.current.name,
        )
    )
    return ()
