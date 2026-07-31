from random import Random

from core_test_support import updated
from fivee_progression_support import answers
from fivee_test_support import initial_5e_game, player_of, ruleset, with_actor

from aidm_5e.advancement import Dnd5eAdvancement, Dnd5eAdvancementDecisions
from aidm_5e.domain.models.consequences import LevelUp
from aidm_5e.domain.models.direction import Dnd5eDirection
from aidm_5e.engine.progression import AdvancementPlan, LevelUpPreview
from aidm_5e.models import Dnd5eActorState


def test_5e_advancement_status_and_full_adapter_flow() -> None:
    engine, state = initial_5e_game()
    advancement = Dnd5eAdvancement(ruleset())

    status = advancement.status(state)

    assert status.headline == "level 1"
    assert status.progress == 1 / 20
    assert "No level-up has been awarded" in status.detail[0]
    assert any("Current class features" in line for line in status.detail)
    assert any("Second Wind" in line and "1/1 uses" in line for line in status.detail)
    assert not advancement.available(state)

    offered = engine.rules.resolve(
        Dnd5eDirection(
            intent="Kael earns a level.",
            tone="triumphant",
            mechanics=[LevelUp()],
        ),
        state,
        Random(1),
    ).state
    assert advancement.available(offered)
    assert advancement.status(offered).detail[0] == "Level 2 is ready."

    preview = advancement.preview(offered)
    assert isinstance(preview, LevelUpPreview)
    decisions = Dnd5eAdvancementDecisions(decisions=answers(preview.choices))
    plan = advancement.plan(offered, decisions)
    assert isinstance(plan, AdvancementPlan)

    advanced = advancement.advance(offered, decisions, Random(1)).state

    assert advancement.status(advanced).headline == "level 2"
    assert not advancement.available(advanced)


def test_5e_advancement_status_covers_classless_and_max_level_characters() -> None:
    advancement = Dnd5eAdvancement(ruleset())
    _, state = initial_5e_game()
    player = player_of(state)
    classless = with_actor(state, player.entity, Dnd5eActorState(stats=player.stats))

    assert "no class" in advancement.status(classless).detail[0]

    assert player.progression is not None
    at_twenty = updated(
        player.state,
        progression=updated(player.progression, level=20, level_up_available=False),
    )
    maximum = with_actor(state, player.entity, at_twenty)

    status = advancement.status(maximum)
    assert status.headline == "level 20"
    assert status.progress == 1.0
    assert status.detail[0] == "Level 20 is the last."
