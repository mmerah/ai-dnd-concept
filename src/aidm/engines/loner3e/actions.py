from random import Random
from typing import Literal

from pydantic import Field

from aidm.engines.counters import adjust
from aidm.engines.sheets import require_sheet
from aidm.state.actions import require_actor_here, reveal
from aidm.state.base import Entity, EntityId, Frozen, Slug
from aidm.state.dice import roll_pool
from aidm.state.facts import Fact, entity_fact
from aidm.state.resolution import Resolution
from aidm.state.world import Game

from .mechanics import LUCK_MAX, TIES_PER_TWIST, Mechanics

HARM: dict[Slug, int] = {
    "yes-and": 3,
    "yes": 2,
    "yes-but": 1,
    "no-but": -1,
    "no": -2,
    "no-and": -3,
}

type Position = Literal["advantage", "neutral", "disadvantage"]


class Question(Frozen):
    actor_id: EntityId = Field(
        description="Exact id of the actor the question is about: the player, or an actor here."
    )
    question: str = Field(
        min_length=1,
        description="The closed dramatic question the dice answer, phrased so that yes is what "
        "the actor wants.",
    )
    position: Position = Field(
        default="neutral",
        description="Your judgment of the fiction: which side the tags and the scene favour.",
    )
    edge: str = Field(
        default="",
        description="The tag or circumstance that decided the position, in a few words. Empty "
        "for neutral.",
    )
    opponent_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor opposed in this exchange of a conflict, or null.",
    )


def twist_pairing(
    subject: int, action: int, twists: tuple[tuple[str, str], ...]
) -> tuple[str, str]:
    """Subject from one d6, action from the other, as the SRD's twist table is read."""
    return twists[subject - 1][0], twists[action - 1][1]


def twist_note(subject: str, action: str) -> str:
    return (
        f"A twist has just interrupted the scene: {subject.upper()} / {action.upper()} — the "
        "narration showed it arriving. Develop it this turn: what it set in motion, what it "
        "costs, what it changes."
    )


def defeat_note(name: str) -> str:
    return (
        f"{name} has run out of luck and lost this conflict. Ask nothing further of it: say how it "
        "ends for them — taken, broken off, cornered, conceding — and let the story move on."
    )


def outcome_for(chance: int, risk: int) -> Slug:
    if chance == risk:
        return "yes-but"
    side = "yes" if chance > risk else "no"
    if min(chance, risk) >= 4:
        return f"{side}-and"
    if max(chance, risk) <= 3:
        return f"{side}-but"
    return side


def resolve_question(
    draft: Game, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = reveal(draft, action.actor_id)
    mechanics = Mechanics.of(draft)
    _ = require_sheet(mechanics.sheets, actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = require_actor_here(draft, action.opponent_id)
        facts.extend(reveal(draft, action.opponent_id))
    _refuse_unless_ready(actor, mechanics, opponent)

    chance, risk, facts_rolled = _pair(action, rng)
    facts.extend(facts_rolled)

    outcome = outcome_for(chance, risk)
    facts.append(
        entity_fact(
            actor,
            "question_answered",
            f"{action.question} -> {outcome}",
            {
                "outcome": outcome,
                "chance": chance,
                "risk": risk,
                "position": action.position,
                "edge": action.edge,
            },
        )
    )
    if opponent is not None:
        facts.extend(_strike(draft, mechanics, actor, opponent, outcome))
    elif chance == risk:
        # The tally itself never becomes a fact: it paces the Director, and the Narrator would
        # only be handed a number it is told never to recite. A conflict exchange never ticks it.
        mechanics.twist.current += 1
        if mechanics.twist.current >= TIES_PER_TWIST:
            mechanics.twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    return Resolution(facts=tuple(facts))


def apply_restore_luck(draft: Game, actor_id: EntityId) -> list[Fact]:
    actor = require_actor_here(draft, actor_id)
    facts = reveal(draft, actor.id)
    luck = require_sheet(Mechanics.of(draft).sheets, actor).luck
    refill = (luck.maximum or LUCK_MAX) - luck.current
    # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
    return [*facts, *adjust(actor, "luck", luck, refill, "the conflict is behind them")]


def _twist(
    draft: Game, actor: Entity, rng: Random, twists: tuple[tuple[str, str], ...]
) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the Director only reads the pairing."""
    subject_die, subject_fact = roll_pool((6,), "twist — subject", rng)
    action_die, action_fact = roll_pool((6,), "twist — action", rng)
    subject, action = twist_pairing(subject_die, action_die, twists)
    draft.world.pending_notes = (*draft.world.pending_notes, twist_note(subject, action))
    # Narrated the turn it lands, as the SRD interrupts the scene: an unnamed intrusion needs
    # no canon, and the note steers the next turn's development.
    due = entity_fact(
        actor,
        "twist_due",
        f"a twist interrupts the scene: {subject} / {action}",
        {"subject": subject, "action": action},
    )
    return [subject_fact, action_fact, due]


def _strike(
    draft: Game, mechanics: Mechanics, actor: Entity, opponent: Entity, outcome: Slug
) -> list[Fact]:
    harm = HARM[outcome]
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    luck = require_sheet(mechanics.sheets, hit).luck
    facts = adjust(hit, "luck", luck, -abs(harm), f"{striker.name} gets the better of the exchange")
    if luck.current == 0:
        draft.world.pending_notes = (*draft.world.pending_notes, defeat_note(hit.name))
        facts.append(entity_fact(hit, "conflict_lost", f"{hit.name} is out of luck", {}))
        # SRD: luck resets after conflicts, and a side at 0 is the only end the engine can see.
        for side in (hit, striker):
            pool = require_sheet(mechanics.sheets, side).luck
            refill = (pool.maximum or LUCK_MAX) - pool.current
            facts.extend(adjust(side, "luck", pool, refill, "the conflict is over"))
    return facts


def _refuse_unless_ready(actor: Entity, mechanics: Mechanics, opponent: Entity | None) -> None:
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise ValueError(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if require_sheet(mechanics.sheets, side).luck.current == 0:
            raise ValueError(
                f"{side.name} is already out of luck, so that conflict is over. Settle what it "
                "costs them instead of rolling it again."
            )


def _pair(action: Question, rng: Random) -> tuple[int, int, list[Fact]]:
    """One extra die at most, and only for the side the judged position favours."""
    chance_faces = (6, 6) if action.position == "advantage" else (6,)
    risk_faces = (6, 6) if action.position == "disadvantage" else (6,)
    chance, chance_fact = roll_pool(chance_faces, f"{action.question} — chance", rng)
    risk, risk_fact = roll_pool(risk_faces, f"{action.question} — risk", rng)
    return chance, risk, [chance_fact, risk_fact]
