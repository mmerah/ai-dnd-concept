from random import Random
from typing import cast

import pytest
from fivee_test_support import initial_5e_game
from pydantic import ValidationError

from aidm.base import PLAYER_ID, Entity, EntityId
from aidm.engines.dnd5e import dice
from aidm.engines.dnd5e import rolls as rules
from aidm.engines.dnd5e.direction import Damage, Dnd5eDirection, dump_direction
from aidm.engines.dnd5e.state import Dnd5eActor, Dnd5eActorState, StatBlock
from aidm.engines.dnd5e.values import Attributes

KAEL = Dnd5eActor(
    entity=Entity(
        id=PLAYER_ID,
        kind="actor",
        name="Kael",
        brief="A relic-hunter.",
        known=True,
        parent_id=EntityId("here"),
    ),
    state=Dnd5eActorState(
        stats=StatBlock(attributes=Attributes(wisdom=14, strength=8), max_hp=10, hp=10)
    ),
)


def test_modifier() -> None:
    assert rules.modifier(KAEL.stats.attributes, "wisdom") == 2
    assert rules.modifier(KAEL.stats.attributes, "strength") == -1


def test_roll_check_adds_the_modifier_and_compares_to_the_dc() -> None:
    check = rules.roll_check(KAEL, "wisdom", dc=12, rng=Random(0))
    total = cast(int, check.fact.data["total"])
    roll = cast(int, check.fact.data["roll"])
    assert total == roll + 2
    assert check.success == (total >= 12)


@pytest.mark.parametrize(
    ("expression", "total"),
    [
        ("2d1+3", 5),  # d1 is deterministic, so every total below is exact
        ("2d1 + 4d1", 6),  # the multi-term sum the old single-term pattern could not express
        ("1d1-1", 0),
        ("10", 10),  # a bare constant: 61 of the pack's heal values are exactly this
    ],
)
def test_roll_dice_sums_every_term(expression: str, total: int) -> None:
    rolled, fact = rules.roll_dice(expression, Random(0))
    assert (rolled, fact.data["total"]) == (total, total)


def test_mod_parses_but_no_role_may_roll_it() -> None:
    """`MOD` belongs to the caster. Content packs carry it, so the grammar keeps it; a Director
    amount is refused at the model boundary rather than dangling at resolve time."""
    assert len(dice.terms("1d8 + MOD")) == 2
    with pytest.raises(ValidationError):
        Damage(amount="1d8 + MOD")


def test_a_malformed_expression_fails_at_its_boundary() -> None:
    """The parse is the validation, so a bad expression never reaches a roll."""
    for expression in ("not-dice", "1d0", "0d6", "2d6 +", "1d6 + + 2"):
        with pytest.raises(ValidationError):
            Damage(amount=expression)


def test_5e_resolution_is_pure_seeded_and_commits_once() -> None:
    """The mirror of the Story purity assertion: a shallow draft would corrupt committed state."""
    engine, state = initial_5e_game()
    direction = dump_direction(
        Dnd5eDirection(
            intent="Kael strikes at Mara.",
            tone="grim",
            mechanics=[Damage(amount=2, target_id=EntityId("mara"))],
        )
    )
    before = state.model_dump_json()

    first = engine.resolve(direction, state, Random(7))

    assert first == engine.resolve(direction, state, Random(7))
    assert state.model_dump_json() == before
    assert first.state is not state
