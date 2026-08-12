from core_test_support import initialized, plan, played, scripted, structured
from pydantic_ai.models.function import FunctionModel

from aidm.state.base import EntityDetail, Kind
from aidm.state.turn import Creation
from aidm.turn.pipeline import admitted

AUTHORED = (
    "The abbey emptied in a single night: meals were left half-eaten, doors left open, and no "
    "brother has been seen on the road since."
)
CONFIDED = "Mara admitted she has not opened the vault ledgers since Elena went below."
CHARTED = "The loose flagstone in the study hid a chart of the undercroft."


def _creation(kind: Kind, name: str) -> Creation:
    return Creation(
        kind=kind, name=name, brief="New canon.", detail=EntityDetail(description="", hook="")
    )


def _memory(text: str, owner: str | None = None) -> dict[str, object]:
    return {"owner_id": owner, "text": text}


def test_screening_drops_known_names_repeats_and_excess_then_sorts_locations_first() -> None:
    _, state = initialized()

    kept = admitted(
        (
            _creation("actor", "mara"),  # already in the world, casefolded
            _creation("actor", "Iven"),
            _creation("actor", "iven"),  # repeat within this report, casefolded
            _creation("actor", "Nia"),
            _creation("location", "Sol's Hollow"),
            _creation("actor", "Extra"),  # over the cap, dropped
        ),
        state,
        maximum=3,
    )

    assert [(creation.kind, creation.name) for creation in kept] == [
        ("location", "Sol's Hollow"),
        ("actor", "Iven"),
        ("actor", "Nia"),
    ]


async def test_the_report_keeps_new_memories_drops_a_repeat_moves_a_thread_and_retries() -> None:
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
                thread_moves=[
                    {"op": "advance-thread", "thread_id": "vault-seal", "stage": "seal-found"}
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
    assert result.state.world.threads["vault-seal"].stage == "seal-found"
