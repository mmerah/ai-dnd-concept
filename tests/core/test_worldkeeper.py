from core_test_support import initialized, plan, played, scripted, structured
from pydantic_ai.models.function import FunctionModel

AUTHORED = (
    "The abbey emptied in a single night: meals were left half-eaten, doors left open, and no "
    "brother has been seen on the road since."
)
CONFIDED = "Mara admitted she has not opened the vault ledgers since Elena went below."
CHARTED = "The loose flagstone in the study hid a chart of the undercroft."


def _memory(text: str, owner: str | None = None) -> dict[str, object]:
    return {"owner_id": owner, "text": text}


async def test_the_report_keeps_new_memories_drops_a_repeat_and_retries() -> None:
    engine, state = initialized()
    keeper = FunctionModel(
        scripted(
            # An owner naming nobody must come back as a retry, or the second answer never runs.
            structured(memories=[_memory(CONFIDED, "brother-aldric")]),
            structured(
                memories=[
                    _memory(AUTHORED),  # the world already holds this one
                    _memory(CONFIDED, "mara"),
                    _memory(CHARTED),
                    _memory("Over the cap of two, and dropped."),
                ],
            ),
        )
    )
    result = await played(
        engine,
        state,
        "I ask Mara about Elena.",
        director=FunctionModel(scripted(plan())),
        worldkeeper=keeper,
    )

    memories = result.state.world.memories
    assert [memory.text for memory in memories.values()][-2:] == [CONFIDED, CHARTED]
    assert len(memories) == 4  # the two authored, plus the two admitted under the cap of two
    assert [memory.owner for memory in memories.values()][-2:] == ["mara", None]
    kept = [fact for fact in result.turn.facts if fact.kind == "memory_kept"]
    assert len(kept) == 2
    # A memory is bookkeeping, like a thread: neither reaches the player's narration.
    assert all(fact.narrator is None for fact in kept)
