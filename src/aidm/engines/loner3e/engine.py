import json
from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, other_than, picked
from aidm.core.entities import EngineId, Refusal, Slug, require_unique, slug
from aidm.core.facts import DiceEvent, Fact, roll
from aidm.core.play import PendingDecision
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Sections
from aidm.engines.base import CHANGE_WORLD, PLAYER_ID, SRD_PACK, keep_highest
from aidm.engines.loner3e.creation import AUTHORING, Pack
from aidm.engines.loner3e.tools import (
    ChangeTags,
    ChangeWorld,
    Drive,
    Outcome,
    Question,
    RestoreLuck,
    WorldChange,
    conflict_prompt,
    defeat_note,
    outcome_for,
    pack_meanings,
    twist_note,
    twist_pairing,
)
from aidm.engines.loner3e.world import (
    DIE_FACE,
    LUCK_MAX,
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eSheet,
    Loner3eWorld,
)
from aidm.engines.scenes.engine import SceneEngine
from aidm.engines.scenes.tools import (
    NEXT_SCENE,
    Enter,
    JoinParty,
    Kill,
    Leave,
    LeaveParty,
    NextScene,
    Reveal,
)

# Read by the next turn, which is usually the next offer click: the note must stand on its own.
GROWTH_NOTE = (
    "The job {title} is closed and was completed. The adventure's end applies: ask what the "
    "character learned if the player has not said, then write it once with `change_tags` and "
    "`drive`."
)


class Loner3eEngine(SceneEngine[Loner3eSheet, Loner3eSheet, Loner3eGame, Pack]):
    id = EngineId("loner3e")
    title = "LONER 3E"
    art_style = "Painterly illustration, muted colours, no text or lettering."
    directory = Path(__file__).parent
    game = Loner3eGame
    scenario = Loner3eScenario
    character = Loner3eCharacter
    cast = Loner3eSheet
    pack = Pack
    world_type = Loner3eWorld
    hub_phrase = "a guild hall or a ship, whoever keeps it and the regulars"
    finished_note = GROWTH_NOTE

    def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
        """Four tools: two world tools, then the two SRD procedures that roll or reset."""
        return (
            master_tool("change_world", CHANGE_WORLD, ChangeWorld, self.change_world),
            master_tool("next_scene", NEXT_SCENE, NextScene, self.next_scene),
            master_tool(
                "roll_question",
                "Roll Chance against Risk for one closed dramatic question.",
                Question,
                self.resolve_question,
            ),
            master_tool(
                "restore_luck",
                "Restore an actor's luck after a conflict ends.",
                RestoreLuck,
                self.restore_luck,
            ),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = CreationStep(
            id="pack", prompt="Choose a character table set", options=self.pack_options()
        )
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        return (
            first,
            CreationStep(
                id="concept",
                prompt="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(id="goal", prompt="What does your character want?"),
            CreationStep(id="motive", prompt="Why do they want it?"),
            CreationStep(id="skill-1", prompt="Choose skill 1", options=pack.skills),
            CreationStep(
                id="skill-2",
                prompt="Choose skill 2",
                options=other_than(pack.skills, picked(picks, "skill-1")),
            ),
            CreationStep(id="frailty", prompt="Choose a frailty", options=pack.frailties),
            CreationStep(id="gear-1", prompt="Choose gear 1", options=pack.gear),
            CreationStep(
                id="gear-2",
                prompt="Choose gear 2",
                options=other_than(pack.gear, picked(picks, "gear-1")),
            ),
        )

    def create_character(self, name: str, brief: str, picks: Picks) -> Loner3eCharacter:
        check_picks(self.creation_steps(picks), picks)
        pack = self.packs[picked(picks, "pack")]
        sheet = Loner3eSheet(
            id=PLAYER_ID,
            name=name,
            brief=brief,
            known=True,
            concept=picked(picks, "concept"),
            tags={
                "skill": [
                    chosen_option(pack.skills, picked(picks, f"skill-{slot}")).label
                    for slot in (1, 2)
                ],
                "frailty": [chosen_option(pack.frailties, picked(picks, "frailty")).label],
                "gear": [
                    chosen_option(pack.gear, picked(picks, f"gear-{slot}")).label for slot in (1, 2)
                ],
            },
            goal=picked(picks, "goal"),
            motive=picked(picks, "motive"),
        )
        return Loner3eCharacter(id=slug(name, ()), engine=self.id, payload=sheet)

    def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
        """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
        selected = {
            pack_id: self.packs[pack_id].model_dump(mode="json", exclude_defaults=True)
            for pack_id in picks
        }
        return f"{AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"

    def glossary(self, state: Loner3eGame) -> Sections:
        spelled: dict[str, str] = {}
        for member in self.world(state).here():
            spelled.update(self.meanings(state.packs, member))
        lines = "\n".join(f"- {tag}: {detail}" for tag, detail in spelled.items())
        return (("WHAT THE TAGS IN PLAY MEAN", lines),) if spelled else ()

    def meanings(
        self, selected: Sequence[Slug], sheet: Loner3eSheet
    ) -> tuple[tuple[str, str], ...]:
        chosen = tuple(self.packs[pack_id] for pack_id in selected)
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        return pack_meanings(
            tuple(
                entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)
            ),
            (*sheet.tagged("skill"), *sheet.tagged("frailty"), *sheet.tagged("gear")),
        )

    def twist_table(self) -> tuple[tuple[str, str], ...]:
        """Always the SRD's own table: no other pack publishes one."""
        srd = self.packs.get(SRD_PACK)
        if srd is None or srd.twist_subjects is None or srd.twist_actions is None:
            raise Refusal("the SRD table set with its twist columns is not installed")
        return tuple(zip(srd.twist_subjects, srd.twist_actions, strict=True))

    def leaving(self, state: Loner3eGame) -> tuple[Fact, ...]:
        """A scene ends its conflicts so nobody carries a spent pool on; the dead keep theirs."""
        facts: list[Fact] = []
        for member in self.world(state).here():
            if member.alive and member.luck.current < LUCK_MAX:
                facts.extend(_refill(member, "the scene is over"))
        return tuple(facts)

    def apply_change(self, world: Loner3eWorld, change: WorldChange) -> list[Fact]:
        match change:
            case Reveal() | Enter() | Leave() | Kill():
                return self.shared_change(world, change)
            case ChangeTags():
                return self.change_tags(world.require_alive_here(change.entity_id), change)
            case Drive():
                return self.drive(world.require_alive_here(change.entity_id), change)
            case JoinParty():
                return world.join_party(change.entity_id)
            case LeaveParty():
                return world.leave_party(change.entity_id)

    def change_world(self, draft: Loner3eGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
        return self.apply_change(draft.payload, args.change)

    def resolve_question(self, draft: Loner3eGame, action: Question, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_alive_here(action.actor_id)
        facts = actor.reveal()
        opponent: Loner3eSheet | None = None
        if action.opponent_id is not None:
            opponent = world.require_alive_here(action.opponent_id)
            facts.extend(opponent.reveal())
        _refuse_unless_ready(actor, opponent)

        chance_kept, chance, risk_kept, risk, facts_rolled = _pair(action, rng)
        facts.extend(facts_rolled)

        outcome = outcome_for(chance_kept, risk_kept)
        answered_at = len(facts)
        facts.append(actor.fact("question_answered", f"{action.question} -> {outcome.name}"))
        effects: tuple[str, ...] = ()
        if opponent is not None:
            exchange, effects = _absorbed(_strike(draft, actor, opponent, outcome))
            facts.extend(exchange)
            # The pools refill the moment a side hits 0, so only the fact says the conflict ended.
            if not any(fact.kind == "conflict_lost" for fact in exchange):
                draft.pending = PendingDecision(
                    kind="conflict",
                    prompt=conflict_prompt(world, actor, opponent),
                    options=(),
                    allows_text=True,
                )
        # SRD: the Twist Counter does not apply to Harm & Luck, so a tied conflict roll never
        # ticks it.
        if chance_kept == risk_kept and opponent is None:
            twist = world.twist
            twist.current += 1
            if twist.shortfall == 0:
                twist.current = 0
                facts.extend(self._twist(draft, actor, rng))
        # The question is master-authored and names unrevealed canon even on a "no": never shown.
        edge = f" ({action.edge})" if action.edge else ""
        card = "\n".join(
            (f"Oracle — {action.position.capitalize()}{edge} → {outcome.name}", *effects)
        )
        facts[answered_at] = facts[answered_at].model_copy(
            update={"card": card, "dice": (chance, risk)}
        )
        return facts

    def restore_luck(self, draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
        actor = self.world(draft).require_alive_here(args.actor_id)
        facts = actor.reveal()
        # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
        facts.extend(_refill(actor, "the conflict is behind them"))
        return facts

    def change_tags(self, sheet: Loner3eSheet, change: ChangeTags) -> list[Fact]:
        if not change.gained and not change.lost:
            raise Refusal("change_tags needs at least one gained or lost tag")
        require_unique(f"{change.kind} tags", (*change.gained, *change.lost))
        current = sheet.tagged(change.kind)
        if carried := [tag for tag in change.gained if tag in current]:
            raise Refusal(f"{sheet.name} already carries the {change.kind} {carried[0]!r}")
        if missing := [tag for tag in change.lost if tag not in current]:
            raise Refusal(f"{sheet.name} carries no {change.kind} {missing[0]!r}")
        sheet.tags[change.kind] = [
            tag for tag in (*current, *change.gained) if tag not in change.lost
        ]
        deltas = (*(f"+{tag}" for tag in change.gained), *(f"-{tag}" for tag in change.lost))
        trace = f"{sheet.label} {change.kind} " + ", ".join(deltas)
        parts: list[str] = []
        if change.gained:
            took = ", ".join(change.gained)
            parts.append(f"Took {took}" if change.kind == "gear" else f"Now: {took}")
        if change.lost:
            lost = ", ".join(change.lost)
            parts.append(f"Lost {lost}" if change.kind == "gear" else f"No longer: {lost}")
        return [sheet.fact("tags_changed", trace, card="; ".join(parts))]

    def drive(self, sheet: Loner3eSheet, change: Drive) -> list[Fact]:
        if not change.goal and not change.motive and not change.nemesis:
            raise Refusal("drive needs a goal, a motive or a nemesis to set")
        parts: list[str] = []
        if change.goal:
            sheet.goal = change.goal
            parts.append(f"goal: {change.goal}")
        if change.motive:
            sheet.motive = change.motive
            parts.append(f"motive: {change.motive}")
        if change.nemesis:
            sheet.nemesis = change.nemesis
            parts.append(f"nemesis: {change.nemesis}")
        trace = f"{sheet.label} " + "; ".join(parts)
        card = f"{sheet.name}: {change.goal}" if change.goal else ""
        return [sheet.fact("drive_set", trace, card=card)]

    def _twist(self, draft: Loner3eGame, actor: Loner3eSheet, rng: Random) -> list[Fact]:
        """The SRD's table is rolled here so the dice trace; the model only reads the pairing."""
        faces = (DIE_FACE, DIE_FACE)
        rolled, rolled_fact = roll(faces, "twist — subject, action", rng)
        subject, action = twist_pairing(rolled[0], rolled[1], self.twist_table())
        draft.note(twist_note(subject, action))
        # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
        due = actor.fact(
            "twist_due",
            f"a twist interrupts the scene: {subject} / {action}",
            card=f"Twist — {subject} / {action}",
            dice=(DiceEvent(label="Twist", faces=faces, rolled=rolled),),
        )
        return [rolled_fact, due]


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(fact.card for fact in exchange if fact.told and fact.card)
    return [fact.model_copy(update={"card": ""}) for fact in exchange], lines


def _refill(side: Loner3eSheet, why: str) -> list[Fact]:
    return side.luck.change(side, side.luck.shortfall, "Luck", why)


def _strike(
    draft: Loner3eGame, actor: Loner3eSheet, opponent: Loner3eSheet, outcome: Outcome
) -> list[Fact]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    why = f"{striker.name} gets the better of the exchange"
    facts = hit.luck.change(hit, -abs(harm), "Luck", why)
    if hit.luck.current != 0:
        return facts
    draft.note(defeat_note(hit.name))
    lost = f"{hit.name} is out of luck"
    facts.append(hit.fact("conflict_lost", lost, card=lost))
    # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
    facts.extend(_refill(hit, "the conflict is over"))
    facts.extend(_refill(striker, "the conflict is over"))
    return facts


def _refuse_unless_ready(actor: Loner3eSheet, opponent: Loner3eSheet | None) -> None:
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise Refusal(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if side.luck.current == 0:
            raise Refusal(
                f"{side.name} is already out of luck, so that conflict is over. Settle what it "
                "costs them instead of rolling it again."
            )


def _pair(action: Question, rng: Random) -> tuple[int, DiceEvent, int, DiceEvent, list[Fact]]:
    """One extra die at most, and only for the side the judged position favours."""
    face = DIE_FACE
    chance_faces = (face, face) if action.position == "advantage" else (face,)
    risk_faces = (face, face) if action.position == "disadvantage" else (face,)
    asked = action.question
    chance_kept, chance, chance_fact = keep_highest(
        chance_faces, f"{asked} — chance", rng, label="Chance"
    )
    risk_kept, risk, risk_fact = keep_highest(risk_faces, f"{asked} — risk", rng, label="Risk")
    return chance_kept, chance, risk_kept, risk, [chance_fact, risk_fact]
