from collections.abc import Mapping
from random import Random
from typing import Literal, Protocol, runtime_checkable

from pydantic import Field

from aidm.engines.actions import Action
from aidm.engines.counters import adjust
from aidm.engines.loader import Engine
from aidm.engines.sheets import require_sheet
from aidm.engines.tags import carriers, tag_key
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import Entity, EntityId, Slug
from aidm.state.dice import roll_pool
from aidm.state.effects import Reveal
from aidm.state.facts import Fact, entity_fact
from aidm.state.plan import Beat, Resolution, TurnPlanBase
from aidm.state.world import GameState

from .mechanics import LUCK_MAX, TIES_PER_TWIST, Loner3eEffect, Mechanics

HARM: dict[Slug, int] = {
    "yes-and": 3,
    "yes": 2,
    "yes-but": 1,
    "no-but": -1,
    "no": -2,
    "no-and": -3,
}

type Position = Literal["advantage", "neutral", "disadvantage"]


class Question(Action):
    """A closed dramatic question, answered by Chance d6 against Risk d6."""

    act: Literal["question"] = "question"
    actor_id: EntityId = Field(
        description="Exact id of the actor the question is about: the player, or an actor here."
    )
    question: str = Field(
        min_length=1,
        description="The closed dramatic question the dice answer, phrased so that yes is what "
        "the actor wants.",
    )
    leverage: tuple[str, ...] = Field(
        default=(),
        max_length=3,
        description="Tags that make this easier, each copied exactly as it is written on the "
        "actor's sheet or on a trait in the scene. Empty when none applies; you cannot invent one.",
    )
    trouble: tuple[str, ...] = Field(
        default=(),
        max_length=3,
        description="Tags that make this harder, copied the same way. Empty when none applies.",
    )
    opponent_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor opposing this, set only when the question is one "
        "exchange of a conflict; the engine then takes luck off whichever side loses it.",
    )

    def resolve(self, engine: Engine, draft: GameState, rng: Random) -> Resolution:
        return resolve_question(draft, self, rng, twist_table_of(engine, draft))


class TurnBeat(Beat[Loner3eEffect, Question]):
    action: Question | None = Field(
        default=None,
        description="The one question this beat resolves, or null when nothing is uncertain "
        "enough to ask.",
    )


class TurnPlan(TurnBeat, TurnPlanBase):
    """The turn's framing and its first beat."""


@runtime_checkable
class TwistTables(Protocol):
    def twists(self, state: GameState) -> tuple[tuple[str, str], ...]: ...


def twist_table_of(engine: Engine, state: GameState) -> tuple[tuple[str, str], ...]:
    """The twist table is the engine's content, not the state's, so the action reads it here."""
    if not isinstance(engine, TwistTables):
        raise ValueError("the loner3e question needs the loner3e engine")
    return engine.twists(state)


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


def available_tags(draft: GameState, actor: Entity, mechanics: Mechanics) -> dict[str, str]:
    known: dict[str, str] = {}
    for carrier in carriers(draft, actor):
        sheet = mechanics.sheets.get(carrier.id)
        for tag in sheet.tags() if sheet is not None else ():
            known[tag_key(tag)] = tag
        for trait in carrier.traits:
            known[tag_key(trait.id)] = trait.name
            known[tag_key(trait.name)] = trait.name
    return known


def resolve_question(
    draft: GameState, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> Resolution:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    mechanics = draft.mechanics_as(Mechanics)
    _ = require_sheet(mechanics.sheets, actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = require_actor_here(draft, action.opponent_id)
        facts.extend(apply_effect(draft, Reveal(entity_id=action.opponent_id)))
    known = available_tags(draft, actor, mechanics)
    _refuse_unless_ready(known, actor, action, mechanics, opponent)

    leverage = {known[tag_key(tag)] for tag in action.leverage}
    trouble = {known[tag_key(tag)] for tag in action.trouble}
    # A tag counts once however often it is named, and cancels the same tag on the other side.
    net = len(leverage - trouble) - len(trouble - leverage)
    position: Position = "advantage" if net > 0 else "disadvantage" if net < 0 else "neutral"

    chance, risk, facts_rolled = _pair(action, rng, position)
    facts.extend(facts_rolled)

    outcome = outcome_for(chance, risk)
    facts.append(
        entity_fact(
            actor,
            "question_answered",
            f"{action.question} -> {outcome}",
            {"outcome": outcome, "chance": chance, "risk": risk, "position": position},
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
    return Resolution(facts=tuple(facts), outcome=outcome)


def _twist(
    draft: GameState, actor: Entity, rng: Random, twists: tuple[tuple[str, str], ...]
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
    draft: GameState, mechanics: Mechanics, actor: Entity, opponent: Entity, outcome: Slug
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


def _refuse_unless_ready(
    known: Mapping[str, str],
    actor: Entity,
    action: Question,
    mechanics: Mechanics,
    opponent: Entity | None,
) -> None:
    for tag in (*action.leverage, *action.trouble):
        if tag_key(tag) not in known:
            written = ", ".join(sorted(set(known.values())))
            raise ValueError(
                f"{actor.name} has no tag {tag!r} to draw on. The tags in play are: {written}"
            )
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


def _pair(action: Question, rng: Random, position: Position) -> tuple[int, int, list[Fact]]:
    """One extra die at most, and only for the side the surviving tags favour."""
    chance_faces = (6, 6) if position == "advantage" else (6,)
    risk_faces = (6, 6) if position == "disadvantage" else (6,)
    chance, chance_fact = roll_pool(chance_faces, f"{action.question} — chance", rng)
    risk, risk_fact = roll_pool(risk_faces, f"{action.question} — risk", rng)
    return chance, risk, [chance_fact, risk_fact]
