import re
from collections.abc import Mapping
from random import Random
from typing import Literal

from aidm.engines.counters import adjust
from aidm.state.apply import apply_effect, entity_fact, require_actor_here
from aidm.state.base import Entity, Slug
from aidm.state.dice import RollMode, roll
from aidm.state.effects import Reveal
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .actions import Question
from .mechanics import TIES_PER_TWIST, Mechanics, Sheet, read, write

TWIST_TABLE: tuple[tuple[str, str], ...] = (
    ("A third party", "Appears"),
    ("The hero", "Alters the location"),
    ("An encounter", "Helps the hero"),
    ("A physical event", "Hinders the hero"),
    ("An emotional event", "Changes the goal"),
    ("An object", "Ends the scene"),
)
HARM: dict[Slug, int] = {
    "yes-and": 3,
    "yes": 2,
    "yes-but": 1,
    "no-but": -1,
    "no": -2,
    "no-and": -3,
}

type Position = Literal["advantage", "neutral", "disadvantage"]


def twist_pairing(subject: int, action: int) -> tuple[str, str]:
    """Subject from one d6, action from the other, as the SRD's twist table is read."""
    return TWIST_TABLE[subject - 1][0], TWIST_TABLE[action - 1][1]


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


def _key(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def available_tags(draft: GameState, actor: Entity, sheet: Sheet) -> dict[str, str]:
    known: dict[str, str] = {_key(tag): tag for tag in sheet.tags()}
    carriers = [actor, *draft.world.children(actor.id, "item")]
    place = draft.world.location_of(actor)
    if place is not None:
        carriers.append(draft.world.require(place))
        carriers.extend(draft.world.children(place))
    for carrier in carriers:
        for trait in carrier.traits:
            known[_key(trait.id)] = trait.name
            known[_key(trait.name)] = trait.name
    return known


def resolve_question(draft: GameState, action: Question, rng: Random) -> tuple[list[Fact], Slug]:
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    mechanics = read(draft)
    sheet = _sheet(mechanics, actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = require_actor_here(draft, action.opponent_id)
        facts.extend(apply_effect(draft, Reveal(entity_id=action.opponent_id)))
    known = available_tags(draft, actor, sheet)
    _refuse_unless_ready(known, actor, action, mechanics, opponent)

    leverage = {known[_key(tag)] for tag in action.leverage}
    trouble = {known[_key(tag)] for tag in action.trouble}
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
            facts.extend(_twist(draft, actor, rng))
    write(draft, mechanics)
    return facts, outcome


def _twist(draft: GameState, actor: Entity, rng: Random) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the Director only reads the pairing."""
    subject_die, subject_fact = roll("1d6", "twist — subject", rng)
    action_die, action_fact = roll("1d6", "twist — action", rng)
    subject, action = twist_pairing(subject_die.total, action_die.total)
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


def _sheet(mechanics: Mechanics, actor: Entity) -> Sheet:
    sheet = mechanics.sheets.get(actor.id)
    if sheet is None:
        raise ValueError(f"{actor.name} has no character sheet")
    return sheet


def _strike(
    draft: GameState, mechanics: Mechanics, actor: Entity, opponent: Entity, outcome: Slug
) -> list[Fact]:
    harm = HARM[outcome]
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    luck = _sheet(mechanics, hit).luck
    facts = adjust(hit, "luck", luck, -abs(harm), f"{striker.name} gets the better of the exchange")
    if luck.current == 0:
        draft.world.pending_notes = (*draft.world.pending_notes, defeat_note(hit.name))
        facts.append(entity_fact(hit, "conflict_lost", f"{hit.name} is out of luck", {}))
    return facts


def _refuse_unless_ready(
    known: Mapping[str, str],
    actor: Entity,
    action: Question,
    mechanics: Mechanics,
    opponent: Entity | None,
) -> None:
    for tag in (*action.leverage, *action.trouble):
        if _key(tag) not in known:
            written = ", ".join(sorted(set(known.values())))
            raise ValueError(
                f"{actor.name} has no tag {tag!r} to draw on. The tags in play are: {written}"
            )
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise ValueError(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if _sheet(mechanics, side).luck.current == 0:
            raise ValueError(
                f"{side.name} is already out of luck, so that conflict is over. Settle what it "
                "costs them instead of rolling it again."
            )


def _pair(action: Question, rng: Random, position: Position) -> tuple[int, int, list[Fact]]:
    """One extra die at most, and only for the side the surviving tags favour."""
    chance_mode: RollMode = "advantage" if position == "advantage" else "normal"
    risk_mode: RollMode = "advantage" if position == "disadvantage" else "normal"
    chance, chance_fact = roll("1d6", f"{action.question} — chance", rng, mode=chance_mode)
    risk, risk_fact = roll("1d6", f"{action.question} — risk", rng, mode=risk_mode)
    return chance.total, risk.total, [chance_fact, risk_fact]
