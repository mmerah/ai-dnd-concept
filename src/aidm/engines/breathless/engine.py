from collections.abc import Mapping
from functools import partial
from pathlib import Path

from pydantic import JsonValue

from aidm.content.io import engine_text
from aidm.content.model import Character
from aidm.engines.breathless.rules import (
    LOOT_ITEM,
    LOOT_MED_KIT,
    ROLL_CHECK,
    RULES,
    SKILLS,
    Breathe,
    BreathlessState,
    ChangeStress,
    Check,
    ItemSheet,
    LootCheck,
    LuckTest,
    Pack,
    Sheet,
    apply_catch_breath,
    apply_change_stress,
    apply_use_med_kit,
    breathers,
    med_kit_holders,
    resolve_check,
    resolve_loot,
    resolve_luck_test,
    resolve_stake,
)
from aidm.engines.core import (
    Engine,
    EntityRenderer,
    Mechanics,
    PackCreation,
    authoring_guidance,
    check_packs,
    describe_rows,
    load_packs,
    mechanics_merged,
    mechanics_of,
    player_action,
    sheet_of,
)
from aidm.state.creation import CreationStep, Picks, check_picks, picked
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, slug
from aidm.state.model import Game
from aidm.state.threads import ADVANCE_THREAD
from aidm.state.tools import director_tool
from aidm.world.authoring import rooms_brief, rooms_growth_due
from aidm.world.scene import rooms_scene
from aidm.world.succession import TAKE_OVER, player_over
from aidm.world.tools import (
    ADD_TRAIT,
    DIRECTOR_WORLD,
    JOIN_PARTY,
    LEAVE_PARTY,
    MOVE,
    REMOVE_TRAIT,
    REVEAL,
    UNLOCK_EXIT,
    kill_tool,
)
from aidm.world.topology import children, validate_rooms

ENGINE_DIR = Path(__file__).parent
RATED = (10, 8, 6)


class BreathlessCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[CreationStep, ...]:
        rated: list[CreationStep] = []
        used: set[str] = set()
        for die in RATED:
            left = tuple(skill for skill in pack.skills if skill.id not in used)
            rated.append(
                CreationStep(id=f"d{die}", prompt=f"Choose the skill rated d{die}", options=left)
            )
            used.add(picked(picks, f"d{die}"))
        return (
            *rated,
            CreationStep(id="job", prompt="The job they had before", hint=", ".join(pack.jobs[:3])),
            CreationStep(id="pronouns", prompt="Their pronouns", hint="they/them"),
            CreationStep(
                id="item",
                prompt="One item they brought, a d10 item",
                hint=", ".join(pack.weapons[:3]),
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> Character:
        check_picks(self.steps(picks), picks)
        rated = {picked(picks, f"d{die}"): die for die in RATED}
        skills: dict[str, JsonValue] = {
            skill: rated.get(skill.lower(), RULES.floor) for skill in SKILLS
        }
        item_name = picked(picks, "item")
        item = Entity(
            id=EntityId(slug(item_name, ())),
            kind="item",
            name=item_name,
            brief=item_name,
            known=True,
            parent_id=PLAYER_ID,
        )
        sheet = Sheet.model_validate(
            {"job": picked(picks, "job"), "pronouns": picked(picks, "pronouns"), "skills": skills}
        )
        return Character(
            id=slug(name, ()),
            engine=EngineId("breathless"),
            name=name,
            brief=brief,
            items=(item,),
            mechanics=BreathlessState(
                sheets={PLAYER_ID: sheet}, items={item.id: ItemSheet(die=RULES.starting_item)}
            ).model_dump(mode="json"),
        )


def _validate(packs: Mapping[str, Pack], state: Game) -> None:
    check_packs(packs, state)
    validate_rooms(state.world)
    game = mechanics_of(state.world, BreathlessState)
    if stray := sorted(set(game.sheets) - set(state.world.entities)):
        raise ValueError(f"mechanics.sheets names entities the world does not hold: {stray}")
    items = {item.id for item in state.world.of_kind("item")}
    if stray := sorted(set(game.items) - items):
        raise ValueError(f"mechanics.items names entities that are not items: {stray}")
    # An item is its die: one the scenario rated none cannot be rolled, so it is not an item.
    if unrated := sorted(items - set(game.items)):
        raise ValueError(f"mechanics.items names no die for: {unrated}")
    # The played character rolls their own skills, so a successor without a sheet cannot play.
    if state.player_id not in game.sheets:
        raise ValueError(f"{state.player.name} has no character sheet")
    for actor in state.world.of_kind("actor"):
        held = len(children(state.world, actor.id, "item"))
        if actor.id in game.sheets and held > RULES.carry:
            raise ValueError(f"{actor.id!r} carries {held} items; the backpack holds {RULES.carry}")


def describer(state: Game) -> EntityRenderer:
    game = mechanics_of(state.world, BreathlessState)

    def describe(entity: Entity) -> str:
        sheet = game.sheets.get(entity.id) or game.items.get(entity.id)
        return describe_rows(sheet.rows(), ()) if sheet is not None else ""

    return describe


def sheet_rows(state: Game) -> tuple[tuple[str, str], ...]:
    return sheet_of(mechanics_of(state.world, BreathlessState).sheets, state.player).rows()


_AUTHORING = (
    "BREATHLESS AUTHORING\n"
    "Actors may omit a sheet; describe threats through risks and complications. An actor "
    "with a sheet goes under `mechanics.sheets` keyed by its entity id, naming the skills "
    "rated above d4 (Bash, Dash, Sneak, Shoot, Think, Sway). Every item is a die: each "
    "one needs `mechanics.items` keyed by its entity id, with its die (6 to 12). Scenery "
    "is not an item; put it in the location description."
)


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    validate = partial(_validate, packs)
    return Engine(
        id=EngineId("breathless"),
        title="BREATHLESS",
        instructions=f"{DIRECTOR_WORLD}\n\n{engine_text(ENGINE_DIR / 'director.md')}",
        packs=packs,
        creation=BreathlessCreation(packs),
        validate=validate,
        sheet_rows=sheet_rows,
        mechanics_merge=partial(mechanics_merged, BreathlessState),
        mechanics_without=_without,
        over=player_over,
        scene=rooms_scene(describer, lambda state: ()),
        resolvers=(TAKE_OVER, LOOT_ITEM, LOOT_MED_KIT),
        authoring_brief=lambda chosen, base, opening: rooms_brief(
            base, opening, authoring_guidance(_AUTHORING, packs, chosen)
        ),
        growth_due=rooms_growth_due,
        tools=(
            # Every item is a die a loot check hands out, so nothing here is improvised.
            REVEAL,
            MOVE,
            ADD_TRAIT,
            REMOVE_TRAIT,
            kill_tool(validate),
            UNLOCK_EXIT,
            JOIN_PARTY,
            LEAVE_PARTY,
            ADVANCE_THREAD,
            director_tool(
                "stake_check",
                "Show the player one check's `risk` and let them accept or revise it before "
                "rolling.",
                Check,
                lambda draft, one, _rng: resolve_stake(draft, one),
            ),
            director_tool(
                ROLL_CHECK,
                "Roll an actor's risky check directly. For the player, use `stake_check` first "
                "unless they already accepted the exact `risk`.",
                Check,
                resolve_check,
            ),
            director_tool(
                "test_luck",
                "Let a die decide whether something happens.",
                LuckTest,
                resolve_luck_test,
            ),
            director_tool(
                "loot_check",
                "Roll the actor's loot die to scavenge, when the fiction allows it.",
                LootCheck,
                resolve_loot,
            ),
            director_tool(
                "change_stress",
                "Add stress for a complication, or clear it for a secure rest.",
                ChangeStress,
                lambda draft, one, _rng: apply_change_stress(draft, one),
            ),
            director_tool(
                "use_med_kit",
                f"Spend the actor's med kit to clear {RULES.med_kit_clears} stress, when they say "
                "they use it.",
                Breathe,
                lambda draft, one, _rng: apply_use_med_kit(draft, one),
            ),
        ),
        player_actions=(
            player_action(
                "catch_breath",
                "Reset skills, loot die and stunt; the group faces a new complication.",
                Breathe,
                apply_catch_breath,
                breathers,
            ),
            player_action(
                "use_med_kit",
                f"Use the carried med kit to clear {RULES.med_kit_clears} stress.",
                Breathe,
                apply_use_med_kit,
                med_kit_holders,
            ),
        ),
    )


def _without(blob: Mechanics, entity_id: EntityId) -> Mechanics:
    game = BreathlessState.model_validate(blob)
    _ = game.sheets.pop(entity_id, None)
    _ = game.items.pop(entity_id, None)
    return game.model_dump(mode="json")
