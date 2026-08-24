from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.core import (
    ProposalBase,
    SheetBase,
    SheetMechanics,
    adjust,
    chipped,
    complete_chapter,
    counter_effect,
    dice_event,
    render_counters,
    require_dice_slot,
    require_sheet,
)
from aidm.state.actions import require_actor_here, roll_pool
from aidm.state.entities import PLAYER_ID, ContentSlug, Counter, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact, entity_fact
from aidm.state.model import Game
from aidm.state.play import EventBadge, MechanicEvent, PendingDecision


@dataclass(frozen=True, slots=True)
class Rules:
    """Loner 3e's numbers in one place; docs/LONER-3E.md names every deviation from the SRD."""

    luck_max: int = 6
    ties_per_twist: int = 3
    die_face: int = 6  # every roll in the game is one d6, and every table is six rows
    and_at: int = 4  # both dice 4+ sharpens the answer to -and
    but_at: int = 3  # both dice 3 or under softens it to -but


RULES = Rules()


SRD_PACK: ContentSlug = "srd"


class PackEntry(Frozen):
    id: ContentSlug
    label: str
    # Empty for packs whose entries are bare phrases, such as AP01.
    detail: str = ""


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    concepts: tuple[PackEntry, ...] = Field(min_length=1)
    skills: tuple[PackEntry, ...] = Field(min_length=1)
    frailties: tuple[PackEntry, ...] = Field(min_length=1)
    gear: tuple[PackEntry, ...] = Field(min_length=1)
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != RULES.die_face:
                raise ValueError("a twist column is one d6: exactly six entries")
        return self


def twist_table(packs: Mapping[str, Pack], chosen: ContentSlug) -> tuple[tuple[str, str], ...]:
    """The chosen set's own twist columns, or the SRD's: AP01 and most user packs publish none."""
    pack = packs.get(chosen)
    if pack is None:
        raise ValueError(f"the {chosen!r} table set is not installed")
    source = pack if pack.twist_subjects is not None else packs.get(SRD_PACK)
    if source is None or source.twist_subjects is None or source.twist_actions is None:
        raise ValueError(f"neither the {chosen!r} table set nor the SRD one carries twists")
    return tuple(zip(source.twist_subjects, source.twist_actions, strict=True))


def conflict_prompt(actor: Entity, opponent: Entity) -> str:
    foe = actor if opponent.id == PLAYER_ID else opponent
    return f"The exchange with {foe.name} is over, but the conflict continues. What do you do?"


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    # The table set this character was built from; the twist table is read from it.
    pack: ContentSlug = SRD_PACK
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=RULES.luck_max, maximum=RULES.luck_max)
    milestones: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"luck": self.luck}


class Mechanics(SheetMechanics[Sheet]):
    # One tally for the whole game, as the note it fires says: a tie anywhere moves the same one.
    twist: Counter = Counter(current=0, maximum=RULES.ties_per_twist)


def describe_entity(mechanics: Mechanics, entity: Entity) -> str:
    sheet = mechanics.sheets.get(entity.id)
    if sheet is None:
        return ""
    lines = (
        f"concept: {sheet.concept}" if sheet.concept else "",
        f"skills: {', '.join(sheet.skills)}" if sheet.skills else "",
        f"frailties: {', '.join(sheet.frailties)}" if sheet.frailties else "",
        f"gear: {', '.join(sheet.gear)}" if sheet.gear else "",
        f"pools: {render_counters(sheet.counters())}",
    )
    return "\n".join(line for line in lines if line)


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
        description="Exact id of the player or actor here who takes the action."
    )
    question: str = Field(
        min_length=1,
        description="Closed question where yes means the actor gets what they want.",
    )
    position: Position = Field(
        default="neutral",
        description="Which side the relevant tags and situation favour.",
    )
    edge: str = Field(
        default="",
        description="Tag or circumstance that sets the position. Empty for neutral.",
    )
    opponent_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor here who resists. Null when no actor fights back.",
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
    if min(chance, risk) >= RULES.and_at:
        return f"{side}-and"
    if max(chance, risk) <= RULES.but_at:
        return f"{side}-but"
    return side


def resolve_question(
    draft: Game, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    mechanics = Mechanics.of_game(draft)
    _ = require_sheet(mechanics.sheets, actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = require_actor_here(draft, action.opponent_id)
        facts.extend(draft.reveal(opponent))
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
                "question": action.question,
                "outcome": outcome,
                "chance": chance,
                "risk": risk,
                "position": action.position,
                "edge": action.edge,
            },
        )
    )
    if opponent is not None:
        exchange = _strike(draft, mechanics, actor, opponent, outcome)
        facts.extend(exchange)
        # The pools are refilled the moment a side hits 0, so only the fact says the conflict ended.
        if not any(fact.kind == "conflict_lost" for fact in exchange):
            draft.pending = PendingDecision(
                kind="conflict", prompt=conflict_prompt(actor, opponent), options=(), payload={}
            )
    elif chance == risk:
        # Keep pacing tallies from the Narrator and exclude conflict exchanges.
        mechanics.twist.current += 1
        if _shortfall(mechanics.twist) == 0:
            mechanics.twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    return tuple(facts)


def _shortfall(pool: Counter) -> int:
    """How far a bounded pool sits below full; every pool this engine declares has a maximum."""
    if pool.maximum is None:
        raise ValueError("an unbounded pool has no full to measure against")
    return pool.maximum - pool.current


def apply_restore_luck(draft: Game, actor_id: EntityId) -> list[Fact]:
    actor = require_actor_here(draft, actor_id)
    facts = draft.reveal(actor)
    luck = require_sheet(Mechanics.of_game(draft).sheets, actor).luck
    refill = _shortfall(luck)
    # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
    return [
        *facts,
        *chipped(adjust(actor, "luck", luck, refill, "the conflict is behind them"), "favorite"),
    ]


def apply_complete_chapter(draft: Game) -> list[Fact]:
    return complete_chapter(draft, "the adventure has ended")


def _twist(
    draft: Game, actor: Entity, rng: Random, twists: tuple[tuple[str, str], ...]
) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the Director only reads the pairing."""
    subject_die, subject_fact = roll_pool((RULES.die_face,), "twist — subject", rng, slot="subject")
    action_die, action_fact = roll_pool((RULES.die_face,), "twist — action", rng, slot="action")
    subject, action = twist_pairing(subject_die, action_die, twists)
    draft.world.pending_notes = (*draft.world.pending_notes, twist_note(subject, action))
    # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
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
            refill = _shortfall(pool)
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
    face = RULES.die_face
    chance_faces = (face, face) if action.position == "advantage" else (face,)
    risk_faces = (face, face) if action.position == "disadvantage" else (face,)
    chance, chance_fact = roll_pool(chance_faces, f"{action.question} — chance", rng, slot="chance")
    risk, risk_fact = roll_pool(risk_faces, f"{action.question} — risk", rng, slot="risk")
    return chance, risk, [chance_fact, risk_fact]


def question_events(facts: tuple[Fact, ...]) -> tuple[MechanicEvent, ...]:
    answered = next((fact for fact in facts if fact.kind == "question_answered"), None)
    if answered is None:
        raise ValueError("no 'question_answered' fact anchors this call")
    if answered.narrator is None:
        return ()
    badges = [EventBadge(label="Position", value=str(answered.data["position"]).capitalize())]
    edge = str(answered.data["edge"])
    if edge:
        badges.append(EventBadge(label="Edge", value=edge))
    # Kept in fact order, never regrouped by kind: that order is the story of the exchange.
    effects = [
        counter_effect(fact) if fact.kind == "counter_changed" else fact.narrator
        for fact in facts
        if fact.narrator is not None and fact.kind in ("counter_changed", "conflict_lost")
    ]
    # The question is director-authored and names unrevealed canon even on a "no": never shown.
    oracle = MechanicEvent(
        source="roll_question",
        title="Oracle",
        badges=tuple(badges),
        dice=(
            dice_event("Chance", require_dice_slot(facts, "chance")),
            dice_event("Risk", require_dice_slot(facts, "risk")),
        ),
        outcome=str(answered.data["outcome"]),
        effects=tuple(effects),
    )
    twist = next((fact for fact in facts if fact.kind == "twist_due"), None)
    if twist is None or twist.narrator is None:
        return (oracle,)
    return (oracle, _twist_event(twist, facts))


def _twist_event(twist: Fact, facts: tuple[Fact, ...]) -> MechanicEvent:
    return MechanicEvent(
        source="roll_question",
        title="Twist",
        badges=(
            EventBadge(label="Subject", value=str(twist.data["subject"])),
            EventBadge(label="Action", value=str(twist.data["action"])),
        ),
        dice=(
            dice_event("Subject", require_dice_slot(facts, "subject")),
            dice_event("Action", require_dice_slot(facts, "action")),
        ),
        icon="bolt",
    )


GROWTH = (
    "Choose 1-4 changes from this adventure: a new skill, signature gear, a frailty, or a "
    "rewrite of an existing tag."
)


class Change(Frozen):
    """One sheet change earned by the adventure."""

    kind: Literal["skill", "gear", "frailty", "rewrite"] = Field(
        description="Type of sheet change."
    )
    tag: str = Field(
        min_length=1,
        description="New title-case tag, or the exact current tag for a rewrite.",
    )
    into: str = Field(
        default="",
        description="New title-case tag for a rewrite. Empty for other kinds.",
    )

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.kind == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class AdventureGrowth(ProposalBase):
    """All sheet changes earned by one adventure."""

    changes: tuple[Change, ...] = Field(
        min_length=1,
        max_length=4,
        description="One to four earned changes, in reading order.",
    )
    why: str = Field(description="One short reason shown to the player before confirmation.")
