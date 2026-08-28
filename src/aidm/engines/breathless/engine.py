from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.content.model import CharacterProfile, CreatedCharacter
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
    Mechanics,
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
from aidm.engines.core import action, player_action, rule
from aidm.engines.packs import PackCreation, character_packs, pack_options
from aidm.engines.sheets import SheetEngine
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.creation import AnyStep, CreationStep, Picks, TextStep, check_picks, picked
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId, slug
from aidm.state.model import Game

RATED = (10, 8, 6)


class BreathlessCreation(PackCreation[Pack]):
    def steps_for(self, pack: Pack, picks: Picks) -> tuple[AnyStep, ...]:
        del picks
        return (
            *(
                CreationStep(
                    id=f"d{die}",
                    prompt=f"Choose the skill rated d{die}",
                    options=pack_options(pack.skills),
                )
                for die in RATED
            ),
            TextStep(id="job", prompt="The job they had before", hint=", ".join(pack.jobs[:3])),
            TextStep(id="pronouns", prompt="Their pronouns", hint="they/them"),
            TextStep(
                id="item",
                prompt="One item they brought, a d10 item",
                hint=", ".join(pack.weapons[:3]),
            ),
        )

    def create(self, name: str, brief: str, picks: Picks, rng: Random) -> CreatedCharacter:
        del rng
        check_picks(self.steps(picks), picks)
        chosen = picked(picks, "pack")[0]
        rated = {picked(picks, f"d{die}")[0]: die for die in RATED}
        if len(rated) != len(RATED):
            raise ValueError("the d10, d8 and d6 go to three different skills")
        skills: dict[str, JsonValue] = {
            skill: rated.get(skill.lower(), RULES.floor) for skill in SKILLS
        }
        item_name = picked(picks, "item")[0]
        item = Entity(
            id=EntityId(slug(item_name, ())),
            kind="item",
            name=item_name,
            brief=item_name,
            known=True,
            parent_id=PLAYER_ID,
            rules={"die": RULES.starting_item},
        )
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief, items=(item,)),
            rules={
                "packs": character_packs(chosen),
                "job": picked(picks, "job")[0],
                "pronouns": picked(picks, "pronouns")[0],
                "skills": skills,
            },
        )


class BreathlessEngine(SheetEngine[Sheet, ItemSheet]):
    id = EngineId("breathless")
    badge = ("BREATHLESS", "red-7")
    engine_dir = Path(__file__).parent
    sheet_type = Sheet
    item_type = ItemSheet
    mechanics_type = Mechanics
    pack_type = Pack
    decisions = (StakedCheck, Loot)
    authoring_instructions = (
        "BREATHLESS AUTHORING\n"
        "Actors may omit rules; describe threats through risks and complications. An actor with "
        "rules names the skills rated above d4 (Bash, Dash, Sneak, Shoot, Think, Sway). Every "
        "item is a die: give a usable one rules with its die (6 to 12) and leave set dressing "
        "without rules, which makes it a d10 item."
    )

    def __init__(self, sources: PackSources = SHIPPED_PACKS) -> None:
        super().__init__(sources)
        self.packs = sources.load(self.engine_dir / "packs", Pack)
        self.creation = BreathlessCreation(self.packs)
        self.director_commands = (
            action(
                "stake_check",
                "Show the player one check's `risk` and let them accept or revise it before "
                "rolling.",
                StakedCheck,
                resolve_stake,
            ),
            rule(
                "roll_check",
                "Roll an actor's risky check directly. For the player, use `stake_check` first "
                "unless they already accepted the exact `risk`.",
                Check,
                resolve_check,
            ),
            rule(
                "test_luck",
                "Let a die decide whether something happens.",
                LuckTest,
                resolve_luck_test,
            ),
            rule(
                "loot_check",
                "Roll the actor's loot die to scavenge, when the fiction allows it.",
                LootCheck,
                resolve_loot,
            ),
            action(
                "change_stress",
                "Add stress for a complication, or clear it for a secure rest.",
                ChangeStress,
                apply_change_stress,
            ),
            action(
                "use_med_kit",
                f"Spend the actor's med kit to clear {RULES.med_kit_clears} stress, when they say "
                "they use it.",
                Breathe,
                apply_use_med_kit,
            ),
        )
        self.player_actions = (
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
        )

    def pack_models(self) -> Mapping[str, Pack]:
        return self.packs

    def uses_item_sheet(self, entity: Entity) -> bool:
        # Every item is a die, so a rules-less one is a d10 item rather than no item.
        return entity.kind == "item"

    def validate(self, state: Game) -> None:
        super().validate(state)
        for actor_id in Mechanics.of_game(state).sheets:
            if (held := len(state.world.children(actor_id, "item"))) > RULES.carry:
                raise ValueError(
                    f"{actor_id!r} carries {held} items; the backpack holds {RULES.carry}"
                )

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        if entity.kind == "item" and not entity.rules:
            raise ValueError("an item found during play comes from `loot_check`, with its die")
        super().seed(draft, entity, rng)
