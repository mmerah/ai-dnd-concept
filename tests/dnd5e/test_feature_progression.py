from random import Random

import pytest
from core_test_support import updated
from fivee_progression_support import (
    RULES,
    SHEET,
    levelled,
    next_of,
    ref,
)
from fivee_test_support import new_game, player_of, summary, with_actor

from aidm.engines.dnd5e import features, progression
from aidm.engines.dnd5e import presentation as views
from aidm.engines.dnd5e.access import Dnd5eWorld
from aidm.engines.dnd5e.direction import Consequence, LevelUp, Rest, UseFeature
from aidm.engines.dnd5e.resolve import resolve as _resolve
from aidm.engines.dnd5e.ruleset import Ruleset
from aidm.engines.dnd5e.state import ResourceState
from aidm.engines.dnd5e.values import Attributes
from aidm.facts import Fact
from aidm.world import GameState

SECOND_WIND = "srd-2014/features/second-wind"
ACTION_SURGE = "srd-2014/features/action-surge-1-use"


def resolve(
    mechanics: list[Consequence], state: GameState, rng: Random, ruleset: Ruleset
) -> list[Fact]:
    """Commit so a later call in the same test sees an earlier call's typed-state mutation."""
    world = Dnd5eWorld(state=state)
    facts = _resolve(mechanics, world, rng, ruleset)
    _ = world.commit()
    return facts


def test_fighter_features_are_owned_spent_and_recharged() -> None:
    state = levelled(new_game(), 2)
    progression_state = player_of(state).progression
    assert progression_state is not None
    assert [feature.index for feature in progression_state.features] == [
        "second-wind",
        "fighter-fighting-style-defense",
        "action-surge-1-use",
    ]
    assert {
        key: resource.remaining for key, resource in progression_state.feature_resources.items()
    } == {SECOND_WIND: 1, ACTION_SURGE: 1}
    shown = views.player_state(player_of(state).stats, player_of(state).progression, RULES)
    assert "Fighting Style: Defense[id=srd-2014/features/fighter-fighting-style-defense]" in shown
    assert (
        f"Second Wind[id={SECOND_WIND}] "
        "[engine-resolved bonus_action — 1/1 uses — short rest — usable]"
    ) in shown
    assert (
        f"Action Surge (1 use)[id={ACTION_SURGE}] "
        "[description-guided special — 1/1 uses — short rest — usable]"
    ) in shown

    player = player_of(state)
    wounded = with_actor(
        state, player.entity, updated(player.state, stats=updated(player.stats, hp=1))
    )
    facts = resolve(
        [UseFeature(feature=SECOND_WIND), UseFeature(feature=ACTION_SURGE)],
        wounded,
        Random(1),
        RULES,
    )
    assert [fact.kind for fact in facts] == [
        "feature_used",
        "dice_rolled",
        "hp_changed",
        "feature_used",
        "feature_activated",
    ]
    spent = wounded
    current = player_of(spent).progression
    assert current is not None
    assert {key: resource.remaining for key, resource in current.feature_resources.items()} == {
        SECOND_WIND: 0,
        ACTION_SURGE: 0,
    }
    assert player_of(spent).stats.hp == 6
    depleted = views.player_state(player_of(spent).stats, player_of(spent).progression, RULES)
    assert f"Second Wind[id={SECOND_WIND}]" in depleted
    assert "0/1 uses — short rest — depleted" in depleted
    with pytest.raises(ValueError, match="0 uses left"):
        resolve([UseFeature(feature=SECOND_WIND)], spent, Random(1), RULES)

    _ = resolve([Rest(rest="short")], spent, Random(1), RULES)
    current = player_of(spent).progression
    assert current is not None
    assert {key: resource.remaining for key, resource in current.feature_resources.items()} == {
        SECOND_WIND: 1,
        ACTION_SURGE: 1,
    }


def test_a_replacement_requires_the_feature_it_replaces() -> None:
    replacement = features.profile_of(ref("features", "action-surge-2-uses"), RULES)
    with pytest.raises(ValueError, match="replaces features not held"):
        features.acquire(
            (),
            {},
            (replacement,),
            ruleset=RULES,
            class_level=17,
            attributes=SHEET.starting_attributes,
        )


@pytest.mark.parametrize(("remaining", "upgraded"), [(0, 1), (1, 2)])
def test_a_resource_upgrade_preserves_uses_spent(remaining: int, upgraded: int) -> None:
    before = features.profile_of(ref("features", "action-surge-1-use"), RULES)
    after = features.profile_of(ref("features", "action-surge-2-uses"), RULES)
    _, resources = features.acquire(
        (before.ref,),
        {
            ACTION_SURGE: ResourceState(
                remaining=remaining,
                maximum=1,
                recharge="short",
            )
        },
        (after,),
        ruleset=RULES,
        class_level=17,
        attributes=Attributes(),
    )
    upgraded_resource = resources["srd-2014/features/action-surge-2-uses"]
    assert (upgraded_resource.remaining, upgraded_resource.maximum) == (upgraded, 2)


def test_shared_and_scaled_resources_need_no_class_specific_engine_rules() -> None:
    ki = features.profile_of(ref("features", "ki"), RULES)
    flurry = features.profile_of(ref("features", "flurry-of-blows"), RULES)
    inspiration = features.profile_of(ref("features", "bardic-inspiration-d6"), RULES)
    lay_on_hands = features.profile_of(ref("features", "lay-on-hands"), RULES)

    _, monk_resources = features.acquire(
        (), {}, (ki, flurry), ruleset=RULES, class_level=5, attributes=Attributes()
    )
    assert {key: resource.maximum for key, resource in monk_resources.items()} == {
        "srd-2014/features/ki": 5
    }
    state = new_game()
    current = player_of(state).progression
    assert current is not None
    monk = updated(
        current,
        level=5,
        features=(ki.ref, flurry.ref),
        feature_resources=monk_resources,
    )
    player = player_of(state)
    spent = with_actor(state, player.entity, updated(player.state, progression=monk))
    _ = resolve([UseFeature(feature="srd-2014/features/flurry-of-blows")], spent, Random(1), RULES)
    monk_after = player_of(spent).progression
    assert monk_after is not None
    assert monk_after.feature_resources["srd-2014/features/ki"].remaining == 4
    (rested,) = resolve([Rest(rest="short")], spent, Random(1), RULES)
    assert summary(rested) == "completed a short rest; recharged Ki"
    assert player_of(spent).progression == monk

    _, bard_resources = features.acquire(
        (), {}, (inspiration,), ruleset=RULES, class_level=1, attributes=Attributes(charisma=16)
    )
    assert bard_resources["srd-2014/features/bardic-inspiration-d6"].maximum == 3

    _, paladin_resources = features.acquire(
        (), {}, (lay_on_hands,), ruleset=RULES, class_level=5, attributes=Attributes()
    )
    assert paladin_resources["srd-2014/features/lay-on-hands"].maximum == 25
    paladin = updated(
        current,
        level=5,
        features=(lay_on_hands.ref,),
        feature_resources=paladin_resources,
    )
    spent = with_actor(state, player.entity, updated(player.state, progression=paladin))
    _ = resolve(
        [UseFeature(feature="srd-2014/features/lay-on-hands", amount=7)], spent, Random(1), RULES
    )
    paladin_after = player_of(spent).progression
    assert paladin_after is not None
    assert paladin_after.feature_resources["srd-2014/features/lay-on-hands"].remaining == 18


def test_the_directors_level_up_consequence_unlocks_the_players_level_up() -> None:
    state = new_game()
    facts = resolve([LevelUp()], state, Random(1), RULES)
    assert [fact.kind for fact in facts] == ["level_up_available"]
    offered = player_of(state).progression
    assert offered is not None
    assert offered.level == 1
    assert offered.level_up_available
    assert resolve([LevelUp()], state, Random(1), RULES) == []


def test_the_player_answers_choices_after_the_director_awards_a_level() -> None:
    state = levelled(new_game(), 2)
    assert "not awarded" in views.level_up_state(player_of(state).progression)
    _ = resolve([LevelUp()], state, Random(1), RULES)
    assert "waiting for the player" in views.level_up_state(player_of(state).progression)

    decisions = next_of(state)
    world = Dnd5eWorld(state=state)
    _ = progression.advance(world.player(), decisions, RULES, Random(1))
    state = world.commit()
    after = player_of(state)
    assert after.progression is not None
    assert after.progression.level == 3
    assert after.progression.origin.subclass_ref == ref("subclasses", "champion")
    assert not after.progression.level_up_available
