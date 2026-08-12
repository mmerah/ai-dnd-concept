from pathlib import Path

import pytest
from core_test_support import STORY, scenario

from aidm.app.session import begin_game
from aidm.content.store import load_character, write_character
from aidm.engines.story.mechanics import read
from aidm.engines.story.rules import StoryEngine
from aidm.state.base import PLAYER_ID
from aidm.state.creation import CreationStep, Picks


def _creation(engine: StoryEngine):
    creation = engine.creation
    assert creation is not None
    return creation


def test_a_created_character_plays_through_the_authored_load_path(tmp_path: Path) -> None:
    engine = StoryEngine()
    creation = _creation(engine)
    picks: Picks = {"archetype": ("sly",), "edge": ("sharp-eyed",), "burden": ("haunted",)}
    created = creation.create("Fen", "A wandering scribe with too many questions.", picks)
    write_character(tmp_path, "fen", STORY, created)
    character = load_character(tmp_path, "fen", STORY)
    state = begin_game(engine, scenario(), character)
    player = state.player
    assert {trait.id for trait in player.traits} == {"sharp-eyed", "haunted"}
    adventurer = read(state).actors[PLAYER_ID]
    assert (adventurer.subtle, adventurer.clever, adventurer.empathetic, adventurer.bold) == (
        2,
        1,
        1,
        0,
    )


def test_an_illegal_pick_set_is_refused_with_the_reason(tmp_path: Path) -> None:
    creation = _creation(StoryEngine())
    steps = creation.steps({})
    legal: Picks = {
        step.id: (step.options[0].id,) for step in steps if isinstance(step, CreationStep)
    }
    with pytest.raises(ValueError, match="no creation step"):
        creation.create("Fen", "", {**legal, "class": ("fighter",)})
    with pytest.raises(ValueError, match="exactly 1"):
        creation.create("Fen", "", {**legal, "edge": ()})
    with pytest.raises(ValueError, match="offers no"):
        creation.create("Fen", "", {**legal, "burden": ("unwritten",)})
    created = creation.create("Fen", "", legal)
    write_character(tmp_path, "fen", STORY, created)
    with pytest.raises(ValueError, match="already exists"):
        write_character(tmp_path, "fen", STORY, created)
