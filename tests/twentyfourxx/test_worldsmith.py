from support.table import TWENTYFOURXX
from support.twentyfourxx import KESTREL, SABLE, SITUATION, small_world

from aidm.core.entities import EntityId
from aidm.core.facts import Fact
from aidm.core.model import AnyScenario, ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.scenes.drafts import SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine

ENGINE = TwentyfourxxEngine()


def _draft(**fields: object) -> SceneDraft[Person]:
    base = {
        "place": "bay-office",
        "title": "The Bay Office",
        "question": "Can they slip past the night crew before the lights return?",
        "situation": SITUATION,
        "arc": "Farther in, the fixer's own supplier still owes for the last load.",
    }
    return SceneDraft[Person].model_validate(base | fields)


def _built(draft: SceneDraft[Person]) -> AnyScenario:
    return ENGINE.build_scenario(
        ScenarioMeta(title="Loading Bay", premise="", scope="One tense night shift."), (), draft, ""
    )


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


def test_the_opening_refuses_a_present_name_that_exists_nowhere() -> None:
    draft = _draft(present=("nobody",))
    assert scene_refusal(draft) == "the scene needs ids that exist; these name nobody: ['nobody']"


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
    prompt = ENGINE.render_next(small_world(), "Explore the bay.")
    assert prompt.index("Rook[player]") < prompt.index("Kestrel[kestrel]")


def test_render_worldsmith_says_who_travels_with_the_player() -> None:
    game = small_world()
    game.payload.party = [KESTREL]
    prompt = ENGINE.render_next(game, "Explore the bay.")
    assert "travels with the player" in prompt


def test_opening_canon_marks_present_known() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    canon = ENGINE.opening_canon(draft, "")
    assert canon.cast[stranger].known is True


def test_build_scenario_stamps_the_engine_id() -> None:
    stranger = EntityId("stranger")
    draft = _draft(
        present=(stranger,),
        cast={stranger: Person(id=stranger, name="A Stranger", brief="new to the world")},
    )
    assert _built(draft).engine == TWENTYFOURXX
