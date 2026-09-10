import pytest
from support.breathless import ENGINE, SITUATION, small_world

from aidm.core.facts import Fact
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.world import SKILLS, Survivor
from aidm.engines.breathless.worldsmith import SheetDraft
from aidm.engines.scenes.tools import SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal


def _draft(**fields: object) -> SceneDraft[Survivor]:
    base = {
        "place": "alley",
        "title": "The Alley",
        "focus": "Can they lose the mob in the alley?",
        "situation": SITUATION,
        "arc": "Farther on, the mob's own paymaster still doesn't know Jax's face.",
    }
    return SceneDraft[Survivor].model_validate(base | fields)


def test_the_bar_refuses_a_scene_that_lists_the_player() -> None:
    world = small_world().payload
    assert "put there by code" in (scene_refusal(_draft(present=("Jax", "mira")), world) or "")


def test_the_bar_refuses_a_draft_cast_entry_under_player_id() -> None:
    world = small_world().payload
    draft = _draft(
        cast={PLAYER_ID: Survivor(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)}
    )
    assert "rewrites the player" in (scene_refusal(draft, world) or "")


def test_the_bar_refuses_hiding_someone_met() -> None:
    world = small_world().payload
    assert "already met" in (scene_refusal(_draft(hidden=("mira",)), world) or "")


def test_a_dead_draft_cast_member_is_refused() -> None:
    world = small_world().payload
    ghost = "ghost"
    draft = _draft(
        present=("mira",), cast={ghost: Survivor(id=ghost, name="Ghost", brief="", alive=False)}
    )
    assert scene_refusal(draft, world) == (
        "the scene needs cast members as the worldsmith may write them: ['ghost: alive']"
    )


def test_a_hidden_multi_word_name_in_situation_is_refused() -> None:
    world = small_world().payload
    stalker = "stalker"
    situation = f"{SITUATION} Old Man Riley waits by the dumpster."
    draft = _draft(
        situation=situation,
        present=("mira",),
        hidden=(stalker,),
        cast={stalker: Survivor(id=stalker, name="Old Man Riley", brief="")},
    )
    assert scene_refusal(draft, world) == (
        "the scene needs a situation that does not name what is hidden: ['Old Man Riley']"
    )


def test_install_scene_appends_a_run_and_returns_the_opened_fact() -> None:
    game = small_world()
    facts = ENGINE.install(game, _draft(present=("mira",)))
    assert len(game.payload.runs) == 2
    assert facts == [
        Fact(
            trace="the scene opens: The Alley",
            told=True,
            card="New scene: The Alley\nCan they lose the mob in the alley?",
        ),
    ]


def test_render_worldsmith_lists_the_player_first() -> None:
    prompt = ENGINE.render_next(small_world(), "Explore the alley.")
    assert prompt.index("Jax[player]") < prompt.index("Mira[mira]")


def test_sheet_draft_rated_off_the_creation_spread_is_refused() -> None:
    with pytest.raises(ValueError, match="three d4"):
        SheetDraft(
            pronouns="he/him",
            job="Bell-ringer",
            skills=dict.fromkeys(SKILLS, 12),
            item="Boat hook",
        )
