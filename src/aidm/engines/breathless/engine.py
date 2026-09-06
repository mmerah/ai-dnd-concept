import json
from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, other_than, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter, Generation, WorldsmithAnswer
from aidm.core.play import PendingDecision
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Panel, PanelRow, Rows, Sections, lines_of
from aidm.engines.base import (
    CHANGE_WORLD,
    HIRE,
    PLAYER_ID,
    SIGNED_ON,
    Hire,
    hire_request,
    hire_target,
    keep_highest,
    sentence,
)
from aidm.engines.breathless.tools import (
    Actor,
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
    SurvivorSheet,
    stepped,
)
from aidm.engines.breathless.worldsmith import AUTHORING, HIRING, Pack, SheetDraft
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, NextScene


class BreathlessEngine(SceneEngine[Survivor, Survivor, BreathlessGame, Pack]):
    id = EngineId("breathless")
    title = "BREATHLESS"
    art_style = (
        "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or lettering."
    )
    directory = Path(__file__).parent
    game = BreathlessGame
    scenario = BreathlessScenario
    character = BreathlessCharacter
    cast = Survivor
    pack = Pack
    world_type = BreathlessWorld
    operations = (*SceneEngine.operations, HIRE)

    def master_tools(self) -> tuple[MasterTool[BreathlessGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "check",
                "Roll a check for an action with a real cost, on a skill, a carried item, or a "
                "stunt. `actor_id` when a hired survivor acts instead of the player; "
                "`helped_by` names a hired survivor who also makes a skill check on their own "
                "die and shares the risk.",
                Check,
                self.check,
            ),
            master_tool(
                "catch_breath",
                "Let the actor catch their breath: skills, loot die and the stunt reset, at the "
                "cost of a new complication. `actor_id` when a hired survivor catches breath "
                "instead of the player.",
                Actor,
                self.catch_breath,
            ),
            master_tool(
                "change_stress",
                "A complication costs the actor stress; laying low somewhere secure clears an "
                "amount at your discretion. Never a stand-in for `use_med_kit`. `actor_id` when "
                "a hired survivor is meant instead of the player.",
                ChangeStress,
                self.change_stress,
            ),
            master_tool(
                "use_med_kit",
                "Spend the actor's med kit to clear 2 stress. `actor_id` when a hired survivor "
                "is meant instead of the player.",
                Actor,
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
            master_tool(
                "hire",
                "The player hires someone here to work: the worldsmith writes their sheet once "
                "this turn ends, and they join the party. Someone already travelling with the "
                "player may be hired too; a sheet is for someone hired to work, never for one "
                "who merely comes along.",
                Hire,
                self.hire,
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

    def preview_character(self, character: AnyCharacter) -> Rows:
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

    def sheet_sections(self, state: BreathlessGame) -> Sections:
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

    def apply_change(self, world: BreathlessWorld, change: WorldChange) -> list[Fact]:
        match change:
            case DropItem():
                return world.require_actor(change.actor_id).drop_item(change.item_id)
            case _:
                return self.shared_change(world, change)

    def change_world(self, draft: BreathlessGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def hire(self, draft: BreathlessGame, args: Hire, _rng: Random) -> list[Fact]:
        world = draft.payload
        member = world.require_hireable(args.entity_id)
        draft.generation, fact = hire_request(member, args.terms)
        return [fact]

    def validate(self, state: BreathlessGame) -> None:
        super().validate(state)
        generation = state.generation
        if generation is not None and generation.operation == HIRE:
            state.payload.require_hireable(hire_target(generation))

    async def advance(
        self, draft: BreathlessGame, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        if request.operation != HIRE:
            return await super().advance(draft, request, worldsmith)
        world = draft.payload
        member = world.require_hireable(hire_target(request))
        pack = self.packs[draft.packs[0]]
        prompt = self.render_request(
            draft,
            guidance=AUTHORING,
            intent=HIRING.format(
                name=member.name,
                brief=member.brief,
                terms=request.brief,
                jobs=", ".join(pack.jobs),
                weapons=", ".join(pack.weapons),
            ),
            answer=SheetDraft,
        )
        answer = await worldsmith(prompt, SheetDraft, lambda _draft: None)
        member.sheet = SurvivorSheet(
            pronouns=answer.pronouns,
            job=answer.job,
            skills=dict(answer.skills),
            worn=dict(answer.skills),
            items={EntityId(slug(answer.item, ())): Item(name=answer.item, die=STARTING_ITEM)},
        )
        facts = world.join_party(member.id) if member.id not in world.party else []
        trace = f"{member.label} signs on — {answer.job}"
        facts.append(member.fact("hired", trace, card=f"{member.name} signs on — {answer.job}"))
        return tuple(facts), SIGNED_ON.format(name=member.name)

    def check(self, draft: BreathlessGame, args: Check, rng: Random) -> list[Fact]:
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
                    raise Refusal(f"{actor.name} cannot help their own check")
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

        facts = [dice_fact, actor.fact("checked", line, card=line, dice=(event,))]
        if item is not None and worn == 4:
            gone = f"{item.name} is gone"
            facts.append(actor.fact("item_gone", gone, card=gone))

        if args.dangerous and result == "fail":
            for who in (actor, *((helper[0],) if helper else ())):
                if who.dice().vulnerable:
                    draft.note(
                        f"{who.name} is vulnerable and this dangerous check failed: rule "
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
        trace = f"{actor.label} catches their breath: skills and loot die restored"
        card = (
            "Caught breath — skills and loot die restored"
            if actor is world.player
            else f"{actor.name} caught breath — skills and loot die restored"
        )
        fact = actor.fact("breath_caught", trace, card=card)
        return [dice_fact, fact]

    def change_stress(self, draft: BreathlessGame, args: ChangeStress, _rng: Random) -> list[Fact]:
        if args.amount == 0:
            raise Refusal("change_stress needs a non-zero amount")
        actor = draft.payload.require_actor(args.actor_id)
        return actor.dice().stress.change(actor, args.amount, "Stress", args.why)

    def use_med_kit(self, draft: BreathlessGame, args: Actor, _rng: Random) -> list[Fact]:
        actor = draft.payload.require_actor(args.actor_id)
        sheet = actor.dice()
        if not sheet.med_kit:
            raise Refusal(f"{actor.name} holds no med kit")
        sheet.med_kit = False
        facts = sheet.stress.change(actor, -MED_KIT_CLEARS, "Stress", "the med kit")
        used = f"{actor.name} uses the med kit"
        facts.append(actor.fact("med_kit_used", used, card="Med kit used"))
        return facts

    def loot_check(self, draft: BreathlessGame, args: LootCheck, rng: Random) -> list[Fact]:
        if args.granted is None or args.choice is None:
            return self.roll_loot(draft, args.item, rng)
        return [draft.payload.player.take_loot(args.item, args.granted, args.choice)]

    def roll_loot(self, draft: BreathlessGame, item: str, rng: Random) -> list[Fact]:
        player = draft.payload.player
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
        fact = player.fact("loot_checked", line, card=line, dice=(event,))
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
        return [dice_fact, Fact(kind="luck_tested", trace=trace)]


def _skill(name: str) -> Skill:
    """`check_picks` has already held the answer to the pack's six ids, which are the SRD's."""
    return next(skill for skill in SKILLS if skill == name)
