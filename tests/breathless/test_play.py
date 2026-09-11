import json
from pathlib import Path
from random import Random

from support.table import BREATHLESS, open_table, play_turn, the_way_on, tool_call

from aidm.core.play import Answer
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.scenes.engine import MOVE_ON

# Any face wears the skill die; the d12 loot roll after it draws a 7, so it finds a d8 item.
LOOT_SEED = 0

NEXT_SCENE = {
    "place": "causeway",
    "title": "The Causeway",
    "situation": "Water climbs past your knees; the chapel lamp waits a mile off across the flats.",
    "recap": "Kael forced the Bell House door and scavenged a first aid kit before the tide rose.",
}


async def test_the_shipped_scenario_plays_several_turns(tmp_path: Path) -> None:
    table = open_table(
        tmp_path, engine_id=BREATHLESS, state_type=BreathlessGame, rng=Random(LOOT_SEED)
    )
    table.service.interjections = False

    state = await play_turn(
        table,
        "Force the jammed door, then scavenge the shelves before the water rises further.",
        tool_call("roll", what="Force the door", skill="bash", dangerous=True),
        tool_call("loot_check", item="First aid kit"),
    )
    world = state.payload
    assert world.player.require_sheet().worn["bash"] == 4
    assert state.pending is not None
    assert [option.id for option in state.pending.options] == ["take"]

    state = await play_turn(table, Answer(option_id="take"))
    assert state.pending is None
    assert state.payload.player.require_sheet().items["first-aid-kit"].die == 8

    state = await play_turn(table, "Ask what lies past the Bell House.", the_way_on())
    assert state.payload.run.offered

    before = len(state.exchanges())
    table.spawner.answers["worldsmith"] = [json.dumps(NEXT_SCENE)]
    pursuit = "Out onto the causeway before the third bell."
    state = await play_turn(
        table,
        pursuit,
        tool_call("next_scene", pursuit=pursuit),
        action=MOVE_ON.id,
        arrival="The Bell House falls behind, and cold water closes around your boots.",
    )

    assert state.payload.run.title == "The Causeway"
    assert state.exchanges()[before].words == pursuit
    assert table.saved() == table.state
