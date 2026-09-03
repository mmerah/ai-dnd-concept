import json
from pathlib import Path

from core_test_support import changed, loner_sheet, open_game, play_turn, the_way_on

from aidm.core.entities import EntityId
from aidm.engines.base import PLAYER_ID


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
        "recap": "The player left the abbot's study behind, lantern shuttered, and made for the "
        "cloister walk with Mara close behind them.",
    }
    scene.update(changes)
    return json.dumps(scene)


async def test_crossing_keeps_a_drive_set_after_the_worldsmith_snapshot(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table,
        "Out into the cloister walk.",
        changed("drive", entity_id=PLAYER_ID, goal="Get the vault map out safely"),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    assert state.payload.player.goal == "Get the vault map out safely"


async def test_a_re_filed_cast_member_takes_the_new_brief_and_keeps_their_name_and_sheet(
    tmp_path: Path,
) -> None:
    """The brief is the worldsmith's between scenes; the name and the sheet are the rules'."""
    table = open_game(tmp_path)
    before = loner_sheet(table.state, EntityId("mara"))
    table.spawner.answers["worldsmith"] = [
        _scene(
            cast={
                "mara": {
                    "id": "mara",
                    "name": "Another Mara",
                    "brief": "Waiting under the arcade with the lantern shuttered.",
                }
            },
        )
    ]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table, "Out into the cloister walk.", arrival="Rain takes the arcade.", moving_on=True
    )

    mara = state.payload.require(EntityId("mara"))
    assert state.payload.run.title == "The Cloister Walk"
    assert mara.name == "Mara"
    assert mara.brief == "Waiting under the arcade with the lantern shuttered."
    assert (mara.concept, mara.skills) == (before.concept, before.skills)
    assert all(
        fact.kind != "way_unwritten" for fact in table.service.engine.history(state)[-1].facts
    )
