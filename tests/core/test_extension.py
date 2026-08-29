from collections.abc import Callable
from pathlib import Path

import pytest
from core_test_support import (
    LONER3E,
    SCENARIOS,
    at_boundary,
    narrated,
    scripted,
    text,
    updated,
    with_entity,
)
from loner3e_test_support import loner3e_session
from pydantic_ai.models.function import FunctionModel

from aidm.app.runtime import GameSession
from aidm.authoring.draft import (
    ExitLink,
    PlaytestCheck,
    ScenarioDraft,
    ScenarioPatch,
    extend_brief,
    extension_patch,
    scenario_refusal,
)
from aidm.authoring.run import GrowthRun, briefing, growth_run
from aidm.content.io import FileStore
from aidm.engines.loner3e.rules import Sheet
from aidm.state.entities import PLAYER_ID, Entity, EntityId, Exit
from aidm.state.model import Game, Thread
from aidm.state.play import WorldExtended
from aidm.turn.run import TurnStep

_CRYPT_ID = EntityId("sub-crypt")


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
    game.state = at_boundary(game.state, Sheet)
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
        cloister = next(e for e in self.draft.entities if e.id == EntityId("cloister"))
        edited = updated(cloister, exits=[*cloister.exits, Exit(to=_CRYPT_ID)])
        _ = self.draft.apply(ScenarioPatch(entities=(_crypt(), edited)))
        return "grew the sub-crypt"

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
    draft = ScenarioDraft.from_game(game.state)
    scenario = draft.scenario(LONER3E, ("srd",))

    ids = {entity.id for entity in scenario.world.entities}
    assert PLAYER_ID not in ids
    assert EntityId("lantern") not in ids
    assert scenario.starting_location_id == game.state.player_location
    assert EntityId("mara") in ids

    unmet = scenario_refusal(
        draft,
        PlaytestCheck(engine=game.engine, character=game.character, packs=("srd",)),
        extend_brief(game.state.world),
    )
    assert isinstance(unmet, str)
    assert "location" in unmet


def test_delta_is_the_canon_a_pass_added_and_the_ways_into_it(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    draft = ScenarioDraft.from_game(game.state)
    cloister = next(entity for entity in draft.entities if entity.id == EntityId("cloister"))
    edited_cloister = updated(cloister, exits=[*cloister.exits, Exit(to=_CRYPT_ID)], brief="edited")
    _ = draft.apply(
        ScenarioPatch(
            entities=(_crypt(), edited_cloister),
            threads=(Thread(id="the-lower-dark", title="The lower dark"),),
        )
    )

    patch = extension_patch(game.state.world, draft)

    assert [entity.id for entity in patch.entities] == [_CRYPT_ID]
    assert patch.exits == (ExitLink(location_id=EntityId("cloister"), to=_CRYPT_ID),)
    assert [thread.id for thread in patch.threads] == ["the-lower-dark"]


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

    saved = FileStore(tmp_path).load("poc")
    assert saved is not None
    assert _CRYPT_ID in {entity.id for entity in game.engine.restored(saved).world.entities}

    assert any(isinstance(entry, WorldExtended) for entry in game.entries)
    assert (SCENARIOS / "whispering-vault" / "world.json").read_bytes() == authored
    assert game.engine.owed_notes(game.state)


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

    warden = Entity(
        id=EntityId("bone-warden"),
        kind="actor",
        name="the bone warden",
        brief="He counts the niches every night and never leaves.",
        parent_id=_CRYPT_ID,
        rules={"concept": "A Bone Warden"},
    )
    _ = run.draft.apply(ScenarioPatch(entities=(updated(_crypt(), exits=[]), warden)))

    refused = run.refusal()
    assert refused is not None and _CRYPT_ID in refused

    _ = run.draft.connect(EntityId("cloister"), _CRYPT_ID, False, False, False)
    assert run.refusal() is None
