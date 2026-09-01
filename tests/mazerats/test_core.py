from pathlib import Path
from random import Random

import pytest

from aidm.core.entities import DEAD, PLAYER_ID, Counter, EngineId, EntityId, Trait
from aidm.core.io import load_character, read_scenario
from aidm.core.model import ScenarioMeta
from aidm.engines.core import load_packs
from aidm.engines.mazerats.creation import Pack
from aidm.engines.mazerats.engine import ENGINE_DIR, build, new_game, player_over
from aidm.engines.mazerats.rules import (
    Attack,
    CastSpell,
    DangerRoll,
    LevelUp,
    Reaction,
    Rest,
    Stow,
    attack,
    cast_spell,
    danger_roll,
    level_up,
    reaction,
    rest,
    stow,
)
from aidm.engines.mazerats.state import (
    XP_FOR_LEVEL,
    ActorSheet,
    CombatState,
    ItemSheet,
    MazeRatsCharacterFile,
    MazeRatsGame,
    MazeRatsScenarioFile,
    Side,
)
from aidm.kits.entities import Entity

PACKS = load_packs((ENGINE_DIR / "packs",), Pack)


class Dice(Random):
    """Scripted faces, taken in the order the procedures ask for them."""

    def __init__(self, *faces: int) -> None:
        super().__init__(0)
        self.faces = list(faces)

    def randint(self, a: int, b: int) -> int:
        return self.faces.pop(0)


def opened() -> MazeRatsGame:
    engine = build(Path("packs/mazerats"))
    scenario = read_scenario(Path("scenarios"), "blackglass-maze", {engine.id: engine.scenario})
    character = load_character(Path("characters"), "kael", engine.id, engine.character)
    assert isinstance(scenario, MazeRatsScenarioFile)
    assert isinstance(character, MazeRatsCharacterFile)
    game = MazeRatsGame(
        scenario_id="blackglass-maze",
        character_id="kael",
        scenario=ScenarioMeta(title="map", premise="map"),
        engine=EngineId("mazerats"),
        packs=("srd",),
        payload=new_game(scenario, character),
    )
    stats(game, PLAYER_ID).armour = 0
    stats(game, PLAYER_ID).attack_bonus = 0
    return game


def stats(game: MazeRatsGame, entity_id: EntityId) -> ActorSheet:
    found = game.payload.world.require(entity_id).sheet
    assert isinstance(found, ActorSheet)
    return found


def actor(game: MazeRatsGame, name: str, sheet: ActorSheet) -> EntityId:
    entity_id = EntityId(name)
    game.payload.world.cast[entity_id] = Entity(
        id=entity_id,
        kind="actor",
        name=name,
        brief=f"A {name}.",
        known=True,
        carried_by=game.payload.world.current.id,
        sheet=sheet,
    )
    return entity_id


def item(game: MazeRatsGame, name: str, holder: EntityId, sheet: ItemSheet) -> EntityId:
    entity_id = EntityId(name)
    game.payload.world.cast[entity_id] = Entity(
        id=entity_id,
        kind="item",
        name=name,
        brief=f"A {name}.",
        known=True,
        carried_by=holder,
        sheet=sheet,
    )
    return entity_id


def fighting(game: MazeRatsGame, *enemies: EntityId, acting: Side = "players") -> CombatState:
    combat = CombatState(
        player_side=(PLAYER_ID, *game.payload.world.companions),
        enemy_side=enemies,
        first_side="players",
        acting_side=acting,
    )
    game.payload.combat = combat
    return combat


def test_authored_map_starts_with_a_player_and_four_places() -> None:
    game = opened()

    assert game.payload.world.player_id == PLAYER_ID
    assert game.payload.world.current.id == "moon-gate"
    assert len([one for one in game.payload.world.cast.values() if one.kind == "place"]) == 4


def test_death_is_game_over() -> None:
    game = opened()
    game.payload.world.player.traits.append(Trait(id=DEAD, name="Dead"))

    assert player_over(game) == "You died."


def test_a_danger_roll_needs_ten_and_an_opposed_tie_goes_to_the_defender() -> None:
    game = opened()
    rival = actor(game, "moon-rat", ActorSheet())
    stats(game, PLAYER_ID).strength = 0

    (missed,) = danger_roll(
        game, DangerRoll(actor_id=PLAYER_ID, ability="strength", danger="the gate"), Dice(4, 5)
    )
    (avoided,) = danger_roll(
        game, DangerRoll(actor_id=PLAYER_ID, ability="strength", danger="the gate"), Dice(5, 5)
    )
    (opposed,) = danger_roll(
        game,
        DangerRoll(actor_id=PLAYER_ID, ability="strength", danger="the shove", opposed_by=rival),
        Dice(3, 4, 3, 4),
    )

    assert missed.card == "Danger strikes: 9 vs 10"
    assert avoided.card == "Danger avoided: 10 vs 10"
    assert opposed.card == "Danger strikes: 7 vs 7"


def test_advantage_rolls_three_dice_and_heavy_armour_refuses_it_on_dexterity() -> None:
    game = opened()
    _ = item(game, "plate", PLAYER_ID, ItemSheet(armour="heavy", position="worn"))

    (fact,) = danger_roll(
        game,
        DangerRoll(actor_id=PLAYER_ID, ability="will", danger="the whispers", advantage=True),
        Dice(1, 5, 6),
    )
    assert fact.dice[0].faces == (6, 6, 6)
    assert fact.dice[0].highlight == (1, 2)

    with pytest.raises(ValueError, match="heavy armour"):
        _ = danger_roll(
            game,
            DangerRoll(actor_id=PLAYER_ID, ability="dexterity", danger="the drop", advantage=True),
            Dice(1, 5, 6),
        )


def test_reaction_rolls_one_disposition_and_only_one() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet())

    (fact,) = reaction(game, Reaction(actor_id=rat), Dice(1))
    assert fact.card == "Reaction: hostile"
    with pytest.raises(ValueError, match="already has a disposition"):
        _ = reaction(game, Reaction(actor_id=rat), Dice(6))


def test_an_unarmed_hit_loses_one_damage() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))

    facts = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(6, 1, 6, 5))

    assert [one.kind for one in facts] == ["combat_started", "attack", "damage"]
    assert stats(game, rat).health.current == 6


def test_an_ambush_seizes_initiative_and_strikes_at_advantage() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))

    facts = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat, ambush=True), Dice(3, 3, 3))

    combat = game.payload.combat
    assert combat is not None
    assert (combat.ambusher, combat.first_side) == ("players", "players")
    assert facts[1].dice[0].faces == (6, 6, 6)


def test_losing_the_opening_initiative_refuses_the_swing_without_a_reroll() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))

    facts = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(2, 5))

    assert [one.kind for one in facts] == ["combat_started", "initiative_lost"]
    combat = game.payload.combat
    assert combat is not None
    assert combat.acting_side == "enemies"
    assert stats(game, rat).health.current == 10
    with pytest.raises(ValueError, match="turn of the enemies side"):
        _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice())


def test_a_ranged_weapon_is_refused_once_the_enemy_is_in_melee() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet())
    bow = item(game, "bow", PLAYER_ID, ItemSheet(weapon="ranged", position="hands"))
    _ = fighting(game, rat)

    with pytest.raises(ValueError, match="ranged weapon"):
        _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat, weapon_id=bow), Dice())


def test_each_character_acts_once_and_initiative_is_rerolled_after_a_round() -> None:
    game = opened()
    guide = actor(game, "torchbearer", ActorSheet())
    game.payload.world.companions.append(guide)
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))
    combat = fighting(game, rat)

    _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(2, 2))
    assert combat.acted == (PLAYER_ID,)
    with pytest.raises(ValueError, match="already taken their action"):
        _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(2, 2))

    _ = attack(game, Attack(actor_id=guide, target_id=rat), Dice(2, 2))
    assert (combat.acting_side, combat.round, combat.acted) == ("enemies", 1, ())

    facts = attack(game, Attack(actor_id=rat, target_id=PLAYER_ID), Dice(2, 2, 1, 6))
    assert facts[-1].kind == "round_started"
    assert (combat.round, combat.first_side, combat.acting_side) == (2, "enemies", "enemies")


def test_a_friendly_bystander_is_not_enlisted_and_does_not_block_the_round() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))
    bystander = actor(game, "lamplighter", ActorSheet())

    _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(6, 1, 2, 2))

    combat = game.payload.combat
    assert combat is not None
    assert (combat.player_side, combat.enemy_side) == ((PLAYER_ID,), (rat,))
    assert bystander not in (*combat.player_side, *combat.enemy_side)
    assert combat.acting_side == "enemies"

    facts = attack(game, Attack(actor_id=rat, target_id=PLAYER_ID), Dice(2, 2, 1, 6))
    assert facts[-1].kind == "round_started"
    assert combat.round == 2


def test_a_reinforcement_joins_the_side_opposite_its_opponent_and_acts_this_turn() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))
    brute = actor(game, "glass-brute", ActorSheet(health=Counter(current=10, maximum=10)))
    combat = fighting(game, rat, acting="enemies")

    _ = attack(game, Attack(actor_id=brute, target_id=PLAYER_ID), Dice(2, 2))

    assert combat.enemy_side == (rat, brute)
    assert combat.acted == (brute,)
    assert (combat.acting_side, combat.round) == ("enemies", 1)


def test_an_ambush_is_refused_once_the_fight_is_under_way() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet())
    _ = fighting(game, rat)

    with pytest.raises(ValueError, match="already under way"):
        _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat, ambush=True), Dice())


def test_stow_redraws_gear_and_refuses_an_illegal_layout() -> None:
    game = opened()
    sword, shield, bow = EntityId("short-sword"), EntityId("shield"), EntityId("bow")

    (fact,) = stow(game, Stow(actor_id=PLAYER_ID, item_id=sword, position="backpack"), Random(1))
    assert fact.card == "Short sword: backpack"

    with pytest.raises(ValueError, match="more than two hands"):
        _ = stow(game, Stow(actor_id=PLAYER_ID, item_id=bow, position="hands"), Random(1))
    with pytest.raises(ValueError, match="shield must be carried in the hands"):
        _ = stow(game, Stow(actor_id=PLAYER_ID, item_id=shield, position="belt"), Random(1))
    with pytest.raises(ValueError, match="not carried by"):
        _ = stow(
            game, Stow(actor_id=PLAYER_ID, item_id=EntityId("pry-bar"), position="belt"), Random(1)
        )


def test_a_weapon_must_be_drawn_from_the_pack_before_it_can_be_attacked_with() -> None:
    game = opened()
    world = game.payload.world
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=10, maximum=10)))
    pry = item(game, "pry", PLAYER_ID, ItemSheet(weapon="heavy", position="backpack"))
    _ = fighting(game, rat)

    with pytest.raises(ValueError, match="held in the attacker's hands"):
        _ = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat, weapon_id=pry), Dice())

    world.require(EntityId("shield")).carried_by = world.current.id
    _ = stow(
        game,
        Stow(actor_id=PLAYER_ID, item_id=EntityId("short-sword"), position="backpack"),
        Random(1),
    )
    (fact,) = stow(game, Stow(actor_id=PLAYER_ID, item_id=pry, position="hands"), Random(1))
    assert fact.card == "pry: hands"

    facts = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat, weapon_id=pry), Dice(6, 5))
    assert [one.kind for one in facts] == ["attack", "damage"]
    assert stats(game, rat).health.current == 4


def test_the_shield_decision_belongs_to_the_player() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(attack_bonus=4))
    _ = item(game, "buckler", PLAYER_ID, ItemSheet(shield=True, position="hands"))
    _ = fighting(game, rat, acting="enemies")

    _ = attack(game, Attack(actor_id=rat, target_id=PLAYER_ID), Dice(6, 5))

    assert game.payload.pending_attack is not None
    assert game.pending is not None
    assert game.pending.kind == "shield"
    assert {one.id for one in game.pending.options} == {"shatter-shield", "take-hit"}


def test_an_npc_spends_its_shield_only_to_survive() -> None:
    survivor = opened()
    rat = actor(survivor, "moon-rat", ActorSheet(health=Counter(current=9, maximum=9)))
    _ = item(survivor, "rat-shield", rat, ItemSheet(shield=True, position="hands"))
    _ = fighting(survivor, rat)
    _ = attack(survivor, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(6, 5))

    assert survivor.pending is None
    assert stats(survivor, rat).health.current == 6

    doomed = opened()
    rat = actor(doomed, "moon-rat", ActorSheet(health=Counter(current=3, maximum=3)))
    shield = item(doomed, "rat-shield", rat, ItemSheet(shield=True, position="hands"))
    _ = fighting(doomed, rat)
    facts = attack(doomed, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(6, 5))

    assert facts[-1].kind == "shield_shattered"
    assert stats(doomed, rat).health.current == 3
    assert doomed.payload.world.require(shield).sheet == ItemSheet(shield=False, position="hands")


def test_a_kill_ends_combat_and_a_night_of_rest_heals_one_and_refills_spells() -> None:
    game = opened()
    rat = actor(game, "moon-rat", ActorSheet(health=Counter(current=1, maximum=1)))
    player = stats(game, PLAYER_ID)
    player.health.current = 1
    player.spell_slots = (None,)

    facts = attack(game, Attack(actor_id=PLAYER_ID, target_id=rat), Dice(6, 1, 6, 5))
    assert facts[-1].kind == "combat_ended"
    assert game.payload.combat is None

    _ = rest(game, Rest(actor_id=PLAYER_ID, kind="night"), Random(1), PACKS)
    assert player.health.current == 2
    assert player.spell_slots[0] is not None


def test_medicine_heals_one_and_only_once_a_day() -> None:
    game = opened()
    player = stats(game, PLAYER_ID)
    player.health.maximum = 6
    player.health.current = 1
    first = item(game, "medicine", PLAYER_ID, ItemSheet(medicine=True))
    second = item(game, "more-medicine", PLAYER_ID, ItemSheet(medicine=True))

    _ = rest(game, Rest(actor_id=PLAYER_ID, medicine_id=first), Random(1), PACKS)
    assert player.health.current == 3
    assert first not in game.payload.world.cast

    with pytest.raises(ValueError, match="already taken a dose"):
        _ = rest(game, Rest(actor_id=PLAYER_ID, medicine_id=second), Random(1), PACKS)


def test_cast_spell_consumes_the_selected_slot() -> None:
    game = opened()
    stats(game, PLAYER_ID).spell_slots = ("Glass Light", None)

    (fact,) = cast_spell(
        game, CastSpell(actor_id=PLAYER_ID, slot=0, effect="reveals a hidden way"), Random(1)
    )

    assert fact.kind == "spell_cast"
    assert stats(game, PLAYER_ID).spell_slots == (None, None)


def test_every_level_adds_two_maximum_health_and_a_choice_including_level_seven() -> None:
    game = opened()
    player = stats(game, PLAYER_ID)

    for level in range(2, 8):
        player.xp = XP_FOR_LEVEL[level - 2] - 1
        facts = level_up(game, LevelUp(actor_id=PLAYER_ID, amount=1), Random(1))
        assert [one.kind for one in facts] == ["xp_awarded", "level_up"]
        assert player.level == level
        assert player.health.maximum == 2 + 2 * level
        assert player.health.current == 4
        assert game.pending is not None
        choice = game.pending.options[0].id
        assert choice == ("strength" if level % 2 == 0 else "attack-bonus")
        _ = level_up(game, LevelUp(actor_id=PLAYER_ID, choice=choice), Random(1))
        assert game.payload.pending_level_up is None

    assert player.level == 7
    assert player.attack_bonus == 3


def test_maze_rats_exposes_the_exact_world_and_mechanics_tools() -> None:
    engine = build(Path("packs/mazerats"))

    assert [tool.name for tool in engine.world_tools] == ["change_world", "move", "unlock_way"]
    assert [tool.name for tool in engine.tools] == [
        "danger_roll",
        "reaction",
        "attack",
        "stow",
        "cast_spell",
        "rest",
        "level_up",
    ]


def test_maze_validation_requires_selected_installed_packs() -> None:
    engine = build(Path("packs/mazerats"))
    game = opened()

    engine.validate(game)
    game.packs = ()
    with pytest.raises(ValueError, match="at least one selected"):
        engine.validate(game)
    game.packs = ("missing",)
    with pytest.raises(ValueError, match="not installed"):
        engine.validate(game)
