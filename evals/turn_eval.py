import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from aidm.app.launch import engine_ids
from aidm.config import Settings, load_settings
from aidm.content.io import load_character, load_scenario
from aidm.engines.core import Engine
from aidm.engines.loner3e.rules import Mechanics as LonerMechanics
from aidm.engines.registry import begin_game, build_engine
from aidm.engines.twentyfourxx.rules import Mechanics as TwentyfourxxMechanics
from aidm.state.entities import (
    DEAD,
    PLAYER_ID,
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
ENGINES = engine_ids()
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
    # Only a stage the scenario's own `when_reached` names can be scored; "" leaves it unscored.
    hidden_stage: str = ""
    companion_stage: str = ""
    # A locked way the scenario guards; "" skips the locked-way case for that engine.
    locked_from: str = ""
    locked_to: str = ""


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
        hidden_stage="stair-charted",
        companion_stage="archivist-found",
        locked_from="cloister",
        locked_to="vault",
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
        hidden_stage="spike-found",
        companion_stage="relay-reached",
        locked_from="relay-nine",
        locked_to="vault-deck",
    ),
}


def canon_for(engine_id: EngineId) -> Canon:
    canon = CANON.get(engine_id)
    if canon is None:
        raise SystemExit(f"engine {engine_id!r} names no scenario for the eval")
    return canon


def begin(engine_id: EngineId, settings: Settings) -> tuple[Engine, Game]:
    engine = build_engine(engine_id)
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


def staged_at(result: TurnResult, thread_id: str, stage: str) -> bool:
    thread = result.state.world.thread(thread_id)
    return thread is not None and thread.stage == stage


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
        and not any(event.title == "Attempt" for event in history[0].events)
    )


# The facts that carry a resolved roll's outcome; luck tests and twists excuse nothing.
ROLL_FACTS = ("attempt_resolved", "question_answered")


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


def has_trait(result: TurnResult, entity_id: str, trait_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.trait(trait_id) is not None


def way_locked(result: TurnResult, source: str, target: str) -> bool:
    way = result.state.world.require_kind(EntityId(source), "location").exit_to(EntityId(target))
    return way is not None and way.locked


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


def luck_restored(result: TurnResult) -> bool:
    return any(
        fact.kind == "counter_changed" and " luck +" in fact.trace for fact in result.turn.facts
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
    LonerMechanics.of_game(draft).sheets[draft.player_id].luck.current = 2
    return draft.committed()


def _bulky_gear(item_id: str, name: str, breaks: int = 1) -> Entity:
    traits = [Trait(id="bulky", name="Bulky")]
    if breaks > 1:
        traits.append(Trait(id=f"breaks-{breaks}", name=f"Breaks {breaks}x"))
    return Entity(
        id=EntityId(item_id),
        kind="item",
        name=name,
        brief=name,
        known=True,
        parent_id=PLAYER_ID,
        traits=traits,
    )


def _armored(state: Game) -> Game:
    draft = staged(state, "holdfast", []).draft()
    draft.world.entities.append(
        _bulky_gear("battle-armor", "battle armor off Verrin's rack", breaks=3)
    )
    return draft.committed()


def _burdened(state: Game) -> Game:
    draft = staged(state, "siren-mast", [("siren-mast", "relay-nine")]).draft()
    draft.world.entities.append(_bulky_gear("battle-armor", "battle armor", breaks=3))
    draft.world.entities.append(_bulky_gear("survey-pack", "a full survey pack"))
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
    TwentyfourxxMechanics.of_game(draft).sheets[draft.player_id].credits.current = 12
    return draft.committed()


def _mara_at_hand(state: Game) -> Game:
    draft = staged(state, "relay-nine", []).draft()
    draft.world.require(EntityId("mara-voss")).known = True
    draft.world.party.append(EntityId("mara-voss"))
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

    # Only 24XX declares the stake tool, so only there is skipping it a miss.
    stake_checks = (
        (Expectation("staked", staked_before_rolling),) if engine_id == "twentyfourxx" else ()
    )
    # Scored only where the scenario's own `when_reached` tells the Director which stage to set.
    find_stage = (
        (Expectation("thread-staged", lambda r: staged_at(r, canon.thread, canon.hidden_stage)),)
        if canon.hidden_stage
        else ()
    )
    met_stage = (
        (
            Expectation(
                "thread-staged",
                unless_lost(lambda r: staged_at(r, canon.thread, canon.companion_stage), won),
            ),
        )
        if canon.companion_stage
        else ()
    )
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
                *find_stage,
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
            id=f"{engine_id}/open-the-way-and-climb",
            engine_id=engine_id,
            # Exclude searches because a valid failed search leaves the one who keeps it hidden.
            prompt=(
                f"I make my way from {named(start, here)} into {named(start, there)}, and the "
                f"moment I am through I see {named(start, companion)}, who keeps the place, "
                "standing there in plain sight."
            ),
            expectations=(
                Expectation(
                    "player-arrived",
                    unless_lost(lambda r: inside(r, "player", there), won),
                ),
                Expectation("companion-known", unless_lost(lambda r: known(r, companion), won)),
                *met_stage,
            ),
            setup=below,
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
    if canon.locked_from:
        source, target = canon.locked_from, canon.locked_to
        cases += (
            Case(
                id=f"{engine_id}/locked-way",
                engine_id=engine_id,
                # Pure presumption, no attempt on the seal: the one correct ruling is a refusal.
                prompt=(
                    f"I walk straight from {named(start, source)} into {named(start, target)} as "
                    "if the way stood open — I do not stop to deal with whatever seals it, I "
                    "simply walk in."
                ),
                # A roll the player won may fairly open the way; an unearned walk-through fails.
                expectations=(
                    Expectation(
                        "held-out",
                        lambda r: won_a_roll(r, won) or not inside(r, "player", target),
                    ),
                    Expectation(
                        "still-locked",
                        lambda r: won_a_roll(r, won) or way_locked(r, source, target),
                    ),
                    Expectation("nothing-invented", lambda r: not has_fact(r, "entity_created")),
                ),
                setup=lambda state: staged(state, source, []),
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
                id=f"{engine_id}/press-the-conflict",
                engine_id=engine_id,
                # Both pools sit at 6 and one exchange moves at most 3, so the hand-back is sure.
                prompt=(
                    "I stay on the rat and press the attack, striking again before it can slip "
                    "back into the walls."
                ),
                expectations=(
                    Expectation("luck-moved", luck_moved),
                    Expectation("hands-back", conflict_handed_back),
                ),
                setup=_mid_conflict,
                answers_decision=True,
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
                        lambda r: EntityId("vault-seal") in LonerMechanics.of_game(r.state).sheets,
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
                prompt=(
                    "Brother Tomas is sweeping with his back to me, deaf to the world. On quiet "
                    "hands I slip through the colonnade shadows past him toward the bell-tower "
                    "arch — he must not mark me."
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
                            (
                                sheet := LonerMechanics.of_game(r.state).sheets[r.state.player_id]
                            ).luck.current
                            == sheet.luck.maximum
                        ),
                    ),
                ),
                setup=_winded,
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
                    # A hit the armor turned must spend a break: the fresh 3x mark cannot survive.
                    Expectation(
                        "armor-spent-if-turned",
                        lambda r: (
                            not has_fact(r, "defence_turned")
                            or not has_trait(r, "battle-armor", "breaks-3")
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
                id=f"{engine_id}/haul-with-ovid",
                engine_id=engine_id,
                # An ally's die or a helpful circumstance both land the Help badge on the card.
                prompt=(
                    "The klaxon cable has come off its drum and the tide is rising toward the "
                    "contacts. Ovid takes the cable's weight with me and together we haul it "
                    "back up the mast — I know that drum can take my fingers and I risk it."
                ),
                expectations=(
                    Expectation("dice-rolled", lambda r: has_fact(r, "dice_rolled")),
                    Expectation("help-counted", lambda r: card_badge(r, "Help")),
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
            if not played.pending.options:
                # An unscripted hand-back ends the interaction; the expectations judge it.
                break
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
            total_steps=len(steps),
            seconds=perf_counter() - started,
            narration_chars=len(merged.turn.narration),
        )
    except Exception as error:
        return Run(
            error=f"{type(error).__name__}: {error}",
            passed={check.name: False for check in case.expectations},
            facts=[
                f"{fact.kind}: {fact.trace}" for segment in segments for fact in segment.turn.facts
            ],
            steps=[step for segment in segments for step in segment.turn.steps],
            seconds=perf_counter() - started,
        )


def _merged(prompt: str, segments: Sequence[TurnResult]) -> TurnResult:
    """The interaction as one result: every segment's prose, facts and steps, the last state."""
    return TurnResult(
        state=segments[-1].state,
        turn=TurnTrace(
            prompt=prompt,
            facts=tuple(fact for segment in segments for fact in segment.turn.facts),
            narration="\n".join(
                segment.turn.narration for segment in segments if segment.turn.narration
            ),
            steps=tuple(step for segment in segments for step in segment.turn.steps),
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
            f"  {mean([run.seconds for run in runs]):.1f}s"
        )
        for name in case.expectations:
            print(f"    {name:<36} {case.rate(name):.0%}")
        for run in runs:
            if run.error is not None:
                print(f"    ! {run.error}")


def select(settings: Settings, ids: Sequence[str], engine: str | None) -> list[Case]:
    engines = ENGINES if engine is None else (EngineId(engine),)
    if unknown := [name for name in engines if name not in ENGINES]:
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
