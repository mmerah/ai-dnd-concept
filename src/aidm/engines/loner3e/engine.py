import json
from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.core.creation import CreationStep, Picks, check_picks, chosen_option, other_than, picked
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.facts import DiceEvent, Fact, roll, roll_pool
from aidm.core.play import PendingDecision
from aidm.core.prompt import Pairs
from aidm.core.tools import MasterTool, master_tool
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.tools import (
    CHANGE_TAGS,
    DRIVE,
    RESTORE_LUCK,
    ROLL,
    ChangeTags,
    Drive,
    RestoreLuck,
    Roll,
)
from aidm.engines.loner3e.world import (
    DIE_FACE,
    Loner3eCast,
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eWorld,
    Outcome,
    outcome_for,
    pack_meanings,
    twist_pairing,
)
from aidm.engines.loner3e.worldsmith import AUTHORING, Pack
from aidm.engines.scenes.engine import SceneEngine

TWIST_NOTE = (
    "A twist has just interrupted the scene: {subject} / {action}. The narration showed it "
    "arriving. Develop it this turn. Say what it set in motion, what it costs, and what it "
    "changes."
)
DEFEAT_NOTE = (
    "{name} has run out of luck and lost this conflict. Roll nothing more for it. Say how it "
    "ends for them: taken, severely injured, broken off, cornered, or conceding. Write any "
    "lasting mark with `change_tags`, as a `condition`. Then let the story move on."
)


class Loner3eEngine(SceneEngine[Loner3eCast, Loner3eGame, Pack]):
    id = EngineId("loner3e")
    title = "LONER 3E"
    art_style = "Painterly illustration, muted colours, no text or lettering."
    directory = Path(__file__).parent
    game = Loner3eGame
    scenario = Loner3eScenario
    character = Loner3eCharacter
    cast = Loner3eCast
    pack = Pack
    world_type = Loner3eWorld

    def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
        return (
            *super().master_tools(),
            master_tool("change_tags", CHANGE_TAGS, ChangeTags, self.change_tags),
            master_tool("drive", DRIVE, Drive, self.drive),
            master_tool("restore_luck", RESTORE_LUCK, RestoreLuck, self.restore_luck),
            master_tool("roll", ROLL, Roll, self.roll),
        )

    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]:
        first = self.pack_step()
        pack = self.packs.get(picked(picks, "pack"))
        if pack is None:
            return (first,)
        return (
            first,
            CreationStep(
                id="concept",
                label="Write a one-line concept",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(id="goal", label="What does your character want?"),
            CreationStep(id="motive", label="Why do they want it?"),
            CreationStep(id="skill-1", label="Choose skill 1", options=pack.skills),
            CreationStep(
                id="skill-2",
                label="Choose skill 2",
                options=other_than(pack.skills, picked(picks, "skill-1")),
            ),
            CreationStep(id="frailty", label="Choose a frailty", options=pack.frailties),
            CreationStep(id="gear-1", label="Choose gear 1", options=pack.gear),
            CreationStep(
                id="gear-2",
                label="Choose gear 2",
                options=other_than(pack.gear, picked(picks, "gear-1")),
            ),
        )

    def create_character(self, name: str, brief: str, picks: Picks) -> Loner3eCharacter:
        check_picks(self.creation_steps(picks), picks)
        pack = self.packs[picked(picks, "pack")]
        sheet = Loner3eCast(
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

    def guidance(self, picks: Sequence[Slug]) -> str:
        """Defaults restate rules the guidance already carries; dropping them halves the prompt."""
        selected = {
            pack_id: self.packs[pack_id].model_dump(mode="json", exclude_defaults=True)
            for pack_id in picks
        }
        return f"{AUTHORING}\n\nSELECTED PACK CONTENT\n{json.dumps(selected)}"

    def glossary(self, state: Loner3eGame) -> Pairs:
        spelled: dict[str, str] = {}
        for member in state.payload.here():
            spelled.update(self._meanings(state.packs, member))
        lines = "\n".join(f"- {tag}: {detail}" for tag, detail in spelled.items())
        return (("WHAT THE TAGS IN PLAY MEAN", lines),) if spelled else ()

    def _meanings(self, selected: Sequence[Slug], sheet: Loner3eCast) -> Pairs:
        chosen = tuple(self.packs[pack_id] for pack_id in selected)
        # The concept's pack blurb is generic where the entity's own brief is not: skip it.
        return pack_meanings(
            tuple(
                entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)
            ),
            (*sheet.tagged("skill"), *sheet.tagged("frailty"), *sheet.tagged("gear")),
        )

    def twist_table(self) -> Pairs:
        """Always the SRD's own table: no other pack publishes one."""
        srd = self.srd_pack()
        if srd.twist_subjects is None or srd.twist_actions is None:
            raise Refusal("the SRD table set has no twist columns")
        return tuple(zip(srd.twist_subjects, srd.twist_actions, strict=True))

    def leaving(self, draft: Loner3eGame) -> list[Fact]:
        """A scene ends its conflicts so nobody carries a spent pool on; the dead keep theirs."""
        return [
            fact
            for member in draft.payload.here()
            if member.alive
            for fact in member.refill("the scene is over")
        ]

    def change_tags(self, draft: Loner3eGame, args: ChangeTags, _rng: Random) -> list[Fact]:
        actor = draft.payload.require_here(args.entity_id, alive=True)
        return actor.change_tags(args.kind, args.gained, args.lost)

    def drive(self, draft: Loner3eGame, args: Drive, _rng: Random) -> list[Fact]:
        actor = draft.payload.require_here(args.entity_id, alive=True)
        return actor.drive(goal=args.goal, motive=args.motive, nemesis=args.nemesis)

    def restore_luck(self, draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
        actor = draft.payload.require_here(args.entity_id, alive=True)
        facts = actor.reveal()
        # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
        facts.extend(actor.refill("the conflict is behind them"))
        return facts

    def roll(self, draft: Loner3eGame, args: Roll, rng: Random) -> list[Fact]:
        world = draft.payload
        actor = world.require_here(args.actor_id, alive=True)
        facts = actor.reveal()
        opponent = None
        if args.opponent_id is not None:
            opponent = world.require_here(args.opponent_id, alive=True)
            facts.extend(opponent.reveal())
        _check_ready(actor, opponent)

        chance_kept, chance, risk_kept, risk, facts_rolled = _pair(args, rng)
        facts.extend(facts_rolled)

        outcome = outcome_for(chance_kept, risk_kept)
        # The question is master-authored and may name unrevealed canon: never told.
        facts.append(Fact(trace=f"asked: {args.question}"))
        line = _oracle_line(args, opponent, outcome)
        answered_at = len(facts)
        facts.append(actor.fact(line))
        effects: tuple[str, ...] = ()
        if opponent is not None:
            struck, ended = _strike(draft, actor, opponent, outcome)
            exchange, effects = _absorbed(struck)
            facts.extend(exchange)
            if not ended:
                draft.pending = PendingDecision(
                    kind="conflict",
                    prompt=world.conflict_prompt(actor, opponent),
                    options=(),
                    allows_text=True,
                )
        # SRD: the Twist Counter skips Harm & Luck, so a tied conflict roll never ticks it.
        if chance_kept == risk_kept and opponent is None:
            world.twist.current += 1
            if world.twist.shortfall == 0:
                world.twist.current = 0
                facts.extend(self._twist(draft, actor, rng))
        facts[answered_at] = facts[answered_at].model_copy(
            update={"card": "\n".join((line, *effects)), "dice": (chance, risk)}
        )
        return facts

    def _twist(self, draft: Loner3eGame, actor: Loner3eCast, rng: Random) -> list[Fact]:
        """The SRD's table is rolled here so the dice trace; the model only reads the pairing."""
        faces = (DIE_FACE, DIE_FACE)
        rolled, rolled_fact = roll(faces, "twist — subject, action", rng)
        subject, action = twist_pairing(rolled[0], rolled[1], self.twist_table())
        draft.note(TWIST_NOTE.format(subject=subject.upper(), action=action.upper()))
        # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
        due = actor.fact(
            f"a twist interrupts the scene: {subject} / {action}",
            card=f"Twist — {subject} / {action}",
            dice=(DiceEvent(label="Twist", faces=faces, rolled=rolled),),
        )
        return [rolled_fact, due]


def _oracle_line(args: Roll, opponent: Loner3eCast | None, outcome: Outcome) -> str:
    footing = args.position + (f" ({args.edge})" if args.edge else "")
    against = f" against {opponent.name}" if opponent is not None else ""
    return f"{args.what}{against} — oracle, {footing}: {outcome.wording}"


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(fact.card for fact in exchange if fact.told and fact.card)
    return [fact.model_copy(update={"card": ""}) for fact in exchange], lines


def _strike(
    draft: Loner3eGame, actor: Loner3eCast, opponent: Loner3eCast, outcome: Outcome
) -> tuple[list[Fact], bool]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    why = f"{striker.name} gets the better of the exchange"
    facts = hit.luck.change(hit, -abs(harm), "Luck", why)
    if hit.luck.current != 0:
        return facts, False
    draft.note(DEFEAT_NOTE.format(name=hit.name))
    lost = f"{hit.name} is out of luck"
    facts.append(hit.fact(lost, card=lost))
    # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
    facts.extend(hit.refill("the conflict is over"))
    facts.extend(striker.refill("the conflict is over"))
    return facts, True


def _check_ready(actor: Loner3eCast, opponent: Loner3eCast | None) -> None:
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


def _pair(args: Roll, rng: Random) -> tuple[int, DiceEvent, int, DiceEvent, list[Fact]]:
    chance_faces = (DIE_FACE, DIE_FACE) if args.position == "advantage" else (DIE_FACE,)
    risk_faces = (DIE_FACE, DIE_FACE) if args.position == "disadvantage" else (DIE_FACE,)
    asked = args.question
    chance_kept, chance, chance_fact = roll_pool(
        chance_faces, f"{asked} — chance", rng, label="Chance"
    )
    risk_kept, risk, risk_fact = roll_pool(risk_faces, f"{asked} — risk", rng, label="Risk")
    return chance_kept, chance, risk_kept, risk, [chance_fact, risk_fact]
