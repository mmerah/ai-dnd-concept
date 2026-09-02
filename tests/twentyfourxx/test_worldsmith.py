from collections.abc import Callable

import pytest
from core_test_support import REPOSITORY_ROOT
from pydantic import BaseModel
from twentyfourxx_test_support import (
    HUB_PLACE,
    HUB_SITUATION,
    JOB,
    JOB_PLACE,
    KESTREL,
    SABLE,
    SITUATION,
    hub_world,
    small_world,
)

from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.core.model import AnyScenario, WorldsmithAnswer
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import GO_HOME, TAKE_JOB
from aidm.engines.scenes.drafts import JobDraft, NextDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.world import scene_refusal
from aidm.engines.scenes.worldsmith import build_scenario, install_scene, opening_canon, write_next
from aidm.engines.twentyfourxx.engine import BOARD_GUIDANCE, JOB_DONE_NOTE, TwentyfourxxEngine
from aidm.engines.twentyfourxx.world import TwentyfourxxGame, TwentyfourxxScenarioFile

TWENTYFOURXX = EngineId("twentyfourxx")
ENGINE = TwentyfourxxEngine(REPOSITORY_ROOT / "packs" / "twentyfourxx")
WORLDSMITH = ENGINE.role
GUIDANCE = "guidance text"


async def _written(
    game: TwentyfourxxGame, intent: str, answer: WorldsmithAnswer
) -> SceneDraft[Person]:
    """The write alone: these tests read the model asked for, and install nothing."""
    return await write_next(
        game.payload.world, intent, answer, cast_type=Person, role=WORLDSMITH, guidance=GUIDANCE
    )


def _draft(**fields: object) -> SceneDraft[Person]:
    base = {
        "place": "bay-office",
        "title": "The Bay Office",
        "question": "Can they slip past the night crew before the lights return?",
        "situation": SITUATION,
    }
    return SceneDraft[Person].model_validate({**base, **fields})


def _built(written: SceneDraft[Person]) -> AnyScenario:
    return build_scenario(
        TwentyfourxxScenarioFile, TWENTYFOURXX, "Loading Bay", "", (), written, "", "one-shot"
    )


def test_apply_scene_resolves_present_by_name() -> None:
    world = small_world().payload.world
    world.apply_scene(_draft(present=("Kestrel", "sable")))
    assert SABLE in world.run.present


def test_apply_scene_resolves_present_by_id_too() -> None:
    world = small_world().payload.world
    world.apply_scene(_draft(present=(str(SABLE),)))
    assert SABLE in world.run.present


def test_apply_scene_marks_present_cast_known() -> None:
    world = small_world().payload.world
    world.apply_scene(_draft(present=("sable",)))
    assert world.cast[SABLE].known is True


def test_apply_scene_lands_new_cast() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    world.apply_scene(
        _draft(
            present=("kestrel", "stranger"),
            cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
        ),
    )
    assert stranger in world.cast


def test_the_bar_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload.world
    draft = _draft(
        cast={PLAYER_ID: Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    assert "rewrites the player" in (scene_refusal(draft, world) or "")


def test_apply_scene_re_files_an_existing_cast_member_as_a_new_brief_alone() -> None:
    world = small_world().payload.world
    draft = _draft(
        present=("kestrel",),
        cast={KESTREL: Person(id=KESTREL, name="Another Kestrel", brief="rewritten")},
    )

    world.apply_scene(draft)

    assert (world.cast[KESTREL].name, world.cast[KESTREL].brief) == ("Kestrel", "rewritten")


def test_the_bar_refuses_a_misfiled_cast_entry() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    other = EntityId("other")
    draft = _draft(
        present=("stranger",),
        cast={stranger: Person(id=other, name="A Stranger", brief="filed wrongly")},
    )
    assert "is filed under" in (scene_refusal(draft, world) or "")


def test_the_bar_refuses_present_hidden_overlap() -> None:
    world = small_world().payload.world
    assert scene_refusal(_draft(present=("sable",), hidden=("sable",)), world) == (
        "the scene needs nobody listed as both present and hidden: ['sable']"
    )


def test_the_bar_refuses_hiding_someone_the_player_has_met() -> None:
    world = small_world().payload.world
    assert scene_refusal(_draft(hidden=("kestrel",)), world) == (
        "the scene needs a hidden list without ['kestrel'], whom the player has already met"
    )


def test_the_opening_needs_a_cast_member() -> None:
    assert scene_refusal(_draft()) == "the scene needs at least one cast member besides the player"


def test_the_opening_refuses_a_present_name_that_exists_nowhere() -> None:
    draft = _draft(present=("nobody",))
    assert scene_refusal(draft) == "the scene needs ids that exist; these name nobody: ['nobody']"


def test_the_next_scene_needs_one_brought_back() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    draft = _draft(
        hidden=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs at least one existing cast member brought back"
    )


def test_nothing_is_owed_back_once_the_whole_cast_travels_with_the_player() -> None:
    world = small_world().payload.world
    stranger = EntityId("stranger")
    draft = _draft(
        hidden=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
    )
    world.party = [KESTREL]
    assert scene_refusal(draft, world) == (
        "the scene needs at least one existing cast member brought back"
    )
    world.cast[SABLE].known = True
    world.party = [KESTREL, SABLE]
    assert scene_refusal(draft, world) is None


def test_a_dead_draft_cast_member_is_refused() -> None:
    world = small_world().payload.world
    ghost = EntityId("ghost")
    draft = _draft(
        present=("kestrel",), cast={ghost: Person(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload.world
    stalker = EntityId("stalker")
    told = f"{SITUATION} Old Man Riley waits by the containers."
    draft = _draft(
        situation=told,
        present=("kestrel",),
        hidden=(stalker,),
        cast={stalker: Person(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_the_bar_refuses_a_scene_that_lists_the_player() -> None:
    world = small_world().payload.world
    assert "put there by code" in (
        scene_refusal(_draft(present=("kestrel", "player")), world) or ""
    )


def test_the_bar_refuses_a_scene_that_lists_the_player_or_the_party() -> None:
    world = small_world().payload.world
    world.party = [KESTREL]
    assert scene_refusal(_draft(present=("kestrel", "sable")), world) == (
        "the scene needs a scene that does not list the player or the party; "
        "they are put there by code: ['kestrel']"
    )
    assert scene_refusal(_draft(present=("player", "kestrel")), world) == (
        "the scene needs a scene that does not list the player or the party; "
        "they are put there by code: ['kestrel', 'player']"
    )


def test_apply_scene_puts_the_party_first_in_the_new_run() -> None:
    world = small_world().payload.world
    world.party = [KESTREL]
    world.apply_scene(_draft(present=("sable",)))
    assert world.run.present == [KESTREL, SABLE]


def test_install_scene_names_who_travelled_in_the_trace() -> None:
    game = small_world()
    game.payload.world.party = [KESTREL]
    facts = install_scene(game, _draft(present=("sable",)), finished_note=JOB_DONE_NOTE)
    assert facts[0].trace == (
        "the story moves to The Bay Office, the player travelling with Kestrel"
    )


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = install_scene(game, _draft(present=("kestrel",)), finished_note=JOB_DONE_NOTE)
    assert len(game.payload.world.runs) == 2
    assert facts == (
        Fact(
            kind="scene_opened",
            trace="the story moves to The Bay Office",
            told=True,
            card="New scene: The Bay Office\n"
            "At stake: Can they slip past the night crew before the lights return?",
        ),
    )


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = small_world().payload.world.render_worldsmith(
        "Explore the bay.", "guidance text", SceneDraft[Person], role=WORLDSMITH
    )
    assert prompt.index("Rook[player]") < prompt.index("Kestrel[kestrel]")


def test_render_worldsmith_says_who_travels_with_the_player() -> None:
    world = small_world().payload.world
    world.party = [KESTREL]
    prompt = world.render_worldsmith(
        "Explore the bay.", "guidance text", SceneDraft[Person], role=WORLDSMITH
    )
    assert "travels with the player" in prompt


def test_opening_canon_marks_present_known() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    canon = opening_canon(draft, source="")
    assert canon.cast[stranger].known is True


def test_build_scenario_refuses_an_unmet_draft() -> None:
    with pytest.raises(ValueError, match="cast member besides the player"):
        _ = _built(_draft())


def test_build_scenario_stamps_the_engine_id() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    assert _built(draft).engine == TWENTYFOURXX


def _return_draft(*, offers: int = 2) -> ReturnDraft[Person]:
    return ReturnDraft[Person].model_validate(
        {
            "place": HUB_PLACE,
            "title": "Back at the Amber Tap",
            "question": "What does Kael do next, now the job is behind them?",
            "situation": HUB_SITUATION,
            "present": ("fixer",),
            "offers": [
                {"title": f"Job {number}", "pitch": f"I take job {number}."}
                for number in range(1, offers + 1)
            ],
            "debrief": "The crates are cleared and paid for.",
        }
    )


def _job_draft() -> JobDraft[Person]:
    away = _draft(place=JOB_PLACE, present=("fixer",)).model_dump()
    return JobDraft[Person].model_validate(
        {
            **away,
            "job": JOB,
            "recap": "Kael left the Amber Tap with the job in hand and made straight for the "
            "dock, the fixer's directions still fresh.",
        }
    )


def _next_draft(**fields: object) -> NextDraft[Person]:
    base = _draft(**fields).model_dump()
    return NextDraft[Person].model_validate(
        {
            **base,
            "recap": "Kael slipped past the night crew, found nothing worth taking, and moved "
            "on before the lights came back up.",
        }
    )


async def test_write_next_picks_the_draft_the_moment_calls_for() -> None:
    game = hub_world()
    recorded: list[type[BaseModel]] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        recorded.append(model)
        if model is ReturnDraft[Person]:
            chosen: SceneDraft[Person] = _return_draft()
        elif model is JobDraft[Person]:
            chosen = _job_draft()
        else:
            chosen = _next_draft(present=("fixer",))
        written = model.model_validate(chosen.model_dump())
        assert refusal(written) is None
        return written

    _ = await _written(game, GO_HOME, answer)
    assert recorded[-1] is ReturnDraft[Person]

    _ = await _written(game, "I look around the warehouse.", answer)
    assert recorded[-1] is NextDraft[Person]

    _ = game.payload.world.runs.pop()  # home again: the next scene is the one that leaves
    _ = await _written(game, TAKE_JOB.format(title="Job One"), answer)
    assert recorded[-1] is JobDraft[Person]


def test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_refused() -> None:
    world = hub_world().payload.world
    stranger = EntityId("stranger")
    world.cast[stranger] = Person(id=stranger, name="Old Man Riley", brief="", known=False)
    draft = _return_draft().model_copy(update={"debrief": "Old Man Riley saw them off with a nod."})
    assert scene_refusal(draft, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )


def test_install_scene_on_a_finished_hub_draft_swaps_the_board_and_notes_the_job() -> None:
    game = hub_world()
    game.payload.world.run.job_done = True
    facts = install_scene(game, _return_draft(), finished_note=JOB_DONE_NOTE)
    world = game.payload.world
    assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any("The Dock Run" in note for note in game.notes)


def test_install_scene_on_an_open_hub_draft_skips_the_note() -> None:
    game = hub_world()
    facts = install_scene(game, _return_draft(), finished_note=JOB_DONE_NOTE)
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == ()


async def test_write_next_gives_the_board_guidance_on_every_campaign_write() -> None:
    game = hub_world()
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        return model.model_validate(_next_draft(present=("fixer",)).model_dump())

    _ = await ENGINE.advance(game, "I look around the warehouse.", answer)
    assert BOARD_GUIDANCE in prompts[-1]


def test_render_worldsmith_prints_the_job_line_for_the_job_run() -> None:
    prompt = hub_world().payload.world.render_worldsmith(
        "I look around.", "guidance text", SceneDraft[Person], role=WORLDSMITH
    )
    assert f"the job: {JOB}" in prompt


def test_the_scene_card_carries_the_stake_and_a_job_draft_its_terms() -> None:
    facts = install_scene(hub_world(), _job_draft(), finished_note=JOB_DONE_NOTE)
    assert facts[0].card == (
        "New scene: The Bay Office\n"
        "At stake: Can they slip past the night crew before the lights return?\n"
        f"The job: {JOB}"
    )


def test_install_scene_on_a_hub_draft_lands_a_home_card() -> None:
    game = hub_world()
    facts = install_scene(game, _return_draft(), finished_note=JOB_DONE_NOTE)
    assert any(fact.card.startswith("Home: Back at the Amber Tap") for fact in facts)
