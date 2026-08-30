from collections.abc import Mapping
from dataclasses import dataclass
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.engines.core import (
    adjust,
    keep_highest,
    pool,
    rules,
    sheet_of,
)
from aidm.state.entities import (
    CheckedEntityId,
    Counter,
    Entity,
    EntityId,
    Frozen,
    Mutable,
    Slug,
)
from aidm.state.facts import DiceEvent, Fact, entity_fact
from aidm.state.model import Game
from aidm.state.play import DecisionOption, PendingDecision
from aidm.world.actions import require_actor_here
from aidm.world.topology import is_here

# Loner 3e's numbers; docs/LONER-3E.md points at the SRD and its deviations.
LUCK_MAX = 6
TIES_PER_TWIST = 3
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but


SRD_PACK: Slug = "srd"


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    concepts: tuple[DecisionOption, ...] = Field(min_length=1)
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    frailties: tuple[DecisionOption, ...] = Field(min_length=1)
    gear: tuple[DecisionOption, ...] = Field(min_length=1)
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != DIE_FACE:
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


def conflict_prompt(state: Game, actor: Entity, opponent: Entity) -> str:
    foe = actor if opponent.id == state.player_id else opponent
    return (
        f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
        "attack, try something else, or break away — what do you do?"
    )


class Sheet(Mutable):
    """The one sheet shape, whether it belongs to the player, an NPC, or a thing that resists."""

    chapters: int = 0
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=LUCK_MAX, maximum=LUCK_MAX)
    milestones: int = 0

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Concept", self.concept),
            ("Skills", ", ".join(self.skills)),
            ("Frailties", ", ".join(self.frailties)),
            ("Gear", ", ".join(self.gear)),
            ("Luck", pool(self.luck)),
        )


class Loner3eState(Mutable):
    sheets: dict[EntityId, Sheet] = Field(default_factory=dict)
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Counter(current=0, maximum=TIES_PER_TWIST)
    # None rolls twists from the game's own first table set, so no scenario has to name one.
    twist_pack: Slug | None = None


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
    if min(chance, risk) >= AND_AT:
        return Outcome(f"{side}-and", 3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(f"{side}-but", sign)
    return Outcome(side, 2 * sign)


def _sheeted(game: Loner3eState, entity: Entity) -> Entity:
    """SRD "Everything is a Character": a thing gets its sheet the first time one is asked for."""
    if entity.kind == "item":
        _ = game.sheets.setdefault(entity.id, Sheet())
    return entity


def resolve_question(
    draft: Game, action: Question, rng: Random, twists: tuple[tuple[str, str], ...]
) -> tuple[Fact, ...]:
    with rules(draft.world, Loner3eState) as game:
        return _question(draft, game, action, rng, twists)


def _question(
    draft: Game,
    game: Loner3eState,
    action: Question,
    rng: Random,
    twists: tuple[tuple[str, str], ...],
) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    opponent: Entity | None = None
    if action.opponent_id is not None:
        opponent = _sheeted(game, _require_opponent_here(draft, action.opponent_id))
        facts.extend(draft.reveal(opponent))
    _refuse_unless_ready(game, actor, opponent)

    chance_kept, chance, risk_kept, risk, facts_rolled = _pair(action, rng)
    facts.extend(facts_rolled)

    outcome = outcome_for(chance_kept, risk_kept)
    answered_at = len(facts)
    facts.append(entity_fact(actor, "question_answered", f"{action.question} -> {outcome.name}"))
    effects: tuple[str, ...] = ()
    if opponent is not None:
        exchange, effects = _absorbed(_strike(draft, game, actor, opponent, outcome))
        facts.extend(exchange)
        # The pools are refilled the moment a side hits 0, so only the fact says the conflict ended.
        if not any(fact.kind == "conflict_lost" for fact in exchange):
            draft.pending = PendingDecision(
                kind="conflict",
                prompt=conflict_prompt(draft, actor, opponent),
                options=(),
                allows_text=True,
            )
    if chance_kept == risk_kept:
        game.twist.current += 1
        if _shortfall(game.twist) == 0:
            game.twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    # The question is director-authored and names unrevealed canon even on a "no": never shown.
    edge = f" ({action.edge})" if action.edge else ""
    card = "\n".join((f"Oracle — {action.position.capitalize()}{edge} → {outcome.name}", *effects))
    facts[answered_at] = facts[answered_at].model_copy(
        update={"card": card, "dice": (chance, risk)}
    )
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
    if not is_here(draft, opponent):
        raise ValueError(
            f"{opponent_id!r} is not here with the player. "
            "Bring it here first, or act on what is here."
        )
    return opponent


def _absorbed(exchange: list[Fact]) -> tuple[list[Fact], tuple[str, ...]]:
    """The exchange reads as lines inside the Oracle card, so it shows no cards of its own."""
    lines = tuple(fact.card for fact in exchange if fact.told and fact.card)
    return [fact.model_copy(update={"card": ""}) for fact in exchange], lines


def _shortfall(pool: Counter) -> int:
    """How far a bounded pool sits below full; every pool this engine declares has a maximum."""
    if pool.maximum is None:
        raise ValueError("an unbounded pool has no full to measure against")
    return pool.maximum - pool.current


def apply_restore_luck(draft: Game, actor_id: EntityId) -> list[Fact]:
    with rules(draft.world, Loner3eState) as game:
        actor = require_actor_here(draft, actor_id)
        facts = draft.reveal(actor)
        # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
        facts.extend(
            _refill(draft, actor, sheet_of(game.sheets, actor), "the conflict is behind them")
        )
    return facts


def _refill(draft: Game, side: Entity, sheet: Sheet, why: str) -> list[Fact]:
    return adjust(draft, side, "luck", sheet.luck, _shortfall(sheet.luck), why)


def _twist(
    draft: Game, actor: Entity, rng: Random, twists: tuple[tuple[str, str], ...]
) -> list[Fact]:
    """The SRD's table is rolled here so the dice trace; the Director only reads the pairing."""
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


def _strike(
    draft: Game, game: Loner3eState, actor: Entity, opponent: Entity, outcome: Outcome
) -> list[Fact]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    why = f"{striker.name} gets the better of the exchange"
    sheet = sheet_of(game.sheets, hit)
    facts = adjust(draft, hit, "luck", sheet.luck, -abs(harm), why)
    if sheet.luck.current != 0:
        return facts
    draft.notes = (*draft.notes, defeat_note(hit.name))
    lost = f"{hit.name} is out of luck"
    facts.append(entity_fact(hit, "conflict_lost", lost, card=lost))
    # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
    facts.extend(_refill(draft, hit, sheet, "the conflict is over"))
    facts.extend(_refill(draft, striker, sheet_of(game.sheets, striker), "the conflict is over"))
    return facts


def _refuse_unless_ready(game: Loner3eState, actor: Entity, opponent: Entity | None) -> None:
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise ValueError(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if sheet_of(game.sheets, side).luck.current == 0:
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


class AdventureGrowth(Frozen):
    """All sheet changes earned by one adventure."""

    subject_id: CheckedEntityId = Field(description="Exact id of the party member who advances.")
    changes: tuple[Change, ...] = Field(
        min_length=1,
        description="Every earned change, in reading order.",
    )
