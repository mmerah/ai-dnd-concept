from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from core_test_support import (
    LONER3E,
    SCENARIOS,
    loner_at_boundary,
    narrated,
    scripted,
    text,
    updated,
    with_entity,
)
from loner3e_test_support import loner3e_session
from pydantic import JsonValue
from pydantic_ai.models.function import FunctionModel

from aidm.app.runtime import GameSession
from aidm.authoring.draft import (
    Draft,
    PlaytestCheck,
    ScenarioPatch,
    scenario_refusal,
)
from aidm.authoring.run import GrowthRun, briefing, growth_run
from aidm.content.io import FileStore
from aidm.state.entities import PLAYER_ID, Entity, EntityId, Exit
from aidm.state.model import Game, Thread
from aidm.turn.run import TurnStep
from aidm.world.authoring import Connect, connect
from aidm.world.topology import player_location

_CRYPT_ID = EntityId("sub-crypt")
_WARDEN_ID = EntityId("bone-warden")
_COUNT_ID = "warden-count"


def _warden() -> Entity:
    return Entity(
        id=_WARDEN_ID,
        kind="actor",
        name="the bone warden",
        brief="He counts the niches every night and never leaves.",
        parent_id=_CRYPT_ID,
    )


def _crypt() -> Entity:
    return Entity(
        id=_CRYPT_ID,
        kind="location",
        name="the sub-crypt",
        brief="A shelf of ossuary niches below the cloister floor.",
        exits=[Exit(to=EntityId("cloister"))],
    )


def _grown(directory: Path, *, thin: bool = True) -> GameSession:
    """A scenario that grows, staged with one door left to find and a change on offer."""
    game = loner3e_session(directory)
    game.scenario = updated(game.scenario, grows=True)
    game.state = loner_at_boundary(game.state)
    if thin:
        tower = game.state.world.require(EntityId("bell-tower"))
        game.state = with_entity(game.state, updated(tower, known=True))
    return game


def _stub_author(monkeypatch: pytest.MonkeyPatch) -> list[Game]:
    """The authoring run itself is one agent run; what this pins is the session hook around it."""
    seen: list[Game] = []

    async def authored(self: GrowthRun, instruction: str) -> str:
        del instruction
        seen.append(self.base)
        cloister = self.draft.world.entities[EntityId("cloister")]
        edited = updated(cloister, exits=[*cloister.exits, Exit(to=_CRYPT_ID)])
        _ = self.draft.apply(
            ScenarioPatch(
                entities=(_crypt(), edited, _warden()),
                threads=(Thread(id=_COUNT_ID, title="The warden's nightly count"),),
                mechanics={"sheets": {_WARDEN_ID: {"concept": "A Bone Warden"}}},
            ),
            self.playing.engine,
        )
        return "grew the sub-crypt and its warden"

    monkeypatch.setattr(GrowthRun, "send", authored)
    return seen


async def _turn(game: GameSession, on_step: Callable[[TurnStep], None] | None = None) -> None:
    assert game.stages is not None
    director = FunctionModel(scripted(text("nothing to do")))
    narrator = FunctionModel(scripted(narrated("You wait.")))
    with (
        game.stages.director.override(model=director),
        game.stages.narrator.override(model=narrator),
    ):
        _ = await game.submit("I wait.", on_step)


def test_the_live_world_becomes_a_scenario_the_extending_author_can_hold(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    draft = Draft.from_game(game.state)
    scenario = draft.scenario(LONER3E, ("srd",))

    ids = set(scenario.world.entities)
    assert PLAYER_ID not in ids
    assert EntityId("lantern") not in ids
    assert scenario.player_parent_id == player_location(game.state)
    assert EntityId("mara") in ids

    unmet = scenario_refusal(
        draft,
        PlaytestCheck(engine=game.engine, character=game.character, packs=("srd",)),
        game.engine.authoring_brief(("srd",), game.state.world, False),
    )
    assert isinstance(unmet, str)
    assert "location" in unmet


async def test_a_thin_world_grows_inside_the_turn_that_ran_it_thin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authored = (SCENARIOS / "whispering-vault" / "world.json").read_bytes()
    game = _grown(tmp_path)
    seen = _stub_author(monkeypatch)
    steps: list[TurnStep] = []

    await _turn(game, steps.append)

    assert len(seen) == 1
    assert "scenario_creator" in steps
    grown = game.state.world.find(_CRYPT_ID)
    assert grown is not None
    assert grown.known is False
    way = game.state.world.require(EntityId("cloister")).exit_to(_CRYPT_ID)
    assert way is not None
    assert way.known is False
    assert game.state.world.thread(_COUNT_ID) is not None

    saved = FileStore(tmp_path).load("poc")
    assert saved is not None
    assert _CRYPT_ID in game.engine.restored(saved).world.entities

    assert (SCENARIOS / "whispering-vault" / "world.json").read_bytes() == authored
    assert "ADVANCES OWED" in dict(game.engine.scene(game.state).director_sections)


async def test_a_world_with_doors_left_to_find_grows_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _stub_author(monkeypatch)

    thick = _grown(tmp_path / "thick", thin=False)
    await _turn(thick)

    plain = loner3e_session(tmp_path / "plain")
    assert plain.scenario.grows is False
    await _turn(plain)

    assert seen == []


def test_a_grown_world_is_briefed_with_its_sheets_and_refused_until_it_hangs_together(
    tmp_path: Path,
) -> None:
    """The loop converges only if the briefing shows the shape the refusal asks for."""
    game = _grown(tmp_path)
    run = growth_run(game.settings, game.engine, game.character, game.state)
    instructions = briefing(run, "finish_growth")
    assert "content packs: srd" in instructions
    assert '"concept": "A Wary Relic-Hunter"' in instructions
    assert '"srd": {' in instructions and '"name": "Starter tables"' in instructions
    assert '"mechanics": {' in instructions

    _ = run.draft.apply(
        ScenarioPatch(
            entities=(updated(_crypt(), exits=[]), _warden()),
            mechanics={"sheets": {_WARDEN_ID: {"concept": "A Bone Warden"}}},
        ),
        game.engine,
    )

    refused = run.refusal()
    assert refused is not None and _CRYPT_ID in refused

    _ = connect(run.draft.world, Connect(from_id=EntityId("cloister"), to_id=_CRYPT_ID))
    assert run.refusal() is None


async def test_a_grown_npc_brings_its_sheet_into_the_live_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _grown(tmp_path)
    held = set(_sheets(game.state.world.mechanics))
    _ = _stub_author(monkeypatch)

    await _turn(game)

    assert set(_sheets(game.state.world.mechanics)) == held | {_WARDEN_ID}


def _sheets(mechanics: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    sheets = mechanics["sheets"]
    assert isinstance(sheets, dict)
    return sheets
