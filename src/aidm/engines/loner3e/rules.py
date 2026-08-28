from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from aidm.engines.core import Decision, ProposalBase, adjust, pool
from aidm.engines.sheets import ItemBase, SheetBase, SheetMechanics, require_sheet
from aidm.state.actions import require_actor_here, roll_pool
from aidm.state.entities import CheckedEntityId, Counter, Entity, EntityId, Frozen, Slug
from aidm.state.facts import DiceEvent, EventBadge, Fact, MechanicEvent, entity_fact
from aidm.state.model import Game


@dataclass(frozen=True, slots=True)
class Rules:
    """Loner 3e's numbers in one place; docs/LONER-3E.md points at the SRD and its deviations."""

    luck_max: int = 6
    ties_per_twist: int = 3
    die_face: int = 6  # every roll in the game is one d6, and every table is six rows
    and_at: int = 4  # both dice 4+ sharpens the answer to -and
    but_at: int = 3  # both dice 3 or under softens it to -but


RULES = Rules()


SRD_PACK: Slug = "srd"


class PackEntry(Frozen):
    id: Slug
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


def twist_table(packs: Mapping[str, Pack], chosen: Slug) -> tuple[tuple[str, str], ...]:
    """The chosen set's own twist columns, or the SRD's: AP01 and most user packs publish none."""
    pack = packs.get(chosen)
    if pack is None:
        raise ValueError(f"the {chosen!r} table set is not installed")
    source = pack if pack.twist_subjects is not None else packs.get(SRD_PACK)
    if source is None or source.twist_subjects is None or source.twist_actions is None:
        raise ValueError(f"neither the {chosen!r} table set nor the SRD one carries twists")
    return tuple(zip(source.twist_subjects, source.twist_actions, strict=True))


class Conflict(Decision):
    """The hand-back is the whole decision: no options, no payload, nothing to resolve."""

    kind: ClassVar[Slug] = "conflict"


def conflict_prompt(state: Game, actor: Entity, opponent: Entity) -> str:
    foe = actor if opponent.id == state.player_id else opponent
    return (
        f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
        "attack, try something else, or break away — what do you do?"
    )


class Sheet(SheetBase, ItemBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    twist_pack: Slug = SRD_PACK
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=RULES.luck_max, maximum=RULES.luck_max)
    milestones: Counter = Counter(current=0)

    @model_validator(mode="after")
    def _twist_pack_is_selected(self) -> Self:
        if self.twist_pack not in self.packs:
            raise ValueError("twist_pack must be one of the sheet packs")
        return self

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Concept", self.concept),
            ("Skills", ", ".join(self.skills)),
            ("Frailties", ", ".join(self.frailties)),
            ("Gear", ", ".join(self.gear)),
            ("Luck", pool(self.luck)),
        )


class Mechanics(SheetMechanics[Sheet]):
    # One tally for the whole game, as the note it fires says: a tie anywhere moves the same one.
    twist: Counter = Counter(current=0, maximum=RULES.ties_per_twist)


type Position = Literal["advantage", "neutral", "disadvantage"]


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


@dataclass(frozen=True, slots=True)
class Outcome:
    """One of the six answers, carrying the luck an exchange costs the side that lost it."""

    name: Slug
    harm: int


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome("yes-but", 1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= RULES.and_at:
        return Outcome(f"{side}-and", 3 * sign)
    if max(chance, risk) <= RULES.but_at:
        return Outcome(f"{side}-but", sign)
    return Outcome(side, 2 * sign)


def resolve_question(
    draft: Game, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    mechanics = Mechanics.of_game(draft)
    _ = require_sheet(mechanics.sheets, actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = _require_opponent_here(draft, action.opponent_id)
        # SRD "Everything is a Character": a thing gets its sheet the first time one is asked for.
        mechanics.sheets.setdefault(opponent.id, Sheet())
        facts.extend(draft.reveal(opponent))
    _refuse_unless_ready(actor, mechanics, opponent)

    chance, risk, facts_rolled = _pair(action, rng)
    facts.extend(facts_rolled)

    outcome = outcome_for(chance.kept, risk.kept)
    answered_at = len(facts)
    facts.append(entity_fact(actor, "question_answered", f"{action.question} -> {outcome.name}"))
    effects: tuple[str, ...] = ()
    if opponent is not None:
        exchange, effects = _absorbed(_strike(draft, mechanics, actor, opponent, outcome))
        facts.extend(exchange)
        # The pools are refilled the moment a side hits 0, so only the fact says the conflict ended.
        if not any(fact.kind == "conflict_lost" for fact in exchange):
            draft.pending = Conflict().pending(conflict_prompt(draft, actor, opponent))
    if chance.kept == risk.kept:
        mechanics.twist.current += 1
        if _shortfall(mechanics.twist) == 0:
            mechanics.twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    # The question is director-authored and names unrevealed canon even on a "no": never shown.
    oracle = MechanicEvent(
        title="Oracle",
        badges=_badges(action),
        dice=(chance, risk),
        outcome=outcome.name,
        effects=effects,
    )
    facts[answered_at] = facts[answered_at].model_copy(update={"event": oracle})
    return tuple(facts)


def _require_opponent_here(draft: Game, opponent_id: EntityId) -> Entity:
    """SRD "Everything is a Character": a ship, an object or a curse resists as an actor does."""
    opponent = draft.world.require(opponent_id)
    if opponent.kind == "actor":
        return require_actor_here(draft, opponent_id)
    if opponent.kind != "item":
        raise ValueError(
            f"{opponent_id!r} is a {opponent.kind}, which cannot resist. "
            "Name an actor or an item here."
        )
    if not draft.is_here(opponent):
        raise ValueError(
            f"{opponent_id!r} is not here with the player. "
            "Bring it here first, or act on what is here."
        )
    return opponent


def _badges(action: Question) -> tuple[EventBadge, ...]:
    position = EventBadge(label="Position", value=action.position.capitalize())
    if not action.edge:
        return (position,)
    return (position, EventBadge(label="Edge", value=action.edge))


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(f.event.title for f in exchange if f.told and f.event is not None)
    return [f.model_copy(update={"event": None}) for f in exchange], lines


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
        *adjust(draft, actor, "luck", luck, refill, "the conflict is behind them", "favorite"),
    ]


def _twist(
    draft: Game, actor: Entity, rng: Random, twists: tuple[tuple[str, str], ...]
) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the Director only reads the pairing."""
    face = (RULES.die_face,)
    subject_die, subject_fact = roll_pool(face, "twist — subject", rng, label="Subject")
    action_die, action_fact = roll_pool(face, "twist — action", rng, label="Action")
    subject, action = twist_pairing(subject_die.kept, action_die.kept, twists)
    draft.world.pending_notes = (*draft.world.pending_notes, twist_note(subject, action))
    # Echo the unnamed SRD intrusion in the call that rolled it without adding canon.
    due = entity_fact(
        actor,
        "twist_due",
        f"a twist interrupts the scene: {subject} / {action}",
        event=MechanicEvent(
            title="Twist",
            badges=(
                EventBadge(label="Subject", value=subject),
                EventBadge(label="Action", value=action),
            ),
            dice=(subject_die, action_die),
            icon="bolt",
        ),
    )
    return [subject_fact, action_fact, due]


def _strike(
    draft: Game, mechanics: Mechanics, actor: Entity, opponent: Entity, outcome: Outcome
) -> list[Fact]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    luck = require_sheet(mechanics.sheets, hit).luck
    why = f"{striker.name} gets the better of the exchange"
    facts = adjust(draft, hit, "luck", luck, -abs(harm), why, "favorite")
    if luck.current == 0:
        draft.world.pending_notes = (*draft.world.pending_notes, defeat_note(hit.name))
        lost = f"{hit.name} is out of luck"
        card = MechanicEvent(title=lost, icon="favorite")
        facts.append(entity_fact(hit, "conflict_lost", lost, event=card))
        # SRD: luck resets after conflicts, and a side at 0 is the only end the engine can see.
        for side in (hit, striker):
            pool = require_sheet(mechanics.sheets, side).luck
            refill = _shortfall(pool)
            facts.extend(
                adjust(draft, side, "luck", pool, refill, "the conflict is over", "favorite")
            )
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


def _pair(action: Question, rng: Random) -> tuple[DiceEvent, DiceEvent, list[Fact]]:
    """One extra die at most, and only for the side the judged position favours."""
    face = RULES.die_face
    chance_faces = (face, face) if action.position == "advantage" else (face,)
    risk_faces = (face, face) if action.position == "disadvantage" else (face,)
    asked = action.question
    chance, chance_fact = roll_pool(chance_faces, f"{asked} — chance", rng, label="Chance")
    risk, risk_fact = roll_pool(risk_faces, f"{asked} — risk", rng, label="Risk")
    return chance, risk, [chance_fact, risk_fact]


GROWTH = (
    "Choose the changes this adventure earned: a new skill, signature gear, a frailty, or a "
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
    why: str = Field(description="One short reason, in the fiction, for this change.")

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.kind == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class AdventureGrowth(ProposalBase):
    """All sheet changes earned by one adventure."""

    changes: tuple[Change, ...] = Field(
        min_length=1,
        description="Every earned change, in reading order.",
    )
