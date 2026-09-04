from collections.abc import Callable

import pytest
from pydantic import BaseModel
from support.table import the_campaign
from support.twentyfourxx import (
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

from aidm.core.entities import EngineId, EntityId, Refusal
from aidm.core.facts import Fact
from aidm.core.model import AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Commission
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.hub import GO_HOME, TAKE_JOB
from aidm.engines.scenes.drafts import CastDraft, JobDraft, NextDraft, ReturnDraft, SceneDraft
from aidm.engines.scenes.world import SceneRun
from aidm.engines.scenes.worldsmith import COMMISSION_ASK, cast_refusal, scene_refusal
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.world import TwentyfourxxGame
from aidm.engines.twentyfourxx.worldsmith import BOARD_GUIDANCE

TWENTYFOURXX = EngineId("twentyfourxx")
ENGINE = TwentyfourxxEngine()


async def _written(
    game: TwentyfourxxGame, intent: str, answer: WorldsmithAnswer
) -> SceneDraft[Person]:
    """The write alone: these tests read the model asked for, and install nothing."""
    return await ENGINE.write_next(game, intent, answer)


def _draft(**fields: object) -> SceneDraft[Person]:
    base = {
        "place": "bay-office",
        "title": "The Bay Office",
        "question": "Can they slip past the night crew before the lights return?",
        "situation": SITUATION,
        "arc": "Farther in, the fixer's own supplier still owes for the last load.",
    }
    return SceneDraft[Person].model_validate({**base, **fields})


def _built(draft: SceneDraft[Person]) -> AnyScenario:
    return ENGINE.build_scenario(ScenarioMeta(title="Loading Bay", premise=""), (), draft, "")


def test_apply_scene_resolves_present_by_name() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=("Kestrel", "sable")))
    assert SABLE in world.present()


def test_apply_scene_resolves_present_by_id_too() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=(str(SABLE),)))
    assert SABLE in world.present()


def test_apply_scene_marks_present_cast_known() -> None:
    world = small_world().payload
    world.apply_scene(_draft(present=("sable",)))
    assert world.cast[SABLE].known is True


def test_apply_scene_lands_new_cast() -> None:
    world = small_world().payload
    stranger = EntityId("stranger")
    world.apply_scene(
        _draft(
            present=("kestrel", "stranger"),
            cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
        ),
    )
    assert stranger in world.cast


def test_the_bar_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload
    draft = _draft(
        cast={PLAYER_ID: Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    assert "rewrites the player" in (scene_refusal(draft, world) or "")


def test_apply_scene_re_files_an_existing_cast_member_as_a_new_brief_alone() -> None:
    world = small_world().payload
    draft = _draft(
        present=("kestrel",),
        cast={KESTREL: Person(id=KESTREL, name="Another Kestrel", brief="rewritten")},
    )

    world.apply_scene(draft)

    assert (world.cast[KESTREL].name, world.cast[KESTREL].brief) == ("Kestrel", "rewritten")


def test_the_bar_refuses_a_misfiled_cast_entry() -> None:
    world = small_world().payload
    stranger = EntityId("stranger")
    other = EntityId("other")
    draft = _draft(
        present=("stranger",),
        cast={stranger: Person(id=other, name="A Stranger", brief="filed wrongly")},
    )
    assert "is filed under" in (scene_refusal(draft, world) or "")


def test_the_bar_refuses_present_hidden_overlap() -> None:
    world = small_world().payload
    assert scene_refusal(_draft(present=("sable",), hidden=("sable",)), world) == (
        "the scene needs nobody listed as both present and hidden: ['sable']"
    )


def test_the_bar_refuses_hiding_someone_the_player_has_met() -> None:
    world = small_world().payload
    assert scene_refusal(_draft(hidden=("kestrel",)), world) == (
        "the scene needs a hidden list without ['kestrel'], whom the player has already met"
    )


def test_the_opening_needs_a_cast_member() -> None:
    assert scene_refusal(_draft()) == "the scene needs at least one cast member besides the player"


def test_the_opening_refuses_a_present_name_that_exists_nowhere() -> None:
    draft = _draft(present=("nobody",))
    assert scene_refusal(draft) == "the scene needs ids that exist; these name nobody: ['nobody']"


def test_the_next_scene_needs_one_brought_back() -> None:
    world = small_world().payload
    stranger = EntityId("stranger")
    draft = _draft(
        hidden=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="unknown to the world")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs at least one existing cast member brought back"
    )


def test_nothing_is_owed_back_once_the_whole_cast_travels_with_the_player() -> None:
    world = small_world().payload
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
    world = small_world().payload
    ghost = EntityId("ghost")
    draft = _draft(
        present=("kestrel",), cast={ghost: Person(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload
    stalker = EntityId("stalker")
    situation = f"{SITUATION} Old Man Riley waits by the containers."
    draft = _draft(
        situation=situation,
        present=("kestrel",),
        hidden=(stalker,),
        cast={stalker: Person(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_the_bar_refuses_a_scene_that_lists_the_player() -> None:
    world = small_world().payload
    assert "put there by code" in (
        scene_refusal(_draft(present=("kestrel", "player")), world) or ""
    )


def test_the_bar_refuses_a_scene_that_lists_the_player_or_the_party() -> None:
    world = small_world().payload
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
    world = small_world().payload
    world.party = [KESTREL]
    world.apply_scene(_draft(present=("sable",)))
    assert world.present() == [KESTREL, SABLE]


def test_install_scene_names_who_travelled_in_the_trace() -> None:
    game = small_world()
    game.payload.party = [KESTREL]
    facts = ENGINE.install(game, _draft(present=("sable",)))
    assert facts[0].trace == (
        "the story moves to The Bay Office, the player travelling with Kestrel"
    )


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = ENGINE.install(game, _draft(present=("kestrel",)))
    assert len(game.payload.runs) == 2
    assert facts == [
        Fact(
            kind="scene_opened",
            trace="the story moves to The Bay Office",
            told=True,
            card="New scene: The Bay Office\n"
            "At stake: Can they slip past the night crew before the lights return?",
        ),
    ]


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = ENGINE.render_next(small_world(), "Explore the bay.", SceneDraft[Person])
    assert prompt.index("Rook[player]") < prompt.index("Kestrel[kestrel]")


def test_render_worldsmith_says_who_travels_with_the_player() -> None:
    game = small_world()
    game.payload.party = [KESTREL]
    prompt = ENGINE.render_next(game, "Explore the bay.", SceneDraft[Person])
    assert "travels with the player" in prompt


def test_opening_canon_marks_present_known() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    canon = ENGINE.opening_canon(draft, "")
    assert canon.cast[stranger].known is True


def test_build_scenario_refuses_an_unmet_draft() -> None:
    with pytest.raises(Refusal, match="cast member besides the player"):
        _ = _built(_draft())


def test_build_scenario_stamps_the_engine_id() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    assert _built(draft).engine == TWENTYFOURXX


RECAP = (
    "Kael cleared the pharmacy shelf by shelf, weighed what could be carried, and slipped back "
    "out before the block woke."
)
SUMMARY = (
    "Kael hit the bay office for the crates the fixer wanted, cleared them off deck by deck, "
    "and the job is done; a second stash they never opened still waits unspoken."
)
ARC = (
    "Farther in, the fixer's own supplier still owes for the last load, and has not yet been "
    "confronted."
)


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
            "recap": RECAP,
            "summary": SUMMARY,
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
            "arc": ARC,
        }
    )


def _next_draft(**fields: object) -> NextDraft[Person]:
    base = _draft(**fields).model_dump()
    return NextDraft[Person].model_validate(
        {
            **base,
            "recap": "Kael slipped past the night crew, found nothing worth taking, and moved "
            "on before the lights came back up.",
            "arc": ARC,
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
        answer = model.model_validate(chosen.model_dump())
        assert refusal(answer) is None
        return answer

    _ = await _written(game, GO_HOME, answer)
    assert recorded[-1] is ReturnDraft[Person]

    _ = await _written(game, "I look around the warehouse.", answer)
    assert recorded[-1] is NextDraft[Person]

    _ = game.payload.runs.pop()  # home again: the next scene is the one that leaves
    _ = await _written(game, TAKE_JOB.format(title="Job One"), answer)
    assert recorded[-1] is JobDraft[Person]


async def test_write_next_shows_this_job_only_on_a_return() -> None:
    game = hub_world()
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        chosen: SceneDraft[Person] = (
            _return_draft() if model is ReturnDraft[Person] else _next_draft(present=("fixer",))
        )
        answer = model.model_validate(chosen.model_dump())
        assert refusal(answer) is None
        return answer

    _ = await _written(game, GO_HOME, answer)
    assert "THIS JOB" in prompts[-1]

    _ = await _written(game, "I look around the warehouse.", answer)
    assert "THIS JOB" not in prompts[-1]


async def test_the_arc_line_only_reaches_a_next_draft_prompt() -> None:
    game = hub_world()
    game.payload.arc = "Farther out, the fixer's own debts are still unpaid."
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        chosen: SceneDraft[Person] = (
            _return_draft() if model is ReturnDraft[Person] else _next_draft(present=("fixer",))
        )
        answered = model.model_validate(chosen.model_dump())
        assert refusal(answered) is None
        return answered

    _ = await _written(game, GO_HOME, answer)
    assert "The arc as last written" not in prompts[-1]

    _ = await _written(game, "I look around the warehouse.", answer)
    assert "The arc as last written" in prompts[-1]


async def test_advance_reopens_a_left_open_job_and_shows_the_job_before() -> None:
    game = hub_world()
    world = game.payload
    campaign = the_campaign(world.campaign)
    job = campaign.jobs[0]
    job.title = "Job One"  # matches a board offer, so the take intent resolves it
    job.close(returned=len(world.runs), debrief="Crates delivered, for now.", summary=JOB)
    world.runs.append(
        SceneRun(
            place=HUB_PLACE,
            title="The Amber Tap",
            question="What job does Kael take off the board tonight?",
            situation=HUB_SITUATION,
            here=[],
        )
    )
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        answered = model.model_validate(_job_draft().model_dump())
        assert refusal(answered) is None
        return answered

    _ = await ENGINE.advance(game, TAKE_JOB.format(title="Job One"), answer)

    assert "THE JOB BEFORE" in prompts[-1]
    assert campaign.jobs[-1] is job
    assert len(job.attempts) == 2


def test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_refused() -> None:
    world = hub_world().payload
    stranger = EntityId("stranger")
    world.cast[stranger] = Person(id=stranger, name="Old Man Riley", brief="", known=False)
    draft = _return_draft().model_copy(update={"debrief": "Old Man Riley saw them off with a nod."})
    assert scene_refusal(draft, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )


def test_only_the_players_own_fields_are_checked_for_what_they_have_not_met() -> None:
    """`summary` is the game master's memory; `situation`, `debrief` and `question` are the
    player's, and none of them may hand the player what they have not found."""
    world = hub_world().payload
    stranger = EntityId("stranger")
    world.cast[stranger] = Person(id=stranger, name="Old Man Riley", brief="", known=False)

    named_in_summary = _return_draft().model_copy(
        update={
            "summary": "Old Man Riley wintered alone behind the loading bay while Kael cleared "
            "the crates; the haul came back whole and the fixer is paid, though a second stash "
            "still waits unspoken."
        }
    )
    assert scene_refusal(named_in_summary, world) is None

    named_in_situation = _return_draft().model_copy(
        update={"situation": f"{HUB_SITUATION} Old Man Riley watches from the doorway."}
    )
    assert scene_refusal(named_in_situation, world) == (
        "the scene needs a situation that does not name what the player has not met: "
        "['Old Man Riley']"
    )

    ided_in_debrief = _return_draft().model_copy(
        update={"debrief": f"The crates are cleared; {stranger} saw them off."}
    )
    assert scene_refusal(ided_in_debrief, world) == (
        "the scene needs a debrief that does not name what the player has not met: "
        "['Old Man Riley']"
    )

    hidden = EntityId("buried-chest")
    named_hidden_id_in_question = _return_draft().model_copy(
        update={
            "question": f"What does Kael do about {hidden}, now the job is behind them?",
            "hidden": (hidden,),
            "cast": {hidden: Person(id=hidden, name="A Buried Chest", brief="", known=False)},
        }
    )
    assert scene_refusal(named_hidden_id_in_question, world) == (
        "the scene needs a question that does not name what the player has not met: "
        "['A Buried Chest']"
    )


def test_install_scene_on_a_finished_hub_draft_swaps_the_board_and_notes_the_job() -> None:
    game = hub_world()
    campaign = the_campaign(game.payload.campaign)
    campaign.jobs[-1].finished = True
    facts = ENGINE.install(game, _return_draft())
    assert [offer.title for offer in campaign.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any("The Dock Run" in note for note in game.notes)


def test_install_scene_on_an_open_hub_draft_skips_the_note() -> None:
    game = hub_world()
    facts = ENGINE.install(game, _return_draft())
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == []


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
    prompt = ENGINE.render_next(hub_world(), "I look around.", SceneDraft[Person])
    assert f"THE JOB:\n{JOB}" in prompt


def test_the_scene_card_carries_the_stake_and_a_job_draft_its_terms() -> None:
    facts = ENGINE.install(hub_world(), _job_draft())
    assert facts[0].card == (
        "New scene: The Bay Office\n"
        "At stake: Can they slip past the night crew before the lights return?\n"
        f"The job: {JOB}"
    )


def test_install_scene_on_a_hub_draft_lands_a_home_card() -> None:
    game = hub_world()
    facts = ENGINE.install(game, _return_draft())
    assert any(fact.card.startswith("Home: Back at the Amber Tap") for fact in facts)


def test_cast_refusal_refuses_a_new_entry_marked_known() -> None:
    world = small_world().payload
    stranger = EntityId("stranger")
    draft = CastDraft[Person](
        cast={
            stranger: Person(
                id=stranger, name="A Stranger", brief="unknown to the world", known=True
            )
        }
    )
    assert "unmet" in (cast_refusal(draft, world) or "")


def test_cast_refusal_accepts_a_re_filed_known_id() -> None:
    world = small_world().payload
    draft = CastDraft[Person](
        cast={KESTREL: Person(id=KESTREL, name="Kestrel", brief="rewritten", known=True)}
    )
    assert cast_refusal(draft, world) is None


def test_install_cast_files_the_entry_unmet_and_drops_the_commission() -> None:
    game = small_world()
    stranger = EntityId("stranger")
    asked = Commission(kind="person", brief="A witness who saw the theft happen.")
    game.commissions.append(asked)
    written = CastDraft[Person](
        cast={stranger: Person(id=stranger, name="A Stranger", brief="Saw the theft happen.")}
    )

    facts = ENGINE.install_cast(game, asked, written)

    assert game.payload.cast[stranger].known is False
    assert game.commissions == []
    assert facts[0].kind == "commissioned"


def test_a_later_commission_is_refused_until_written_then_cleared_by_install() -> None:
    world = small_world().payload
    later = [Commission(kind="person", brief="A witness who saw the theft happen.", later=True)]

    assert scene_refusal(_draft(present=("kestrel",)), world, later) == (
        "the scene needs 1 asked for, 0 written: one new cast entry per commission"
    )

    stranger = EntityId("stranger")
    written_draft = _draft(
        present=("kestrel", "stranger"),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="A witness.")},
    )
    assert scene_refusal(written_draft, world, later) is None

    game = small_world()
    game.commissions.append(later[0])
    ENGINE.install(game, written_draft)
    assert game.commissions == []


def test_render_commission_carries_the_arc_line_and_no_asked_for_section() -> None:
    game = hub_world()
    game.payload.arc = "Farther in, the fixer's own supplier still owes for the last load."
    asked = Commission(kind="person", brief="A witness who saw the theft happen.")

    prompt = ENGINE.render_commission(game, asked)

    assert "The arc as last written" in prompt
    assert "THE GAME MASTER ASKED FOR:\n" not in prompt
    assert COMMISSION_ASK.format(kind=asked.kind, brief=asked.brief) in prompt
