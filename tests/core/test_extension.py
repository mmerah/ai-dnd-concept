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

import aidm.app.session
from aidm.app.authoring.draft import ScenarioPatch, WorldDraft
from aidm.app.authoring.extend import ExitLink, ExtensionPatch, delta
from aidm.app.authoring.playability import Playtest, extend_brief, playability
from aidm.app.session import WORLDSMITH, GameSession
from aidm.config import Settings
from aidm.content.authored import Character
from aidm.content.store import FileStore
from aidm.engines.engine import Engine
from aidm.engines.sheets import SheetBase
from aidm.state.base import PLAYER_ID, Entity, EntityId, Exit
from aidm.state.trace import Extended
from aidm.state.world import Game, Thread

_CRYPT_ID = EntityId("sub_crypt")


def _crypt() -> Entity:
    return Entity(
        id=_CRYPT_ID,
        kind="location",
        name="the sub-crypt",
        brief="A shelf of ossuary niches below the cloister floor.",
        exits=[Exit(to=EntityId("cloister"))],
    )


_ADDED = ExtensionPatch(
    entities=(_crypt(),),
    exits=(ExitLink(location_id=EntityId("cloister"), to=_CRYPT_ID),),
)


def _grown(directory: Path, *, thin: bool = True) -> GameSession:
    """A scenario that grows, staged with one door left to find and a change on offer."""
    game = loner3e_session(directory)
    game.scenario = updated(game.scenario, grows=True)
    game.state = at_boundary(game.state)
    if thin:
        tower = game.state.world.require(EntityId("bell_tower"))
        game.state = with_entity(game.state, updated(tower, known=True))
    return game


def _stub_author(monkeypatch: pytest.MonkeyPatch) -> list[Game]:
    """The authoring run itself is one agent run; what this pins is the session hook around it."""
    seen: list[Game] = []

    async def authored(
        config: Settings,
        engine: Engine[SheetBase],
        character: Character,
        state: Game,
    ) -> ExtensionPatch:
        del config, engine, character
        seen.append(state)
        return _ADDED

    monkeypatch.setattr(aidm.app.session, "author_extension", authored)
    return seen


async def _turn(game: GameSession, on_step: Callable[[str], None] | None = None) -> None:
    director = FunctionModel(scripted(text("nothing to do")))
    narrator = FunctionModel(scripted(narrated("You wait.")))
    with (
        game.stages.director.override(model=director),
        game.stages.narrator.override(model=narrator),
    ):
        _ = await game.submit("I wait.", on_step)


def test_the_live_world_becomes_a_scenario_the_extending_author_can_hold(tmp_path: Path) -> None:
    """The live world holds the player and their gear, which a `Scenario` refuses."""
    game = loner3e_session(tmp_path)
    draft = WorldDraft.of_game(game.state)
    scenario = draft.scenario((LONER3E,))

    ids = {entity.id for entity in scenario.world.entities}
    assert PLAYER_ID not in ids
    assert EntityId("lantern") not in ids
    assert scenario.starting_location_id == game.state.player_location
    assert EntityId("mara") in ids

    unmet = playability(
        draft,
        (Playtest(engine=game.engine, character=game.character),),
        extend_brief(game.state.world),
    )
    assert isinstance(unmet, str)
    assert "location" in unmet


def test_delta_is_the_canon_a_pass_added_and_the_ways_into_it(tmp_path: Path) -> None:
    game = loner3e_session(tmp_path)
    draft = WorldDraft.of_game(game.state)
    cloister = next(entity for entity in draft.entities if entity.id == EntityId("cloister"))
    edited_cloister = updated(cloister, exits=[*cloister.exits, Exit(to=_CRYPT_ID)], brief="edited")
    _ = draft.apply(
        ScenarioPatch(
            entities=(_crypt(), edited_cloister),
            threads=(Thread(id="the-lower-dark", title="The lower dark"),),
        )
    )

    patch = delta(game.state.world, draft)

    assert [entity.id for entity in patch.entities] == [_CRYPT_ID]
    assert patch.exits == (ExitLink(location_id=EntityId("cloister"), to=_CRYPT_ID),)
    assert [thread.id for thread in patch.threads] == ["the-lower-dark"]


async def test_a_thin_world_grows_inside_the_turn_that_ran_it_thin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canon lands in the save; the scenario other games load is never written to."""
    authored = (SCENARIOS / "whispering-vault" / "world.json").read_bytes()
    game = _grown(tmp_path)
    seen = _stub_author(monkeypatch)
    steps: list[str] = []

    await _turn(game, steps.append)

    assert len(seen) == 1
    assert WORLDSMITH in steps
    grown = game.state.world.find(_CRYPT_ID)
    assert grown is not None
    assert grown.known is False

    saved = FileStore(tmp_path).load("poc")
    assert saved is not None
    assert _CRYPT_ID in {entity.id for entity in saved.world.entities}

    assert any(isinstance(entry, Extended) for entry in game.entries)
    assert (SCENARIOS / "whispering-vault" / "world.json").read_bytes() == authored
    assert game.offers()


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
