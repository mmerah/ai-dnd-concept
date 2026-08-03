from random import Random

from core_test_support import updated
from fivee_test_support import initial_5e_game, player_of, ruleset, with_actor

from aidm.advancement import AdvancementChoice, FormField, SelectField
from aidm.engines.dnd5e.advancement import Dnd5eAdvancement
from aidm.engines.dnd5e.direction import Dnd5eDirection, LevelUp, dump_direction
from aidm.engines.dnd5e.state import Dnd5eActorState


def _answer(fields: tuple[FormField, ...]) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {}
    for field in fields:
        assert isinstance(field, SelectField)
        values[field.id] = tuple(option.key for option in field.options[: field.choose])
    return values


def test_5e_advancement_status_and_full_flow() -> None:
    engine, state = initial_5e_game()
    advancement = Dnd5eAdvancement(ruleset())

    status = advancement.status(state)

    assert status.headline == "level 1"
    assert status.progress == 1 / 20
    assert "No level-up has been awarded" in status.detail[0]
    assert any("Second Wind" in line and "1/1 uses" in line for line in status.detail)
    assert not advancement.available(state)

    proposal = dump_direction(
        Dnd5eDirection(intent="Kael earns a level.", tone="triumphant", mechanics=[LevelUp()])
    )
    offered = engine.resolve(proposal, state, Random(1)).state
    assert advancement.available(offered)
    assert advancement.status(offered).detail[0] == "Level 2 is ready."

    form = advancement.form(offered)
    option = form.options[0]
    choice = AdvancementChoice(option_id=option.id, values=_answer(option.fields))
    review = advancement.review(offered, choice)

    advanced = advancement.advance(review.decision, offered, Random(1)).state

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
