# CLAUDE.md's 1000-line file cap is waived for this eval script.
import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from aidm.config import Settings, load_settings
from aidm.content.io import load_character, load_scenario
from aidm.engines.breathless.rules import RULES as BreathlessRules
from aidm.engines.breathless.rules import Breathe, Skill, apply_catch_breath
from aidm.engines.breathless.rules import ItemSheet as BreathlessItemSheet
from aidm.engines.breathless.rules import Sheet as BreathlessSheet
from aidm.engines.core import Engine, EntityRules, SheetBase, complete_chapter, rules
from aidm.engines.loner3e.rules import RULES as LonerRules
from aidm.engines.loner3e.rules import Sheet as LonerSheet
from aidm.engines.registry import begin_game, build_engines
from aidm.engines.twentyfourxx.rules import ItemSheet
from aidm.engines.twentyfourxx.rules import Sheet as TwentyfourxxSheet
from aidm.state.entities import (
    DEAD,
    PLAYER_ID,
    Counter,
    EngineId,
    Entity,
    EntityId,
    Exit,
    Frozen,
    Slug,
    Trait,
)
from aidm.state.model import Game
from aidm.state.play import Answer, PendingDecision, StepTrace, TurnTrace
from aidm.turn.run import TurnResult, build_turn_agents, run_segment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


@cache
def built() -> dict[EngineId, Engine]:
    return build_engines(ROOT / load_settings().packs_dir)


# The longest valid chain is stake -> proceed -> defence.
SEGMENT_CAP = 4


@dataclass(frozen=True, slots=True)
class Expectation:
    name: str
    holds: Callable[[TurnResult], bool]


def _last_option(pending: PendingDecision) -> Slug:
    return pending.options[-1].id


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    engine_id: EngineId
    prompt: str
    expectations: tuple[Expectation, ...]
    setup: Callable[[Game], Game] = lambda state: state
    # True sends the prompt as a written Answer: how the app delivers text over a staged decision.
    answers_decision: bool = False
    # Which option answers a mid-run hand-back; stake offers proceed, defence ends on take-it.
    choose: Callable[[PendingDecision], Slug] = _last_option


class Run(Frozen):
    error: str | None = None
    passed: dict[str, bool] = {}
    facts: list[str] = []
    # Full stage prompts and outputs, kept only for a run that failed: the debugging record.
    steps: list[StepTrace] = []
    director_calls: int = 0
    refusals: list[str] = []
    total_steps: int = 0
    seconds: float = 0.0
    narration_chars: int = 0

    @property
    def scored(self) -> bool:
        return self.error is None and all(self.passed.values())


class CaseResult(Frozen):
    id: str
    engine: str
    prompt: str
    expectations: list[str]
    runs: list[Run]

    def rate(self, name: str) -> float:
        return mean([float(run.passed.get(name, False)) for run in self.runs])


class Report(Frozen):
    label: str
    repeats: int
    seed: int
    cases: list[CaseResult]


@dataclass(frozen=True, slots=True)
class Canon:
    scenario_id: Slug
    walk_to: str
    climb_from: str
    climb_to: str
    companion: str
    hidden: str
    thread: str
    won: tuple[str, ...]
    # The note that says the prize is taken: an adventure over.
    done_note: str = ""


CANON: dict[EngineId, Canon] = {
    EngineId("loner3e"): Canon(
        scenario_id="whispering-vault",
        walk_to="cloister",
        climb_from="cloister",
        climb_to="bell-tower",
        companion="elena",
        hidden="vault-map",
        thread="vault-seal",
        won=("yes-and", "yes", "yes-but"),
        done_note="Kael broke the seal, took what he came for, and there is nothing left to do "
        "for this thread.",
    ),
    EngineId("twentyfourxx"): Canon(
        scenario_id="drowned-road",
        walk_to="holdfast",
        climb_from="siren-mast",
        climb_to="relay-nine",
        companion="mara-voss",
        hidden="cipher-spike",
        thread="vault-survey",
        won=("success",),
        done_note="Kael opened the hatch, took the founding survey, and there is nothing left "
        "to do for this thread.",
    ),
    EngineId("breathless"): Canon(
        scenario_id="saint-ivo",
        walk_to="triage-hall",
        climb_from="ambulance-bay",
        climb_to="roof-walk",
        companion="wren-halloway",
        hidden="ward-card",
        thread="cold-cache",
        won=("success",),
        done_note="Kael opened the cold vault, took the cased antivirals, and there is nothing "
        "left to do for this thread.",
    ),
}


def canon_for(engine_id: EngineId) -> Canon:
    canon = CANON.get(engine_id)
    if canon is None:
        raise SystemExit(f"engine {engine_id!r} names no scenario for the eval")
    return canon


def begin(engine_id: EngineId, settings: Settings) -> tuple[Engine, Game]:
    engine = built()[engine_id]
    canon = canon_for(engine_id)
    scenario = load_scenario(ROOT / settings.scenarios_dir, canon.scenario_id)
    character = load_character(
        ROOT / settings.characters_dir,
        settings.authoring.starter_character,
        engine.id,
        engine.check_overlay,
    )
    return engine, begin_game(engine, canon.scenario_id, scenario, character)


def named(state: Game, entity_id: str) -> str:
    return state.world.require(EntityId(entity_id)).name


def staged(state: Game, at: str, ways: Sequence[tuple[str, str]]) -> Game:
    draft = state.draft()
    for source, target in ways:
        source_id, target_id = EntityId(source), EntityId(target)
        exit_ = draft.world.require_kind(source_id, "location").exit_to(target_id)
        if exit_ is None:
            raise ValueError(f"no way joins {source!r} and {target!r}")
        # A known way needs both ends known: the world refuses a known exit to an unmet place.
        draft.world.require(source_id).known = True
        draft.world.require(target_id).known = True
        exit_.known = True
        mirror = draft.world.require_kind(target_id, "location").exit_to(source_id)
        if mirror is not None:
            mirror.known = True
    draft.world.require(EntityId(at)).known = True
    draft.player.parent_id = EntityId(at)
    return draft.committed()


def known(result: TurnResult, entity_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.known


def inside(result: TurnResult, entity_id: str, holder: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.parent_id == EntityId(holder)


def dead(result: TurnResult, entity_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.trait(DEAD) is not None


def has_fact(result: TurnResult, kind: str) -> bool:
    return any(fact.kind == kind for fact in result.turn.facts)


def gained_a_trait(result: TurnResult, before: frozenset[str]) -> bool:
    return bool({trait.id for trait in result.state.player.traits} - before)


def luck_moved(result: TurnResult) -> bool:
    # The counter key sits between the actor label and the delta arrow in the trace.
    return any(
        fact.kind == "counter_changed" and " luck " in fact.trace for fact in result.turn.facts
    )


def credits_spent(result: TurnResult) -> bool:
    # A charge, not a payment: the counter trace carries the key and a negative delta.
    return any(
        fact.kind == "counter_changed" and " credits -" in fact.trace for fact in result.turn.facts
    )


def conflict_handed_back(result: TurnResult) -> bool:
    pending = result.state.pending
    return pending is not None and pending.kind == "conflict"


def staked_before_rolling(result: TurnResult) -> bool:
    """The first segment ended on the stake's hand-back, with no roll taken in it."""
    history = result.state.history
    return (
        bool(history)
        and bool(history[0].decision)
        and not any(event.title in ("Attempt", "Check") for event in history[0].events)
    )


# The facts that carry a resolved roll's outcome; luck tests and twists excuse nothing.
ROLL_FACTS = ("attempt_resolved", "question_answered", "check_resolved")


def player_outcomes(result: TurnResult) -> list[str]:
    """Outcomes of the player's own resolved rolls: NPC rolls and luck tests count for nothing."""
    return [
        fact.event.outcome
        for fact in result.turn.facts
        if fact.kind in ROLL_FACTS
        and fact.entity_id == result.state.player_id
        and fact.event is not None
        and fact.event.outcome
    ]


def lost_a_roll(result: TurnResult, won: Sequence[str]) -> bool:
    return any(outcome not in won for outcome in player_outcomes(result))


def won_a_roll(result: TurnResult, won: Sequence[str]) -> bool:
    return any(outcome in won for outcome in player_outcomes(result))


def unless_lost(
    holds: Callable[[TurnResult], bool], won: Sequence[str]
) -> Callable[[TurnResult], bool]:
    """A lost roll fairly strands the climber below, so its consequences go unscored."""
    return lambda result: lost_a_roll(result, won) or holds(result)


def sheet_of[R: EntityRules](state: Game, entity_id: str, model: type[R]) -> R:
    return model.model_validate(state.world.require(EntityId(entity_id)).rules)


def has_trait(result: TurnResult, entity_id: str, trait_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.trait(trait_id) is not None


def breaks_left(result: TurnResult, entity_id: str) -> int:
    """Sturdy gear counts its breaks on its own rules; gear with none still breaks once."""
    return sheet_of(result.state, entity_id, ItemSheet).breaks.current


def card_badge(result: TurnResult, label: str, value: str | None = None) -> bool:
    """A mechanic card carried the badge: how helped, hindered, and position reach the record."""
    return any(
        badge.label == label and (value is None or badge.value == value)
        for fact in result.turn.facts
        if fact.event is not None
        for badge in fact.event.badges
    )


def bad_luck_rolled(result: TurnResult) -> bool:
    # The engine prefixes every bad-luck die's reason, so a clear roll still leaves this trace.
    return any(
        fact.kind == "dice_rolled" and fact.trace.startswith("bad luck")
        for fact in result.turn.facts
    )


def counter_rose(result: TurnResult, marker: str) -> bool:
    return any(
        fact.kind == "counter_changed" and marker in fact.trace for fact in result.turn.facts
    )


def luck_restored(result: TurnResult) -> bool:
    return counter_rose(result, " luck +")


def _twists_left(state: Game) -> int:
    return LonerSheet.model_validate(state.player.rules).twist.current


def tied_a_roll(result: TurnResult) -> bool:
    """A Loner tie: Chance equal to Risk, the one result that moves the Twist Counter."""
    return any(
        fact.kind == "question_answered"
        and fact.event is not None
        and len(fact.event.dice) == 2
        and fact.event.dice[0].kept == fact.event.dice[1].kept
        for fact in result.turn.facts
    )


def loner_luck(result: TurnResult, entity_id: str) -> int:
    return sheet_of(result.state, entity_id, LonerSheet).luck.current


def skill_face(result: TurnResult, skill: str) -> int:
    return sheet_of(result.state, result.state.player_id, TwentyfourxxSheet).face(skill)


def breathless_sheet(result: TurnResult) -> BreathlessSheet:
    return sheet_of(result.state, result.state.player_id, BreathlessSheet)


def skill_rolled(result: TurnResult, skill: Skill) -> bool:
    """The wear line names the skill and the face it rolled: `Kael[player] Sneak d10 -> d8`."""
    return any(
        fact.kind == "skill_worn" and f" {skill} d" in fact.trace for fact in result.turn.facts
    )


def worn_by(result: TurnResult, actor_id: str) -> bool:
    return any(
        fact.kind == "skill_worn" and fact.entity_id == EntityId(actor_id)
        for fact in result.turn.facts
    )


def item_rolled(result: TurnResult, item_id: str) -> bool:
    return any(
        fact.kind == "item_worn" and fact.entity_id == EntityId(item_id)
        for fact in result.turn.facts
    )


def worn_down(result: TurnResult, skill: Skill) -> bool:
    sheet = breathless_sheet(result)
    return sheet.worn[skill] < sheet.skills[skill]


def luck_die(result: TurnResult) -> int:
    """The die the Director rated by the odds; a luck test rolls exactly one."""
    return next(
        (
            die.faces[0]
            for fact in result.turn.facts
            if fact.kind == "luck_tested" and fact.event is not None
            for die in fact.event.dice
        ),
        0,
    )


def stunt_rolled(result: TurnResult) -> bool:
    """Nothing Kael carries or rates is a d12, so a lone d12 in a check can only be the stunt."""
    return any(
        fact.kind == "check_resolved"
        and fact.event is not None
        and any(die.faces == (12,) for die in fact.event.dice)
        for fact in result.turn.facts
    )


def rolled_with_help(result: TurnResult) -> bool:
    """A helper adds their die to the same pool, so the check shows two faces instead of one."""
    return any(
        fact.kind == "check_resolved"
        and fact.event is not None
        and any(len(die.faces) == 2 for die in fact.event.dice)
        for fact in result.turn.facts
    )


def rolled_for(result: TurnResult, actor_id: str) -> bool:
    return any(
        fact.kind == "check_resolved" and fact.entity_id == EntityId(actor_id)
        for fact in result.turn.facts
    )


def failed_a_check(result: TurnResult) -> bool:
    return "fail" in player_outcomes(result)


def flagged_vulnerable(result: TurnResult) -> bool:
    """The engine writes the warning only when a vulnerable actor fails a `dangerous` check."""
    return any("taken out, or dead" in fact.trace for fact in result.turn.facts)


def carried_items(result: TurnResult) -> int:
    return len(result.state.world.children(result.state.player_id, "item"))


COMPLICATIONS = frozenset(
    {
        "check_resolved",
        "counter_changed",
        "trait_added",
        "entity_discovered",
        "entity_moved",
        "luck_tested",
    }
)


def complicated(result: TurnResult) -> bool:
    """Something landed on the group: any mechanic that moves the fiction against the player."""
    return bool(COMPLICATIONS & {fact.kind for fact in result.turn.facts}) or (
        result.state.pending is not None
    )


def _rat_met(state: Game) -> Game:
    """The kill is what is scored, so the rat is already met."""
    draft = staged(state, "cloister", []).draft()
    draft.world.require(EntityId("cloister-rat")).known = True
    return draft.committed()


def _mid_conflict(state: Game) -> Game:
    """The turn before ended on the conflict's hand-back; this one answers it."""
    draft = _rat_met(state).draft()
    draft.pending = PendingDecision(
        kind="conflict",
        prompt=(
            "The conflict with a bloated rat runs on: neither side is out of luck yet. Press "
            "the attack, try something else, or break away — what do you do?"
        ),
        options=(),
        allows_text=True,
        payload={},
    )
    return draft.committed()


def _seal_met(state: Game) -> Game:
    """A non-living opponent the SRD's "Everything is a Character" covers, staged as an item."""
    draft = staged(state, "cloister", []).draft()
    draft.world.entities.append(
        Entity(
            id=EntityId("vault-seal"),
            kind="item",
            name="the seal on the vault door",
            brief="An unweathered seal cut into the vault door; touched, it hums and pushes back.",
            known=True,
            parent_id=EntityId("cloister"),
        )
    )
    return draft.committed()


def _winded(state: Game) -> Game:
    draft = _rat_met(state).draft()
    with rules(draft.player, LonerSheet) as sheet:
        sheet.luck.current = 2
    return draft.committed()


def _rat_on_its_last_luck(state: Game) -> Game:
    """Any yes ends the conflict: the rat's one luck cannot survive an exchange it loses."""
    draft = _mid_conflict(state).draft()
    with rules(draft.world.require(EntityId("cloister-rat")), LonerSheet) as sheet:
        sheet.luck.current = 1
    return draft.committed()


def _two_ties_in(state: Game) -> Game:
    draft = staged(state, "cloister", []).draft()
    with rules(draft.player, LonerSheet) as sheet:
        sheet.twist.current = LonerRules.ties_per_twist - 1
    return draft.committed()


def _adventure_done(state: Game, canon: Canon) -> Game:
    """The main thread is spent: the world agrees with a player who says the adventure is over."""
    draft = staged(state, canon.walk_to, []).draft()
    thread = draft.world.thread(canon.thread)
    if thread is None:
        raise ValueError(f"no thread {canon.thread!r}")
    thread.note = canon.done_note
    return draft.committed()


def _adventure_closed[S: SheetBase](state: Game, canon: Canon, sheet_type: type[S]) -> Game:
    """One chapter closed and no advance taken yet: the Director owes the player one."""
    draft = _adventure_done(state, canon).draft()
    thread = draft.world.thread(canon.thread)
    if thread is None:
        raise ValueError(f"no thread {canon.thread!r}")
    thread.status = "resolved"
    _ = complete_chapter(draft, "the chapter closed", sheet_type)
    return draft.committed()


def _broken_arm(state: Game) -> Game:
    draft = staged(state, "siren-mast", [("siren-mast", "relay-nine")]).draft()
    draft.player.traits.append(
        Trait(id="broken-arm", name="Broken Arm", text="(injury) Splinted; it bears no weight.")
    )
    return draft.committed()


def _bulky_gear(draft: Game, item_id: str, name: str, breaks: int = 1) -> None:
    """Written straight into the world: the item's own rules are the sheet it plays by."""
    marks = ItemSheet(bulky=True, breaks=Counter(current=breaks, maximum=breaks))
    draft.world.entities.append(
        Entity(
            id=EntityId(item_id),
            kind="item",
            name=name,
            brief=name,
            known=True,
            parent_id=PLAYER_ID,
            rules=marks.model_dump(mode="json"),
        )
    )


def _armored(state: Game) -> Game:
    draft = staged(state, "holdfast", []).draft()
    _bulky_gear(draft, "battle-armor", "battle armor off Verrin's rack", breaks=3)
    return draft.committed()


def _burdened(state: Game) -> Game:
    draft = staged(state, "siren-mast", [("siren-mast", "relay-nine")]).draft()
    _bulky_gear(draft, "battle-armor", "battle armor", breaks=3)
    _bulky_gear(draft, "survey-pack", "a full survey pack")
    return draft.committed()


def _docked_skiff(state: Game) -> Game:
    """A ship is a location; the SRD sells its upgrades through the same catalogue."""
    draft = staged(state, "holdfast", []).draft()
    draft.world.entities.append(
        Entity(
            id=EntityId("skiff"),
            kind="location",
            name="the hired tide-skiff",
            brief="A salvage skiff riding at the Holdfast stair, every system at the basic set.",
            known=True,
            exits=[Exit(to=EntityId("holdfast"), known=True)],
        )
    )
    draft.world.require_kind(EntityId("holdfast"), "location").exits.append(
        Exit(to=EntityId("skiff"), known=True)
    )
    with rules(draft.player, TwentyfourxxSheet) as sheet:
        sheet.credits.current = 12
    return draft.committed()


def _mara_at_hand(state: Game) -> Game:
    draft = staged(state, "relay-nine", []).draft()
    draft.world.require(EntityId("mara-voss")).known = True
    draft.world.party.append(EntityId("mara-voss"))
    return draft.committed()


def _stunt_spent(state: Game) -> Game:
    """One d12 flourish is all there is until the player catches their breath."""
    draft = state.draft()
    with rules(draft.player, BreathlessSheet) as sheet:
        sheet.stunted = True
    return draft.committed()


def _stressed(state: Game, stress: int) -> Game:
    draft = state.draft()
    with rules(draft.player, BreathlessSheet) as sheet:
        sheet.stress.current = stress
    return draft.committed()


def _med_kit_at_hand(state: Game) -> Game:
    """Stress to spend it on and the kit to spend: using it is the player's own move."""
    draft = _stressed(state, 3).draft()
    with rules(draft.player, BreathlessSheet) as sheet:
        sheet.med_kit = True
    return draft.committed()


def _spent_loot_die(state: Game) -> Game:
    """A loot die at d4 keeps rolling: the SRD allows it at the player's own risk."""
    draft = state.draft()
    with rules(draft.player, BreathlessSheet) as sheet:
        sheet.loot = BreathlessRules.floor
    return draft.committed()


def _wren_at_hand(state: Game) -> Game:
    draft = staged(state, "roof-walk", [("ambulance-bay", "roof-walk")]).draft()
    draft.world.require(EntityId("wren-halloway")).known = True
    draft.world.party.append(EntityId("wren-halloway"))
    return draft.committed()


def _full_backpack(state: Game) -> Game:
    """Two more on top of the lantern fills the backpack; the next find lies where it drops."""
    draft = state.draft()
    for item_id, name in (("pry-bar", "a pry bar"), ("water-can", "a water can")):
        draft.world.entities.append(
            Entity(
                id=EntityId(item_id),
                kind="item",
                name=name,
                brief=name,
                known=True,
                parent_id=PLAYER_ID,
                rules={"die": 6},
            )
        )
    return draft.committed()


def _spent_lantern(state: Game) -> Game:
    """An item at d4 has broken, been lost, or faded: it rolls no more."""
    draft = state.draft()
    with rules(draft.world.require(EntityId("lantern")), BreathlessItemSheet) as sheet:
        sheet.die = BreathlessRules.floor
    return draft.committed()


def _breath_caught(state: Game) -> Game:
    """The player's own move landed between turns, and its note owes the group a complication."""
    draft = state.draft()
    _ = apply_catch_breath(draft, Breathe(actor_id=draft.player_id))
    return draft.committed()


def _armed_gatekeeper(state: Game) -> Game:
    """Dov rolls for himself, so he is rated and armed as an authored actor with rules would be."""
    draft = state.draft()
    dov = draft.world.require(EntityId("dov-marek"))
    dov.rules = BreathlessSheet(skills={"Bash": 8}).model_dump(mode="json")
    draft.world.require(EntityId("fire-axe")).parent_id = dov.id
    return draft.committed()


def cases_for(engine_id: EngineId, settings: Settings) -> tuple[Case, ...]:
    canon = canon_for(engine_id)
    # `unless_lost` passes on any outcome outside these, so a missing vocabulary scores vacuously.
    won = canon.won
    _, start = begin(engine_id, settings)
    before = frozenset(trait.id for trait in start.player.traits)
    here, there = canon.climb_from, canon.climb_to
    companion = canon.companion
    # The starter character brings the lantern, so no scenario names it.
    carried = "lantern"

    def below(state: Game) -> Game:
        return staged(state, here, [(here, there)])

    def defence_settled(result: TurnResult) -> bool:
        if not lost_a_roll(result, won):
            return True
        return any(f.kind in ("defence_taken", "defence_turned") for f in result.turn.facts)

    # Only engines that declare a stake tool can miss by skipping it.
    stakes = any(one.name.startswith("stake_") for one in built()[engine_id].director_tools)
    stake_checks = (Expectation("staked", staked_before_rolling),) if stakes else ()
    cases = (
        Case(
            id=f"{engine_id}/find-and-take",
            engine_id=engine_id,
            prompt=(
                f"I search {named(start, start.player_location)} until I turn up "
                f"{named(start, canon.hidden)}, hidden there, and I pick it up and keep it."
            ),
            expectations=(
                Expectation("find-known", lambda r: known(r, canon.hidden)),
                Expectation("find-carried", lambda r: inside(r, canon.hidden, "player")),
                # The item's own `when_reached` tells the Director to advance the thread.
                Expectation("thread-advanced", lambda r: has_fact(r, "thread_advanced")),
            ),
        ),
        Case(
            id=f"{engine_id}/walk-and-look",
            engine_id=engine_id,
            prompt=(
                f"I walk out of {named(start, start.player_location)} into "
                f"{named(start, canon.walk_to)}, and there I look around."
            ),
            expectations=(
                Expectation("player-moved", lambda r: inside(r, "player", canon.walk_to)),
                Expectation("nothing-invented", lambda r: not has_fact(r, "entity_created")),
            ),
        ),
        Case(
            id=f"{engine_id}/three-things",
            engine_id=engine_id,
            # Require a lasting effect because both engines define `add_trait` that way.
            prompt=(
                f"I make my way from {named(start, here)} into {named(start, there)}, hand "
                f"{named(start, carried)} to {named(start, companion)} whom I find there, and "
                "the way up leaves me with a wrenched knee I will be limping on for a long while."
            ),
            expectations=(
                Expectation("player-arrived", lambda r: inside(r, "player", there)),
                Expectation("companion-known", lambda r: known(r, companion)),
                Expectation("item-given", lambda r: inside(r, carried, companion)),
                Expectation(
                    "trait-gained",
                    lambda r: gained_a_trait(r, before),
                ),
            ),
            setup=below,
        ),
        Case(
            id=f"{engine_id}/risky-climb",
            engine_id=engine_id,
            # Reckless haste implies danger without accepting a risk, so 24XX must stake it.
            prompt=(
                f"I rush from {named(start, here)} to {named(start, there)} as fast as I can go, "
                "taking every risk on the way — I have to get there before the light goes."
            ),
            expectations=(
                *stake_checks,
                Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                Expectation(
                    "win-arrived",
                    unless_lost(lambda r: inside(r, "player", there), won),
                ),
            ),
            setup=below,
        ),
    )
    if engine_id == "loner3e":
        cases += (
            Case(
                id=f"{engine_id}/fight-the-rat",
                engine_id=engine_id,
                prompt=(
                    "The bloated rat springs at my throat and I fight it in earnest — it has "
                    "to die before it slips back into the walls."
                ),
                expectations=(
                    # Require the rat so a Tomas conflict cannot satisfy the other checks.
                    Expectation("rat-engaged", lambda r: known(r, "cloister-rat")),
                    Expectation("luck-moved", luck_moved),
                    Expectation("hands-back", conflict_handed_back),
                ),
                setup=lambda state: staged(state, "cloister", []),
            ),
            Case(
                id=f"{engine_id}/finish-the-rat",
                engine_id=engine_id,
                prompt=(
                    "The rat is broken at my feet and still twitching. I bring the stone down "
                    "and finish it."
                ),
                expectations=(Expectation("rat-dead", lambda r: dead(r, "cloister-rat")),),
                setup=_rat_met,
            ),
            Case(
                id=f"{engine_id}/oppose-the-seal",
                engine_id=engine_id,
                # SRD "Everything is a Character": the resisting thing takes `opponent_id`.
                prompt=(
                    "The seal on the vault door hums under my hand — it is awake, and it pushes "
                    "back. I set my pry bar and my will against the seal itself and wrestle it "
                    "for the way down, though it fights me like a living thing."
                ),
                expectations=(
                    Expectation(
                        "seal-sheeted",
                        lambda r: bool(r.state.world.require(EntityId("vault-seal")).rules),
                    ),
                    Expectation("luck-moved", luck_moved),
                    Expectation("hands-back", conflict_handed_back),
                ),
                setup=_seal_met,
            ),
            Case(
                id=f"{engine_id}/sneak-past-tomas",
                engine_id=engine_id,
                # Quiet Hands plus a deaf porter: the one correct position call is advantage.
                # The lantern is hooded so its light cannot be read as the deciding tag instead.
                prompt=(
                    "Brother Tomas is sweeping the colonnade and lifts his head at every scrape "
                    "of grit. I hood my lantern and try to slip through the shadows past him to "
                    "the bell-tower arch — if he marks me, the whole abbey hears of it."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation(
                        "advantage-called", lambda r: card_badge(r, "Position", "Advantage")
                    ),
                ),
                setup=lambda state: staged(state, "cloister", []),
            ),
            Case(
                id=f"{engine_id}/rest-after-conflict",
                engine_id=engine_id,
                prompt=(
                    "The rat breaks off and is gone into the walls — the fight is over. I sit "
                    "against a pillar, get my breath back, and steady myself before I move on."
                ),
                expectations=(
                    Expectation("luck-restored", luck_restored),
                    Expectation(
                        "luck-full",
                        lambda r: (
                            (sheet := sheet_of(r.state, r.state.player_id, LonerSheet)).luck.current
                            == sheet.luck.maximum
                        ),
                    ),
                ),
                setup=_winded,
            ),
            Case(
                id=f"{engine_id}/back-away-at-disadvantage",
                engine_id=engine_id,
                # Never Walks Away is the frailty in play: the one correct position is disadvantage.
                prompt=(
                    "The rat squares up in the colonnade and I try to do the one thing I am "
                    "worst at: turn my back on a fight, walk away from it, and get out of the "
                    "cloister before it comes at me. I have never walked away from anything."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation(
                        "disadvantage-called",
                        lambda r: card_badge(r, "Position", "Disadvantage"),
                    ),
                ),
                setup=_rat_met,
            ),
            Case(
                id=f"{engine_id}/twist-on-the-brink",
                engine_id=engine_id,
                # The counter sits at two: the third tie fires a twist in this very question.
                prompt=(
                    "Brother Tomas is sweeping the colonnade and lifts his head at every scrape "
                    "of grit. I try to slip through the shadows past him to the bell-tower arch "
                    "— if he marks me, the whole abbey hears of it."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation(
                        "twist-if-tied",
                        lambda r: not tied_a_roll(r) or has_fact(r, "twist_due"),
                    ),
                    Expectation(
                        "counter-reset-if-tied",
                        lambda r: not tied_a_roll(r) or _twists_left(r.state) == 0,
                    ),
                ),
                setup=_two_ties_in,
            ),
            Case(
                id=f"{engine_id}/rat-out-of-luck",
                engine_id=engine_id,
                prompt=(
                    "I stay on the rat and press the attack, striking again before it can slip "
                    "back into the walls."
                ),
                expectations=(
                    Expectation("luck-moved", luck_moved),
                    # A won exchange drops the rat to 0: the conflict ends and both pools refill.
                    Expectation(
                        "ended-if-won",
                        lambda r: not won_a_roll(r, won) or has_fact(r, "conflict_lost"),
                    ),
                    Expectation(
                        "refilled-if-won",
                        lambda r: (
                            not won_a_roll(r, won)
                            or (loner_luck(r, "cloister-rat") == 6 and loner_luck(r, "player") == 6)
                        ),
                    ),
                    Expectation(
                        "no-hand-back-if-won",
                        lambda r: not won_a_roll(r, won) or not conflict_handed_back(r),
                    ),
                ),
                setup=_rat_on_its_last_luck,
                answers_decision=True,
            ),
            Case(
                id=f"{engine_id}/grow-after-the-adventure",
                engine_id=engine_id,
                # The advance is owed and the player asks for it by name: one skill gained.
                prompt=(
                    "The adventure is over and I have earned my growth. I take what the vault "
                    "taught me as a new skill: Reads Old Rites. Put it on my sheet now."
                ),
                expectations=(
                    Expectation("skill-gained", lambda r: has_fact(r, "skill_gained")),
                    Expectation(
                        "on-the-sheet",
                        lambda r: any(
                            "rites" in skill.lower()
                            for skill in sheet_of(r.state, r.state.player_id, LonerSheet).skills
                        ),
                    ),
                ),
                setup=lambda state: _adventure_closed(state, canon, LonerSheet),
            ),
            Case(
                id=f"{engine_id}/close-the-adventure",
                engine_id=engine_id,
                # The whole adventure closes by the player's own account: one chapter recorded.
                prompt=(
                    "It is done. The vault stands open, I have what I came to the abbey for, and "
                    "I walk out through the cloister gate with it under my arm. This adventure "
                    "is over; the next one starts somewhere else."
                ),
                expectations=(
                    Expectation("chapter-completed", lambda r: has_fact(r, "chapter_completed")),
                ),
                setup=lambda state: _adventure_done(state, canon),
            ),
        )
    if engine_id == "twentyfourxx":
        cases += (
            Case(
                id=f"{engine_id}/fight-the-wrecker",
                engine_id=engine_id,
                prompt=(
                    "Deel Hask comes out of the Holdfast bar with a salvage cutting bar and goes "
                    "for me, and I fight him in earnest — he is not walking off this road with "
                    "what he takes off the drowned."
                ),
                expectations=(
                    # Require the wrecker so a brawl with the salvagers cannot score the rest.
                    Expectation("wrecker-engaged", lambda r: known(r, "deel-hask")),
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("defence-settled", defence_settled),
                ),
                setup=lambda state: staged(state, "holdfast", []),
            ),
            Case(
                id=f"{engine_id}/buy-the-vest",
                engine_id=engine_id,
                # The catalogue rides the tool description, so this measures the shop end to end.
                prompt=(
                    f"I go to {named(start, 'verrin-ade')} in {named(start, 'holdfast')} and buy "
                    "a vest off her rack, paying her price for it."
                ),
                expectations=(
                    Expectation("vest-carried", lambda r: inside(r, "vest", "player")),
                    Expectation("credits-spent", credits_spent),
                ),
                setup=lambda state: staged(state, "holdfast", []),
            ),
            Case(
                id=f"{engine_id}/armored-defence",
                engine_id=engine_id,
                # The player names and accepts the risk, so a direct roll and a stake both stand.
                prompt=(
                    "Deel Hask comes out of the Holdfast bar with his cutting bar and I meet him "
                    "head on in my battle armor — I know that bar can carve me open and I fight "
                    "him anyway."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("defence-settled", defence_settled),
                    # A hit the armor turned must spend a break: its fresh 3 cannot survive.
                    Expectation(
                        "armor-spent-if-turned",
                        lambda r: (
                            not has_fact(r, "defence_turned") or breaks_left(r, "battle-armor") < 3
                        ),
                    ),
                ),
                setup=_armored,
                choose=lambda pending: (
                    "battle-armor" if pending.kind == "defence" else pending.options[-1].id
                ),
            ),
            Case(
                id=f"{engine_id}/wait-out-the-tide",
                engine_id=engine_id,
                # Time passing under a named threat is the SRD's standalone luck test. The wait
                # must be the whole action: naming the crossing invites staking the crossing.
                prompt=(
                    "I hole up under the siren mast and let the hours pass until the next "
                    "klaxon. I am going nowhere until it sounds — I just wait, out of sight. "
                    "The tide is shifting, and the wrecker who marks travellers is somewhere "
                    "on this road."
                ),
                expectations=(
                    Expectation("bad-luck-rolled", bad_luck_rolled),
                    Expectation("stayed-put", lambda r: inside(r, "player", "siren-mast")),
                ),
            ),
            Case(
                id=f"{engine_id}/burdened-climb",
                engine_id=engine_id,
                # Two bulky items on one climb: the director guidance names this as hindered.
                prompt=(
                    f"I go up {named(start, there)}'s corroded gantry ladder hauling everything "
                    "I own — the battle armor on my back and the full survey pack swinging from "
                    "my shoulder. I know the load could pull me off into the water below, and I "
                    "accept that and climb anyway."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("hindered-called", lambda r: card_badge(r, "Hindered")),
                    Expectation(
                        "win-arrived",
                        unless_lost(lambda r: inside(r, "player", there), won),
                    ),
                ),
                setup=_burdened,
            ),
            Case(
                id=f"{engine_id}/fit-the-skiff",
                engine_id=engine_id,
                # A ship upgrade is a catalogue entry with `onto_id`; the printed price is ₡10.
                prompt=(
                    "The hired tide-skiff at the Holdfast stair is mine for the season, and its "
                    "comms are the basic set. At Verrin's counter I pay to have a tachyon burst "
                    "fitted to the skiff's comms — no lag in-system."
                ),
                expectations=(
                    Expectation("upgrade-installed", lambda r: inside(r, "tachyon-burst", "skiff")),
                    Expectation(
                        "ten-paid",
                        lambda r: any(
                            fact.kind == "counter_changed" and " credits -10 " in fact.trace
                            for fact in r.turn.facts
                        ),
                    ),
                ),
                setup=_docked_skiff,
            ),
            Case(
                id=f"{engine_id}/death-and-succession",
                engine_id=engine_id,
                # The player narrates a death already past saving; recording it is the ruling.
                prompt=(
                    "The gantry ladder sheared and I have already fallen — Kael lies broken on "
                    "the rocks with the tide coming in over him, past any saving. This is his "
                    "death; let it land. Mara Voss climbs down from the relay and reaches him "
                    "as it takes him."
                ),
                expectations=(
                    Expectation("kael-dead", lambda r: dead(r, "player")),
                    Expectation("handed-over", lambda r: has_fact(r, "player_succeeded")),
                    Expectation(
                        "playing-mara", lambda r: r.state.player_id == EntityId("mara-voss")
                    ),
                ),
                setup=_mara_at_hand,
            ),
            Case(
                id=f"{engine_id}/ovid-lends-his-die",
                engine_id=engine_id,
                # An ally who helps rolls their own skill die: Ovid's Labor d10, not a d6.
                prompt=(
                    "The klaxon cable has come off its drum and the tide is rising toward the "
                    "contacts. I ask Ovid to take the drum with his labourer's back while I "
                    "guide the cable — he is the one hauling, I am steering it. I know that "
                    "drum can take my fingers and I risk it."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("helper-die", lambda r: card_badge(r, "Help", "d10")),
                ),
            ),
            Case(
                id=f"{engine_id}/luck-rides-the-attempt",
                engine_id=engine_id,
                # A risked crossing with a named, separate threat: a luck test rides the attempt.
                prompt=(
                    "I start across the drowned road toward Relay Nine between soundings, "
                    "wading the causeway with the water at my thighs — the tide could take me "
                    "and I accept that. And the wrecker who marks travellers is somewhere "
                    "behind me on this shore; whether he has seen me go is out of my hands."
                ),
                expectations=(
                    Expectation("attempt-resolved", lambda r: has_fact(r, "attempt_resolved")),
                    Expectation("bad-luck-rolled", bad_luck_rolled),
                ),
                setup=below,
            ),
            Case(
                id=f"{engine_id}/climb-with-a-broken-arm",
                engine_id=engine_id,
                # An injury that hinders drops the die to d4: the SRD's own example.
                prompt=(
                    f"I go up {named(start, there)}'s corroded gantry ladder one-handed, my "
                    "splinted arm strapped to my chest and useless. I know one slip puts me in "
                    "the water and I climb anyway."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("hindered-called", lambda r: card_badge(r, "Hindered")),
                ),
                setup=_broken_arm,
            ),
            Case(
                id=f"{engine_id}/advance-after-the-job",
                engine_id=engine_id,
                # The advance is owed: one skill up a step and d6 credits, as the SRD prints it.
                prompt=(
                    "The job is done and I have my advance coming. I put what the road taught "
                    "me into my Climbing — take it up a step now."
                ),
                expectations=(
                    Expectation("skill-raised", lambda r: has_fact(r, "skill_increased")),
                    Expectation("climbing-d12", lambda r: skill_face(r, "Climbing") == 12),
                    Expectation("credits-earned", lambda r: counter_rose(r, " credits +")),
                ),
                setup=lambda state: _adventure_closed(state, canon, TwentyfourxxSheet),
            ),
            Case(
                id=f"{engine_id}/close-the-job",
                engine_id=engine_id,
                prompt=(
                    "That is the job: the founding survey is in my pack, the vault deck is "
                    "behind me, and I am back on the Holdfast shore with it. It is done and "
                    "paid; the next job starts somewhere else."
                ),
                expectations=(
                    Expectation("chapter-completed", lambda r: has_fact(r, "chapter_completed")),
                ),
                setup=lambda state: _adventure_done(state, canon),
            ),
        )
    if engine_id == "breathless":
        cases += (
            Case(
                id=f"{engine_id}/climb-the-scaffold",
                engine_id=engine_id,
                # The player names and accepts the exact risk, so the stake is already paid.
                prompt=(
                    "I go up the bay scaffold to the roof walk. I know the clamps have rusted "
                    "loose and a slip drops me six storeys onto the apron — that is the risk, I "
                    "accept it, and I climb."
                ),
                expectations=(
                    Expectation("dash-rolled", lambda r: skill_rolled(r, "Dash")),
                    Expectation("rolled-direct", lambda r: not staked_before_rolling(r)),
                ),
                setup=below,
            ),
            Case(
                id=f"{engine_id}/force-the-stair-door",
                engine_id=engine_id,
                # Wrecking and forcing is Bash, and the prompt puts the cutters out of reach.
                prompt=(
                    "The stairwell door at the end of the triage hall is chained shut from this "
                    "side. I am not asking Sela for her cutters and I am not paying her price: I "
                    "put my boot and my shoulder into it and tear the chain out of the frame."
                ),
                expectations=(Expectation("bash-rolled", lambda r: skill_rolled(r, "Bash")),),
                setup=lambda state: staged(state, "triage-hall", []),
            ),
            Case(
                id=f"{engine_id}/slip-past-the-gate",
                engine_id=engine_id,
                # Hiding and skulking is Sneak, Kael's d10: the roll must wear it down a step.
                prompt=(
                    "Dov Marek is working the burn drum with his back half to the gate. I keep "
                    "the dead rig between us, go low and quiet along the wall, and slip out "
                    "through the gate into the triage hall before he turns round."
                ),
                expectations=(
                    Expectation("sneak-rolled", lambda r: skill_rolled(r, "Sneak")),
                    Expectation("sneak-worn", lambda r: worn_down(r, "Sneak")),
                ),
            ),
            Case(
                id=f"{engine_id}/talk-dov-round",
                engine_id=engine_id,
                # Charming, manipulating and intimidating is Sway.
                prompt=(
                    "I put my hands where Dov Marek can see them and talk him into opening the "
                    "gate for me — what I am after, and what the block gets out of it. He has "
                    "not let anyone in after dark in four years and I have to change his mind."
                ),
                expectations=(Expectation("sway-rolled", lambda r: skill_rolled(r, "Sway")),),
            ),
            Case(
                id=f"{engine_id}/mend-the-floodlight",
                engine_id=engine_id,
                # Perceiving, analyzing and repairing is Think.
                prompt=(
                    "The dead rig still has a floodlight on its roof bar and I want it working "
                    "before I go inside. I strip the wiring back and work the battery cell over, "
                    "tracing the fault by hand — cross the wrong pair and it goes across me."
                ),
                expectations=(Expectation("think-rolled", lambda r: skill_rolled(r, "Think")),),
            ),
            Case(
                id=f"{engine_id}/swing-the-fire-axe",
                engine_id=engine_id,
                # An item rolls in place of a skill, and it must be in hand before it rolls.
                prompt=(
                    "I lift the fire axe off the bay wall bracket and take it to the gurney rack "
                    "in the dead ambulance. The rack is welded down and I am swinging hard in a "
                    "metal box to get it open — I know the head can come back at me."
                ),
                expectations=(
                    Expectation("axe-in-hand", lambda r: inside(r, "fire-axe", "player")),
                    Expectation("axe-rolled", lambda r: item_rolled(r, "fire-axe")),
                ),
            ),
            Case(
                id=f"{engine_id}/stunt-the-gate",
                engine_id=engine_id,
                # A declared stunt rolls the d12 instead of a skill, however low that skill is.
                prompt=(
                    "Dov Marek is between me and the gate and I am done talking. I pull a stunt: "
                    "up onto the burn drum and over the welded gate frame in one showy vault, out "
                    "into the hall before he can turn round. One shot at it, and I know that "
                    "frame will open my leg up if I catch it."
                ),
                expectations=(Expectation("stunt-rolled", stunt_rolled),),
            ),
            Case(
                id=f"{engine_id}/stunt-already-spent",
                engine_id=engine_id,
                # The stunt is spent until they catch their breath: the engine refuses a second.
                prompt=(
                    "I pull another stunt on Dov Marek: up the burn drum and over the welded gate "
                    "frame in one showy vault, and I know that frame will open my leg up if I "
                    "catch it."
                ),
                expectations=(Expectation("no-second-stunt", lambda r: not stunt_rolled(r)),),
                setup=_stunt_spent,
            ),
            Case(
                id=f"{engine_id}/wren-braces-the-clamp",
                engine_id=engine_id,
                # An ally here who helps rolls their own die into the same pool and shares the risk.
                prompt=(
                    "The scaffold clamps under the plank have worked loose and the span is "
                    "shifting. I ask Wren Halloway to put her weight on the far end and hold it "
                    "while I get the clamp bolted back down — if it goes while we are both out "
                    "there we drop six storeys, and I take that on."
                ),
                expectations=(
                    Expectation("helped-roll", rolled_with_help),
                    Expectation("player-rolled", lambda r: worn_by(r, PLAYER_ID)),
                    Expectation("wren-rolled", lambda r: worn_by(r, "wren-halloway")),
                ),
                setup=_wren_at_hand,
            ),
            Case(
                id=f"{engine_id}/ask-the-generator",
                engine_id=engine_id,
                # A question of chance about the world: a die decides it, rated by long odds.
                prompt=(
                    "Saint Ivo's kept a standby generator behind the bay. Eleven years of "
                    "scavengers have been through this block and fuel is the first thing any of "
                    "them takes, so it would be a small miracle if there is a drop left in its "
                    "tank. Is there? I have no way of knowing before I get to it."
                ),
                expectations=(
                    Expectation("luck-tested", lambda r: has_fact(r, "luck_tested")),
                    Expectation("long-odds-die", lambda r: 0 < luck_die(r) <= 6),
                ),
            ),
            Case(
                id=f"{engine_id}/scavenge-the-rig",
                engine_id=engine_id,
                # Scavenging where the fiction allows it rolls the loot die and steps it down.
                prompt=(
                    "I go through the dead ambulance properly — every drawer, every locker, the "
                    "door bins — for anything I can use out of there: a crowbar, a strap, a "
                    "length of hose, whatever it still holds."
                ),
                expectations=(
                    Expectation("loot-rolled", lambda r: has_fact(r, "loot_found")),
                    Expectation(
                        "loot-die-worn",
                        lambda r: breathless_sheet(r).loot < BreathlessRules.loot_start,
                    ),
                ),
            ),
            Case(
                id=f"{engine_id}/scavenge-on-a-spent-loot-die",
                engine_id=engine_id,
                # A loot die at d4 still rolls, at the player's own risk: it is not a spent item.
                prompt=(
                    "I have turned this rig over twice already and there is nothing good left in "
                    "it. I go through the door bins and the underseat lockers one more time "
                    "anyway — a strap, a wrench, anything at all. I know the only thing left to "
                    "turn up in there is trouble and I want it turned over regardless."
                ),
                expectations=(
                    Expectation("loot-rolled", lambda r: has_fact(r, "loot_found")),
                    Expectation(
                        "loot-die-held",
                        lambda r: breathless_sheet(r).loot == BreathlessRules.floor,
                    ),
                ),
                setup=_spent_loot_die,
            ),
            Case(
                id=f"{engine_id}/scavenge-with-a-full-backpack",
                engine_id=engine_id,
                # The backpack holds three: a fourth find lies where they stand, uncarried.
                prompt=(
                    "My hands are full already, but I go through the ambulance's lockers anyway "
                    "for anything else worth carrying out of here."
                ),
                expectations=(
                    Expectation("loot-rolled", lambda r: has_fact(r, "loot_found")),
                    Expectation(
                        "backpack-held", lambda r: carried_items(r) <= BreathlessRules.carry
                    ),
                ),
                setup=_full_backpack,
            ),
            Case(
                id=f"{engine_id}/stress-from-the-drum",
                engine_id=engine_id,
                # A complication that leaves no wound costs stress: nothing here is a trait.
                prompt=(
                    "Dov Marek drags what the night left at the gate over to the burn drum and I "
                    "stand there and watch him put it in. Nothing touches me and nothing of mine "
                    "is hurt, but I cannot stop shaking afterwards and I cannot get the smell "
                    "back out of my head. That is stress, and I am taking it."
                ),
                expectations=(Expectation("stress-added", lambda r: counter_rose(r, " stress +")),),
            ),
            Case(
                id=f"{engine_id}/bar-the-door-and-rest",
                engine_id=engine_id,
                # A secure rest clears stress: the negative side of the same tool.
                prompt=(
                    "I roll the dead rig across the mouth of the bay, bar the gate behind it, "
                    "and sleep four hours in the back of it with the doors shut — the first safe "
                    "rest since I came into the block."
                ),
                expectations=(
                    Expectation("stress-cleared", lambda r: counter_rose(r, " stress -")),
                    Expectation("stress-lower", lambda r: breathless_sheet(r).stress.current < 3),
                ),
                setup=lambda state: _stressed(state, 3),
            ),
            Case(
                id=f"{engine_id}/use-the-med-kit",
                engine_id=engine_id,
                # "I use my med kit" in chat spends the kit for exactly 2, not a free change_stress.
                prompt=(
                    "I am shaking and I have had enough of it. I get the med kit out of my pack, "
                    "sit down on the rig's step, and patch myself up with it before I go one step "
                    "further into this place."
                ),
                expectations=(
                    Expectation("cleared-two", lambda r: counter_rose(r, " stress -2")),
                    Expectation("kit-spent", lambda r: not breathless_sheet(r).med_kit),
                ),
                setup=_med_kit_at_hand,
            ),
            Case(
                id=f"{engine_id}/vulnerable-and-forcing-it",
                engine_id=engine_id,
                # At 4 stress a failed dangerous check is taken out or dead, and Bash is a d4.
                prompt=(
                    "I am spent, shaking, and running on nothing, and I do it anyway: I get "
                    "under the welded bed-frame gate and heave it off its hinges with my back, "
                    "with the whole frame coming down on me if it drops. I accept that."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation(
                        "flagged-if-failed",
                        lambda r: not failed_a_check(r) or flagged_vulnerable(r),
                    ),
                    Expectation(
                        "ruled-if-failed",
                        lambda r: (
                            not failed_a_check(r)
                            or has_fact(r, "trait_added")
                            or has_fact(r, "actor_killed")
                        ),
                    ),
                ),
                setup=lambda state: _stressed(state, 4),
            ),
            Case(
                id=f"{engine_id}/after-the-breath",
                engine_id=engine_id,
                # Catching their breath costs the group a new complication, however quiet the turn.
                prompt=(
                    "I sit down on the rig's step out of the wind, wipe my hands, and let myself "
                    "do nothing at all for a minute before I go on."
                ),
                expectations=(Expectation("complication-landed", complicated),),
                setup=_breath_caught,
            ),
            Case(
                id=f"{engine_id}/spent-lantern",
                engine_id=engine_id,
                # The lantern stands at d4: broken, lost, or faded, and it rolls no more.
                prompt=(
                    "I hold the lantern up and work its light through the rig and over the "
                    "gurney rack — I have to find what is in there fast, Dov is coming across "
                    "the apron and the light is the only way I see anything in that box."
                ),
                expectations=(
                    Expectation("no-spent-roll", lambda r: not item_rolled(r, "lantern")),
                ),
                setup=_spent_lantern,
            ),
            Case(
                id=f"{engine_id}/dov-swings-the-axe",
                engine_id=engine_id,
                # Only players roll in Breathless: a threat is the player's own dangerous check.
                prompt=(
                    "I am going through that gate whether Dov Marek likes it or not. He comes off "
                    "the burn drum with the fire axe already up and I do not stop and do not slow "
                    "down: I go past him and out into the hall, and if he lands that axe on my "
                    "way through it opens me up."
                ),
                expectations=(
                    Expectation("player-rolled", lambda r: rolled_for(r, "player")),
                    Expectation("dov-not-rolled", lambda r: not rolled_for(r, "dov-marek")),
                    Expectation(
                        "hurt-if-lost",
                        lambda r: (
                            not lost_a_roll(r, won)
                            or has_fact(r, "trait_added")
                            or has_fact(r, "counter_changed")
                        ),
                    ),
                ),
                setup=_armed_gatekeeper,
            ),
            Case(
                id=f"{engine_id}/no-improvised-brick",
                engine_id=engine_id,
                # Throwing is Shoot, and a thing picked up off the ground is no item: loot only.
                prompt=(
                    "I pick up a lump of broken concrete off the apron and throw it hard at the "
                    "burn drum, right across the bay, to knock the lid off it and pull Dov Marek "
                    "off the gate. It is a long throw; if it falls short it just rolls into the "
                    "dark and I have wasted the moment."
                ),
                expectations=(
                    Expectation("nothing-created", lambda r: not has_fact(r, "entity_created")),
                    Expectation("shoot-rolled", lambda r: skill_rolled(r, "Shoot")),
                ),
            ),
        )
    return cases


async def play(case: Case, settings: Settings, seed: int) -> Run:
    engine, state = begin(case.engine_id, settings)
    stages = build_turn_agents(engine, settings)
    rng = Random(seed)
    started = perf_counter()
    segments: list[TurnResult] = []
    try:
        played = case.setup(state)
        player_input: str | Answer = (
            Answer(text=case.prompt) if case.answers_decision else case.prompt
        )
        answered: set[Slug] = set()
        for _ in range(SEGMENT_CAP):
            result = await run_segment(
                played,
                player_input,
                engine=engine,
                stages=stages,
                settings=settings,
                rng=rng,
            )
            segments.append(result)
            played = result.state
            if played.pending is None:
                break
            # A case scripts one answer per decision kind: an unscripted hand-back, or a kind
            # already answered (a fight's next exchange), is a choice no case scripts.
            if not played.pending.options or played.pending.kind in answered:
                break
            answered.add(played.pending.kind)
            player_input = Answer(option_id=case.choose(played.pending))
        else:
            raise ValueError(f"the interaction was still going after {SEGMENT_CAP} segments")
        merged = _merged(case.prompt, segments)
        steps = merged.turn.steps
        passed = {check.name: check.holds(merged) for check in case.expectations}
        return Run(
            passed=passed,
            facts=[f"{fact.kind}: {fact.trace}" for fact in merged.turn.facts],
            steps=[] if all(passed.values()) else list(steps),
            director_calls=sum(1 for step in steps if step.name == "director"),
            refusals=[refusal for step in steps for refusal in step.refusals],
            total_steps=len(steps),
            seconds=perf_counter() - started,
            narration_chars=len(merged.turn.narration),
        )
    except Exception as error:
        return Run(
            error=f"{type(error).__name__}: {error}",
            passed={check.name: False for check in case.expectations},
            facts=[f"{fact.kind}: {fact.trace}" for _, trace in segments for fact in trace.facts],
            steps=[step for _, trace in segments for step in trace.steps],
            seconds=perf_counter() - started,
        )


def _merged(prompt: str, segments: Sequence[TurnResult]) -> TurnResult:
    """The interaction as one result: every segment's prose, facts and steps, the last state."""
    return TurnResult(
        segments[-1].state,
        TurnTrace(
            prompt=prompt,
            facts=tuple(fact for _, trace in segments for fact in trace.facts),
            narration="\n".join(trace.narration for _, trace in segments if trace.narration),
            steps=tuple(step for _, trace in segments for step in trace.steps),
        ),
    )


async def play_all(
    cases: Sequence[Case], settings: Settings, repeats: int, seed: int, concurrency: int
) -> list[CaseResult]:
    limit = asyncio.Semaphore(concurrency)

    async def one(case: Case, repeat: int) -> Run:
        async with limit:
            return await play(case, settings, seed + repeat)

    async with asyncio.TaskGroup() as group:
        tasks = [[group.create_task(one(case, n)) for n in range(repeats)] for case in cases]
    return [
        CaseResult(
            id=case.id,
            engine=case.engine_id,
            prompt=case.prompt,
            expectations=[check.name for check in case.expectations],
            runs=[task.result() for task in row],
        )
        for case, row in zip(cases, tasks, strict=True)
    ]


def print_report(report: Report) -> None:
    for case in report.cases:
        runs, total = case.runs, len(case.runs)
        scored = sum(1 for run in runs if run.scored)
        errors = sum(1 for run in runs if run.error is not None)
        print(
            f"{case.id:<40} score {scored}/{total} ({scored / total:.0%})"
            f"  errors {errors}/{total}"
            f"  director_calls {mean([run.director_calls for run in runs]):.1f}"
            f"  refusals {sum(len(run.refusals) for run in runs)}"
            f"  {mean([run.seconds for run in runs]):.1f}s"
        )
        for refusal in sorted({one for run in runs for one in run.refusals}):
            print(f"    ! refused: {refusal.splitlines()[0][:110]}")
        for name in case.expectations:
            print(f"    {name:<36} {case.rate(name):.0%}")
        for run in runs:
            if run.error is not None:
                print(f"    ! {run.error}")


def select(settings: Settings, ids: Sequence[str], engine: str | None) -> list[Case]:
    engines = tuple(built()) if engine is None else (EngineId(engine),)
    if unknown := [name for name in engines if name not in built()]:
        raise SystemExit(f"unknown engine(s): {unknown}")
    cases = [case for name in engines for case in cases_for(name, settings)]
    if not ids:
        return cases
    chosen = [case for case in cases if case.id in ids]
    if missing := sorted(set(ids) - {case.id for case in chosen}):
        raise SystemExit(f"unknown case id(s): {missing}. Known: {[c.id for c in cases]}")
    return chosen


def run_command(args: argparse.Namespace) -> None:
    label: str = args.label
    settings = load_settings()
    cases = select(settings, args.case, args.engine)
    started = perf_counter()
    results = asyncio.run(
        play_all(cases, settings, args.repeats, args.seed, args.concurrency),
    )
    report = Report(label=label, repeats=args.repeats, seed=args.seed, cases=results)
    RESULTS.mkdir(parents=True, exist_ok=True)
    written = RESULTS / f"{label}.json"
    _ = written.write_text(report.model_dump_json(indent=2))
    print_report(report)
    print(f"\n{label}: {len(cases)} cases in {perf_counter() - started:.1f}s -> {written}")


def _overall(report: Report) -> tuple[float, float, float, float]:
    runs = [run for case in report.cases for run in case.runs]
    return (
        mean([float(run.scored) for run in runs]),
        mean([float(run.error is not None) for run in runs]),
        mean([run.director_calls for run in runs]),
        mean([run.seconds for run in runs]),
    )


def _delta(before: float, after: float) -> str:
    return f"{before:.0%} -> {after:.0%} ({after - before:+.0%})"


def compare_command(args: argparse.Namespace) -> None:
    baseline = Report.model_validate_json(Path(args.baseline).read_text())
    candidate = Report.model_validate_json(Path(args.candidate).read_text())
    was = {case.id: case for case in baseline.cases}
    for case in candidate.cases:
        old = was.pop(case.id, None)
        if old is None:
            print(f"{case.id:<40} new")
            continue
        scored = mean([float(run.scored) for run in case.runs])
        print(f"{case.id:<40} score {_delta(mean([float(r.scored) for r in old.runs]), scored)}")
        for name in case.expectations:
            seen = f"{case.rate(name):.0%}" if name in old.expectations else "new"
            known_before = f"{old.rate(name):.0%} -> " if name in old.expectations else ""
            print(f"    {name:<36} {known_before}{seen}")
    for case_id in was:
        print(f"{case_id:<40} missing from candidate")
    labels = (baseline.label, candidate.label)
    old_score, old_errors, old_calls, old_seconds = _overall(baseline)
    new_score, new_errors, new_calls, new_seconds = _overall(candidate)
    print(f"\noverall {labels[0]} -> {labels[1]}")
    print(f"  score          {_delta(old_score, new_score)}")
    print(f"  errors         {_delta(old_errors, new_errors)}")
    print(f"  director_calls {old_calls:.2f} -> {new_calls:.2f} ({new_calls - old_calls:+.2f})")
    gap = new_seconds - old_seconds
    print(f"  seconds        {old_seconds:.1f} -> {new_seconds:.1f} ({gap:+.1f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn-quality benchmark (makes real model calls)")
    commands = parser.add_subparsers(dest="command", required=True)

    runner = commands.add_parser("run")
    _ = runner.add_argument("--label", required=True)
    _ = runner.add_argument("--repeats", type=int, default=9)
    _ = runner.add_argument("--concurrency", type=int, default=4)
    _ = runner.add_argument("--seed", type=int, default=1000)
    _ = runner.add_argument("--case", action="append", default=[])
    _ = runner.add_argument("--engine", default=None)
    runner.set_defaults(handler=run_command)

    comparison = commands.add_parser("compare")
    _ = comparison.add_argument("--baseline", required=True)
    _ = comparison.add_argument("--candidate", required=True)
    comparison.set_defaults(handler=compare_command)

    args = parser.parse_args()
    handler: Callable[[argparse.Namespace], None] = args.handler
    handler(args)


if __name__ == "__main__":
    main()
