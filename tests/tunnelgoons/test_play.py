import json
from pathlib import Path
from random import Random

from support.table import TUNNELGOONS, open_game_for, play_turn, take, tool_call

from aidm.engines.rooms.engine import EXTEND, MORE_MAP

# A miss against the crawler's DS 6 (brute 1 + 2d6[1,1] = 3): the margin lands on the player.
FIGHT_SEED = 2
MARGIN = 3

REGION = {
    "places": {
        "deep-vault": {
            "id": "deep-vault",
            "name": "Deep Vault",
            "brief": "Past the flooded cellar",
            "known": False,
            "description": "A dry vault the flood never reached.",
        },
        "black-stair": {
            "id": "black-stair",
            "name": "Black Stair",
            "brief": "Down further still",
            "known": False,
            "description": "A stair cut into raw rock, going down.",
        },
    },
    "ways": {"deep-vault": [{"to": "black-stair", "known": False}]},
    "npcs": {},
    "items": {
        "old-coin": {
            "id": "old-coin",
            "name": "Old Coin",
            "brief": "Green with age",
            "known": False,
            "on": "deep-vault",
        }
    },
    "start": "deep-vault",
}


async def test_the_shipped_map_plays_start_to_finish(tmp_path: Path) -> None:
    table = open_game_for(tmp_path, TUNNELGOONS, rng=Random(FIGHT_SEED))

    state = await play_turn(
        table,
        "Down the corridor, into the storeroom, then back to face the thing in the roots.",
        tool_call("move", to_id="corridor"),
        tool_call("move", to_id="storeroom"),
        tool_call("move", to_id="corridor"),
        tool_call(
            "action_roll",
            what="Fight the crawler",
            ability="brute",
            against="crawler",
            dangerous=True,
        ),
    )
    world = state.payload
    assert world.current.id == "corridor"
    assert world.npcs["crawler"].alive
    assert world.player.hp.current == world.player.hp.maximum - MARGIN

    state = await play_turn(
        table,
        "Back to the storeroom, force the sealed cell, and rest once it is safe.",
        tool_call("move", to_id="storeroom"),
        tool_call("unlock_way", to_id="sealed-cell"),
        tool_call("move", to_id="sealed-cell"),
        tool_call("rest"),
    )
    world = state.payload
    assert world.current.id == "sealed-cell"
    assert world.player.hp.current == world.player.hp.maximum

    state = await play_turn(
        table,
        "Back out and down into the flooded cellar.",
        tool_call("move", to_id="storeroom"),
        tool_call("move", to_id="corridor"),
        tool_call("move", to_id="cellar"),
    )
    assert table.service.player_view().action == MORE_MAP

    engine = table.service.engine
    before_turn, before_place = len(engine.history(state)), state.payload.current.id
    table.spawner.answers["worldsmith"] = [json.dumps(REGION)]
    after = await take(table, EXTEND, "Deeper in.")

    # The region lands hidden: nobody moved, nothing is told, no master or narrator ran.
    assert len(engine.history(after)) == before_turn
    assert after.payload.current.id == before_place
    assert set(REGION["places"]) <= set(after.payload.places)
    assert all(not after.payload.places[place].known for place in REGION["places"])
    assert table.spawner.prompts[-1][0] == "worldsmith"
    assert table.service.player_view().action is None
