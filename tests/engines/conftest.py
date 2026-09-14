from pathlib import Path

import pytest
import support.fifth
import support.sixth


@pytest.fixture
def room_engine(tmp_path: Path) -> support.sixth.SixthEngine:
    return support.sixth.installed(tmp_path)


@pytest.fixture
def begun_room(room_engine: support.sixth.SixthEngine) -> support.sixth.SixthGame:
    character = room_engine.create_character("Wren", "A quiet scout", {})
    return room_engine.begin("the-keep", support.sixth.scenario(), character)


@pytest.fixture
def scene_engine(tmp_path: Path) -> support.fifth.FifthEngine:
    return support.fifth.installed(tmp_path)


@pytest.fixture
def begun_scene(scene_engine: support.fifth.FifthEngine) -> support.fifth.FifthGame:
    character = scene_engine.create_character("Wren", "A quiet scout", {})
    return scene_engine.begin("the-taproom", support.fifth.scenario(), character)
