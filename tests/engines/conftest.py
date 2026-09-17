from pathlib import Path

import pytest
from support.fifth import FifthEngine, FifthGame
from support.fifth import installed as fifth_installed
from support.fifth import scenario as fifth_scenario
from support.sixth import SixthEngine, SixthGame
from support.sixth import installed as sixth_installed
from support.sixth import scenario as sixth_scenario


@pytest.fixture
def room_engine(tmp_path: Path) -> SixthEngine:
    return sixth_installed(tmp_path)


@pytest.fixture
def begun_room(room_engine: SixthEngine) -> SixthGame:
    character = room_engine.create_character("Wren", "A quiet scout", ("srd",), {})
    return room_engine.begin("the-keep", sixth_scenario(), character)


@pytest.fixture
def scene_engine(tmp_path: Path) -> FifthEngine:
    return fifth_installed(tmp_path)


@pytest.fixture
def begun_scene(scene_engine: FifthEngine) -> FifthGame:
    character = scene_engine.create_character("Wren", "A quiet scout", ("srd",), {})
    return scene_engine.begin("the-taproom", fifth_scenario(), character)
