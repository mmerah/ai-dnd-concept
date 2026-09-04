from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, option_of, picked
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.model import AnyCharacter
from aidm.core.play import DecisionOption
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Panel, PanelRow, Rows, Sections, lines_of
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID, Person, keep_highest, sentence
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import NEXT_SCENE, Enter, Kill, Leave, NextScene, Reveal
from aidm.engines.twentyfourxx.tools import (
    AfterJob,
    ChangeHindrances,
    ChangeWorld,
    Defend,
    DropItem,
    GainItem,
    RepairItem,
    Roll,
    Spend,
    TestLuck,
    WorldChange,
    outcome,
)
from aidm.engines.twentyfourxx.world import (
    DEFAULT_DIE,
    HELP_DIE,
    HINDERED_DIE,
    MAIMED,
    Item,
    Kit,
    Operator,
    SkillDie,
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxWorld,
    raised,
)
from aidm.engines.twentyfourxx.worldsmith import AUTHORING, Pack

BOARD_GUIDANCE = (
    "The SRD's job-finding setup is the board's range, not a recipe: 1–2 nothing, owe somebody to "
    "get in on a job; 3–4 found a job, but something seems off; 5–6 a choice between two jobs."
)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
JOB_DONE_NOTE = (
    "The job {title} is closed and was completed. The SRD's after-a-job step applies: call "
    "`after_job` once, with the skill the player names, else the skill the job called on."
)


class TwentyfourxxEngine(SceneEngine[Person, Operator, TwentyfourxxGame, Pack]):
    id = EngineId("twentyfourxx")
    title = "24XX"
    art_style = (
        "Clean science-fiction illustration: hard light, neon on steel, lived-in "
        "technology, no text or lettering."
    )
    directory = Path(__file__).parent
    game = TwentyfourxxGame
    scenario = TwentyfourxxScenario
    character = TwentyfourxxCharacter
    cast = Person
    pack = Pack
    world_type = TwentyfourxxWorld
    hub_phrase = "the fixer and the regulars"
    finished_note = JOB_DONE_NOTE

    def master_tools(self) -> tuple[MasterTool[TwentyfourxxGame], ...]:
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "attempt",
                "Roll for something whose outcome matters. Name `helped` with why circumstances "
                "help — an ally who pitches in counts, named in it: the SRD gives them their own "
                "die, but here it is the d6 of circumstance, because an NPC carries no dice. Name "
                "`hindered` with why the player is hindered, when they are.",
                Roll,
                self.attempt,
            ),
            master_tool(
                "test_luck",
                "Roll a d6 to test the world's bad luck, where nobody is acting.",
                TestLuck,
                self.test_luck,
            ),
            master_tool(
                "defend",
                "Break a carried item to turn a hit into a hindrance instead of taking it "
                "outright; word the harm yourself.",
                Defend,
                self.defend,
            ),
            master_tool(
                "after_job",
                "The SRD's after-a-job step, once per job, when the player's own words close it: "
                "raise the named skill and pay out its credits.",
                AfterJob,
                self.after_job,
            ),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options())
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        steps = [
            first,
            CreationStep(id="specialty", prompt="Specialty", options=pack.specialties),
        ]
        specialty = option_of(pack.specialties, picked(picks, "specialty"))
        if specialty is None:
            return tuple(steps)
        if specialty.choice:
            steps.append(
                CreationStep(
                    id="specialty-choice", prompt="Specialty skill", options=specialty.choice
                )
            )
        if specialty.kit_choice:
            steps.append(
                CreationStep(
                    id="weapon",
                    prompt="Weapon",
                    options=tuple(
                        DecisionOption(id=slug(kit.name, ()), label=kit.name)
                        for kit in specialty.kit_choice
                    ),
                )
            )
        steps.append(CreationStep(id="origin", prompt="Origin", options=pack.origins))
        origin = option_of(pack.origins, picked(picks, "origin"))
        if origin is None:
            return tuple(steps)
        for number in range(1, origin.invents + 1):
            steps.append(
                CreationStep(id=f"trait-{number}", prompt=f"Trait {number}", hint=origin.detail)
            )
        if origin.choice:
            steps.append(CreationStep(id="body", prompt="Body", options=origin.choice))
        for number in range(1, origin.increases + 1):
            steps.append(
                CreationStep(id=f"increase-{number}", prompt="Skill increase", options=pack.skills)
            )
        return tuple(steps)

    def create_character(self, name: str, brief: str, picks: Picks) -> TwentyfourxxCharacter:
        check_picks(self.creation_steps(picks), picks)
        pack = self.packs[picked(picks, "pack")]
        specialty = chosen_option(pack.specialties, picked(picks, "specialty"))
        origin = chosen_option(pack.origins, picked(picks, "origin"))

        skills: dict[str, SkillDie] = dict(specialty.skills)
        if specialty.choice:
            chosen = chosen_option(specialty.choice, picked(picks, "specialty-choice"))
            skills.update(chosen.skills)
        for number in range(1, origin.increases + 1):
            option = chosen_option(pack.skills, picked(picks, f"increase-{number}"))
            skills[option.label] = raised(skills.get(option.label))

        weapon: Kit | None = None
        if specialty.kit_choice:
            wanted = picked(picks, "weapon")
            weapon = next(
                (kit for kit in specialty.kit_choice if slug(kit.name, ()) == wanted), None
            )
            if weapon is None:
                raise Refusal(f"{wanted!r} is not one of the weapons on offer")

        traits = tuple(picked(picks, f"trait-{number}") for number in range(1, origin.invents + 1))
        if origin.choice:
            body = chosen_option(origin.choice, picked(picks, "body"))
            traits = (*traits, body.label)

        kits = pack.starting_kit + specialty.kit + ((weapon,) if weapon is not None else ())
        sheet = Operator(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            specialty=specialty.label,
            origin=origin.label,
            traits=traits,
            skills=skills,
            items=starting_items(kits),
        )
        return TwentyfourxxCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def preview_character(self, character: AnyCharacter) -> Rows:
        sheet = self.player_of(character)
        return (*sheet.rows(), ("Gear", ", ".join(item.name for item in sheet.items.values())))

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        """This pack holds creation tables, not setting vocabulary: the preamble alone suffices."""
        return "\n\n".join((AUTHORING, BOARD_GUIDANCE)) if campaign else AUTHORING

    def sheet_sections(self, state: TwentyfourxxGame) -> Sections:
        lines: list[str] = []
        for key, item in state.payload.player.items.items():
            line = f"- {item.name}[{key}]"
            if detail := gear_detail(item):
                line += f" — {detail}"
            lines.append(line)
        return (("GEAR", lines_of(lines)),)

    def panels(self, state: TwentyfourxxGame) -> tuple[Panel, ...]:
        rows = tuple(
            PanelRow(label=item.name, detail=gear_detail(item))
            for item in state.payload.player.items.values()
        )
        return (Panel(title="Gear", rows=rows),)

    def resolve_skill(self, player: Operator, wanted: str) -> str:
        """A skill the master names is matched against the sheet, then the table sets."""
        folded = wanted.casefold()
        for key in player.skills:
            if key.casefold() == folded:
                return key
        labels: list[str] = []
        for pack in self.packs.values():
            for option in pack.skills:
                if option.label.casefold() == folded:
                    return option.label
                if option.label not in labels:
                    labels.append(option.label)
        sheet = ", ".join(sorted(player.skills)) or "none"
        raise Refusal(
            f"{wanted!r} is not a skill on the sheet ({sheet}) or in the packs "
            f"({', '.join(labels)})"
        )

    def apply_change(self, world: TwentyfourxxWorld, change: WorldChange) -> list[Fact]:
        match change:
            case Reveal() | Enter() | Leave() | Kill():
                return self.shared_change(world, change)
            case ChangeHindrances():
                return self.change_hindrances(world, change)
            case GainItem():
                return self.gain_item(world, change)
            case DropItem():
                return self.drop_item(world, change.item_id)
            case RepairItem():
                return self.repair_item(world, change)
            case Spend():
                return self.spend(world, change)

    def change_world(self, draft: TwentyfourxxGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def attempt(self, draft: TwentyfourxxGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.payload
        player = world.player

        if args.skill:
            label = self.resolve_skill(player, args.skill)
            die = player.die(label)
        else:
            label = "unskilled"
            die = DEFAULT_DIE
        if args.hindered:
            die = HINDERED_DIE

        reason = f"{args.what} — {label}"
        die_label = f"d{die}+d{HELP_DIE}" if args.helped else f"d{die}"
        if args.helped:
            face, event, dice_fact = keep_highest((die, HELP_DIE), reason, rng, label=die_label)
        else:
            rolled, dice_fact = roll((die,), reason, rng)
            face = rolled[0]
            event = DiceEvent(label=die_label, faces=(die,), rolled=rolled)

        result = outcome(face)
        shown = ", ".join(str(value) for value in event.rolled)
        trace = f"{args.what} — {label} {die_label} [{shown}] -> {result}"
        card = f"{args.what} — {sentence(label)} {die_label} → {result}"
        qualifiers = "; ".join(
            part
            for part in (
                f"helped — {args.helped}" if args.helped else "",
                f"hindered — {args.hindered}" if args.hindered else "",
            )
            if part
        )
        if qualifiers:
            card = f"{card} ({qualifiers})"

        facts: list[Fact] = [dice_fact, player.fact("attempted", trace, card=card, dice=(event,))]

        if args.risking_death and result == "disaster":
            facts.extend(world.kill(player.id))
        elif args.risking_death and result == "setback" and MAIMED not in player.hindrances:
            player.hindrances.append(MAIMED)
            maimed_trace = f"{player.label} is maimed"
            facts.append(player.fact("hindrances_changed", maimed_trace, card="Maimed"))

        return facts

    def after_job(self, draft: TwentyfourxxGame, args: AfterJob, rng: Random) -> list[Fact]:
        player = draft.payload.player
        label = self.resolve_skill(player, args.skill)
        new_die = raised(player.skills.get(label))
        player.skills[label] = new_die
        raise_trace = f"{player.label} — {label} rises to d{new_die}"
        raise_fact = player.fact("skill_raised", raise_trace, card=f"Skill up: {label} d{new_die}")

        rolled, dice_fact = roll((6,), "credits earned", rng)
        gained = rolled[0]
        player.credits += gained
        event = DiceEvent(label="d6", faces=(6,), rolled=rolled)
        credit_trace = f"{player.label} earns ₡{gained} -> ₡{player.credits}"
        credit_fact = player.fact(
            "credits_gained",
            credit_trace,
            card=f"+₡{gained} -> ₡{player.credits}",
            dice=(event,),
        )
        return [raise_fact, dice_fact, credit_fact]

    def test_luck(self, _draft: TwentyfourxxGame, args: TestLuck, rng: Random) -> list[Fact]:
        rolled, dice_fact = roll((6,), args.question, rng)
        face = rolled[0]
        if face <= 2:
            result = "trouble now"
        elif face <= 4:
            result = "signs of it"
        else:
            result = "nothing"
        trace = f"{args.question} — d6 [{face}] -> {result}"
        return [dice_fact, Fact(kind="luck_tested", trace=trace)]

    def defend(self, draft: TwentyfourxxGame, args: Defend, _rng: Random) -> list[Fact]:
        player = draft.payload.player
        item = player.items.get(args.item_id)
        if item is None:
            raise Refusal(f"{args.item_id!r} is not among the player's items")
        if item.broken:
            raise Refusal(f"{item.name} is already broken")
        if args.hindrance in player.hindrances:
            raise Refusal(f"{args.hindrance!r} is already among the player's hindrances")
        item.broken_times += 1
        player.hindrances.append(args.hindrance)
        card = f"{item.name} breaks — {args.hindrance}"
        trace = f"{player.label} breaks {item.name} — {args.hindrance}"
        return [player.fact("item_broken", trace, card=card)]

    def change_hindrances(self, world: TwentyfourxxWorld, change: ChangeHindrances) -> list[Fact]:
        player = world.player
        current = set(player.hindrances)
        for hindrance in change.gained:
            if hindrance in current:
                raise Refusal(f"{hindrance!r} is already among the player's hindrances")
            current.add(hindrance)
        for hindrance in change.lost:
            if hindrance not in player.hindrances:
                raise Refusal(f"{hindrance!r} is not among the player's hindrances")
        for hindrance in change.lost:
            player.hindrances.remove(hindrance)
        player.hindrances.extend(change.gained)
        parts: list[str] = []
        if change.gained:
            parts.append(f"Hindered: {', '.join(change.gained)}")
        if change.lost:
            parts.append(f"Recovered: {', '.join(change.lost)}")
        card = " / ".join(parts)
        trace = f"{player.label} — {card}"
        return [player.fact("hindrances_changed", trace, card=card)]

    def gain_item(self, world: TwentyfourxxWorld, change: GainItem) -> list[Fact]:
        player = world.player
        if change.cost > player.credits:
            raise Refusal(f"the player has only ₡{player.credits}, not ₡{change.cost}")
        player.credits -= change.cost
        key = EntityId(slug(change.name, player.items))
        player.items[key] = Item(name=change.name, bulky=change.bulky, breaks=change.breaks)
        suffix = f" (₡{change.cost})" if change.cost > 0 else ""
        card = f"Gained {change.name}{suffix}"
        trace = f"{player.label} gains {change.name}{suffix}"
        return [player.fact("item_gained", trace, card=card)]

    def drop_item(self, world: TwentyfourxxWorld, item_id: EntityId) -> list[Fact]:
        player = world.player
        item = player.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among the player's items")
        del player.items[item_id]
        trace = f"{player.label} drops {item.name}"
        return [player.fact("item_dropped", trace, card=f"Dropped {item.name}")]

    def repair_item(self, world: TwentyfourxxWorld, change: RepairItem) -> list[Fact]:
        player = world.player
        item = player.items.get(change.item_id)
        if item is None:
            raise Refusal(f"{change.item_id!r} is not among the player's items")
        if item.broken_times == 0:
            raise Refusal(f"{item.name} is not broken")
        if change.cost > player.credits:
            raise Refusal(f"the player has only ₡{player.credits}, not ₡{change.cost}")
        player.credits -= change.cost
        item.broken_times = 0
        card = f"Repaired {item.name}"
        trace = f"{player.label} repairs {item.name}"
        return [player.fact("item_repaired", trace, card=card)]

    def spend(self, world: TwentyfourxxWorld, change: Spend) -> list[Fact]:
        player = world.player
        if change.amount > player.credits:
            raise Refusal(f"the player has only ₡{player.credits}, not ₡{change.amount}")
        player.credits -= change.amount
        card = f"₡{change.amount} spent — {change.why}"
        trace = f"{player.label} spends ₡{change.amount} — {change.why}"
        return [player.fact("credits_spent", trace, card=card)]


def starting_items(kits: Sequence[Kit]) -> dict[EntityId, Item]:
    """Filed by name in order, a duplicate name taking the next free slug."""
    taken: list[str] = []
    items: dict[EntityId, Item] = {}
    for kit in kits:
        key = slug(kit.name, taken)
        taken.append(key)
        items[EntityId(key)] = Item(name=kit.name, bulky=kit.bulky, breaks=kit.breaks)
    return items


def gear_detail(item: Item) -> str:
    parts: list[str] = []
    if item.bulky:
        parts.append("bulky")
    if item.broken:
        parts.append("broken")
    elif item.breaks > 1 and item.broken_times > 0:
        parts.append(f"broken {item.broken_times}/{item.breaks}")
    return ", ".join(parts)
