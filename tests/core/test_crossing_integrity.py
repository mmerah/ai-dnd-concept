import json
from pathlib import Path

from core_test_support import changed, opened, played, the_way_on

from aidm.core.entities import EntityId
from aidm.engines.core import PLAYER_ID


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


async def test_crossing_keeps_a_drive_set_after_the_worldsmith_snapshot(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "Out into the cloister walk.",
        changed("drive", entity_id=PLAYER_ID, goal="Get the vault map out safely"),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    assert state.payload.world.player.goal == "Get the vault map out safely"


async def test_invalid_actor_from_crossing_is_rejected_before_commit(tmp_path: Path) -> None:
    """A cast id already in the world only clashes once merged: soft checks let it through."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [
        _scene(
            cast={
                "mara": {
                    "id": "mara",
                    "name": "Another Mara",
                    "brief": "Filed under an id the world already holds.",
                }
            },
        )
    ]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(table, "Out into the cloister walk.", moving_on=True)

    assert state.payload.world.current.title == "The Abbot's Study"
    assert state.payload.world.require(EntityId("mara")).name == "Mara"
    assert "already in the cast" in table.service.write_failure
