import json
from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, parse, slug
from aidm.core.facts import DiceEvent, Fact, keep_highest, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import PendingDecision, PendingOption
from aidm.core.prompt import lines_of
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import DiceLook, Pairs, Panel, PanelRow
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID
from aidm.engines.breathless.tools import (
    Actor,
    ChangeStress,
    ChangeWorld,
    Check,
    DropItem,
    LootCheck,
    TakeLoot,
    TestLuck,
    UseMedKit,
    outcome,
)
from aidm.engines.breathless.world import (
    LADDER,
    LOOT_START,
    SKILLS,
    STARTING_DICE,
    STARTING_ITEM,
    STUNT_DIE,
    TAKE_LOOT,
    BreathlessCharacter,
    BreathlessGame,
    BreathlessScenario,
    BreathlessWorld,
    Die,
    Item,
    Skill,
    Survivor,
    SurvivorSheet,
    stepped,
)
from aidm.engines.breathless.worldsmith import AUTHORING, HIRING, Pack, SheetDraft
from aidm.engines.hiring import HIRE_TOOL, Hire, Hiring
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, NextScene
from aidm.engines.scenes.world import sentence


class BreathlessEngine(
    Hiring[Survivor, Survivor, BreathlessGame, SheetDraft],
    SceneEngine[Survivor, Survivor, BreathlessGame, Pack],
):
    id = EngineId("breathless")
    title = "BREATHLESS"
    art_style = (
        "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or lettering."
    )
    dice_look = DiceLook(body="#5a1216", ink="#efe1d3", glow="#e0393e")
    palette = {
        "game-bg": "#0d1818",
        "game-surface": "#162525",
        "game-surface-raised": "#203332",
        "game-text": "#e0eeea",
        "game-muted": "#a8c1bb",
        "game-border": "#35504b",
        "game-accent": "#94d5be",
        "game-wash": "rgba(148, 213, 190, .07)",
        "game-radius": "5px",
        "game-heading": "'Arial Narrow', 'Helvetica Neue', Arial, sans-serif",
    }
    directory = Path(__file__).parent
    game = BreathlessGame
    scenario = BreathlessScenario
    character = BreathlessCharacter
    cast = Survivor
    pack = Pack
    world_type = BreathlessWorld
    hire_answer = SheetDraft

    def master_tools(self) -> tuple[MasterTool[BreathlessGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "roll",
                "Call this for an action with a real cost. Roll one thing: a skill, a carried "
                "item, or a stunt. The engine rolls, reads the result, and wears the die down.",
                Check,
                self.roll,
            ),
            master_tool(
                "catch_breath",
                "Call this after a lull in the danger. The engine resets the actor's skills, "
                "loot die and stunt, and brings a new complication.",
                Actor,
                self.catch_breath,
            ),
            master_tool(
                "loot_check",
                "Call this to scavenge for an item. The engine rolls the loot die and asks the "
                "player what to do with a find.",
                LootCheck,
                self.loot_check,
            ),
            master_tool(
                "test_luck",
                "Call this to ask about the world when nobody acts. The engine rolls the die "
                "you pick and reads it.",
                TestLuck,
                self.test_luck,
            ),
            master_tool("hire", HIRE_TOOL, Hire, self.hire),
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
        player = Survivor(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            sheet=SurvivorSheet(
                pronouns=picked(picks, "pronouns"),
                job=picked(picks, "job"),
                skills=skills,
                worn=dict(skills),
                items={EntityId(slug(item, ())): Item(name=item, die=STARTING_ITEM)},
            ),
        )
        return BreathlessCharacter(id=slug(name, ()), engine=self.id, payload=player)

    def preview_character(self, character: AnyCharacter) -> Pairs:
        sheet = self.player_of(character).dice()
        return (*sheet.rows(), ("Backpack", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, picks: Sequence[Slug]) -> str:
        selected = {
            pack_id: self.packs[pack_id].model_dump(
                mode="json", include={"locations", "complications", "missions"}
            )
            for pack_id in picks
        }
        return f"{AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"

    def sheet_sections(self, state: BreathlessGame) -> Pairs:
        sheet = state.payload.player.dice()
        lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in sheet.items.items()]
        if sheet.med_kit:
            lines.append("- med kit")
        return (("BACKPACK", lines_of(lines)),)

    def panels(self, state: BreathlessGame) -> tuple[Panel, ...]:
        sheet = state.payload.player.dice()
        rows = [PanelRow(label=item.name, detail=f"d{item.die}") for item in sheet.items.values()]
        if sheet.med_kit:
            rows.append(PanelRow(label="Med kit", detail="held"))
        return (Panel(title="Backpack", rows=tuple(rows)),)

    def complications(self) -> tuple[str, ...]:
        """Always the SRD's own table: no other pack publishes one."""
        return self.srd_pack().complications

    def change_world(self, draft: BreathlessGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        world, change = draft.payload, args.change
        match change:
            case DropItem():
                return world.require_actor(change.actor_id).drop_item(change.item_id)
            case ChangeStress():
                return world.require_actor(change.actor_id).change_stress(change.amount, change.why)
            case UseMedKit():
                return world.require_actor(change.actor_id).use_med_kit()
            case _:
                return self.shared_change(world, change)

    def hireable(self, draft: BreathlessGame, entity_id: EntityId) -> Survivor:
        return draft.payload.require_hireable(entity_id)

    def hire_prompt(self, draft: BreathlessGame, member: Survivor, terms: str) -> str:
        pack = self.packs[draft.packs[0]]
        return self.render_request(
            draft,
            guidance=AUTHORING,
            intent=HIRING.format(
                name=member.name,
                brief=member.brief,
                terms=terms,
                jobs=", ".join(pack.jobs),
                weapons=", ".join(pack.weapons),
            ),
            answer=SheetDraft,
        )

    def install_sheet(self, draft: BreathlessGame, member: Survivor, answer: SheetDraft) -> str:
        member.sheet = SurvivorSheet(
            pronouns=answer.pronouns,
            job=answer.job,
            skills=dict(answer.skills),
            worn=dict(answer.skills),
            items={EntityId(slug(answer.item, ())): Item(name=answer.item, die=STARTING_ITEM)},
        )
        return answer.job

    def roll(self, draft: BreathlessGame, args: Check, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_actor(args.actor_id)
        sheet = actor.dice()

        item: Item | None = None
        helper: tuple[Survivor, Die] | None = None
        if args.skill is not None:
            die = sheet.worn[args.skill]
            label = args.skill
            if args.helped_by is not None:
                partner = world.require_actor(args.helped_by)
                if partner is actor:
                    raise Refusal(f"{actor.name} cannot help their own roll")
                helper = (partner, partner.dice().worn[args.skill])
        elif args.item_id is not None:
            item = actor.require_item(args.item_id)
            die = item.die
            label = item.name
        else:
            if sheet.stunted:
                raise Refusal(f"the stunt is spent until {actor.name} catches their breath")
            die = STUNT_DIE
            label = "stunt"
            sheet.stunted = True

        reason = f"{args.what} — {label}"
        if helper is None:
            rolled, dice_fact = roll((die,), reason, rng)
            face = rolled[0]
            event = DiceEvent(label=f"d{die}", faces=(die,), rolled=rolled)
        else:
            face, event, dice_fact = keep_highest(
                (die, helper[1]), reason, rng, label=f"d{die}+d{helper[1]}"
            )

        result = outcome(face)
        worn = stepped(die)

        if args.skill is not None:
            sheet.worn[args.skill] = worn
            if helper is not None:
                helper[0].dice().worn[args.skill] = stepped(helper[1])
        elif item is not None and args.item_id is not None:
            # SRD: "When reduced to a d4, the item either breaks, gets lost, or fades away".
            if worn == 4:
                del sheet.items[args.item_id]
            else:
                item.die = worn

        prefix = "" if actor is world.player else f"{actor.name}: "
        line = f"{args.what} — {prefix}{sentence(label)} d{die}"
        if helper is not None:
            line += f", helped by {helper[0].name} (d{helper[1]})"
        line += f" → {result}"

        facts = [dice_fact, actor.fact(line, card=line, dice=(event,))]
        if item is not None and worn == 4:
            gone = f"{item.name} is gone"
            facts.append(actor.fact(gone, card=gone))

        if args.dangerous and result == "fail":
            for who in (actor, *((helper[0],) if helper else ())):
                if who.dice().vulnerable:
                    draft.note(
                        f"{who.name} is vulnerable and this dangerous roll failed: rule "
                        "whether they are taken out of the scene or dead. Death is "
                        f"`change_world` `kill` on {who.name}."
                    )
        return facts

    def catch_breath(self, draft: BreathlessGame, args: Actor, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_actor(args.actor_id)
        sheet = actor.dice()
        sheet.worn = dict(sheet.skills)
        sheet.loot = LOOT_START
        sheet.stunted = False

        rolled, dice_fact = roll((12,), "a new complication", rng)
        text = self.complications()[rolled[0] - 1]
        draft.note(
            f"Catching breath brings a new complication. The SRD's table suggests: {text} Bring "
            "it in through the story, or one that fits better."
        )
        trace = f"{actor.mention} catches their breath: skills and loot die restored"
        card = (
            "Caught breath — skills and loot die restored"
            if actor is world.player
            else f"{actor.name} caught breath — skills and loot die restored"
        )
        fact = actor.fact(trace, card=card)
        return [dice_fact, fact]

    def answer(self, draft: BreathlessGame, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        if chosen.name != TAKE_LOOT:
            return super().answer(draft, chosen, rng)
        taken = parse(TakeLoot, chosen.args)
        return (draft.payload.player.take_loot(taken.item, taken.granted, taken.choice),)

    def loot_check(self, draft: BreathlessGame, args: LootCheck, rng: Random) -> list[Fact]:
        item, player = args.item, draft.payload.player
        sheet = player.dice()
        before = sheet.loot
        rolled, dice_fact = roll((before,), f"scavenging — {item}", rng)
        face = rolled[0]
        sheet.loot = stepped(before)

        found: Die | None = None
        if face <= 2:
            draft.note("The scavenge turns up trouble right here; nothing is found.")
        elif face <= 4:
            draft.note("The scavenge finds nothing, and trouble is coming.")
        else:
            found = next(die for die in LADDER if face <= die)

        result = f"found {item} (d{found})" if found is not None else "nothing"
        line = f"Scavenge — d{before} → {result}"
        event = DiceEvent(label=f"d{before}", faces=(before,), rolled=rolled)
        fact = player.fact(line, card=line, dice=(event,))
        facts = [dice_fact, fact]

        if found is not None:
            draft.pending = PendingDecision(
                kind="loot",
                prompt=f"You found {item} (d{found}). Take it?",
                options=sheet.loot_options(item, found),
                allows_text=False,
            )
        return facts

    def test_luck(self, _draft: BreathlessGame, args: TestLuck, rng: Random) -> list[Fact]:
        rolled, dice_fact = roll((args.die,), args.question, rng)
        result = outcome(rolled[0])
        trace = f"{args.question} — d{args.die} [{rolled[0]}] -> {result}"
        return [dice_fact, Fact(trace=trace)]


def _skill(name: str) -> Skill:
    """`check_picks` has already held the answer to the pack's six ids, which are the SRD's."""
    return next(skill for skill in SKILLS if skill == name)
