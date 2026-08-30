from collections.abc import Sequence

from aidm.config import Settings
from aidm.engines.core import mechanics_of, rules, sheet_of
from aidm.engines.loner3e.engine import complete_chapter
from aidm.engines.loner3e.rules import TIES_PER_TWIST, Loner3eState
from aidm.engines.loner3e.rules import Sheet as LonerSheet
from aidm.state.entities import EngineId, Entity, EntityId
from aidm.state.model import Game
from aidm.state.play import PendingDecision
from evals.cases.shared import (
    Canon,
    adventure_closed,
    adventure_done,
    card_says,
    cases_for,
    counter_rose,
    dead,
    has_fact,
    known,
    player_outcomes,
    staged,
)
from evals.turn_eval import Case, Expectation, Played

ENGINE_ID = EngineId("loner3e")

CANON = Canon(
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
)


def luck_moved(result: Played) -> bool:
    # The counter key sits between the actor label and the delta arrow in the trace.
    return any(fact.kind == "counter_changed" and " luck " in fact.trace for fact in result.facts)


def conflict_handed_back(result: Played) -> bool:
    pending = result.state.pending
    return pending is not None and pending.kind == "conflict"


def won_a_roll(result: Played, won: Sequence[str]) -> bool:
    return any(outcome in won for outcome in player_outcomes(result))


def loner_sheet(state: Game, entity_id: str) -> LonerSheet:
    game = mechanics_of(state.world, Loner3eState)
    return sheet_of(game.sheets, state.world.require(EntityId(entity_id)))


def luck_restored(result: Played) -> bool:
    return counter_rose(result, " luck +")


def _twists_left(state: Game) -> int:
    return mechanics_of(state.world, Loner3eState).twist.current


def tied_a_roll(result: Played) -> bool:
    """A Loner tie: Chance equal to Risk, the one result that moves the Twist Counter."""
    return any(
        fact.kind == "question_answered"
        and len(fact.dice) == 2
        and max(fact.dice[0].rolled) == max(fact.dice[1].rolled)
        for fact in result.facts
    )


def loner_luck(result: Played, entity_id: str) -> int:
    return loner_sheet(result.state, entity_id).luck.current


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
    )
    return draft.committed()


def _seal_met(state: Game) -> Game:
    """A non-living opponent the SRD's "Everything is a Character" covers, staged as an item."""
    draft = staged(state, "cloister", []).draft()
    _ = draft.add(
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
    with rules(draft.world, Loner3eState) as game:
        sheet_of(game.sheets, draft.player).luck.current = 2
    return draft.committed()


def _rat_on_its_last_luck(state: Game) -> Game:
    """Any yes ends the conflict: the rat's one luck cannot survive an exchange it loses."""
    draft = _mid_conflict(state).draft()
    with rules(draft.world, Loner3eState) as game:
        sheet_of(game.sheets, draft.world.require(EntityId("cloister-rat"))).luck.current = 1
    return draft.committed()


def _two_ties_in(state: Game) -> Game:
    draft = staged(state, "cloister", []).draft()
    with rules(draft.world, Loner3eState) as game:
        game.twist.current = TIES_PER_TWIST - 1
    return draft.committed()


def CASES(settings: Settings) -> tuple[Case, ...]:
    engine_id, canon, won = ENGINE_ID, CANON, CANON.won
    return cases_for(engine_id, canon, settings) + (
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
                    lambda r: (
                        EntityId("vault-seal") in mechanics_of(r.state.world, Loner3eState).sheets
                    ),
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
                Expectation("advantage-called", lambda r: card_says(r, "Oracle — Advantage")),
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
                        (sheet := loner_sheet(r.state, r.state.player_id)).luck.current
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
                    lambda r: card_says(r, "Oracle — Disadvantage"),
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
                        for skill in loner_sheet(r.state, r.state.player_id).skills
                    ),
                ),
            ),
            setup=lambda state: adventure_closed(state, canon, complete_chapter),
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
            setup=lambda state: adventure_done(state, canon),
        ),
    )
