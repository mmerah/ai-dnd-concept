from random import Random

from support.game import ENGINE, initialized, loner_sheet, with_entity
from support.table import change, refused

from aidm.core.facts import cards
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.tools import Roll
from aidm.engines.loner3e.world import Loner3eEntity, outcome_for

FOE = "mara"
HIDDEN = Loner3eEntity(id="watcher", name="The Watcher", brief="unseen so far", known=False)
REVEALED = Loner3eEntity(id="warden", name="The Warden", brief="already met", known=True)


def _seal(**args: object) -> Roll:
    return Roll.model_validate(
        {
            "what": "Force the seal",
            "actor_id": PLAYER_ID,
            "question": "Does he get the seal open before the whispering finds him?",
        }
        | args
    )


def test_a_neutral_question_shows_one_chance_die_and_one_risk_die() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(), Random(0))

    (oracle,) = cards(facts)
    assert [die.label for die in oracle.dice] == ["Chance", "Risk"]
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Force the seal — oracle, neutral: ")


def test_advantage_rolls_two_chance_dice() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(position="advantage", edge="Relic Hunter"), Random(0))

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 2
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Force the seal — oracle, advantage (Relic Hunter): ")
    assert oracle.trace == oracle.card


def test_disadvantage_rolls_two_risk_dice() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(position="disadvantage"), Random(0))

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 2


def test_the_six_way_outcome_is_mapped_onto_the_card() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(), Random(0))

    (oracle,) = cards(facts)
    chance, risk = max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)
    assert oracle.card.endswith(f": {outcome_for(chance, risk).wording}")


def test_a_defeat_shows_the_owner_prefixed_effects_in_fact_order() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, FOE).luck.current = 1
    weakened = draft.commit()
    duel = Roll(
        what="Force her back",
        actor_id=PLAYER_ID,
        question="Does he force her back from the door?",
        target_id=FOE,
    )

    # Seed 0 rolls chance 4 against risk 4: a yes-but, one luck off the foe's last point.
    facts = ENGINE.roll(weakened.draft(), duel, Random(0))
    (oracle,) = cards(facts)

    assert oracle.card.split("\n")[1:] == [
        "Mara: Luck -1 → 0/6",
        "Mara: Out of luck",
        "Mara: Luck +6 → 6/6",
    ]


def test_the_players_own_defeat_reads_without_their_name() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1
    weakened = draft.commit()
    lunge = Roll(
        what="Hold the doorway",
        actor_id=FOE,
        question="Does she drive him off the doorway?",
        target_id=PLAYER_ID,
    )

    # Seed 0 rolls chance 4 against risk 4: a yes-but, one luck off the player's last point.
    facts = ENGINE.roll(weakened.draft(), lunge, Random(0))
    (oracle,) = cards(facts)

    assert oracle.card.split("\n")[1:] == [
        "Luck -1 → 0/6",
        "Out of luck",
        "Luck +6 → 6/6",
    ]


def test_restoring_luck_shows_as_a_counter_card() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1
    spent = draft.commit()

    facts = tuple(change(ENGINE, spent.draft(), "restore_luck", actor_id=PLAYER_ID))
    (event,) = cards(facts)
    assert event.card == "Luck +5 → 6/6"


def test_drive_refuses_naming_a_hidden_entity_but_allows_a_revealed_one() -> None:
    _, state = initialized()
    state = with_entity(with_entity(state, HIDDEN), REVEALED)
    draft = state.draft()
    kael = loner_sheet(draft, PLAYER_ID)

    assert "not met" in refused(
        ENGINE, draft, "drive", actor_id=PLAYER_ID, nemesis="The Watcher hunts him"
    )
    assert kael.nemesis == ""

    _ = change(ENGINE, draft, "drive", actor_id=PLAYER_ID, nemesis="The Warden hunts him")
    assert kael.nemesis == "The Warden hunts him"


def test_drive_refuses_naming_someone_unmet_who_is_not_in_this_scene() -> None:
    """The sheet row outlives the scene that wrote it, so the screen is the whole cast."""
    _, state = initialized()
    draft = with_entity(state, HIDDEN).draft()
    draft.world.scene.here.remove(HIDDEN.id)
    kael = loner_sheet(draft, PLAYER_ID)

    assert "not met" in refused(
        ENGINE, draft, "drive", actor_id=PLAYER_ID, nemesis="The Watcher hunts him"
    )
    assert kael.nemesis == ""


def test_spend_luck_is_refused_when_the_pack_does_not_spend_it() -> None:
    _, state = initialized()

    assert "this pack does not spend luck" in refused(
        ENGINE, state.draft(), "spend_luck", actor_id=PLAYER_ID, amount=2, why="A ward"
    )


def test_spend_luck_above_the_pool_is_refused_naming_it() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.pack_id = "ap01-fantasy"
    fantasy = draft.commit()

    assert "has 6 luck, not 10" in refused(
        ENGINE, fantasy.draft(), "spend_luck", actor_id=PLAYER_ID, amount=10, why="A ward"
    )


def test_spend_luck_lands_one_fact_and_no_defeat() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.pack_id = "ap01-fantasy"
    fantasy = draft.commit()

    facts = change(
        ENGINE, fantasy.draft(), "spend_luck", actor_id=PLAYER_ID, amount=2, why="A ward"
    )

    (event,) = cards(facts)
    assert event.card == "Luck -2 → 4/6"
    assert not loner_sheet(fantasy, PLAYER_ID).defeated


def test_change_tags_refuses_naming_a_hidden_entity_but_allows_a_revealed_one() -> None:
    _, state = initialized()
    state = with_entity(with_entity(state, HIDDEN), REVEALED)
    draft = state.draft()
    kael = loner_sheet(draft, PLAYER_ID)

    before = list(kael.tagged("gear"))

    assert "not met" in refused(
        ENGINE,
        draft,
        "change_tags",
        actor_id=PLAYER_ID,
        kind="gear",
        gained=["The Watcher's Key"],
    )
    assert kael.tagged("gear") == before

    _ = change(
        ENGINE,
        draft,
        "change_tags",
        actor_id=PLAYER_ID,
        kind="gear",
        gained=["The Warden's Key"],
    )
    assert kael.tagged("gear") == [*before, "The Warden's Key"]
