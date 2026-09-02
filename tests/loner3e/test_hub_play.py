from loner3e_test_support import HUB_PLACE, HUB_SITUATION, JOB, JOB_PLACE, KEEPER, PACKS, hub_world
from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.model import CheckAnswer
from aidm.engines.hub import GO_HOME, HOME_ROW, HUB_ROW, TAKE_JOB, Debrief
from aidm.engines.loner3e.views import master_sections, player_view
from aidm.engines.loner3e.world import LonerCharacter
from aidm.engines.loner3e.worldsmith import (
    HubDraft,
    SceneDraft,
    install_scene,
    opening_canon,
    render_worldsmith,
    scene_refusal,
    write_next,
)


def _draft(**fields: object) -> SceneDraft:
    base = {
        "place": "deeper-in",
        "title": "Deeper In",
        "question": "Can Kael get further into the cairn before dawn?",
        "situation": HUB_SITUATION,
    }
    return SceneDraft.model_validate({**base, **fields})


def _hub_draft(*, finished: bool, offers: int = 2) -> HubDraft:
    return HubDraft.model_validate(
        {
            "place": HUB_PLACE,
            "title": "Back at the Guild Hall",
            "question": "What does Kael do next, now the job is behind him?",
            "situation": HUB_SITUATION,
            "present": (KEEPER,),
            "offers": [
                {"title": f"Job {number}", "pitch": f"I take job {number}."}
                for number in range(1, offers + 1)
            ],
            "debrief": {
                "text": "The cairn is sealed again and the relic is recovered.",
                "finished": finished,
            },
        }
    )


async def test_write_next_asks_for_hub_draft_only_on_go_home_away_from_the_hub() -> None:
    game = hub_world()
    recorded: list[type[BaseModel]] = []

    async def answer(prompt: str, model: type[BaseModel], refusal: CheckAnswer) -> BaseModel:
        recorded.append(model)
        written = _hub_draft(finished=True) if model is HubDraft else _draft(present=(KEEPER,))
        assert refusal(written) is None
        return written

    _ = await write_next({}, game, GO_HOME, answer)
    assert recorded[-1] is HubDraft

    _ = await write_next({}, game, "I look around the cairn.", answer)
    assert recorded[-1] is SceneDraft


def test_a_job_scene_placed_at_the_hub_is_refused() -> None:
    world = hub_world().payload.world
    draft = _draft(place=HUB_PLACE, present=(KEEPER,))
    assert scene_refusal(draft, world) == (
        "the scene needs a place away from the hub: home is reached by going home"
    )


def test_a_return_with_one_offer_is_refused() -> None:
    world = hub_world().payload.world
    assert scene_refusal(_hub_draft(finished=True, offers=1), world, hub=True) == (
        "the scene needs a board of 2 to 3 offers"
    )


def test_a_scene_draft_with_offers_is_refused_off_the_hub() -> None:
    world = hub_world().payload.world
    draft = _draft(
        place=JOB_PLACE, present=(KEEPER,), offers=[{"title": "A", "pitch": "I take A."}]
    )
    assert scene_refusal(draft, world) == "the scene needs no offers: only the hub has a board"


def test_a_take_written_at_the_hub_without_a_job_is_refused() -> None:
    game = hub_world()
    install_scene(game, _hub_draft(finished=True))
    world = game.payload.world
    draft = _draft(place=JOB_PLACE, present=(KEEPER,))
    assert scene_refusal(draft, world) == (
        "the scene needs a `job` of a short paragraph: who wants what done, what done looks "
        "like, what it pays"
    )


def test_a_later_job_scene_carrying_a_job_is_refused() -> None:
    world = hub_world().payload.world
    draft = _draft(place=JOB_PLACE, present=(KEEPER,), job=JOB)
    assert scene_refusal(draft, world) == (
        "the scene needs no `job`: only the scene that leaves the hub carries it"
    )


def test_install_scene_on_a_finished_return_swaps_board_notes_job_keeps_companion() -> None:
    game = hub_world()
    world = game.payload.world
    scout = EntityId("scout")
    world.cast[scout] = LonerCharacter(id=scout, name="Scout", brief="A hired scout", known=True)
    world.companions = [scout]

    facts = install_scene(game, _hub_draft(finished=True))

    world = game.payload.world
    assert [offer.title for offer in world.board] == ["Job 1", "Job 2"]
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert any(fact.card == "Home: Back at the Guild Hall" for fact in facts)
    assert any("The Sealed Cairn" in note for note in game.notes)
    assert scout in world.run.present


def test_install_scene_on_an_open_return_skips_the_growth_note() -> None:
    game = hub_world()
    facts = install_scene(game, _hub_draft(finished=False))
    assert [fact.kind for fact in facts] == ["job_closed", "scene_opened"]
    assert game.notes == ()


def test_render_worldsmith_in_a_campaign_has_the_hub_section() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, "I look around the hall.", "guidance text")
    assert "THE HUB" in prompt


def test_render_worldsmith_returning_has_the_hub_draft_schema() -> None:
    world = hub_world().payload.world
    prompt = render_worldsmith(world, GO_HOME, "guidance text", returning=True)
    assert '"debrief"' in prompt


def test_render_worldsmith_at_the_hub_has_the_take_brief() -> None:
    game = hub_world()
    install_scene(game, _hub_draft(finished=True))
    world = game.payload.world
    prompt = render_worldsmith(world, "I look at the board.", "guidance text")
    assert "WHAT COMES NEXT is the job they take" in prompt


def test_player_view_shows_the_board_panel_and_hub_row_at_the_hub() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    view = player_view(game)
    board = next(panel for panel in view.panels if panel.title == "Board")
    assert [row.label for row in board.rows] == ["Job One", "Job Two"]
    scene = next(panel for panel in view.panels if panel.title == "This scene")
    assert HUB_ROW.label in [row.label for row in scene.rows]


def test_player_view_board_rows_play_take_job_intents() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    view = player_view(game)
    board = next(panel for panel in view.panels if panel.title == "Board")
    assert [row.intent for row in board.rows] == [
        TAKE_JOB.format(title="Job One"),
        TAKE_JOB.format(title="Job Two"),
    ]


def test_player_view_shows_home_row_only_when_settled_away_from_the_hub() -> None:
    game = hub_world()
    world = game.payload.world

    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert HOME_ROW.label not in [row.label for row in scene.rows]

    at_hub = hub_world()
    at_hub.payload.world.runs = [at_hub.payload.world.runs[0]]
    scene = next(panel for panel in player_view(at_hub).panels if panel.title == "This scene")
    assert HOME_ROW.label not in [row.label for row in scene.rows]

    world.run.settled = True
    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert HOME_ROW.label in [row.label for row in scene.rows]


def test_player_view_jobs_panel_has_a_row_after_a_return() -> None:
    game = hub_world()
    world = game.payload.world
    debrief = Debrief(text="The cairn is sealed again.", finished=True)
    returned = world.runs[0].model_copy(
        update={"scene": world.runs[0].scene.model_copy(update={"debrief": debrief})}
    )
    world.runs.append(returned)
    jobs = next(panel for panel in player_view(game).panels if panel.title == "Jobs")
    assert len(jobs.rows) == 1


def test_master_sections_has_jobs_so_far_in_a_campaign_and_the_board_at_the_hub() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    sections = dict(master_sections(PACKS, game))
    assert "JOBS SO FAR" in sections
    assert "Job One" in sections["THE BOARD"]


def test_master_sections_has_the_job_away_from_the_hub_and_the_hub_heading_at_the_hub() -> None:
    game = hub_world()
    sections = dict(master_sections(PACKS, game))
    assert sections["THE JOB"] == JOB
    assert "THE QUESTION THIS SCENE SETTLES" in sections

    at_hub = hub_world()
    at_hub.payload.world.runs = [at_hub.payload.world.runs[0]]
    hub_sections_dict = dict(master_sections(PACKS, at_hub))
    assert "WHAT THIS PLACE IS ABOUT" in hub_sections_dict
    assert "THE QUESTION THIS SCENE SETTLES" not in hub_sections_dict


def _opening(**fields: object) -> SceneDraft:
    return _draft(
        place=HUB_PLACE,
        present=("keeper",),
        cast={
            "keeper": LonerCharacter(id=EntityId("keeper"), name="Keeper", brief="Keeps the hall")
        },
        **fields,
    )


def test_opening_canon_sets_the_hub_and_board_for_a_campaign_only() -> None:
    offers = [{"title": "A", "pitch": "Take A."}, {"title": "B", "pitch": "Take B."}]
    campaign = opening_canon(_opening(offers=offers), source="", kind="campaign")
    assert campaign.hub == HUB_PLACE
    assert [offer.title for offer in campaign.board] == ["A", "B"]
    assert opening_canon(_opening(), source="", kind="one-shot").hub is None
