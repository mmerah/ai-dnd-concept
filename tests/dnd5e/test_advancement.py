from collections.abc import Sequence
from random import Random

from core_test_support import updated
from fivee_test_support import initial_5e_game, player_of, ruleset, turn_of, with_actor

from aidm.plugins.dnd5e.advancement import (
    Dnd5eAdvancement,
    Dnd5eAdvancementDecisions,
    benefit_sections,
    dump_decision,
    plan_sections,
)
from aidm.plugins.dnd5e.content.records.character import ProgressionChoice
from aidm.plugins.dnd5e.state import Decisions, Dnd5eActorState


def _answer(choices: Sequence[ProgressionChoice]) -> Decisions:
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        for choice in choices
    }


def test_5e_advancement_status_and_full_flow() -> None:
    _, state = initial_5e_game()
    advancement = Dnd5eAdvancement(ruleset())

    status = advancement.status(state)

    assert status.headline == "level 1"
    assert status.progress == 1 / 20
    assert "No level-up has been awarded" in status.detail[0]
    assert any("Second Wind" in line and "1/1 uses" in line for line in status.detail)
    assert not advancement.available(state)

    turn = turn_of(state, Random(1))
    _ = turn.call(turn.tools.level_up)
    offered = turn.committed()
    assert advancement.available(offered)
    assert advancement.status(offered).detail[0] == "Level 2 is ready."

    preview = advancement.preview(offered)
    decisions = Dnd5eAdvancementDecisions(decisions=_answer(preview.choices))
    plan = advancement.plan(offered, decisions.decisions)
    assert plan.benefits.level == 2
    # The panel renders these verbatim, so the level's prose is only proved here.
    level_section = benefit_sections(preview.benefits)[0]
    assert level_section.heading == "Level 2"
    assert any("Hit die" in line for line in level_section.lines)
    assert plan_sections(plan)[0].heading == "Level 2"

    advanced = advancement.advance(dump_decision(decisions), offered, Random(1)).state

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
