from collections.abc import Mapping
from pathlib import Path

from pydantic import JsonValue

from aidm.content.io import engine_text
from aidm.content.model import Character, CharacterProfile
from aidm.engines.breathless.rules import (
    RULES,
    SKILLS,
    Breathe,
    ChangeStress,
    Check,
    ItemSheet,
    Loot,
    LootCheck,
    LuckTest,
    Pack,
    Sheet,
    StakedCheck,
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
    EntityRules,
    NoRules,
    PackCreation,
    describe_by,
    director_tool,
    load_packs,
    player_action,
)
from aidm.engines.world import CORE_TOOLS
from aidm.state.creation import CreationStep, Picks, check_picks, picked
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, Kind, slug
from aidm.state.model import Game

ENGINE_DIR = Path(__file__).parent
RATED = (10, 8, 6)
# Every item is a die, so a rules-less one is a d10 item rather than no item.
RULES_TYPES: Mapping[Kind, type[EntityRules]] = {
    "actor": Sheet,
    "item": ItemSheet,
    "location": NoRules,
}


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
            rules={"die": RULES.starting_item},
        )
        return Character(
            id=slug(name, ()),
            profile=CharacterProfile(name=name, brief=brief, items=(item,)),
            rules={
                "job": picked(picks, "job"),
                "pronouns": picked(picks, "pronouns"),
                "skills": skills,
            },
        )


def _checks(state: Game) -> None:
    # The played character rolls their own skills, so a successor without rules cannot play.
    if not state.player.rules:
        raise ValueError(f"{state.player.name} has no character sheet")
    for actor in state.world.of_kind("actor"):
        held = len(state.world.children(actor.id, "item"))
        if actor.rules and held > RULES.carry:
            raise ValueError(f"{actor.id!r} carries {held} items; the backpack holds {RULES.carry}")


def build(user_packs: Path) -> Engine:
    packs = load_packs((ENGINE_DIR / "packs", user_packs), Pack)
    return Engine(
        id=EngineId("breathless"),
        badge=("BREATHLESS", "red-7"),
        director_instructions=engine_text(ENGINE_DIR / "director.md"),
        rules_types=RULES_TYPES,
        packs=packs,
        creation=BreathlessCreation(packs),
        checks=_checks,
        describe=describe_by(RULES_TYPES),
        decisions=(StakedCheck, Loot),
        authoring_instructions=(
            "BREATHLESS AUTHORING\n"
            "Actors may omit rules; describe threats through risks and complications. An actor "
            "with rules names the skills rated above d4 (Bash, Dash, Sneak, Shoot, Think, Sway). "
            "Every item is a die: give a usable one rules with its die (6 to 12) and leave set "
            "dressing without rules, which makes it a d10 item."
        ),
        director_tools=(
            # Every item is a die a loot check hands out, so nothing here is improvised.
            *(one for one in CORE_TOOLS if one.name != "gain_improvised_item"),
            director_tool(
                "stake_check",
                "Show the player one check's `risk` and let them accept or revise it before "
                "rolling.",
                StakedCheck,
                lambda draft, one, _rng: resolve_stake(draft, one),
            ),
            director_tool(
                "roll_check",
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
