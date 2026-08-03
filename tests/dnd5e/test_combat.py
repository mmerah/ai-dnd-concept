from random import Random

import pytest
from core_test_support import updated
from fivee_test_support import content_ref as ref
from fivee_test_support import new_game, ruleset, summary, with_actor, with_item

from aidm.base import PLAYER_ID, ActorEntity, EntityId, ItemEntity
from aidm.engines.dnd5e import bestiary, procedures
from aidm.engines.dnd5e import rolls as rules
from aidm.engines.dnd5e.access import actor_of
from aidm.engines.dnd5e.direction import Attack, Damage, RollSave
from aidm.engines.dnd5e.resolve import resolve
from aidm.engines.dnd5e.state import (
    Dnd5eActor,
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eItemState,
)
from aidm.world import GameState

RULES = ruleset()


def armed(state: GameState) -> GameState:
    goblin = ActorEntity(
        id=EntityId("goblin"),
        name="a goblin",
        brief="Small and mean.",
        known=True,
        location_id=actor_of(state, PLAYER_ID).location_id,
    )
    state = with_actor(
        state,
        goblin,
        bestiary.statted_actor(
            goblin.id, Dnd5eActorDefinition(ref=ref("monsters", "goblin")), RULES
        ),
    )
    sword = ItemEntity(
        id=EntityId("sword"),
        name="a notched longsword",
        brief="Old steel.",
        known=True,
        container_id=PLAYER_ID,
    )
    return with_item(state, sword, Dnd5eItemState(ref=ref("weapons", "longsword")))


def test_a_to_hit_comes_from_the_record_for_a_monster_and_from_progression_for_the_player() -> None:
    state = armed(new_game())
    goblin = actor_of(state, EntityId("goblin"))
    assert procedures.swing(state, goblin, "scimitar", RULES).to_hit == 4
    mine = procedures.swing(state, actor_of(state, PLAYER_ID), "a notched longsword", RULES)
    assert (mine.name, mine.to_hit, mine.damage) == ("a notched longsword", 2, "1d8")
    with pytest.raises(ValueError, match="no attack called"):
        procedures.swing(state, goblin, "Vorpal Sneeze", RULES)


def test_archery_fighting_style_modifies_a_ranged_weapon_attack() -> None:
    state = armed(new_game())
    player = actor_of(state, PLAYER_ID)
    progression = player.progression
    assert progression is not None
    held = tuple(
        ref("features", "fighter-fighting-style-archery")
        if feature.index == "fighter-fighting-style-defense"
        else feature
        for feature in progression.features
    )
    archer = updated(player.state, progression=updated(progression, features=held))
    state = with_actor(state, player.entity, archer)
    bow = ItemEntity(
        id=EntityId("bow"),
        name="a yew longbow",
        brief="A tall bow polished smooth by use.",
        known=True,
        container_id=PLAYER_ID,
    )
    state = with_item(state, bow, Dnd5eItemState(ref=ref("weapons", "longbow")))
    attack = procedures.swing(state, actor_of(state, PLAYER_ID), bow.name, RULES)
    assert attack.to_hit == 6


def test_a_hit_deals_the_weapon_s_damage_and_a_miss_deals_nothing() -> None:
    swung = Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))
    hit = resolve([swung], armed(new_game()), Random(0), RULES)
    assert [fact.fact for fact in hit] == ["attack_rolled", "dice_rolled", "hp_changed"]
    assert summary(hit[0]).endswith("13 -> 17 vs ac 10: HIT")
    miss = resolve([swung], armed(new_game()), Random(2), RULES)
    assert [fact.fact for fact in miss] == ["attack_rolled"]
    assert summary(miss[0]).endswith("2 -> 6 vs ac 10: MISS")
    with pytest.raises(ValueError, match="does not strike at themselves"):
        resolve([Attack(weapon="Scimitar")], armed(new_game()), Random(0), RULES)


def test_a_save_uses_the_record_s_bonus_or_the_player_s_proficiency() -> None:
    state = new_game()
    player = actor_of(state, PLAYER_ID)
    assert player.progression is not None
    scores = player.stats.attributes
    assert rules.save_bonus(player, "constitution") == rules.modifier(scores, "constitution") + 2
    assert rules.save_bonus(player, "wisdom") == rules.modifier(scores, "wisdom")

    lich = RULES.archetype(ref("monsters", "lich"))
    assert lich is not None
    stats = lich.stats
    undead = Dnd5eActor(entity=player.entity, state=Dnd5eActorState(stats=stats))
    assert rules.save_bonus(undead, "constitution") == 10
    assert rules.save_bonus(undead, "strength") == rules.modifier(stats.attributes, "strength")


def test_a_save_selects_its_branch_like_a_check_does() -> None:
    state = armed(new_game())
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=EntityId("goblin"),
        on_failure=[Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))],
    )
    facts = resolve([gas], state, Random(0), RULES)
    assert summary(facts[0]) == "a goblin dexterity save: 13 -> 15 vs DC 25: FAILURE"
    assert [fact.fact for fact in facts[1:]] == [
        "attack_rolled",
        "dice_rolled",
        "hp_changed",
    ]


def test_a_save_on_someone_unseen_reveals_them_exactly_once() -> None:
    state = armed(new_game())
    goblin = state.world.require_kind(EntityId("goblin"), ActorEntity)
    unseen = with_actor(state, updated(goblin, known=False), actor_of(state, goblin.id).state)
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=goblin.id,
        on_failure=[Damage(amount=1, target_id=goblin.id)],
    )
    facts = resolve([gas], unseen, Random(0), RULES)
    assert [fact.fact for fact in facts] == ["entity_discovered", "dc_rolled", "hp_changed"]
