from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from random import Random
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Slug, require_unique
from aidm.core.facts import DiceEvent, Fact
from aidm.core.play import DecisionOption, PendingDecision
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.engines.core import Counter, keep_highest, pool
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.world import (
    DIE_FACE,
    LUCK_MAX,
    SCENE_SETTLED,
    Loner3eGame,
    LonerCharacter,
    LonerWorld,
    TagKind,
    entity_fact,
    labeled,
    set_tags,
    tags_of,
)

AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but

SRD_PACK: Slug = "srd"

CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)

GROWTH = (
    "Choose the changes this adventure earned: a new skill, signature gear, a frailty, or a "
    "rewrite of an existing tag."
)

ADVANCE_SPENT = "Spend one advance a party member has earned, when the player asks for it. "

type Position = Literal["advantage", "neutral", "disadvantage"]


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class ChangeTags(Frozen):
    """A character here gains or loses tags: a thing taken or lost, a lasting mark, a lesson."""

    verb: Literal["change_tags"]
    entity_id: CheckedEntityId = Field(description="Exact id of the player or someone here.")
    kind: TagKind = Field(
        description="`gear` for a thing taken or lost; `condition` for a lasting mark such as "
        "`Battle Worn` or `Poisoned`; `skill` or `frailty` only when the story plainly wrote one."
    )
    gained: tuple[str, ...] = Field(
        default=(), description="Title-case tags gained, such as `Rusty Key`."
    )
    lost: tuple[str, ...] = Field(default=(), description="Exact tags lost, lifted or used up.")


class Drive(Frozen):
    """What a living character wants, why, and who stands in their way, once play has shown it."""

    verb: Literal["drive"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of the player or a living character here."
    )
    goal: str = Field(
        default="",
        description="What they now pursue, in one line. Empty keeps the current goal.",
    )
    motive: str = Field(default="", description="Why, in one line. Empty keeps the current motive.")
    nemesis: str = Field(
        default="", description="Who or what stands in their way. Empty keeps the current nemesis."
    )


class Kill(Frozen):
    """Record that someone here has died."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


class JoinParty(Frozen):
    """A character here starts travelling with the player."""

    verb: Literal["join_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    """A companion stops travelling with the player."""

    verb: Literal["leave_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of the companion leaving.")


# A plain alias, not `type`: the union must flatten so the discriminator sees every arm.
WorldChange = Reveal | Enter | Leave | ChangeTags | Drive | Kill | JoinParty | LeaveParty


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


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
        description=("Exact id of the character here that resists. Null when nothing fights back."),
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
    actor_id: CheckedEntityId = Field(description="Exact id of the player or a character here.")


def apply_change(world: LonerWorld, change: WorldChange) -> list[Fact]:
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    run = world.run
    match change:
        case Reveal():
            one = world.require(change.entity_id)
            if change.entity_id not in run.hidden:
                raise ValueError(f"{change.entity_id!r} is not hidden here")
            run.hidden.remove(one.id)
            run.present.append(one.id)
            return _reveal(world, one)
        case Enter():
            one = world.require(change.entity_id)
            if one.id in run.present:
                raise ValueError(f"{one.name} is already here")
            if one.id in run.hidden:
                raise ValueError(f"{one.name} is hidden here; reveal them instead")
            run.present.append(one.id)
            seen = world.reveal(one)
            trace = f"{world.label(one)} arrives"
            return [*seen, entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives")]
        case Leave():
            one = world.require_here(change.entity_id)
            if one.id == world.player_id:
                raise ValueError("the player is in every scene; move the story on instead")
            run.present.remove(one.id)
            trace = f"{world.label(one)} leaves"
            return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]
        case ChangeTags():
            return _change_tags(world, world.require_alive_here(change.entity_id), change)
        case Drive():
            return _drive(world, world.require_alive_here(change.entity_id), change)
        case Kill():
            return _kill(world, change.entity_id)
        case JoinParty():
            return _join_party(world, change)
        case LeaveParty():
            return _leave_party(world, change)


def change_world(draft: Loner3eGame, args: ChangeWorld, _rng: Random) -> list[Fact]:
    return apply_change(draft.payload.world, args.change)


def next_scene(draft: Loner3eGame, _args: NoArgs, _rng: Random) -> tuple[Fact, ...]:
    world = draft.payload.world
    if world.run.settled:
        raise ValueError("this scene is already settled; the player has the way on")
    world.run.settled = True
    return (SCENE_SETTLED,)


def twist_table(packs: Mapping[str, Pack], chosen: Slug) -> tuple[tuple[str, str], ...]:
    """The chosen set's own twist columns, or the SRD's: AP01 and most user packs publish none."""
    pack = packs.get(chosen)
    if pack is None:
        raise ValueError(f"the {chosen!r} table set is not installed")
    source = pack if pack.twist_subjects is not None else packs.get(SRD_PACK)
    if source is None or source.twist_subjects is None or source.twist_actions is None:
        raise ValueError(f"neither the {chosen!r} table set nor the SRD one carries twists")
    return tuple(zip(source.twist_subjects, source.twist_actions, strict=True))


def outcome_for(chance: int, risk: int) -> Outcome:
    if chance == risk:
        return Outcome("yes-but", 1)
    side, sign = ("yes", 1) if chance > risk else ("no", -1)
    if min(chance, risk) >= AND_AT:
        return Outcome(f"{side}-and", 3 * sign)
    if max(chance, risk) <= BUT_AT:
        return Outcome(f"{side}-but", sign)
    return Outcome(side, 2 * sign)


def adjust(
    player_id: EntityId, one: LonerCharacter, key: str, counter: Counter, amount: int, why: str
) -> list[Fact]:
    before = counter.current
    counter.current = counter.clamped(before + amount)
    landed = counter.current - before
    if landed == 0:
        return []
    return [_counter_fact(player_id, one, key, counter, landed, why)]


def resolve_question(
    packs: Mapping[str, Pack], draft: Loner3eGame, action: Question, rng: Random
) -> tuple[Fact, ...]:
    world = draft.payload.world
    actor = world.require_alive_here(action.actor_id)
    facts = world.reveal(actor)
    opponent: LonerCharacter | None = None
    if action.opponent_id is not None:
        opponent = world.require_alive_here(action.opponent_id)
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
    # SRD: the Twist Counter does not apply to Harm & Luck, so a tied conflict roll never ticks it.
    if chance_kept == risk_kept and opponent is None:
        twist = draft.payload.twist
        twist.current += 1
        if _shortfall(twist) == 0:
            twist.current = 0
            twists = twist_table(packs, draft.payload.twist_pack)
            facts.extend(_twist(draft, actor, rng, twists))
    # The question is master-authored and names unrevealed canon even on a "no": never shown.
    edge = f" ({action.edge})" if action.edge else ""
    card = "\n".join((f"Oracle — {action.position.capitalize()}{edge} → {outcome.name}", *effects))
    facts[answered_at] = facts[answered_at].model_copy(
        update={"card": card, "dice": (chance, risk)}
    )
    return tuple(facts)


def apply_restore_luck(draft: Loner3eGame, args: RestoreLuck, _rng: Random) -> list[Fact]:
    actor = draft.payload.world.require_alive_here(args.actor_id)
    facts = draft.payload.world.reveal(actor)
    # Already full is a quiet no-op: `adjust` writes no fact for a zero delta.
    facts.extend(_refill(draft, actor, "the conflict is behind them"))
    return facts


def close_conflicts(draft: Loner3eGame) -> tuple[Fact, ...]:
    """A scene ends its conflicts so nobody carries a spent pool on; the dead keep theirs."""
    facts: list[Fact] = []
    for one in draft.payload.world.here():
        if one.alive and one.luck.current < LUCK_MAX:
            facts.extend(_refill(draft, one, "the scene is over"))
    return tuple(facts)


def party(state: Loner3eGame) -> tuple[EntityId, ...]:
    return (state.payload.world.player_id, *state.payload.world.companions)


def advance_notes(state: Loner3eGame) -> tuple[tuple[str, str], ...]:
    """Advances owed standing above the ledger of advances spent, one note each."""
    # An advance mid-suspension could invalidate the frozen call an open decision holds.
    if state.pending is not None:
        return ()
    owed = [
        f"- {state.payload.world.require(one).name} has an advance owed; call advance only "
        "when the player asks for it."
        for one in party(state)
        if state.payload.world.require(one).advances_owed > 0
    ]
    return (("ADVANCES OWED", "\n".join(owed)),) if owed else ()


def complete_chapter(draft: Loner3eGame, _args: NoArgs, _rng: Random) -> tuple[Fact, ...]:
    """Only those who played the chapter are credited with it: nobody is owed one they missed."""
    ending = "the adventure has ended"
    for member_id in party(draft):
        draft.payload.world.require(member_id).advances_owed += 1
    return (Fact(kind="chapter_completed", trace=ending, told=True, card=ending),)


def advance(draft: Loner3eGame, proposal: AdventureGrowth, _rng: Random) -> tuple[Fact, ...]:
    """One advance per adventure a party member played: the tags it rewrote or grew."""
    subject = _party_member(draft, proposal.subject_id)
    if subject.advances_owed == 0:
        raise ValueError(f"{subject.name} has no advance owed")
    # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
    granted = tuple(
        _rewrite(subject, change) if change.kind == "rewrite" else _gain(subject, change)
        for change in proposal.changes
    )
    subject.advances_owed -= 1
    spent = entity_fact(
        subject,
        "advance_spent",
        f"{draft.payload.world.label(subject)} spent an advance",
        card=f"{subject.name}: advance spent",
    )
    return (*granted, spent)


def meanings(
    packs: Mapping[str, Pack], selected: Sequence[Slug], one: LonerCharacter
) -> tuple[tuple[str, str], ...]:
    chosen = tuple(packs[pack_id] for pack_id in selected)
    # The concept's pack blurb is generic where the entity's own brief is not: skip it.
    return _pack_meanings(
        tuple(entry for pack in chosen for entry in (*pack.skills, *pack.frailties, *pack.gear)),
        (*one.skills, *one.frailties, *one.gear),
    )


def conflict_prompt(world: LonerWorld, actor: LonerCharacter, opponent: LonerCharacter) -> str:
    foe = actor if opponent.id == world.player_id else opponent
    return (
        f"The conflict with {foe.name} runs on: neither side is out of luck yet. Press the "
        "attack, try something else, or break away — what do you do?"
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
        "lasting mark the ending leaves with `change_tags` (a `condition`), and let the story "
        "move on."
    )


def tools(packs: Mapping[str, Pack]) -> tuple[MasterTool[Loner3eGame], ...]:
    """Six tools: two world tools, then the four SRD procedures."""
    return (
        master_tool(
            "change_world", CHANGE_WORLD, ChangeWorld, change_world, during_suspension=True
        ),
        master_tool(
            "next_scene",
            "Say this scene's question is settled. The player is then asked what they want to "
            "pursue, and their own words build the next scene. Do not answer for them.",
            NoArgs,
            next_scene,
        ),
        master_tool(
            "roll_question",
            "Roll Chance against Risk for one closed dramatic question.",
            Question,
            partial(resolve_question, packs),
        ),
        master_tool(
            "restore_luck",
            "Restore an actor's luck after a conflict ends.",
            RestoreLuck,
            apply_restore_luck,
        ),
        master_tool(
            "complete_chapter",
            "Record that the current adventure has ended.",
            NoArgs,
            complete_chapter,
        ),
        master_tool("advance", ADVANCE_SPENT + GROWTH, AdventureGrowth, advance),
    )


def _reveal(world: LonerWorld, one: LonerCharacter) -> list[Fact]:
    """The discovery itself, distinct from the standalone `reveal` verb's card."""
    facts = world.reveal(one)
    if not facts:
        raise ValueError(f"the player has already met {one.name}")
    return [facts[0].model_copy(update={"card": _sentence(f"{one.name} discovered")})]


def _change_tags(world: LonerWorld, one: LonerCharacter, change: ChangeTags) -> list[Fact]:
    if not change.gained and not change.lost:
        raise ValueError("change_tags needs at least one gained or lost tag")
    require_unique(f"{change.kind} tags", (*change.gained, *change.lost))
    current = tags_of(one, change.kind)
    if held := [tag for tag in change.gained if tag in current]:
        raise ValueError(f"{one.name} already carries the {change.kind} {held[0]!r}")
    if missing := [tag for tag in change.lost if tag not in current]:
        raise ValueError(f"{one.name} carries no {change.kind} {missing[0]!r}")
    set_tags(
        one, change.kind, tuple(tag for tag in (*current, *change.gained) if tag not in change.lost)
    )
    deltas = (*(f"+{tag}" for tag in change.gained), *(f"-{tag}" for tag in change.lost))
    trace = f"{world.label(one)} {change.kind} " + ", ".join(deltas)
    parts: list[str] = []
    if change.gained:
        took = ", ".join(change.gained)
        parts.append(f"Took {took}" if change.kind == "gear" else f"Now: {took}")
    if change.lost:
        lost = ", ".join(change.lost)
        parts.append(f"Lost {lost}" if change.kind == "gear" else f"No longer: {lost}")
    return [entity_fact(one, "tags_changed", trace, card="; ".join(parts))]


def _drive(world: LonerWorld, one: LonerCharacter, change: Drive) -> list[Fact]:
    if not change.goal and not change.motive and not change.nemesis:
        raise ValueError("drive needs a goal, a motive or a nemesis to set")
    parts: list[str] = []
    if change.goal:
        one.goal = change.goal
        parts.append(f"goal: {change.goal}")
    if change.motive:
        one.motive = change.motive
        parts.append(f"motive: {change.motive}")
    if change.nemesis:
        one.nemesis = change.nemesis
        parts.append(f"nemesis: {change.nemesis}")
    trace = f"{world.label(one)} " + "; ".join(parts)
    card = f"{one.name}: {change.goal}" if change.goal else ""
    return [entity_fact(one, "drive_set", trace, card=card)]


def _kill(world: LonerWorld, entity_id: EntityId) -> list[Fact]:
    one = world.require_here(entity_id)
    if not one.alive:
        raise ValueError(f"{one.name} is already dead")
    facts = world.reveal(one)
    if one.id in world.companions:
        world.companions.remove(one.id)
    one.alive = False
    trace = f"{world.label(one)} is dead"
    facts.append(entity_fact(one, "actor_killed", trace, card=f"{one.name} is dead"))
    return facts


def _join_party(world: LonerWorld, change: JoinParty) -> list[Fact]:
    one = world.require_alive_here(change.entity_id)
    if one.id in world.companions:
        raise ValueError(f"{one.name} already travels with the player")
    seen = world.reveal(one)
    world.companions.append(one.id)
    trace = f"{world.label(one)} travels with the player"
    return [*seen, entity_fact(one, "party_joined", trace, card=f"{one.name} joins your party")]


def _leave_party(world: LonerWorld, change: LeaveParty) -> list[Fact]:
    one = world.require(change.entity_id)
    if one.id not in world.companions:
        raise ValueError(f"{one.name} does not travel with the player")
    world.companions.remove(one.id)
    trace = f"{world.label(one)} no longer travels with the player"
    return [entity_fact(one, "party_left", trace, card=f"{one.name} leaves your party")]


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _counter_fact(
    player_id: EntityId, one: LonerCharacter, key: str, counter: Counter, delta: int, why: str
) -> Fact:
    moved = f"{key.capitalize()} {delta:+d} -> {pool(counter)}"
    card = moved if one.id == player_id else f"{one.name}: {moved}"
    trace = f"{labeled(one, player_id)} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(one, "counter_changed", f"{trace} ({why})", card=card)


def _party_member(draft: Loner3eGame, subject_id: EntityId) -> LonerCharacter:
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
    """How far a bounded pool sits below full."""
    return pool.maximum - pool.current


def _refill(draft: Loner3eGame, side: LonerCharacter, why: str) -> list[Fact]:
    player_id = draft.payload.world.player_id
    return adjust(player_id, side, "luck", side.luck, _shortfall(side.luck), why)


def _twist(
    draft: Loner3eGame, actor: LonerCharacter, rng: Random, twists: tuple[tuple[str, str], ...]
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


def _strike(
    draft: Loner3eGame, actor: LonerCharacter, opponent: LonerCharacter, outcome: Outcome
) -> list[Fact]:
    harm = outcome.harm
    hit, striker = (opponent, actor) if harm > 0 else (actor, opponent)
    why = f"{striker.name} gets the better of the exchange"
    facts = adjust(draft.payload.world.player_id, hit, "luck", hit.luck, -abs(harm), why)
    if hit.luck.current != 0:
        return facts
    draft.notes = (*draft.notes, defeat_note(hit.name))
    draft.payload.world.run.spent = f"the conflict with {hit.name} is settled"
    lost = f"{hit.name} is out of luck"
    facts.append(entity_fact(hit, "conflict_lost", lost, card=lost))
    # SRD: luck resets after conflicts, and a side at 0 is the only end the engine sees.
    facts.extend(_refill(draft, hit, "the conflict is over"))
    facts.extend(_refill(draft, striker, "the conflict is over"))
    return facts


def _refuse_unless_ready(actor: LonerCharacter, opponent: LonerCharacter | None) -> None:
    if opponent is None:
        return
    if opponent.id == actor.id:
        raise ValueError(f"{actor.name} cannot be their own opposition in a conflict.")
    for side in (actor, opponent):
        if side.luck.current == 0:
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


def _gain(subject: LonerCharacter, change: Change) -> Fact:
    if change.kind == "rewrite":
        raise ValueError("gain does not rewrite a tag")
    if change.tag in (
        *tags_of(subject, "skill"),
        *tags_of(subject, "gear"),
        *tags_of(subject, "frailty"),
    ):
        raise ValueError(f"{subject.name} already has the tag {change.tag!r}")
    set_tags(subject, change.kind, (*tags_of(subject, change.kind), change.tag))
    return entity_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag} ({change.why})",
        card=f"{subject.name}: new {change.kind} {change.tag}",
    )


def _rewrite(subject: LonerCharacter, change: Change) -> Fact:
    old, new = change.tag, change.into
    kind: TagKind
    if old in subject.skills:
        kind = "skill"
    elif old in subject.frailties:
        kind = "frailty"
    elif old in subject.gear:
        kind = "gear"
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    set_tags(subject, kind, _swapped(tags_of(subject, kind), old, new))
    return entity_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new} ({change.why})",
        card=f"{subject.name}: {old} → {new}",
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


def _pack_meanings(
    entries: Sequence[DecisionOption], tags: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    detail_of = {entry.label: entry.detail for entry in entries if entry.detail}
    return tuple((tag, detail_of[tag]) for tag in tags if tag in detail_of)
