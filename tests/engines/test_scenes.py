import copy
from collections.abc import Sequence
from random import Random

import pytest
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    game,
    narrowed,
    scenario_for,
)

from aidm.core.entities import Refusal, Slug, parse
from aidm.core.model import Generation, PackSelection
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eCast, Loner3eGame
from aidm.engines.scenes.engine import MOVE_ON
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.tools import NextDraft, NextScene
from aidm.engines.scenes.world import SceneRun, SceneWorld
from aidm.engines.scenes.worldsmith import check_scene

PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = "mara"
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
ARC = "A few lines on what waits farther in, long enough to satisfy the model's own minimum."


def _world(*runs: SceneRun, **fields: object) -> SceneWorld[Person]:
    return SceneWorld[Person].model_validate({"player": PLAYER, "runs": list(runs), **fields})


def _run(place: str, title: str, *, here: Sequence[Slug] = ()) -> SceneRun:
    return SceneRun(
        place=place,
        title=title,
        focus="What happens next here?",
        situation=SITUATION,
        here=list(here),
    )


def _travelling() -> SceneWorld[Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    return _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara}, party=[MARA])


def test_a_party_member_leaves_the_scene_only_through_leave_party() -> None:
    world = _travelling()
    with pytest.raises(Refusal, match="leaves through `leave_party`"):
        _ = world.leave(MARA)
    assert world.present() == [MARA]


def test_killing_a_party_member_drops_them_from_the_party() -> None:
    world = _travelling()
    facts = world.kill(MARA)
    assert world.party == []
    assert not world.cast[MARA].alive
    assert any(fact.card == "Mara is dead" for fact in facts)


def test_require_living_here_refuses_the_dead_where_require_here_does_not() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True, alive=False)
    world = _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara})

    assert world.require_here(MARA).id == MARA
    with pytest.raises(Refusal, match="dead"):
        _ = world.require_living_here(MARA)


def test_a_party_member_who_is_not_in_this_scene_is_refused() -> None:
    world = _travelling()
    world.run.here.remove(MARA)
    with pytest.raises(ValueError, match="the party is in every scene"):
        _ = _world(*world.runs, cast=world.cast, party=[MARA])


def test_the_next_scene_prompt_carries_the_scene_as_it_stands() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    run = narrowed(state, Loner3eGame).payload.run

    prompt = engine.render_next(state, "Down the stair.")

    assert f"THE SCENE NOW:\n{run.title} [{run.place}]\n{run.situation}" in prompt
    assert "present: Mara[mara]\nhidden: the vault map[vault-map]" in prompt


def test_apply_scene_with_an_empty_arc_keeps_the_worlds_arc() -> None:
    world = _travelling()
    world.arc = ARC
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        present=(MARA,),
        recap=RECAP,
    )

    world.apply_scene(draft)

    assert world.arc == ARC


def test_entering_someone_hidden_is_refused_reveal_makes_them_present() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=False)
    world = _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara})
    with pytest.raises(Refusal, match="already here"):
        _ = world.enter(MARA)
    _ = world.reveal_hidden(MARA)
    assert MARA in world.present()


def test_a_next_draft_naming_no_one_but_the_player_passes_and_installs() -> None:
    world = _world(_run("a1", "A1"))
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        recap=RECAP,
    )

    check_scene(draft, world)

    world.apply_scene(draft)

    assert world.runs[-1].title == "A2"


def test_next_scene_refuses_a_pursuit_and_a_complication_together() -> None:
    with pytest.raises(Refusal, match="not both"):
        _ = parse(
            NextScene,
            {"pursuit": "Down the stair.", "complication": "A second crew breaks in."},
        )


def test_a_departure_over_an_offer_requests_the_crossing_and_leaves_the_offer() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    _ = engine.tools["next_scene"].call(draft, {}, Random(0))

    _ = engine.tools["next_scene"].call(draft, {"pursuit": "Down the stair."}, Random(0))

    assert draft.generation is not None
    assert draft.generation.detail == "Down the stair."


def test_a_scene_engine_refuses_to_write_an_operation_not_its_own() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    draft.generation = Generation(operation="hire", detail="Hire a fixer.")

    with pytest.raises(Refusal, match="writes no 'hire'"):
        engine.validate(draft)


def test_an_action_the_scene_no_longer_offers_is_refused_and_notes_nothing() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()

    with pytest.raises(Refusal, match="the way on has changed"):
        engine.act(draft, MOVE_ON.id, "Down the stair.")

    assert draft.notes == []


def test_the_dead_stay_in_the_scene_but_do_not_speak() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    _ = draft.payload.kill(MARA)

    view = engine.narrator_view(draft)

    assert MARA in [subject.id for subject in view.subjects]
    assert MARA not in view.speakers


def test_a_party_member_prints_under_the_party_and_not_here() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    draft.payload.party.append(MARA)

    assert "Mara[mara]" not in draft.payload.here_lines()

    view = engine.narrator_view(draft)

    assert MARA in view.party
    assert MARA not in [subject.id for subject in view.others()]

    panels = engine.player_view(draft).panels
    party_panel = next(panel for panel in panels if panel.title == "Party")
    here_panel = next(panel for panel in panels if panel.title == "Also here")
    assert MARA in [row.icon_id for row in party_panel.rows]
    assert MARA not in [row.icon_id for row in here_panel.rows]


def test_a_scene_without_a_focus_installs_and_shows_no_scene_panel() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    draft = narrowed(state, Loner3eGame).draft()
    scene = NextDraft[Loner3eCast](place="a2", title="A2", situation=SITUATION, recap=RECAP)

    _ = engine.install(draft, scene)

    assert "This scene" not in [panel.title for panel in engine.player_view(draft).panels]
    assert "WHAT THIS SCENE IS ABOUT" not in str(engine.master_sections(draft))


def test_beginning_the_game_does_not_mutate_the_authored_scenario() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    before = scenario.payload.model_dump()
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    draft = engine.begin(scenario_id, scenario, character)
    world = narrowed(draft, Loner3eGame).payload

    world.cast[MARA].name = "Someone else"

    assert scenario.payload.model_dump() == before


def test_new_game_refuses_a_character_made_from_an_unselected_pack() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    stranded = character.model_copy(update={"packs": PackSelection(ids=(SRD_PACK, "other"))})

    with pytest.raises(Refusal, match="'kael' was made with srd, other"):
        engine.new_game(scenario, stranded)


def test_new_game_accepts_a_character_made_from_a_subset_of_the_scenarios_packs() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    wider = scenario.model_copy(update={"packs": PackSelection(ids=(SRD_PACK, "ap01-fantasy"))})
    character = LIBRARY.read_character("kael", engine.id, engine.character)

    assert engine.begin(scenario_id, wider, character).packs == wider.packs


def test_select_refuses_a_selection_without_the_srd() -> None:
    engine = narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine)

    with pytest.raises(Refusal, match="plays the 'srd' tables"):
        engine.select(PackSelection(ids=("ap01-fantasy",)))


def test_select_refuses_two_packs_that_define_the_same_id() -> None:
    engine = copy.copy(narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine))
    engine.packs = {**engine.packs, "twin": engine.packs[SRD_PACK]}

    with pytest.raises(Refusal, match="both define"):
        engine.select(PackSelection(ids=(SRD_PACK, "twin")))
