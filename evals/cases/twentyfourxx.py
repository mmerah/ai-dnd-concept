from aidm.config import Settings
from aidm.engines.core import mechanics_of, rules, sheet_of
from aidm.engines.twentyfourxx.engine import complete_chapter
from aidm.engines.twentyfourxx.rules import ItemSheet, TwentyfourxxState
from aidm.state.entities import PLAYER_ID, Counter, EngineId, Entity, EntityId, Exit, Trait
from aidm.state.model import Game
from evals.cases.shared import (
    Canon,
    adventure_closed,
    adventure_done,
    below,
    card_says,
    cases_for,
    counter_rose,
    dead,
    has_fact,
    inside,
    known,
    lost_a_roll,
    named,
    staged,
    unless_lost,
)
from evals.turn_eval import Case, Expectation, Played, begin

ENGINE_ID = EngineId("twentyfourxx")

CANON = Canon(
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
)


def credits_spent(result: Played) -> bool:
    # A charge, not a payment: the counter trace carries the key and a negative delta.
    return any(
        fact.kind == "counter_changed" and " credits -" in fact.trace for fact in result.facts
    )


def breaks_left(result: Played, entity_id: str) -> int:
    """Sturdy gear counts its breaks on a sheet; gear with none is sheetless and breaks once."""
    items = mechanics_of(result.state.world, TwentyfourxxState).items
    return items.get(EntityId(entity_id), ItemSheet()).breaks.current


def bad_luck_rolled(result: Played) -> bool:
    # The engine prefixes every bad-luck die's reason, so a clear roll still leaves this trace.
    return any(
        fact.kind == "dice_rolled" and fact.trace.startswith("bad luck") for fact in result.facts
    )


def skill_face(result: Played, skill: str) -> int:
    game = mechanics_of(result.state.world, TwentyfourxxState)
    return sheet_of(game.sheets, result.state.player).face(skill)


def _broken_arm(state: Game) -> Game:
    draft = staged(state, "siren-mast", [("siren-mast", "relay-nine")]).draft()
    draft.player.traits.append(
        Trait(id="broken-arm", name="Broken Arm", text="(injury) Splinted; it bears no weight.")
    )
    return draft.committed()


def _bulky_gear(draft: Game, item_id: str, name: str, breaks: int = 1) -> None:
    """Written straight into the world: the sheet the gear plays by is the engine's own blob."""
    with rules(draft.world, TwentyfourxxState) as game:
        _ = draft.add(
            Entity(
                id=EntityId(item_id),
                kind="item",
                name=name,
                brief=name,
                known=True,
                parent_id=PLAYER_ID,
            )
        )
        game.items[EntityId(item_id)] = ItemSheet(
            bulky=True, breaks=Counter(current=breaks, maximum=breaks)
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
    _ = draft.add(
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
    with rules(draft.world, TwentyfourxxState) as game:
        sheet_of(game.sheets, draft.player).credits.current = 12
    return draft.committed()


def _mara_at_hand(state: Game) -> Game:
    draft = staged(state, "relay-nine", []).draft()
    draft.world.require(EntityId("mara-voss")).known = True
    draft.world.party.append(EntityId("mara-voss"))
    return draft.committed()


def defence_settled(result: Played) -> bool:
    if not lost_a_roll(result, CANON.won):
        return True
    return any(fact.kind in ("defence_taken", "defence_turned") for fact in result.facts)


def CASES(settings: Settings) -> tuple[Case, ...]:
    engine_id, canon, won = ENGINE_ID, CANON, CANON.won
    there = canon.climb_to
    _, start = begin(engine_id, settings)
    return cases_for(engine_id, canon, settings) + (
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
                Expectation("hindered-called", lambda r: card_says(r, "Hindered")),
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
                        for fact in r.facts
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
                Expectation("playing-mara", lambda r: r.state.player_id == EntityId("mara-voss")),
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
                Expectation("helper-die", lambda r: card_says(r, "Help d10")),
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
            setup=below(canon),
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
                Expectation("hindered-called", lambda r: card_says(r, "Hindered")),
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
            setup=lambda state: adventure_closed(state, canon, complete_chapter),
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
            setup=lambda state: adventure_done(state, canon),
        ),
    )
