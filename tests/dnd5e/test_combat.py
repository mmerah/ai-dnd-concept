from random import Random

import pytest
from core_test_support import updated
from fivee_test_support import actor_of, new_game, ruleset, summary, with_actor, with_item
from fivee_test_support import content_ref as ref

from aidm.base import PLAYER_ID, Entity, EntityId
from aidm.engines.dnd5e import bestiary, procedures
from aidm.engines.dnd5e import rolls as rules
from aidm.engines.dnd5e.access import Dnd5eWorld
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
    goblin = Entity(
        id=EntityId("goblin"),
        kind="actor",
        name="a goblin",
        brief="Small and mean.",
        known=True,
        parent_id=actor_of(state, PLAYER_ID).entity.parent_id,
    )
    authored = Dnd5eActorDefinition(ref=ref("monsters", "goblin"))
    state = with_actor(
        state,
        goblin,
        bestiary.statted_actor(goblin.id, authored.model_dump(mode="json"), RULES),
    )
    sword = Entity(
        id=EntityId("sword"),
        kind="item",
        name="a notched longsword",
        brief="Old steel.",
        known=True,
        parent_id=PLAYER_ID,
    )
    return with_item(state, sword, Dnd5eItemState(ref=ref("weapons", "longsword")))


def test_a_to_hit_comes_from_the_record_for_a_monster_and_from_progression_for_the_player() -> None:
    state = armed(new_game())
    world = Dnd5eWorld(state=state)
    goblin = world.actor(EntityId("goblin"))
    assert procedures.swing(world, goblin, "scimitar", RULES).to_hit == 4
    mine = procedures.swing(world, world.actor(PLAYER_ID), "a notched longsword", RULES)
    assert (mine.name, mine.to_hit, mine.damage) == ("a notched longsword", 2, "1d8")
    with pytest.raises(ValueError, match="no attack called"):
        procedures.swing(world, goblin, "Vorpal Sneeze", RULES)


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
    bow = Entity(
        id=EntityId("bow"),
        kind="item",
        name="a yew longbow",
        brief="A tall bow polished smooth by use.",
        known=True,
        parent_id=PLAYER_ID,
    )
    state = with_item(state, bow, Dnd5eItemState(ref=ref("weapons", "longbow")))
    world = Dnd5eWorld(state=state)
    attack = procedures.swing(world, world.actor(PLAYER_ID), bow.name, RULES)
    assert attack.to_hit == 6


def test_a_hit_deals_the_weapon_s_damage_and_a_miss_deals_nothing() -> None:
    swung = Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))
    hit = resolve([swung], Dnd5eWorld(state=armed(new_game())), Random(0), RULES)
    assert [fact.kind for fact in hit] == ["attack_rolled", "dice_rolled", "hp_changed"]
    assert summary(hit[0]).endswith("13 -> 17 vs ac 10: HIT")
    miss = resolve([swung], Dnd5eWorld(state=armed(new_game())), Random(2), RULES)
    assert [fact.kind for fact in miss] == ["attack_rolled"]
    assert summary(miss[0]).endswith("2 -> 6 vs ac 10: MISS")
    with pytest.raises(ValueError, match="does not strike at themselves"):
        resolve([Attack(weapon="Scimitar")], Dnd5eWorld(state=armed(new_game())), Random(0), RULES)


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


def test_a_save_selects_its_branch_and_reveals_the_target_exactly_once() -> None:
    state = armed(new_game())
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=EntityId("goblin"),
        on_failure=[Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))],
    )
    facts = resolve([gas], Dnd5eWorld(state=state), Random(0), RULES)
    assert summary(facts[0]) == "a goblin dexterity save: 13 -> 15 vs DC 25: FAILURE"
    assert [fact.kind for fact in facts[1:]] == ["attack_rolled", "dice_rolled", "hp_changed"]

    goblin = state.world.require_kind(EntityId("goblin"), "actor")
    unseen = with_actor(state, updated(goblin, known=False), actor_of(state, goblin.id).state)
    gas_on_hidden = RollSave(
        ability="dexterity",
        dc=25,
        target_id=goblin.id,
        on_failure=[Damage(amount=1, target_id=goblin.id)],
    )
    hidden_facts = resolve([gas_on_hidden], Dnd5eWorld(state=unseen), Random(0), RULES)
    assert [fact.kind for fact in hidden_facts] == ["entity_discovered", "dc_rolled", "hp_changed"]
