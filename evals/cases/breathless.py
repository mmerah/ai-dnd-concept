from aidm.config import Settings
from aidm.engines.breathless.rules import (
    CARRY_LIMIT,
    DIE_FLOOR,
    LOOT_START,
    Breathe,
    BreathlessState,
    Skill,
    apply_catch_breath,
    item_sheet_of,
)
from aidm.engines.breathless.rules import ItemSheet as BreathlessItemSheet
from aidm.engines.breathless.rules import Sheet as BreathlessSheet
from aidm.engines.core import mechanics_of, rules, sheet_of
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId
from aidm.state.model import Game
from aidm.world.topology import children
from evals.cases.shared import (
    Canon,
    below,
    cases_for,
    counter_rose,
    has_fact,
    inside,
    lost_a_roll,
    player_outcomes,
    staged,
    staked_before_rolling,
)
from evals.turn_eval import Case, Expectation, Played

ENGINE_ID = EngineId("breathless")

CANON = Canon(
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
)


def breathless_sheet(result: Played) -> BreathlessSheet:
    game = mechanics_of(result.state.world, BreathlessState)
    return sheet_of(game.sheets, result.state.player)


def skill_rolled(result: Played, skill: Skill) -> bool:
    """The wear line names the skill and the face it rolled: `Kael[player] Sneak d10 -> d8`."""
    return any(fact.kind == "skill_worn" and f" {skill} d" in fact.trace for fact in result.facts)


def worn_by(result: Played, actor_id: str) -> bool:
    return any(
        fact.kind == "skill_worn" and fact.entity_id == EntityId(actor_id) for fact in result.facts
    )


def item_rolled(result: Played, item_id: str) -> bool:
    return any(
        fact.kind == "item_worn" and fact.entity_id == EntityId(item_id) for fact in result.facts
    )


def worn_down(result: Played, skill: Skill) -> bool:
    sheet = breathless_sheet(result)
    return sheet.worn[skill] < sheet.skills[skill]


def luck_die(result: Played) -> int:
    """The die the Director rated by the odds; a luck test rolls exactly one."""
    return next(
        (die.faces[0] for fact in result.facts if fact.kind == "luck_tested" for die in fact.dice),
        0,
    )


def stunt_rolled(result: Played) -> bool:
    """Nothing Kael carries or rates is a d12, so a lone d12 in a check can only be the stunt."""
    return any(
        fact.kind == "check_resolved" and any(die.faces == (12,) for die in fact.dice)
        for fact in result.facts
    )


def rolled_with_help(result: Played) -> bool:
    """A helper adds their die to the same pool, so the check shows two faces instead of one."""
    return any(
        fact.kind == "check_resolved" and any(len(die.faces) == 2 for die in fact.dice)
        for fact in result.facts
    )


def rolled_for(result: Played, actor_id: str) -> bool:
    return any(
        fact.kind == "check_resolved" and fact.entity_id == EntityId(actor_id)
        for fact in result.facts
    )


def failed_a_check(result: Played) -> bool:
    return "fail" in player_outcomes(result)


def flagged_vulnerable(result: Played) -> bool:
    """The engine writes the warning only when a vulnerable actor fails a `dangerous` check."""
    return any("taken out, or dead" in fact.trace for fact in result.facts)


def carried_items(result: Played) -> int:
    return len(children(result.state.world, result.state.player_id, "item"))


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


def complicated(result: Played) -> bool:
    """Something landed on the group: any mechanic that moves the fiction against the player."""
    return bool(COMPLICATIONS & {fact.kind for fact in result.facts}) or (
        result.state.pending is not None
    )


def _stunt_spent(state: Game) -> Game:
    """One d12 flourish is all there is until the player catches their breath."""
    draft = state.draft()
    with rules(draft.world, BreathlessState) as game:
        sheet_of(game.sheets, draft.player).stunted = True
    return draft.committed()


def _stressed(state: Game, stress: int) -> Game:
    draft = state.draft()
    with rules(draft.world, BreathlessState) as game:
        sheet_of(game.sheets, draft.player).stress.current = stress
    return draft.committed()


def _med_kit_at_hand(state: Game) -> Game:
    """Stress to spend it on and the kit to spend: using it is the player's own move."""
    draft = _stressed(state, 3).draft()
    with rules(draft.world, BreathlessState) as game:
        sheet_of(game.sheets, draft.player).med_kit = True
    return draft.committed()


def _spent_loot_die(state: Game) -> Game:
    """A loot die at d4 keeps rolling: the SRD allows it at the player's own risk."""
    draft = state.draft()
    with rules(draft.world, BreathlessState) as game:
        sheet_of(game.sheets, draft.player).loot = DIE_FLOOR
    return draft.committed()


def _wren_at_hand(state: Game) -> Game:
    draft = staged(state, "roof-walk", [("ambulance-bay", "roof-walk")]).draft()
    draft.world.require(EntityId("wren-halloway")).known = True
    draft.world.party.append(EntityId("wren-halloway"))
    return draft.committed()


def _full_backpack(state: Game) -> Game:
    """Two more on top of the lantern fills the backpack; the next find lies where it drops."""
    draft = state.draft()
    with rules(draft.world, BreathlessState) as game:
        for item_id, name in (("pry-bar", "a pry bar"), ("water-can", "a water can")):
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
            game.items[EntityId(item_id)] = BreathlessItemSheet(die=6)
    return draft.committed()


def _spent_lantern(state: Game) -> Game:
    """An item at d4 has broken, been lost, or faded: it rolls no more."""
    draft = state.draft()
    with rules(draft.world, BreathlessState) as game:
        lantern = draft.world.require(EntityId("lantern"))
        item_sheet_of(game, lantern).die = DIE_FLOOR
    return draft.committed()


def _breath_caught(state: Game) -> Game:
    """The player's own move landed between turns, and its note owes the group a complication."""
    draft = state.draft()
    _ = apply_catch_breath(draft, Breathe(actor_id=draft.player_id))
    return draft.committed()


def _armed_gatekeeper(state: Game) -> Game:
    """Dov rolls for himself, so he is rated and armed as an authored actor would be."""
    draft = state.draft()
    dov = draft.world.require(EntityId("dov-marek"))
    with rules(draft.world, BreathlessState) as game:
        game.sheets[dov.id] = BreathlessSheet(skills={"Bash": 8})
    draft.world.require(EntityId("fire-axe")).parent_id = dov.id
    return draft.committed()


def CASES(settings: Settings) -> tuple[Case, ...]:
    engine_id, canon, won = ENGINE_ID, CANON, CANON.won
    return cases_for(engine_id, canon, settings) + (
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
            setup=below(canon),
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
                    lambda r: breathless_sheet(r).loot < LOOT_START,
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
                    lambda r: breathless_sheet(r).loot == DIE_FLOOR,
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
                Expectation("backpack-held", lambda r: carried_items(r) <= CARRY_LIMIT),
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
            expectations=(Expectation("no-spent-roll", lambda r: not item_rolled(r, "lantern")),),
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
