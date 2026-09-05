import json
from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import PendingDecision
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.core.views import Panel, PanelRow, Rows, Sections, lines_of
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID, Person, sentence
from aidm.engines.breathless.tools import (
    ChangeStress,
    ChangeWorld,
    Check,
    DropItem,
    LootCheck,
    TestLuck,
    WorldChange,
    outcome,
)
from aidm.engines.breathless.world import (
    LADDER,
    LOOT_START,
    MED_KIT_CLEARS,
    SKILLS,
    STARTING_DICE,
    STARTING_ITEM,
    STUNT_DIE,
    BreathlessCharacter,
    BreathlessGame,
    BreathlessScenario,
    BreathlessWorld,
    Die,
    Item,
    Skill,
    Survivor,
    stepped,
)
from aidm.engines.breathless.worldsmith import AUTHORING, Pack
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, NextScene


class BreathlessEngine(SceneEngine[Person, Survivor, BreathlessGame, Pack]):
    id = EngineId("breathless")
    title = "BREATHLESS"
    art_style = (
        "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or lettering."
    )
    directory = Path(__file__).parent
    game = BreathlessGame
    scenario = BreathlessScenario
    character = BreathlessCharacter
    cast = Person
    pack = Pack
    world_type = BreathlessWorld

    def master_tools(self) -> tuple[MasterTool[BreathlessGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "check",
                "Roll a check for an action with a real cost, on a skill, a carried item, or a "
                "stunt.",
                Check,
                self.check,
            ),
            master_tool(
                "catch_breath",
                "Let the player catch their breath: skills, loot die and the stunt reset, at the "
                "cost of a new complication.",
                NoArgs,
                self.catch_breath,
            ),
            master_tool(
                "change_stress",
                "A complication costs the player stress; laying low somewhere secure clears an "
                "amount at your discretion. Never a stand-in for `use_med_kit`.",
                ChangeStress,
                self.change_stress,
            ),
            master_tool(
                "use_med_kit",
                "Spend the player's med kit to clear 2 stress.",
                NoArgs,
                self.use_med_kit,
            ),
            master_tool(
                "loot_check",
                "Scavenge for an item. Leave `granted` and `choice` null; the engine fills them "
                "once the player answers.",
                LootCheck,
                self.loot_check,
            ),
            master_tool(
                "test_luck",
                "Roll a die to answer a question about the world where nobody is acting.",
                TestLuck,
                self.test_luck,
            ),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = self.pack_step()
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        d10 = picked(picks, "skill-d10")
        d8 = picked(picks, "skill-d8")
        return (
            first,
            CreationStep(id="pronouns", prompt="Pronouns"),
            CreationStep(id="job", prompt="Job", hint=", ".join(pack.jobs[:3])),
            CreationStep(id="skill-d10", prompt="Skill at d10", options=pack.skills),
            CreationStep(id="skill-d8", prompt="Skill at d8", options=other_than(pack.skills, d10)),
            CreationStep(
                id="skill-d6",
                prompt="Skill at d6",
                options=other_than(other_than(pack.skills, d10), d8),
            ),
            CreationStep(id="item", prompt="Your one item", hint=", ".join(pack.weapons[:3])),
        )

    def create_character(self, name: str, brief: str, picks: Picks) -> BreathlessCharacter:
        check_picks(self.creation_steps(picks), picks)
        skills: dict[Skill, Die] = dict.fromkeys(SKILLS, 4)
        skills.update({_skill(picked(picks, f"skill-d{die}")): die for die in STARTING_DICE})
        item = picked(picks, "item")
        sheet = Survivor(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            pronouns=picked(picks, "pronouns"),
            job=picked(picks, "job"),
            skills=skills,
            worn=dict(skills),
            items={EntityId(slug(item, ())): Item(name=item, die=STARTING_ITEM)},
        )
        return BreathlessCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Backpack", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, picks: Sequence[Slug]) -> str:
        selected = {
            pack_id: self.packs[pack_id].model_dump(
                mode="json", include={"locations", "complications", "missions"}
            )
            for pack_id in picks
        }
        return f"{AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"

    def sheet_sections(self, state: BreathlessGame) -> Sections:
        player = state.payload.player
        lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in player.items.items()]
        if player.med_kit:
            lines.append("- med kit")
        return (("BACKPACK", lines_of(lines)),)

    def panels(self, state: BreathlessGame) -> tuple[Panel, ...]:
        player = state.payload.player
        rows = [PanelRow(label=item.name, detail=f"d{item.die}") for item in player.items.values()]
        if player.med_kit:
            rows.append(PanelRow(label="Med kit", detail="held"))
        return (Panel(title="Backpack", rows=tuple(rows)),)

    def complications(self) -> tuple[str, ...]:
        """Always the SRD's own table: no other pack publishes one."""
        return self.srd_pack().complications

    def apply_change(self, world: BreathlessWorld, change: WorldChange) -> list[Fact]:
        match change:
            case DropItem():
                return world.player.drop_item(change.item_id)
            case _:
                return self.shared_change(world, change)

    def change_world(self, draft: BreathlessGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def check(self, draft: BreathlessGame, args: Check, rng: Random) -> list[Fact]:
        player = draft.payload.player

        item: Item | None = None
        if args.skill is not None:
            die = player.worn[args.skill]
            label = args.skill
        elif args.item_id is not None:
            item = player.require_item(args.item_id)
            die = item.die
            label = item.name
        else:
            if player.stunted:
                raise Refusal("the stunt is spent until the player catches their breath")
            die = STUNT_DIE
            label = "stunt"
            player.stunted = True

        rolled, dice_fact = roll((die,), f"{args.what} — {label}", rng)
        face = rolled[0]
        result = outcome(face)
        worn = stepped(die)

        if args.skill is not None:
            player.worn[args.skill] = worn
        elif item is not None and args.item_id is not None:
            # SRD: "When reduced to a d4, the item either breaks, gets lost, or fades away".
            if worn == 4:
                del player.items[args.item_id]
            else:
                item.die = worn

        trace = f"{args.what} — {label} d{die} [{face}] -> {result}"
        card = f"{args.what} — {sentence(label)} d{die} → {result}"
        event = DiceEvent(label=f"d{die}", faces=(die,), rolled=rolled)
        facts = [dice_fact, player.fact("checked", trace, card=card, dice=(event,))]
        if item is not None and worn == 4:
            gone = f"{item.name} is gone"
            facts.append(player.fact("item_gone", gone, card=gone))

        if args.dangerous and result == "fail" and player.vulnerable:
            draft.note(
                "The player is vulnerable and this dangerous check failed: rule whether they are "
                "taken out of the scene or dead. Death is `change_world` `kill` on the player."
            )
        return facts

    def catch_breath(self, draft: BreathlessGame, _args: NoArgs, rng: Random) -> list[Fact]:
        player = draft.payload.player
        player.worn = dict(player.skills)
        player.loot = LOOT_START
        player.stunted = False

        rolled, dice_fact = roll((12,), "a new complication", rng)
        text = self.complications()[rolled[0] - 1]
        draft.note(
            f"Catching breath brings a new complication. The SRD's table suggests: {text} Bring it "
            "in through the story, or one that fits better."
        )
        trace = f"{player.label} catches their breath: skills and loot die restored"
        fact = player.fact(
            "breath_caught", trace, card="Caught breath — skills and loot die restored"
        )
        return [dice_fact, fact]

    def change_stress(self, draft: BreathlessGame, args: ChangeStress, _rng: Random) -> list[Fact]:
        if args.amount == 0:
            raise Refusal("change_stress needs a non-zero amount")
        player = draft.payload.player
        return player.stress.change(player, args.amount, "Stress", args.why)

    def use_med_kit(self, draft: BreathlessGame, _args: NoArgs, _rng: Random) -> list[Fact]:
        player = draft.payload.player
        if not player.med_kit:
            raise Refusal("the player holds no med kit")
        player.med_kit = False
        facts = player.stress.change(player, -MED_KIT_CLEARS, "Stress", "the med kit")
        used = f"{player.name} uses the med kit"
        facts.append(player.fact("med_kit_used", used, card="Med kit used"))
        return facts

    def loot_check(self, draft: BreathlessGame, args: LootCheck, rng: Random) -> list[Fact]:
        player = draft.payload.player
        if args.granted is None or args.choice is None:
            return self.roll_loot(draft, args.item, rng)
        return [player.take_loot(args.item, args.granted, args.choice)]

    def roll_loot(self, draft: BreathlessGame, item: str, rng: Random) -> list[Fact]:
        player = draft.payload.player
        before = player.loot
        rolled, dice_fact = roll((before,), f"scavenging — {item}", rng)
        face = rolled[0]
        player.loot = stepped(before)

        found: Die | None = None
        if face <= 2:
            draft.note("The scavenge turns up trouble right here; nothing is found.")
        elif face <= 4:
            draft.note("The scavenge finds nothing, and trouble is coming.")
        else:
            found = next(die for die in LADDER if face <= die)

        result = f"found {item} (d{found})" if found is not None else "nothing"
        trace = f"scavenging — loot d{before} [{face}] -> {found or 'nothing'}"
        card = f"Scavenge — d{before} → {result}"
        event = DiceEvent(label=f"d{before}", faces=(before,), rolled=rolled)
        fact = player.fact("loot_checked", trace, card=card, dice=(event,))
        facts = [dice_fact, fact]

        if found is not None:
            draft.pending = PendingDecision(
                kind="loot",
                prompt=f"You found {item} (d{found}). Take it?",
                options=player.loot_options(item, found),
                allows_text=False,
            )
        return facts

    def test_luck(self, _draft: BreathlessGame, args: TestLuck, rng: Random) -> list[Fact]:
        rolled, dice_fact = roll((args.die,), args.question, rng)
        result = outcome(rolled[0])
        trace = f"{args.question} — d{args.die} [{rolled[0]}] -> {result}"
        return [dice_fact, Fact(kind="luck_tested", trace=trace)]


def _skill(name: str) -> Skill:
    """`check_picks` has already held the answer to the pack's six ids, which are the SRD's."""
    return next(skill for skill in SKILLS if skill == name)
