from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pytest
from pydantic import BaseModel
from support.breathless import DAX as BREATHLESS_DAX
from support.breathless import ENGINE as BREATHLESS_ENGINE
from support.breathless import MIRA as BREATHLESS_MIRA
from support.breathless import SITUATION as BREATHLESS_SITUATION
from support.breathless import small_world as breathless_world
from support.game import ENGINE as LONER3E_ENGINE
from support.game import MAP, MARA, initialized
from support.game import SITUATION as LONER3E_SITUATION
from support.table import LIBRARY, narrowed, stub_worldsmith, updated
from support.twentyfourxx import ENGINE as TWENTYFOURXX_ENGINE
from support.twentyfourxx import KESTREL, SABLE
from support.twentyfourxx import SITUATION as TWENTYFOURXX_SITUATION
from support.twentyfourxx import small_world as twentyfourxx_world

from aidm.core.entities import Refusal, Slug
from aidm.core.model import AnyGame, Check, Generation
from aidm.core.play import Exchange
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.breathless.world import BreathlessWorld, Survivor
from aidm.engines.loner3e.world import Loner3eCast, Loner3eWorld
from aidm.engines.scenes.engine import DEPARTURE
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.world import SceneWorld
from aidm.engines.scenes.worldsmith import check_scene
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import Crewmate, TwentyfourxxWorld

DECOY_CAST_ENTRY = {"id": PLAYER_ID, "name": "Someone", "brief": "filed wrongly", "known": True}
BREATHLESS_BASE: Mapping[str, object] = {
    "place": "alley",
    "title": "The Alley",
    "focus": "Can they lose the mob in the alley?",
    "situation": BREATHLESS_SITUATION,
    "arc": "Farther on, the mob's own paymaster still doesn't know Jax's face.",
}
TWENTYFOURXX_BASE: Mapping[str, object] = {
    "place": "bay-office",
    "title": "The Bay Office",
    "focus": "Can they slip past the night crew before the lights return?",
    "situation": TWENTYFOURXX_SITUATION,
    "arc": "Farther in, the fixer's own supplier still owes for the last load.",
}
LONER3E_BASE: Mapping[str, object] = {
    "place": "cloister",
    "title": "The Cloister",
    "focus": "Does the cloister walk still reach the stair?",
    "situation": LONER3E_SITUATION,
    "arc": "Farther along, the stair still leads down to what Tomas would not speak of.",
}


@dataclass(frozen=True, slots=True)
class SceneCase:
    engine: AnyEngine
    game: Callable[[], AnyGame]
    base: Mapping[str, object]  # the draft fields every scene of this case starts from
    bar: Callable[[Mapping[str, object]], None]
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


CASES = (
    SceneCase(
        engine=BREATHLESS_ENGINE,
        game=breathless_world,
        base=BREATHLESS_BASE,
        bar=_bar(SceneDraft[Survivor], BreathlessWorld, BREATHLESS_BASE, breathless_world),
        player="Jax",
        met=BREATHLESS_MIRA,
        unmet=BREATHLESS_DAX,
    ),
    SceneCase(
        engine=TWENTYFOURXX_ENGINE,
        game=twentyfourxx_world,
        base=TWENTYFOURXX_BASE,
        bar=_bar(SceneDraft[Crewmate], TwentyfourxxWorld, TWENTYFOURXX_BASE, twentyfourxx_world),
        player="Rook",
        met=KESTREL,
        unmet=SABLE,
    ),
    SceneCase(
        engine=LONER3E_ENGINE,
        game=lambda: initialized()[1],
        base=LONER3E_BASE,
        bar=_bar(SceneDraft[Loner3eCast], Loner3eWorld, LONER3E_BASE, lambda: initialized()[1]),
        player="Kael",
        met=MARA,
        unmet=MAP,
    ),
)


def _case_id(case: SceneCase) -> str:
    return case.engine.id


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
def test_a_player_id_cast_entry_is_refused_by_new_game(case: SceneCase) -> None:
    scenario = case.engine.scenario.model_validate(
        {
            "meta": {"title": "Test", "premise": "A test scenario.", "scope": "One tense evening."},
            "engine": case.engine.id,
            "packs": (SRD_PACK,),
            "payload": {**case.base, "cast": {PLAYER_ID: DECOY_CAST_ENTRY}},
        }
    )
    character = LIBRARY.read_character("kael", case.engine.id, case.engine.character)
    with pytest.raises(Refusal, match="the player is in the cast"):
        case.engine.new_game(scenario, character)


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_a_scenario_with_no_packs_is_refused_by_check_packs(case: SceneCase) -> None:
    with pytest.raises(Refusal, match="at least one table set"):
        case.engine.validate(updated(case.game(), packs=()))


@pytest.mark.parametrize("case", CASES, ids=_case_id)
async def test_install_scene_appends_a_run_and_returns_the_opened_fact(case: SceneCase) -> None:
    draft = case.game().draft()
    # A chapter with no exchanges yet is dropped, not appended to; give it one first.
    draft.log[-1].exchanges.append(Exchange(words="They wait.", lines=()))
    chapters_before = len(draft.log)
    answer = {
        **case.base,
        "present": [case.met],
        "hidden": [case.unmet],
        "recap": "They leave the mess behind and press on toward what waits next.",
    }
    written = await case.engine.advance(
        draft, Generation(operation=DEPARTURE, detail="Onward."), stub_worldsmith(answer)
    )
    assert len(draft.log) == chapters_before + 1
    assert any(fact.card.startswith("New scene:") for fact in written.facts)


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
