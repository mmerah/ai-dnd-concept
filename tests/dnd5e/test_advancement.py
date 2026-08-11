from pathlib import Path

from core_test_support import capability
from fivee_test_support import dnd5e_game, dnd5e_session, ready

from aidm.engines.dnd5e.advance import ADVANCEMENT_READY, MAX_ABILITY, LevelUp
from aidm.engines.dnd5e.mechanics import read, sheet_of, write
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.packs import ContentRef

ACTION_SURGE = ContentRef(pack="srd-2014", collection="features", index="action-surge-1-use")
SECOND_WIND = ContentRef(pack="srd-2014", collection="features", index="second-wind")
LEGAL = LevelUp(picks=(ACTION_SURGE,), hit_points=7, why="second level")
OUTSIDE = LevelUp(picks=(SECOND_WIND,), hit_points=7, why="a feature already held")


def test_the_ready_tag_opens_the_next_level_row() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    assert growth.offered(state) is None

    offer = growth.offered(ready(state))

    assert offer is not None
    assert offer.prompt.startswith("Fighter 2")
    assert offer.options == (ACTION_SURGE,)
    assert offer.choose == 1


def test_standing_at_a_scenario_milestone_opens_the_offer_without_the_tag() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    draft = state.draft()
    _ = draft.move(draft.world.require(PLAYER_ID), draft.world.require(EntityId("vault")))
    at_vault = draft.committed()

    assert growth.offered(at_vault) is not None

    leveled = at_vault.draft()
    mechanics = read(leveled)
    sheet_of(mechanics, leveled.player).numbers["level"] = 2
    write(leveled, mechanics)
    assert growth.offered(leveled) is None


def test_a_pick_outside_the_offer_a_wrong_pick_count_and_an_ability_over_cap_are_refused() -> None:
    engine, state = dnd5e_game()
    growth = capability(engine)
    advancing = ready(state)
    offer = growth.offered(advancing)
    assert offer is not None

    no_picks = LevelUp(picks=(), hit_points=7, why="forgot the feature")
    over_cap = LevelUp(
        picks=(ACTION_SURGE,), hit_points=7, abilities={"strength": MAX_ABILITY + 1}, why="too much"
    )

    assert growth.violation(advancing, offer, LEGAL) is None
    assert "not on offer" in str(growth.violation(advancing, offer, OUTSIDE))
    assert "exactly 1 picks" in str(growth.violation(advancing, offer, no_picks))
    assert f"cannot pass {MAX_ABILITY}" in str(growth.violation(advancing, offer, over_cap))


def test_the_confirmed_level_up_commits_the_whole_level(tmp_path: Path) -> None:
    """The advisor's retry loop is engine-independent and covered by the story suite; this
    exercises what is 5e's own: `advance` writing the level onto the committed state."""
    game = dnd5e_session(tmp_path)
    game.state = ready(game.state)

    _ = game.apply_proposal(LEGAL)

    player = sheet_of(read(game.state), game.state.player)
    assert (player.numbers["level"], player.counters["hp"].maximum) == (2, 18)
    assert ACTION_SURGE in player.refs
    assert game.state.player.trait(ADVANCEMENT_READY) is None
    assert game.offer() is None
