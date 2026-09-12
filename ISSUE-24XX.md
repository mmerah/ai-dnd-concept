# 24XX: fidelity and play quality

Status: findings for a specification session, not an approved implementation spec.
Reviewed 2026-09-12 against master `09aee87a` and the v1.4 SRD this engine targets.
Code, prompts, and existing tests inspected; no live playtest performed. Player-experience
risks below are hypotheses, not observed session failures.

## Goal and baseline

Keep the working engine. Make risk, commitment, defense, and consequences form a dependable
player decision. The dice ladder, highest-die resolution, actor hindrance, and job advancement
closely follow the source. Gear, repairs, credits, ship functions, and succession already
have implementations and tests. Preserve code-owned dice/state and revealed-fact narration.

24XX's likely strengths here are fast encounters and concrete choices about help, equipment,
and recovery. The main concern is fairness: players should understand danger and have a real
chance to use their resources before consequences become irreversible.

## Decisions for the spec, in priority order

### 1. Connect defense to the consequence it prevents

**Observed:** `TwentyfourxxEngine.roll` immediately kills on a lethal disaster or adds
`Maimed` on a lethal setback. `TwentyfourxxWorld.defend` separately breaks an item and adds
a hindrance (or breaks harmlessly), but does not replace an already-applied death or maiming.
There is no explicit pending-hit decision linking these operations.

**Risk:** The player can lose the opportunity to sacrifice gear to survive. Calling defense
afterward cannot undo the consequence; calling it beforehand has no explicit connection to
the subsequent roll. The individual tools work, but their composition is underspecified.

**Decide:** Define defense timing, eligible hits/items, who chooses, and when consequences
become final. Specify how harmless armor, multi-use armor, maiming, and succession interact.
Consider a pending consequence only if needed; do not prescribe new state before defining
the behavior.

**Acceptance examples:** An eligible lethal hit permits a player-chosen gear sacrifice before
death is final. Declining or lacking usable gear applies the consequence exactly once.
Defending does not leave the prevented death/maiming in state or narration. Broken gear cannot
defend again; multi-use armor respects its limit. If a decision persists, save/reload preserves
it without duplicate effects or premature succession.

### 2. Establish risk before commitment

**Observed:** The SRD gives players an opportunity to revise plans after the GM presents
risks. Our shared GM prompt mentions stopping for an accepted risk, but `Roll.risking_death`
can impose lethal stakes without recording that the player knew and accepted them.
The same prompt accepts player-declared outcomes, potentially bypassing adjudication.

**Decide:** Distinguish intent, established facts, risk disclosure, and commitment. Recommend
disclosing material new danger before resolving an attempt, while avoiding repetitive
confirmation when the player already understands and accepts the stakes. Resolve the shared
declared-success policy together with `ISSUE-LONER.md`; check its original rationale and
impact on other engines before editing it.

**Acceptance examples:** “I cross the exposed gantry” does not acquire undisclosed lethal
stakes after commitment. The player can seek cover or another route. An already-accepted
risk proceeds without another approval loop. “I kill the guard” and “I try to shoot the guard”
receive consistent adjudication against the same opposition. Certain actions stay roll-free.

### 3. Make assistance share risk

**Observed:** `_pool` adds a hired helper's skill die. Automatic lethal consequences in
`roll` affect only the actor; the helper's applicable hindrances are not separately assessed.
The GM could apply helper consequences manually, but engine guidance does not explain this.
The SRD explicitly says allies share risk.

**Decide:** Define the helper's exposure from their fictional role, how their hindrances
affect their contribution, and how consequences/defense apply to each participant. Sharing
risk need not mean identical injuries in every situation. Keep circumstantial help distinct
from an ally putting themselves in danger. Combining both kinds of help is explicitly left
to table judgment by the SRD; document our choice rather than treating it as a bug.

**Acceptance examples:** A helper exposed to the same gunfire is not mechanically exempt
from the agreed danger. A remote helper can face a different stated consequence. A relevant
helper injury affects their die. Each affected participant resolves eligible defense once.

## Smaller adaptation decisions to document

- The SRD permits invented skills. Creation and advancement currently use the offered skill
  vocabulary (including specialty skills). Decide whether that restriction is intentional.
- After death, the SRD favors promptly introducing a replacement character. We instead offer
  hired-member succession and end the game when no successor lives. Keep or change this as
  a deliberate campaign policy.
- `docs/24XX.md` currently claims unlisted rules are implemented as printed. Update it to
  distinguish exact mechanics, chosen interpretations, and the procedural gaps above.

## Validation and next-session deliverable

Write a spec with the three decisions, concrete turn examples, affected files, and acceptance
checks. Start with `src/aidm/engines/twentyfourxx/{engine,world,tools}.py`, its `rules.md`,
and `src/aidm/turn/prompts/master.md`. Reuse existing decision infrastructure if appropriate;
avoid adding a generic combat framework.

Add targeted deterministic checks around the chosen boundaries in `tests/twentyfourxx/`.
Current `test_tools.py` and `test_play.py` cover individual rolls, damage, defense, advancement,
and succession, but do not establish the complete risk-to-defense interaction or live fun.

Play one short dangerous encounter with a helper, a chance to revise the approach, and a
gear-defense choice. Record disclosed stakes, player commitment, dice, final state, and next
choices. Check that help has a cost, defense changes the outcome, and the next decision is
meaningful. Do not substitute prose snapshots or more dice-ladder tests for this pacing check.

## Sources

- [Official 24XX v1.4 SRD](https://24xx-srd.carrd.co/): play, rolling, defense,
  advancement, character options, and deliberate room for rulings.
- [Author's download page](https://jasontocci.itch.io/24xx): published SRD downloads
  include v1.41; this review does not claim a v1.41 compatibility audit.
- Repository source map and current adaptation claims: `docs/24XX.md`.
