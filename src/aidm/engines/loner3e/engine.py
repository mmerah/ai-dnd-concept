from collections.abc import Callable, Mapping
from pathlib import Path
from random import Random
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.content.model import CharacterOverlay, CharacterProfile, CreatedCharacter
from aidm.engines.core import (
    Advancement,
    CharacterCreation,
    Engine,
    PlanContext,
    ProposalBase,
    SheetBase,
    SheetMechanics,
    act,
    actor_sheets,
    adjust,
    check_sheets,
    chipped,
    complete_chapter,
    counter_effect,
    dice_event,
    load_packs,
    pack_paths,
    pack_step,
    render_counters,
    require_dice_role,
    require_sheet,
    sequential_toolset,
)
from aidm.state.actions import require_actor_here, roll_pool
from aidm.state.model import (
    PLAYER_ID,
    AnyStep,
    ContentSlug,
    Counter,
    CreationOption,
    CreationStep,
    EngineId,
    Entity,
    EntityId,
    EventBadge,
    Fact,
    Frozen,
    Game,
    MechanicEvent,
    Picks,
    Slug,
    TextStep,
    WorldState,
    check_picks,
    entity_fact,
    explained_fact,
    picked,
)

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
            if column is not None and len(column) != 6:
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


LUCK_MAX = 6
TIES_PER_TWIST = 3


class Sheet(SheetBase):
    """The one sheet shape, whether it belongs to the player or to an NPC."""

    # The table set this character was built from; the twist table is read from it.
    pack: ContentSlug = SRD_PACK
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Counter(current=LUCK_MAX, maximum=LUCK_MAX)
    milestones: Counter = Counter(current=0)

    def counters(self) -> dict[Slug, Counter]:
        return {"luck": self.luck}


class Mechanics(SheetMechanics[Sheet]):
    # One tally for the whole game, as the note it fires says: a tie anywhere moves the same one.
    twist: Counter = Counter(current=0, maximum=TIES_PER_TWIST)


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
) -> tuple[Fact, ...]:
    actor = require_actor_here(draft, action.actor_id)
    facts = draft.reveal(actor)
    mechanics = Mechanics.of(draft)
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
        facts.extend(_strike(draft, mechanics, actor, opponent, outcome))
    elif chance == risk:
        # The tally itself never becomes a fact: it paces the Director, and the Narrator would
        # only be handed a number it is told never to recite. A conflict exchange never ticks it.
        mechanics.twist.current += 1
        if mechanics.twist.current >= TIES_PER_TWIST:
            mechanics.twist.current = 0
            facts.extend(_twist(draft, actor, rng, twists))
    return tuple(facts)


def apply_restore_luck(draft: Game, actor_id: EntityId) -> list[Fact]:
    actor = require_actor_here(draft, actor_id)
    facts = draft.reveal(actor)
    luck = require_sheet(Mechanics.of(draft).sheets, actor).luck
    refill = (luck.maximum or LUCK_MAX) - luck.current
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
    subject_die, subject_fact = roll_pool((6,), "twist — subject", rng, role="subject")
    action_die, action_fact = roll_pool((6,), "twist — action", rng, role="action")
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
    chance, chance_fact = roll_pool(chance_faces, f"{action.question} — chance", rng, role="chance")
    risk, risk_fact = roll_pool(risk_faces, f"{action.question} — risk", rng, role="risk")
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
        tool="roll_question",
        title="Oracle",
        badges=tuple(badges),
        dice=(
            dice_event("Chance", require_dice_role(facts, "chance")),
            dice_event("Risk", require_dice_role(facts, "risk")),
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
        tool="roll_question",
        title="Twist",
        badges=(
            EventBadge(label="Subject", value=str(twist.data["subject"])),
            EventBadge(label="Action", value=str(twist.data["action"])),
        ),
        dice=(
            dice_event("Subject", require_dice_role(facts, "subject")),
            dice_event("Action", require_dice_role(facts, "action")),
        ),
        icon="bolt",
    )


type Twists = Callable[[Game], tuple[tuple[str, str], ...]]


def director_toolset(twists: Twists) -> FunctionToolset[PlanContext]:
    def roll_question(ctx: RunContext[PlanContext], question: Question) -> str:
        """Put a closed dramatic question to Chance d6 against Risk d6.

        Args:
            question: The question to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_question(draft, question, rng, twists(draft)))

    def restore_luck(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor's luck back to full.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
        """
        return act(
            ctx,
            lambda draft, _rng: tuple(apply_restore_luck(draft, actor_id)),
        )

    def complete_chapter(ctx: RunContext[PlanContext]) -> str:
        """Record that the adventure this character has been living has ended."""
        return act(ctx, lambda draft, _rng: tuple(apply_complete_chapter(draft)))

    return sequential_toolset([roll_question, restore_luck, complete_chapter])


GROWTH = (
    "Say how the character has changed over this adventure. Each change is one of four: a "
    "new skill, a new piece of signature gear, a new frailty, or one tag they already carry "
    "rewritten."
)


class Change(Frozen):
    """One change the post-adventure update writes."""

    kind: Literal["skill", "gear", "frailty", "rewrite"] = Field(
        description="Which of the four growths this change spends."
    )
    tag: str = Field(
        min_length=1,
        description="The new tag in title case — or, for a rewrite, the tag already written on "
        "the sheet, copied exactly.",
    )
    into: str = Field(
        default="",
        description="A rewrite only: what that tag becomes, in title case. Empty otherwise.",
    )

    @model_validator(mode="after")
    def _rewrite_names_what_it_becomes(self) -> Self:
        if bool(self.into) != (self.kind == "rewrite"):
            raise ValueError("`into` belongs to a rewrite and to nothing else")
        return self


class AdventureGrowth(ProposalBase):
    """Everything this adventure changed on the sheet, at once, as the post-adventure update."""

    changes: tuple[Change, ...] = Field(
        min_length=1,
        max_length=4,
        description="Each change: a new skill, new gear, a new frailty, or one rewrite.",
    )
    why: str = Field(description="One short sentence the player reads before confirming.")


class Loner3eAdvancement(Advancement):
    proposal_type = AdventureGrowth
    ledger_key = "milestones"
    occasion = "finishes an adventure"
    offer_text = GROWTH
    spent_why = "a milestone spent"

    def ledger(self, state: Game, subject_id: EntityId) -> Counter:
        return Mechanics.of(state).sheets[subject_id].milestones

    def earned(self, state: Game) -> int:
        return Mechanics.of(state).completed.current

    def grant(
        self, draft: Game, subject_id: EntityId, proposal: ProposalBase, rng: Random
    ) -> tuple[Fact, ...]:
        del rng  # post-adventure growth spends nothing random
        assert isinstance(proposal, AdventureGrowth)
        sheet = Mechanics.of(draft).sheets[subject_id]
        subject = draft.world.require(subject_id)
        # Sequential against the live sheet, so a rewrite may name what an earlier change wrote.
        return tuple(
            _rewrite(sheet, subject, change, proposal.why)
            if change.kind == "rewrite"
            else _gain(sheet, subject, change, proposal.why)
            for change in proposal.changes
        )


def _gain(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    if change.kind == "skill":
        sheet.skills = (*sheet.skills, change.tag)
    elif change.kind == "gear":
        sheet.gear = (*sheet.gear, change.tag)
    else:
        sheet.frailties = (*sheet.frailties, change.tag)
    return explained_fact(
        subject,
        f"{change.kind}_gained",
        f"{subject.name} gained {change.kind} {change.tag}",
        {"tag": change.tag},
        why,
        narrate=False,
    )


def _rewrite(sheet: Sheet, subject: Entity, change: Change, why: str) -> Fact:
    old, new = change.tag, change.into
    if old in sheet.skills:
        sheet.skills = _swapped(sheet.skills, old, new)
    elif old in sheet.frailties:
        sheet.frailties = _swapped(sheet.frailties, old, new)
    elif old in sheet.gear:
        sheet.gear = _swapped(sheet.gear, old, new)
    else:
        raise ValueError(f"{subject.name} carries no tag {old!r} to rewrite")
    return explained_fact(
        subject,
        "tag_rewritten",
        f"{subject.name} rewrote {old} as {new}",
        {"was": old, "tag": new},
        why,
        narrate=False,
    )


def _swapped(tags: tuple[str, ...], old: str, new: str) -> tuple[str, ...]:
    return tuple(new if tag == old else tag for tag in tags)


class Loner3eCreation(CharacterCreation):
    def __init__(self, packs: Mapping[str, Pack]) -> None:
        self._packs = packs

    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        first = pack_step(self._packs)
        chosen = picked(picks, "pack")
        pack = self._packs.get(chosen[0]) if chosen else None
        if pack is None:
            return (first,)
        return (
            first,
            TextStep(
                id="concept",
                prompt="Their concept, in one line",
                hint=", ".join(entry.label for entry in pack.concepts[:3]),
            ),
            CreationStep(
                id="skills", prompt="Choose two skills", options=_options(pack.skills), choose=2
            ),
            CreationStep(id="frailty", prompt="Choose a frailty", options=_options(pack.frailties)),
            CreationStep(
                id="gear", prompt="Choose two pieces of gear", options=_options(pack.gear), choose=2
            ),
        )

    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        check_picks(self.steps(picks), picks)
        pack = self._packs[picked(picks, "pack")[0]]
        return CreatedCharacter(
            profile=CharacterProfile(name=name, brief=brief),
            overlay=CharacterOverlay(
                character={
                    "pack": picked(picks, "pack")[0],
                    "concept": picked(picks, "concept")[0],
                    "skills": [_label(pack.skills, skill) for skill in picked(picks, "skills")],
                    "frailties": [_label(pack.frailties, picked(picks, "frailty")[0])],
                    "gear": [_label(pack.gear, gear) for gear in picked(picks, "gear")],
                }
            ),
        )


def _options(entries: tuple[PackEntry, ...]) -> tuple[CreationOption, ...]:
    return tuple(
        CreationOption(id=entry.id, label=entry.label, detail=entry.detail) for entry in entries
    )


def _label(entries: tuple[PackEntry, ...], chosen: str) -> str:
    return next(entry.label for entry in entries if entry.id == chosen)


ENGINE_ID: EngineId = EngineId("loner3e")


class Loner3eEngine(Engine):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    engine_dir = Path(__file__).parent
    mechanics_type = Mechanics

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(self.packs)
        self.director_toolsets = (director_toolset(self.twists),)

    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        _ = Sheet.model_validate(rules)

    def opening_mechanics(self, world: WorldState, player_rules: dict[str, JsonValue]) -> Mechanics:
        return Mechanics(sheets=actor_sheets(world, player_rules, Sheet))

    def validate(self, state: Game) -> None:
        mechanics = Mechanics.of(state)
        check_sheets(state.world, mechanics.sheets, self.id)
        if (chosen := mechanics.sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a loner3e sheet is rolled
        mechanics = Mechanics.of(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        mechanics.sheets[entity.id] = Sheet(milestones=Counter(current=mechanics.completed.current))

    def describe(self, state: Game, entity: Entity) -> str:
        return describe_entity(Mechanics.of(state), entity)

    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        sheet = Mechanics.of(state).sheets[PLAYER_ID]
        return (
            ("Concept", sheet.concept),
            ("Skills", ", ".join(sheet.skills)),
            ("Frailties", ", ".join(sheet.frailties)),
            ("Gear", ", ".join(sheet.gear)),
            ("Luck", f"{sheet.luck.current} / {sheet.luck.maximum}"),
        )

    def twists(self, state: Game) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, Mechanics.of(state).sheets[PLAYER_ID].pack)

    def player_events(self, tool_name: str, facts: tuple[Fact, ...]) -> tuple[MechanicEvent, ...]:
        if tool_name == "roll_question":
            return question_events(facts)
        return super().player_events(tool_name, facts)
