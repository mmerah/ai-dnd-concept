from random import Random

import pytest
from aidm_5e.content.records.base import ContentRef
from aidm_5e.domain.models.base import PLAYER_ID, EntityId
from aidm_5e.domain.models.consequences import Attack, Damage, RollSave
from aidm_5e.domain.models.entities import ActorEntity, ItemEntity
from aidm_5e.domain.models.state import GameState
from aidm_5e.engine import bestiary, procedures, rules
from aidm_5e.engine.resolve import resolve
from aidm_5e.utils.models import updated
from fivee_test_support import new_game, ruleset

RULES = ruleset()


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def armed(state: GameState) -> GameState:
    goblin = bestiary.statted(
        ActorEntity(
            id=EntityId("goblin"),
            name="a goblin",
            brief="Small and mean.",
            known=True,
            location_id=state.player.location_id,
            ref=ref("monsters", "goblin"),
        ),
        RULES,
    )
    assert isinstance(goblin, ActorEntity)
    sword = ItemEntity(
        id=EntityId("sword"),
        name="a notched longsword",
        brief="Old steel.",
        known=True,
        ref=ref("weapons", "longsword"),
        container_id=PLAYER_ID,
    )
    entities = {**state.world.entities, goblin.id: goblin, sword.id: sword}
    return updated(state, world=updated(state.world, entities=entities))


def test_a_to_hit_comes_from_the_record_for_a_monster_and_from_progression_for_the_player() -> None:
    state = armed(new_game("whispering_vault_5e"))
    goblin = state.world.entities[EntityId("goblin")]
    assert isinstance(goblin, ActorEntity)
    assert procedures.swing(state, goblin, "scimitar", RULES).to_hit == 4
    mine = procedures.swing(state, state.player, "a notched longsword", RULES)
    assert (mine.name, mine.to_hit, mine.damage) == ("a notched longsword", 2, "1d8")
    with pytest.raises(ValueError, match="no attack called"):
        procedures.swing(state, goblin, "Vorpal Sneeze", RULES)


def test_archery_fighting_style_modifies_a_ranged_weapon_attack() -> None:
    state = armed(new_game("whispering_vault_5e"))
    player = state.player
    progression = player.progression
    assert progression is not None
    held = tuple(
        ref("features", "fighter-fighting-style-archery")
        if feature.index == "fighter-fighting-style-defense"
        else feature
        for feature in progression.features
    )
    player = updated(player, progression=updated(progression, features=held))
    bow = ItemEntity(
        id=EntityId("bow"),
        name="a yew longbow",
        brief="A tall bow polished smooth by use.",
        known=True,
        ref=ref("weapons", "longbow"),
        container_id=PLAYER_ID,
    )
    world = state.world.replacing(player).adding(bow)
    attack = procedures.swing(updated(state, world=world), player, bow.name, RULES)
    assert attack.to_hit == 6


def test_a_hit_deals_the_weapon_s_damage_and_a_miss_deals_nothing() -> None:
    state = armed(new_game("whispering_vault_5e"))
    swung = Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))
    hit = resolve([swung], state, Random(0), RULES)
    assert [event.type for event in hit] == ["attack_rolled", "dice_rolled", "hp_changed"]
    assert hit[0].summary.endswith("13 -> 17 vs ac 10: HIT")
    miss = resolve([swung], state, Random(2), RULES)
    assert [event.type for event in miss] == ["attack_rolled"]
    assert miss[0].summary.endswith("2 -> 6 vs ac 10: MISS")
    with pytest.raises(ValueError, match="does not strike at themselves"):
        resolve([Attack(weapon="Scimitar")], state, Random(0), RULES)


def test_a_save_uses_the_record_s_bonus_or_the_player_s_proficiency() -> None:
    state = new_game("whispering_vault_5e")
    player = state.player
    assert player.progression is not None
    scores = player.stats.attributes
    assert rules.save_bonus(player, "constitution") == rules.modifier(scores, "constitution") + 2
    assert rules.save_bonus(player, "wisdom") == rules.modifier(scores, "wisdom")

    lich = RULES.archetype(ref("monsters", "lich"))
    assert lich is not None
    stats = lich.stats
    undead = updated(player, stats=stats, progression=None)
    assert rules.save_bonus(undead, "constitution") == 10
    assert rules.save_bonus(undead, "strength") == rules.modifier(stats.attributes, "strength")


def test_a_save_selects_its_branch_like_a_check_does() -> None:
    state = armed(new_game("whispering_vault_5e"))
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=EntityId("goblin"),
        on_failure=[Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))],
    )
    events = resolve([gas], state, Random(0), RULES)
    assert events[0].summary == "a goblin dexterity save: 13 -> 15 vs DC 25: FAILURE"
    assert [event.type for event in events[1:]] == [
        "attack_rolled",
        "dice_rolled",
        "hp_changed",
    ]


def test_a_save_on_someone_unseen_reveals_them_exactly_once() -> None:
    state = armed(new_game("whispering_vault_5e"))
    goblin = state.world.entities[EntityId("goblin")]
    hidden = {**state.world.entities, goblin.id: updated(goblin, known=False)}
    unseen = updated(state, world=updated(state.world, entities=hidden))
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=goblin.id,
        on_failure=[Damage(amount=1, target_id=goblin.id)],
    )
    events = resolve([gas], unseen, Random(0), RULES)
    assert [event.type for event in events] == ["entity_discovered", "dc_rolled", "hp_changed"]
