from collections.abc import Callable, Sequence
from dataclasses import dataclass

from aidm.config import Settings
from aidm.state.entities import DEAD, EngineId, EntityId, Slug
from aidm.state.model import Game
from aidm.world.topology import player_location
from evals.turn_eval import Case, Expectation, Played, begin, built


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


def below(canon: Canon) -> Callable[[Game], Game]:
    """At the foot of the climb, with the way up already known."""
    return lambda state: staged(state, canon.climb_from, [(canon.climb_from, canon.climb_to)])


def known(result: Played, entity_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.known


def inside(result: Played, entity_id: str, holder: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.parent_id == EntityId(holder)


def dead(result: Played, entity_id: str) -> bool:
    entity = result.state.world.find(EntityId(entity_id))
    return entity is not None and entity.trait(DEAD) is not None


def has_fact(result: Played, kind: str) -> bool:
    return any(fact.kind == kind for fact in result.facts)


def gained_a_trait(result: Played, before: frozenset[str]) -> bool:
    return bool({trait.id for trait in result.state.player.traits} - before)


def card_says(result: Played, text: str) -> bool:
    """A card carried the line: how helped, hindered, and position reach the record."""
    return any(text in fact.card for fact in result.facts)


def counter_rose(result: Played, marker: str) -> bool:
    return any(fact.kind == "counter_changed" and marker in fact.trace for fact in result.facts)


def staked_before_rolling(result: Played) -> bool:
    """The first segment ended on the stake's hand-back, with no roll taken in it."""
    history = result.state.history
    return (
        bool(history)
        and bool(history[0].decision)
        and not any(fact.card.startswith(("Attempt", "Check")) for fact in history[0].facts)
    )


# The facts that carry a resolved roll's outcome; luck tests and twists excuse nothing.
ROLL_FACTS = ("attempt_resolved", "question_answered", "check_resolved")


def _outcome(trace: str) -> str:
    """Breathless appends a vulnerability warning after the outcome; the tail stops at it."""
    return trace.rsplit("-> ", 1)[1].split(". ", 1)[0]


def player_outcomes(result: Played) -> list[str]:
    """Outcomes of the player's own resolved rolls: NPC rolls and luck tests count for nothing."""
    return [
        _outcome(fact.trace)
        for fact in result.facts
        if fact.kind in ROLL_FACTS
        and fact.entity_id == result.state.player_id
        and "-> " in fact.trace
    ]


def lost_a_roll(result: Played, won: Sequence[str]) -> bool:
    return any(outcome not in won for outcome in player_outcomes(result))


def unless_lost(holds: Callable[[Played], bool], won: Sequence[str]) -> Callable[[Played], bool]:
    """A lost roll fairly strands the climber below, so its consequences go unscored."""
    return lambda result: lost_a_roll(result, won) or holds(result)


def adventure_done(state: Game, canon: Canon) -> Game:
    """The main thread is spent: the world agrees with a player who says the adventure is over."""
    draft = staged(state, canon.walk_to, []).draft()
    thread = draft.world.thread(canon.thread)
    if thread is None:
        raise ValueError(f"no thread {canon.thread!r}")
    thread.note = canon.done_note
    return draft.committed()


def adventure_closed(state: Game, canon: Canon, close: Callable[[Game], object]) -> Game:
    """One chapter closed and no advance taken yet: the Director owes the player one."""
    draft = adventure_done(state, canon).draft()
    thread = draft.world.thread(canon.thread)
    if thread is None:
        raise ValueError(f"no thread {canon.thread!r}")
    thread.status = "resolved"
    _ = close(draft)
    return draft.committed()


def cases_for(engine_id: EngineId, canon: Canon, settings: Settings) -> tuple[Case, ...]:
    # `unless_lost` passes on any outcome outside these, so a missing vocabulary scores vacuously.
    won = canon.won
    _, start = begin(engine_id, settings)
    before = frozenset(trait.id for trait in start.player.traits)
    here, there = canon.climb_from, canon.climb_to
    companion = canon.companion
    # The starter character brings the lantern, so no scenario names it.
    carried = "lantern"
    # Only engines that declare a stake tool can miss by skipping it.
    stakes = any(one.name.startswith("stake_") for one in built()[engine_id].tools)
    stake_checks = (Expectation("staked", staked_before_rolling),) if stakes else ()
    return (
        Case(
            id=f"{engine_id}/find-and-take",
            engine_id=engine_id,
            prompt=(
                f"I search {named(start, player_location(start))} until I turn up "
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
                f"I walk out of {named(start, player_location(start))} into "
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
            setup=below(canon),
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
            setup=below(canon),
        ),
    )
