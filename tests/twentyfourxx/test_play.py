import json
from pathlib import Path
from random import Random

from support.table import TWENTYFOURXX, open_game_for, play_turn, the_way_on, tool_call

from aidm.core.play import Answer
from aidm.engines.scenes.engine import MOVE_ON

# A setback (not a disaster or a success): the roll maims the player without killing them.
SETBACK_SEED = 1
# A disaster: the lead dies and, with a hired member alive, succession opens instead of ending.
DISASTER_SEED = 2

NEXT_SCENE = {
    "place": "cargo-bay",
    "title": "The Cargo Bay",
    "situation": "Stacked containers throw long shadows, and the station's power hums back on "
    "somewhere overhead.",
    "recap": "Kael slipped past Vessa's watch at the airlock, favouring a bruised leg.",
}


async def test_the_shipped_scenario_plays_several_turns(tmp_path: Path) -> None:
    table = open_game_for(tmp_path, TWENTYFOURXX, rng=Random(SETBACK_SEED))
    table.service.interjections = False

    state = await play_turn(
        table,
        "Slip past the dockhand before she clocks the override key.",
        tool_call("roll", what="Slip past the dockhand", skill="Stealth", risking_death=True),
    )
    world = state.payload
    assert world.player.alive
    assert world.player.dice().hindrances == ["Maimed"]

    state = await play_turn(table, "Ask what else this shift wants of Kael.", the_way_on())
    assert state.payload.run.offered

    before = len(table.service.engine.history(state))
    table.spawner.answers["worldsmith"] = [json.dumps(NEXT_SCENE)]
    pursuit = "Deeper into the station, past the dark corridor."
    state = await play_turn(
        table,
        pursuit,
        tool_call("next_scene", pursuit=pursuit),
        action=MOVE_ON.id,
        arrival="The docking ring falls away, and stacked containers rise up around you.",
    )

    assert state.payload.run.title == "The Cargo Bay"
    assert table.service.engine.history(state)[before].prompt == pursuit
    assert table.saved() == table.state


async def test_a_hired_member_survives_a_save_and_succeeds_the_dead_lead(tmp_path: Path) -> None:
    table = open_game_for(tmp_path, TWENTYFOURXX)
    table.service.interjections = False
    member_id = "vessa-rune"
    sheet = {
        "specialty": "Face",
        "skills": {"Deception": 8},
        "items": ["Override key"],
    }

    table.spawner.answers["worldsmith"] = [json.dumps(sheet)]
    state = await play_turn(
        table,
        "Hire Vessa to keep the corridor guards talking.",
        tool_call("hire", entity_id=member_id, terms="Keep the corridor guards talking"),
        narration="Vessa pockets the terms and falls in step behind Kael.",
    )
    world = state.payload
    member = world.cast[member_id]
    assert member.id in world.party
    assert member.sheet is not None
    assert member.sheet.specialty == "Face"

    reloaded = table.saved()
    hired = reloaded.payload.cast[member_id]
    assert member_id in reloaded.payload.party
    assert hired.sheet == member.sheet

    table.service.rng = Random(DISASTER_SEED)
    state = await play_turn(
        table,
        "Slip past the dockhand before she clocks the override key.",
        tool_call("roll", what="Slip past", skill="Stealth", risking_death=True),
    )
    assert not state.payload.player.alive
    assert state.pending is not None
    assert state.pending.kind == "succession"
    assert [option.id for option in state.pending.options] == [member_id]
    assert table.service.engine.over(state) is None

    state = await play_turn(table, Answer(option_id=member_id))

    world = state.payload
    assert world.player.id == member_id
    assert world.player.sheet is not None
    assert world.player.sheet.specialty == "Face"
    assert world.player.sheet.skills == {"Deception": 8}
    assert "player" in world.cast
    assert not world.cast["player"].alive
    assert "player" in world.run.here
    assert member_id not in world.party
    assert table.saved() == table.state
