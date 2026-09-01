import json
from pathlib import Path

from core_test_support import changed, opened, played, the_way_on

from aidm.core.entities import EntityId


def _scene(**changes: object) -> str:
    scene: dict[str, object] = {
        "place": "cloister-walk",
        "title": "The Cloister Walk",
        "situation": (
            "Rain drums the open arcade and the flagstones run black with it, and Mara waits "
            "at the far end with the lantern shuttered to a slit."
        ),
        "present": ["mara"],
        "hidden": [],
        "question": "Can you reach the chapter house before the lantern gives you away?",
        "secret": "",
    }
    scene.update(changes)
    return json.dumps(scene)


async def test_crossing_keeps_a_thread_advanced_after_the_worldsmith_snapshot(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [
        _scene(
            threads={
                "vault-seal": {
                    "id": "vault-seal",
                    "title": "The sealed vault",
                    "status": "active",
                    "note": "stale snapshot note",
                }
            }
        )
    ]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "Out into the cloister walk.",
        changed(
            "advance_thread",
            thread_id="vault-seal",
            status="dormant",
            note="The player now knows the seal is weakening.",
        ),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    thread = state.payload.world.threads["vault-seal"]
    assert thread.status == "dormant"
    assert thread.note == "The player now knows the seal is weakening."


async def test_invalid_actor_from_crossing_is_rejected_before_commit(tmp_path: Path) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [
        _scene(
            cast={
                "broken-actor": {
                    "id": "broken-actor",
                    "kind": "actor",
                    "name": "Broken Actor",
                    "brief": "A person with no rules sheet.",
                    "sheet": None,
                }
            },
            present=["mara", "broken-actor"],
        )
    ]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(table, "Out into the cloister walk.", moving_on=True)

    assert state.payload.world.current.title == "The Abbot's Study"
    assert EntityId("broken-actor") not in state.payload.world.cast
    assert "has no sheet" in table.service.write_failure
