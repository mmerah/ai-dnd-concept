import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel
from support.breathless import DAX as BREATHLESS_DAX
from support.breathless import ENGINE as BREATHLESS_ENGINE
from support.breathless import MIRA as BREATHLESS_MIRA
from support.breathless import SITUATION as BREATHLESS_SITUATION
from support.breathless import hired as breathless_hired
from support.breathless import small_world as breathless_world
from support.game import ENGINE as LONER3E_ENGINE
from support.game import MAP, MARA, initialized
from support.game import SITUATION as LONER3E_SITUATION
from support.table import LIBRARY, narrowed, refused, stub_worldsmith, updated
from support.twentyfourxx import ENGINE as TWENTYFOURXX_ENGINE
from support.twentyfourxx import KESTREL, SABLE
from support.twentyfourxx import SCENE_BASE as TWENTYFOURXX_BASE
from support.twentyfourxx import hired as twentyfourxx_hired
from support.twentyfourxx import small_world as twentyfourxx_world

from aidm.core.entities import Refusal, Slug
from aidm.core.model import AnyGame, Check, Generation, PackSelection
from aidm.core.play import Exchange
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import BreathlessWorld, Survivor
from aidm.engines.loner3e.world import Loner3eCast, Loner3eWorld
from aidm.engines.scenes.engine import DEPARTURE, SceneEngine
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld
from aidm.engines.scenes.worldsmith import check_scene
from aidm.engines.twentyfourxx.world import Crewmate, CrewSheet, TwentyfourxxWorld

DECOY_CAST_ENTRY = {"id": PLAYER_ID, "name": "Someone", "brief": "filed wrongly", "known": True}
BREATHLESS_BASE: Mapping[str, object] = {
    "place": "alley",
    "title": "The Alley",
    "focus": "Can they lose the mob in the alley?",
    "situation": BREATHLESS_SITUATION,
    "arc": "Farther on, the mob's own paymaster still doesn't know Jax's face.",
}
LONER3E_BASE: Mapping[str, object] = {
    "place": "cloister",
    "title": "The Cloister",
    "focus": "Does the cloister walk still reach the stair?",
    "situation": LONER3E_SITUATION,
    "arc": "Farther along, the stair still leads down to what Tomas would not speak of.",
}
# `SceneEngine`'s three type parameters are erased here on purpose: a tuple of concrete engines
# needs one shared type, and only the middle one (`G: Game[Any]`) is CLAUDE.md's sanctioned `Any`.
type AnySceneEngine = SceneEngine[Any, Any, Any]


@dataclass(frozen=True, slots=True)
class SceneCase:
    engine: AnySceneEngine
    game: Callable[[], AnyGame]
    base: Mapping[str, object]  # the draft fields every scene of this case starts from
    bar: Callable[[Mapping[str, object]], None]
    apply: Callable[[AnyGame, Mapping[str, object]], None]
    hire: Callable[[AnyGame, Slug], AnyGame] | None  # None where the engine hires nobody
    sheets_the_player: bool  # whether the player's own `Person` subtype carries a `sheet`
    player: str
    met: Slug
    unmet: Slug


def _bar[C: Person](
    draft_type: type[SceneDraft[C]],
    world: type[SceneWorld[C]],
    base: Mapping[str, object],
    game: Callable[[], AnyGame],
) -> Callable[[Mapping[str, object]], None]:
    def bar(fields: Mapping[str, object]) -> None:
        draft = draft_type.model_validate(dict(base) | dict(fields))
        check_scene(draft, narrowed(game().payload, world))

    return bar


def _apply[C: Person](
    draft_type: type[SceneDraft[C]], base: Mapping[str, object]
) -> Callable[[AnyGame, Mapping[str, object]], None]:
    """`case.bar`'s counterpart: hands the same draft shape to a real world's `apply_scene`."""

    def apply(state: AnyGame, fields: Mapping[str, object]) -> None:
        state.payload.apply_scene(draft_type.model_validate(dict(base) | dict(fields)))

    return apply


def _plain_scene(base: Mapping[str, object], fields: Mapping[str, object]) -> SceneDraft[Person]:
    """A scene draft with no engine-specific cast, for the tests that only need the shape."""
    return SceneDraft[Person].model_validate(dict(base) | dict(fields))


def _twentyfourxx_hire(state: AnyGame, member_id: Slug) -> AnyGame:
    return twentyfourxx_hired(state, member_id, skills={"Shooting": 8})


def _breathless_hire(state: AnyGame, member_id: Slug) -> AnyGame:
    breathless_hired(state.payload, member_id)
    return state


CASES = (
    SceneCase(
        engine=BREATHLESS_ENGINE,
        game=breathless_world,
        base=BREATHLESS_BASE,
        bar=_bar(SceneDraft[Survivor], BreathlessWorld, BREATHLESS_BASE, breathless_world),
        apply=_apply(SceneDraft[Survivor], BREATHLESS_BASE),
        hire=_breathless_hire,
        sheets_the_player=True,
        player="Jax",
        met=BREATHLESS_MIRA,
        unmet=BREATHLESS_DAX,
    ),
    SceneCase(
        engine=TWENTYFOURXX_ENGINE,
        game=twentyfourxx_world,
        base=TWENTYFOURXX_BASE,
        bar=_bar(SceneDraft[Crewmate], TwentyfourxxWorld, TWENTYFOURXX_BASE, twentyfourxx_world),
        apply=_apply(SceneDraft[Crewmate], TWENTYFOURXX_BASE),
        hire=_twentyfourxx_hire,
        sheets_the_player=True,
        player="Rook",
        met=KESTREL,
        unmet=SABLE,
    ),
    SceneCase(
        engine=LONER3E_ENGINE,
        game=lambda: initialized()[1],
        base=LONER3E_BASE,
        bar=_bar(SceneDraft[Loner3eCast], Loner3eWorld, LONER3E_BASE, lambda: initialized()[1]),
        apply=_apply(SceneDraft[Loner3eCast], LONER3E_BASE),
        hire=None,  # loner3e plays solo: nobody but the player ever acts
        sheets_the_player=False,  # Loner3eCast is a plain Person: no `Sheeted` mixin at all
        player="Kael",
        met=MARA,
        unmet=MAP,
    ),
)


def _case_id(case: SceneCase) -> str:
    return case.engine.id


SHEETED_CASES = tuple(case for case in CASES if case.sheets_the_player)
HIRING_CASES = tuple((case, case.hire) for case in CASES if case.hire is not None)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_the_bar_refuses_a_scene_that_lists_the_player(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="put there by code"):
        case.bar({"present": (case.player, case.met)})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_the_bar_refuses_a_draft_cast_entry_under_player_id(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="rewrites the player"):
        case.bar({"cast": {PLAYER_ID: DECOY_CAST_ENTRY}})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_the_bar_refuses_hiding_someone_met(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="already met"):
        case.bar({"hidden": (case.met,)})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_dead_draft_cast_member_is_refused(case: SceneCase) -> None:
    ghost = {"id": "ghost", "name": "Ghost", "brief": "", "alive": False}
    with pytest.raises(Refusal, match="may write them"):
        case.bar({"present": (case.met,), "cast": {"ghost": ghost}})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_the_bar_refuses_a_misfiled_cast_entry(case: SceneCase) -> None:
    stranger = {"id": "other", "name": "A Stranger", "brief": "filed wrongly"}
    with pytest.raises(Refusal, match="is filed under"):
        case.bar({"cast": {"stranger": stranger}})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_the_bar_refuses_present_hidden_overlap(case: SceneCase) -> None:
    message = f"nobody listed as both present and hidden: ['{case.unmet}']"
    with pytest.raises(Refusal, match=re.escape(message)):
        case.bar({"present": (case.unmet,), "hidden": (case.unmet,)})


def test_a_fresh_cast_member_may_be_authored_with_a_smaller_full_pool() -> None:
    bar = next(case.bar for case in CASES if case.engine is LONER3E_ENGINE)
    minor = {"id": "minor", "name": "Minor", "brief": "", "luck": {"current": 2, "maximum": 2}}
    bar({"cast": {"minor": minor}})


def test_a_fresh_cast_member_with_a_spent_pool_is_refused() -> None:
    bar = next(case.bar for case in CASES if case.engine is LONER3E_ENGINE)
    spent = {"id": "spent", "name": "Spent", "brief": "", "luck": {"current": 1, "maximum": 6}}
    with pytest.raises(Refusal, match="may write them"):
        bar({"cast": {"spent": spent}})


def test_a_fresh_cast_member_with_an_empty_pool_is_refused() -> None:
    bar = next(case.bar for case in CASES if case.engine is LONER3E_ENGINE)
    hollow = {"id": "hollow", "name": "Hollow", "brief": "", "luck": {"current": 0, "maximum": 0}}
    with pytest.raises(Refusal, match="may write them"):
        bar({"cast": {"hollow": hollow}})


def test_a_fresh_cast_member_already_defeated_is_refused() -> None:
    bar = next(case.bar for case in CASES if case.engine is LONER3E_ENGINE)
    beaten = {"id": "beaten", "name": "Beaten", "brief": "", "defeated": True}
    with pytest.raises(Refusal, match="may write them"):
        bar({"cast": {"beaten": beaten}})


def test_a_present_entitys_row_values_naming_what_is_hidden_is_refused() -> None:
    """A cast member's rows are free text beyond `brief` alone — screen those too."""
    bar = next(case.bar for case in CASES if case.engine is LONER3E_ENGINE)
    newbie = {"id": "newbie", "name": "Newbie", "brief": "", "nemesis": "the Bell"}
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        bar(
            {
                "present": ("newbie",),
                "hidden": ("bell-prop",),
                "cast": {"newbie": newbie, "bell-prop": bell},
            }
        )


def test_a_sheeted_draft_cast_member_is_refused() -> None:
    """Only twentyfourxx and breathless carry a sheet at all; pinned once is enough."""
    world = twentyfourxx_world().payload
    stranger = "stranger"
    draft = SceneDraft[Crewmate].model_validate(
        dict(TWENTYFOURXX_BASE)
        | {
            "present": ("kestrel", stranger),
            "cast": {
                stranger: Crewmate(
                    id=stranger, name="Stranger", brief="", sheet=CrewSheet(specialty="Muscle")
                )
            },
        }
    )
    with pytest.raises(Refusal, match="no sheet"):
        check_scene(draft, world)


def test_the_bar_refuses_a_scene_that_lists_the_player_or_the_party() -> None:
    world = twentyfourxx_world().payload
    world.party = [KESTREL]
    with pytest.raises(Refusal, match=re.escape("they are put there by code: ['kestrel']")):
        draft = SceneDraft[Crewmate].model_validate(
            dict(TWENTYFOURXX_BASE) | {"present": ("kestrel", "sable")}
        )
        check_scene(draft, world)
    with pytest.raises(
        Refusal, match=re.escape("they are put there by code: ['kestrel', 'player']")
    ):
        draft = SceneDraft[Crewmate].model_validate(
            dict(TWENTYFOURXX_BASE) | {"present": ("player", "kestrel")}
        )
        check_scene(draft, world)


def test_a_party_members_own_brief_naming_what_is_hidden_is_refused() -> None:
    """The party travels unlisted, but its members' briefs are read as closely as anyone's."""
    world = breathless_world().payload
    world.join_party(BREATHLESS_MIRA)
    draft = SceneDraft[Survivor].model_validate(
        dict(BREATHLESS_BASE)
        | {
            "hidden": (BREATHLESS_DAX,),
            "cast": {
                BREATHLESS_MIRA: {
                    "id": BREATHLESS_MIRA,
                    "name": "Mira",
                    "brief": "She is watching for Dax.",
                }
            },
        }
    )
    with pytest.raises(Refusal, match="does not name what is hidden"):
        check_scene(draft, world)


def test_the_opening_refuses_a_present_name_that_exists_nowhere() -> None:
    draft = _plain_scene(TWENTYFOURXX_BASE, {"present": ("nobody",)})
    with pytest.raises(Refusal, match="these name nobody"):
        check_scene(draft)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_hidden_multi_word_name_in_situation_is_refused(case: SceneCase) -> None:
    stalker = {"id": "stalker", "name": "Old Man Riley", "brief": ""}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {
                "situation": f"{case.base['situation']} Old Man Riley waits by the door.",
                "present": (case.met,),
                "hidden": ("stalker",),
                "cast": {"stalker": stalker},
            }
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_hidden_one_word_name_in_situation_is_refused(case: SceneCase) -> None:
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {
                "situation": f"{case.base['situation']} A bell tolls somewhere close.",
                "present": (case.met,),
                "hidden": ("bell-prop",),
                "cast": {"bell-prop": bell},
            }
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_hidden_one_word_name_matches_case_insensitively(case: SceneCase) -> None:
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {
                "situation": f"{case.base['situation']} a bell tolls somewhere close.",
                "present": (case.met,),
                "hidden": ("bell-prop",),
                "cast": {"bell-prop": bell},
            }
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_one_word_name_inside_another_word_is_not_refused(case: SceneCase) -> None:
    """Word boundaries stop `Bell` matching inside `doorbell`, unlike a bell on its own."""
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    case.bar(
        {
            "situation": f"{case.base['situation']} A doorbell rings somewhere close.",
            "present": (case.met,),
            "hidden": ("bell-prop",),
            "cast": {"bell-prop": bell},
        }
    )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
@pytest.mark.parametrize("field", ("title", "focus"))
def test_a_hidden_name_in_title_or_focus_is_refused(case: SceneCase, field: str) -> None:
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {
                field: f"{case.base[field]} A bell tolls somewhere close.",
                "present": (case.met,),
                "hidden": ("bell-prop",),
                "cast": {"bell-prop": bell},
            }
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_hidden_name_in_a_present_entitys_brief_is_refused(case: SceneCase) -> None:
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    watchman = {"id": "watchman", "name": "Watchman", "brief": "He is posted to guard the Bell."}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {
                "present": (case.met, "watchman"),
                "hidden": ("bell-prop",),
                "cast": {"bell-prop": bell, "watchman": watchman},
            }
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_hidden_entitys_own_brief_naming_another_hidden_entity_is_refused(
    case: SceneCase,
) -> None:
    """The leak a later `reveal` would make must be caught while both are still hidden."""
    bell = {"id": "bell-prop", "name": "Bell", "brief": ""}
    watchman = {"id": "watchman", "name": "Watchman", "brief": "He is posted to guard the Bell."}
    with pytest.raises(Refusal, match="does not name what is hidden"):
        case.bar(
            {"hidden": ("watchman", "bell-prop"), "cast": {"bell-prop": bell, "watchman": watchman}}
        )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_player_id_cast_entry_is_refused_by_new_game(case: SceneCase) -> None:
    scenario = case.engine.scenario.model_validate(
        {
            "meta": {"title": "Test", "premise": "A test scenario.", "scope": "One tense evening."},
            "engine": case.engine.id,
            "packs": PackSelection(ids=(SRD_PACK,)),
            "payload": {**case.base, "cast": {PLAYER_ID: DECOY_CAST_ENTRY}},
        }
    )
    character = LIBRARY.read_character("kael", case.engine.id, case.engine.character)
    with pytest.raises(Refusal, match="the player is in the cast"):
        case.engine.new_game(scenario, character)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_scenario_with_no_packs_is_refused_by_check_packs(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="needs a table set"):
        case.engine.validate(updated(case.game(), packs=None))


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="not installed"):
        packs = PackSelection(ids=(SRD_PACK, "uninstalled"))
        case.engine.validate(updated(case.game(), packs=packs))


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_resolves_present_by_name(case: SceneCase) -> None:
    state = case.game()
    name = state.payload.cast[case.unmet].name
    case.apply(state, {"present": (name,)})
    assert case.unmet in state.payload.present()


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_resolves_present_by_id_too(case: SceneCase) -> None:
    state = case.game()
    case.apply(state, {"present": (str(case.unmet),)})
    assert case.unmet in state.payload.present()


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_marks_present_cast_known(case: SceneCase) -> None:
    state = case.game()
    case.apply(state, {"present": (str(case.unmet),)})
    assert state.payload.cast[case.unmet].known is True


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_lands_new_cast(case: SceneCase) -> None:
    state = case.game()
    stranger = "stranger"
    case.apply(
        state,
        {
            "present": (str(case.met), stranger),
            "cast": {
                stranger: {"id": stranger, "name": "A Stranger", "brief": "unknown to the world"}
            },
        },
    )
    assert stranger in state.payload.cast


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_re_files_an_existing_cast_member_as_a_new_brief_alone(case: SceneCase) -> None:
    state = case.game()
    original_name = state.payload.cast[case.met].name
    case.apply(
        state,
        {
            "present": (str(case.met),),
            "cast": {case.met: {"id": case.met, "name": "Someone Else", "brief": "rewritten"}},
        },
    )
    assert (state.payload.cast[case.met].name, state.payload.cast[case.met].brief) == (
        original_name,
        "rewritten",
    )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_puts_the_party_first_in_the_new_run(case: SceneCase) -> None:
    state = case.game()
    state.payload.party = [case.met]
    case.apply(state, {"present": (str(case.unmet),)})
    assert state.payload.present() == [case.met, case.unmet]


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_apply_scene_refuses_a_present_name_that_resolves_to_nobody(case: SceneCase) -> None:
    state = case.game()
    with pytest.raises(Refusal, match="no such id or name exists"):
        case.apply(state, {"present": ("nobody",)})


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_an_entity_is_never_lost_when_a_scene_leaves_it_behind(case: SceneCase) -> None:
    state = case.game()
    left_title = state.payload.run.title
    runs_before = len(state.payload.runs)
    case.apply(state, {"present": (str(case.met),)})
    assert state.payload.last_seen(case.unmet) == f"last seen in: {left_title}"
    assert case.unmet in state.payload.cast
    assert len(state.payload.runs) == runs_before + 1


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_install_scene_names_who_travelled_in_the_trace(case: SceneCase) -> None:
    state = case.game()
    state.payload.party = [case.met]
    met_name = state.payload.cast[case.met].name
    facts = case.engine.install(state, _plain_scene(case.base, {"present": (str(case.unmet),)}))
    assert (
        facts[0].trace
        == f"the scene opens: {case.base['title']}, the player travelling with {met_name}"
    )


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_render_worldsmith_says_who_travels_with_the_player(case: SceneCase) -> None:
    state = case.game()
    state.payload.party = [case.met]
    prompt = case.engine.render_next(state, "Explore what lies ahead.")
    assert "travels with the player" in prompt


@pytest.mark.parametrize("case", SHEETED_CASES, ids=_case_id)
def test_a_player_with_no_sheet_is_refused(case: SceneCase) -> None:
    world = case.game().payload
    unsheeted = world.player.model_copy(update={"sheet": None})
    with pytest.raises(ValueError, match="the player carries no sheet"):
        type(world)(cast=world.cast, player=unsheeted, runs=world.runs)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_cast_that_holds_the_player_is_refused(case: SceneCase) -> None:
    world = case.game().payload
    decoy = world.cast[case.met].model_copy(update={"id": PLAYER_ID})
    with pytest.raises(ValueError, match="the player is in the cast"):
        type(world)(cast={**world.cast, PLAYER_ID: decoy}, player=world.player, runs=world.runs)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_player_is_never_listed_in_the_scene(case: SceneCase) -> None:
    world = case.game().payload
    bad_run = world.run.model_copy(update={"here": [*world.run.here, PLAYER_ID]})
    with pytest.raises(ValueError, match="never listed in it"):
        type(world)(cast=world.cast, player=world.player, runs=[bad_run])


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_check_filing_rejects_mis_filed_cast(case: SceneCase) -> None:
    world = case.game().payload
    with pytest.raises(ValueError, match="is filed under"):
        type(world)(cast={"wrong-key": world.cast[case.met]}, player=world.player, runs=world.runs)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_only_what_is_hidden_here_can_be_revealed(case: SceneCase) -> None:
    state = case.game()
    assert "not hidden here" in refused(case.engine, state.draft(), "reveal", entity_id=case.met)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_require_here_alive_refuses_dead_cast_member(case: SceneCase) -> None:
    world = case.game().payload
    world.cast[case.met].alive = False
    with pytest.raises(Refusal):
        world.require_living_here(case.met)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_require_actor_none_is_the_player(case: SceneCase) -> None:
    world = case.game().payload
    assert world.require_actor(None) is world.player
    assert world.require_actor(PLAYER_ID) is world.player


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_require_returns_the_player_for_player_id(case: SceneCase) -> None:
    world = case.game().payload
    assert world.require(PLAYER_ID) is world.player


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_here_yields_the_player_first(case: SceneCase) -> None:
    world = case.game().payload
    assert next(world.here()) is world.player


@pytest.mark.parametrize(
    ("case", "hire"), HIRING_CASES, ids=[case.engine.id for case, _ in HIRING_CASES]
)
def test_require_actor_accepts_a_living_sheeted_party_member(
    case: SceneCase, hire: Callable[[AnyGame, Slug], AnyGame]
) -> None:
    world = hire(case.game(), case.met).payload
    assert world.require_actor(case.met) is world.cast[case.met]


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_require_actor_refuses_an_unsheeted_member(case: SceneCase) -> None:
    world = case.game().payload
    world.party = [case.met]
    with pytest.raises(Refusal, match="not the player or a hired party member"):
        world.require_actor(case.met)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_party_member_stops_travelling_when_they_leave_the_party(case: SceneCase) -> None:
    world = case.game().payload
    world.party = [case.met]
    assert world.leave_party(case.met)
    assert case.met not in world.party


@pytest.mark.parametrize("case", CASES, ids=_case_id)
async def test_install_scene_appends_a_run_and_returns_the_opened_fact(case: SceneCase) -> None:
    draft = case.game().draft()
    # A chapter with no exchanges yet is dropped, not appended to; give it one first.
    draft.log[-1].exchanges.append(Exchange(words="They wait.", lines=()))
    chapters_before = len(draft.log)
    recap = "They leave the mess behind and press on toward what waits next."
    answer = {**case.base, "present": [case.met], "hidden": [case.unmet], "recap": recap}
    written = await case.engine.advance(
        draft, Generation(operation=DEPARTURE, detail="Onward."), stub_worldsmith(answer)
    )
    assert len(draft.log) == chapters_before + 1
    assert any(fact.card.startswith("New scene:") for fact in written.facts)
    # `install` stamps the recap on the chapter being left, not the fresh one it opens.
    assert draft.log[-2].recap == recap
    assert draft.log[-1].recap == ""


@pytest.mark.parametrize("case", CASES, ids=_case_id)
async def test_render_worldsmith_lists_the_player_first(case: SceneCase) -> None:
    prompts: list[str] = []

    async def recording[M: BaseModel](prompt: str, _model: type[M], _check: Check[M]) -> M:
        prompts.append(prompt)
        raise Refusal("recorded")

    with pytest.raises(Refusal, match="recorded"):
        await case.engine.advance(
            case.game().draft(), Generation(operation=DEPARTURE, detail="Onward."), recording
        )

    cast_section = prompts[0].split("THE WHOLE CAST:\n", 1)[1].split("\n\n", 1)[0]
    assert cast_section.index(f"{case.player}[player]") < cast_section.index(f"[{case.met}]")
    assert cast_section.index(f"{case.player}[player]") < cast_section.index(f"[{case.unmet}]")
