from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import DEAD, CheckedEntityId, Counter, EntityId, Frozen, Slug
from aidm.core.facts import DiceEvent, Fact
from aidm.core.play import DecisionOption, PendingDecision
from aidm.engines.core import adjust, keep_highest
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.state import (
    AND_AT,
    BUT_AT,
    DIE_FACE,
    LUCK_MAX,
    SRD_PACK,
    ActorSheet,
    ItemSheet,
    Loner3eGame,
    LonerSheet,
    LonerWorld,
)
from aidm.kits.entities import Entity, entity_fact

type Actor = Entity[LonerSheet]

type Position = Literal["advantage", "neutral", "disadvantage"]

GROWTH = (
    "Choose the changes this adventure earned: a new skill, signature gear, a frailty, or a "
    "rewrite of an existing tag."
)

ADVANCE_SPENT = "Spend one advance a party member has earned, when the player asks for it. "


class Question(Frozen):
    actor_id: CheckedEntityId = Field(
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
    opponent_id: CheckedEntityId | None = Field(
        default=None,
        description=(
            "Exact id of the actor or item here that resists. Null when nothing fights back."
        ),
    )


@dataclass(frozen=True, slots=True)
class Outcome:
    """One of the six answers, carrying the luck an exchange costs the side that lost it."""

    name: Slug
    harm: int


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
    why: str = Field(description="One short reason, in the fiction, for this change.")

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.kind == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class AdventureGrowth(Frozen):
    """All sheet changes earned by one adventure."""

    subject_id: CheckedEntityId = Field(description="Exact id of the party member who advances.")
    changes: tuple[Change, ...] = Field(
        min_length=1,
        description="Every earned change, in reading order.",
    )


class RestoreLuck(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the player or an actor here.")


def twist_table(packs: Mapping[str, Pack], chosen: Slug) -> tuple[tuple[str, str], ...]:
    """The chosen set's own twist columns, or the SRD's: AP01 and most user packs publish none."""
    pack = packs.get(chosen)
    if pack is None:
        raise ValueError(f"the {chosen!r} table set is not installed")
    source = pack if pack.twist_subjects is not None else packs.get(SRD_PACK)
    if source is None or source.twist_subjects is None or source.twist_actions is None:
        raise ValueError(f"neither the {chosen!r} table set nor the SRD one carries twists")
    return tuple(zip(source.twist_subjects, source.twist_actions, strict=True))


def conflict_prompt(world: LonerWorld, actor: Actor, opponent: Actor) -> str:
    foe = actor if opponent.id == world.player_id else opponent
    return (
        f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
        "attack, try something else, or break away — what do you do?"
    )


def luck_of(one: Actor) -> Counter:
    """Every side of a conflict rolls by a sheet: one nobody wrote is refused, not invented."""
    if one.sheet is None:
        raise ValueError(f"{one.name} has no character sheet")
    return one.sheet.luck


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
        "ends for them — taken, severely injured, broken off, cornered, conceding — write any "
        "lasting mark the ending leaves with `add_trait`, and let the story move on."
    )


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome("yes-but", 1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= AND_AT:
        return Outcome(f"{side}-and", 3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(f"{side}-but", sign)
    return Outcome(side, 2 * sign)


def resolve_question(
    draft: Loner3eGame, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> tuple[Fact, ...]:
    world = draft.payload.world
    actor = world.require_actor_here(action.actor_id)
    facts = world.reveal(actor)
    opponent: Actor | None = None
    if action.opponent_id is not None:
        opponent = _sheeted(_require_opponent_here(world, action.opponent_id))
        facts.extend(world.reveal(opponent))
    _refuse_unless_ready(actor, opponent)

    chance_kept, chance, risk_kept, risk, facts_rolled = _pair(action, rng)
    facts.extend(facts_rolled)

    outcome = outcome_for(chance_kept, risk_kept)
    answered_at = len(facts)
    facts.append(entity_fact(actor, "question_answered", f"{action.question} -> {outcome.name}"))
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
    if chance_kept == risk_kept:
        twist = draft.payload.twist
        twist.current += 1
        if _shortfall(twist) == 0:
            twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    # The question is master-authored and names unrevealed canon even on a "no": never shown.
    edge = f" ({action.edge})" if action.edge else ""
    card = "\n".join((f"Oracle — {action.position.capitalize()}{edge} → {outcome.name}", *effects))
    facts[answered_at] = facts[answered_at].model_copy(
        update={"card": card, "dice": (chance, risk)}
    )
    return tuple(facts)


def apply_restore_luck(draft: Loner3eGame, actor_id: EntityId) -> list[Fact]:
    actor = draft.payload.world.require_actor_here(actor_id)
    facts = draft.payload.world.reveal(actor)
    # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
    facts.extend(_refill(draft, actor, "the conflict is behind them"))
    return facts


def close_conflicts(draft: Loner3eGame) -> tuple[Fact, ...]:
    """A scene ends its conflicts so nobody carries a spent pool on; the dead keep theirs."""
    facts: list[Fact] = []
    for one in draft.payload.world.here():
        if one.sheet is not None and one.trait(DEAD) is None and one.sheet.luck.current < LUCK_MAX:
            facts.extend(_refill(draft, one, "the scene is over"))
    return tuple(facts)


def party(state: Loner3eGame) -> tuple[EntityId, ...]:
    return (state.payload.world.player_id, *state.payload.world.companions)


def advances_owed(state: Loner3eGame) -> tuple[tuple[str, str], ...]:
    """Chapters played standing above the ledger of advances taken, one note each."""
    # An advance mid-suspension could invalidate the frozen call an open decision holds.
    if state.pending is not None:
        return ()
    owed = [
        f"- {state.payload.world.require(one).name} has an advance owed; call advance only "
        "when the player asks for it."
        for one in party(state)
        if _advance_owed(state, one)
    ]
    return (("ADVANCES OWED", "\n".join(owed)),) if owed else ()


def complete_chapter(draft: Loner3eGame) -> tuple[Fact, ...]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    ending = "the adventure has ended"
    for member_id in party(draft):
        sheet = draft.payload.world.require(member_id).sheet
        if isinstance(sheet, ActorSheet):
            sheet.chapters += 1
    return (Fact(kind="chapter_completed", trace=ending, told=True, card=ending),)


def advance(draft: Loner3eGame, proposal: AdventureGrowth, rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    del rng
    subject: Actor = _party_member(draft, proposal.subject_id)
    sheet = _actor_sheet(subject)
    if sheet.chapters <= sheet.milestones:
        raise ValueError(f"{subject.name} has no advance owed")
    # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
    granted = tuple(
        _rewrite(sheet, subject, change)
        if change.kind == "rewrite"
        else _gain(sheet, subject, change)
        for change in proposal.changes
    )
    sheet.milestones += 1
    spent = entity_fact(
        subject,
        "milestone_spent",
        f"{draft.payload.world.label(subject)} milestones -> {sheet.milestones} "
        "(a milestone spent)",
        card=f"{subject.name}: milestone {sheet.milestones} spent",
    )
    return (*granted, spent)


def meanings(
    packs: Mapping[str, Pack], selected: Sequence[Slug], sheet: ActorSheet
) -> tuple[tuple[str, str], ...]:
    chosen = tuple(packs[pack_id] for pack_id in selected)
    # The concept's pack blurb is generic where the entity's own brief is not: skip it.
    return _pack_meanings(
        tuple(entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)),
        (*sheet.skills, *sheet.frailties, *sheet.gear),
    )


def twists(packs: Mapping[str, Pack], state: Loner3eGame) -> tuple[tuple[str, str], ...]:
    return twist_table(packs, state.payload.twist_pack)


def _sheeted(one: Actor) -> Actor:
    """SRD "Everything is a Character": a thing gets its sheet the first time one is asked for."""
    if one.kind == "item" and one.sheet is None:
        one.sheet = ItemSheet()
    return one


def _require_opponent_here(world: LonerWorld, opponent_id: EntityId) -> Actor:
    """SRD "Everything is a Character": a ship, an object or a curse resists as an actor does."""
    opponent = world.require(opponent_id)
    if opponent.kind == "actor":
        return world.require_actor_here(opponent_id)
    if opponent.kind != "item":
        raise ValueError(
            f"{opponent_id!r} is a {opponent.kind}, which cannot resist. "
            "Name an actor or an item here."
        )
    if opponent.id not in world.run.present:
        raise ValueError(
            f"{opponent_id!r} is not here with the player. "
            "Bring it here first, or act on what is here."
        )
    return opponent


def _actor_sheet(one: Actor) -> ActorSheet:
    if not isinstance(one.sheet, ActorSheet):
        raise ValueError(f"{one.name} has no character sheet")
    return one.sheet


def _party_member(draft: Loner3eGame, subject_id: EntityId) -> Actor:
    """An advance is a party member's own: nobody else's sheet is an engine's to grow."""
    subject = draft.payload.world.require(subject_id)
    if subject_id not in party(draft):
        raise ValueError(f"{subject.name} is not in the party")
    return subject


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(fact.card for fact in exchange if fact.told and fact.card)
    return [fact.model_copy(update={"card": ""}) for fact in exchange], lines


def _shortfall(pool: Counter) -> int:
    """How far a bounded pool sits below full; every pool this engine declares has a maximum."""
    if pool.maximum is None:
        raise ValueError("an unbounded pool has no full to measure against")
    return pool.maximum - pool.current


def _refill(draft: Loner3eGame, side: Actor, why: str) -> list[Fact]:
    luck = luck_of(side)
    return adjust(draft.payload.world.player_id, side, "luck", luck, _shortfall(luck), why)


def _twist(
    draft: Loner3eGame, actor: Actor, rng: Random, twists: tuple[tuple[str, str], ...]
) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the model only reads the pairing."""
    face = (DIE_FACE,)
    subject_kept, subject_die, subject_fact = keep_highest(
        face, "twist — subject", rng, label="Subject"
    )
    action_kept, action_die, action_fact = keep_highest(face, "twist — action", rng, label="Action")
    subject, action = twist_pairing(subject_kept, action_kept, twists)
    draft.notes = (*draft.notes, twist_note(subject, action))
    # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
    due = entity_fact(
        actor,
        "twist_due",
        f"a twist interrupts the scene: {subject} / {action}",
        card=f"Twist — {subject} / {action}",
        dice=(subject_die, action_die),
    )
    return [subject_fact, action_fact, due]


def _strike(draft: Loner3eGame, actor: Actor, opponent: Actor, outcome: Outcome) -> list[Fact]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    why = f"{striker.name} gets the better of the exchange"
    luck = luck_of(hit)
    facts = adjust(draft.payload.world.player_id, hit, "luck", luck, -abs(harm), why)
    if luck.current != 0:
        return facts
    draft.notes = (*draft.notes, defeat_note(hit.name))
    draft.payload.world.run.spent = f"the conflict with {hit.name} is settled"
    lost = f"{hit.name} is out of luck"
    facts.append(entity_fact(hit, "conflict_lost", lost, card=lost))
    # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
    facts.extend(_refill(draft, hit, "the conflict is over"))
    facts.extend(_refill(draft, striker, "the conflict is over"))
    return facts


def _refuse_unless_ready(actor: Actor, opponent: Actor | None) -> None:
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise ValueError(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if luck_of(side).current == 0:
            raise ValueError(
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


def _gain(sheet: ActorSheet, subject: Actor, change: Change) -> Fact:
    if change.tag in (*sheet.skills, *sheet.gear, *sheet.frailties):
        raise ValueError(f"{subject.name} already has the tag {change.tag!r}")
    if change.kind == "skill":
        sheet.skills = (*sheet.skills, change.tag)
    elif change.kind == "gear":
        sheet.gear = (*sheet.gear, change.tag)
    else:
        sheet.frailties = (*sheet.frailties, change.tag)
    return entity_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag} ({change.why})",
        card=f"{subject.name}: new {change.kind} {change.tag}",
    )


def _rewrite(sheet: ActorSheet, subject: Actor, change: Change) -> Fact:
    old, new = change.tag, change.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    return entity_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new} ({change.why})",
        card=f"{subject.name}: {old} → {new}",
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


def _advance_owed(state: Loner3eGame, entity_id: EntityId) -> bool:
    sheet = state.payload.world.require(entity_id).sheet
    return isinstance(sheet, ActorSheet) and sheet.chapters > sheet.milestones


def _pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)
