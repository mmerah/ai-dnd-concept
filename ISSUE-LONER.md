# Loner 3e: fidelity and play quality

Status: findings for a specification session, not an approved implementation spec.
Reviewed 2026-09-12 against master `306106f3`. Code, prompts, and tests inspected;
no live playtest performed. Fun-related concerns below are hypotheses to validate.

## Goal

Keep the working 3e engine. Make player intent, conflict pacing, and defeat consequences
reliable enough that each outcome changes the next meaningful choice. Resolve the decisions
below before adding mechanics or changing shared prompts.

## Baseline to preserve

- Oracle outcome mapping, capped advantage/disadvantage, Luck damage, and the three-tie twist
  trigger match the reviewed 3e SRD. Harm & Luck exchanges correctly do not advance twists.
- Code owns dice and state changes; the narrator receives revealed facts. Conflict exchanges
  return control to the player. Existing tests cover these boundaries and core outcomes.
- Scene purpose and stopping-point guidance already exist in `src/aidm/engines/scenes/rules.md`.
  Do not specify scene closure as a missing feature.
- Hidden twist tally, party support, and same-turn twist handling are documented adaptations
  in `docs/LONER-3E.md`. Keep adaptations explicit rather than assuming exact equivalence.

## Decisions for the spec, in priority order

### 1. Who can declare success?

**Observed:** `src/aidm/turn/prompts/master.md` tells the GM to accept any outcome the player
declares. This can bypass uncertainty: “I kill the guard” may settle what “I try to stab the
guard” leaves to the oracle. The instruction is shared by all engines.

**Decide:** Is play adjudicated challenge, collaborative authorship, or an explicit choice
between them? Recommended default for Loner: player prose establishes intent; uncertain
success is resolved by the engine. Preserve established facts and genuinely certain actions.
Check the original reason for the shared instruction before changing it.

**Acceptance examples:** Against the same alert guard, both phrasings require adjudication.
An uncontested action stays roll-free. A multi-part action preserves completed facts while
resolving only uncertain parts. Scope any shared-prompt change across the other engines.

### 2. When should opposition use Luck?

**Observed:** `src/aidm/engines/loner3e/rules.md` directs active opposition into `opponent_id`;
`Loner3eEngine.roll` then applies Luck damage and normally pauses after one exchange.
Official 3e also offers single-question and key-action conflict resolution.

**Risk:** Minor opposition, negotiations, and chases can become repeated attrition. Different
prose alone does not make “attack again” a new decision.

**Decide:** Define when each resolution method applies, who selects it, and how withdrawal
or a decisive fictional solution ends a conflict. Do not automatically add a mode selector
or new state: specify the smallest behavior needed first.

**Acceptance examples:** A minor obstacle can resolve in one question; a sustained duel can
use Luck; an environmental solution can change or end the contest. Each continuing exchange
leaves a meaningful choice. Clarify temporary positioning changes versus the current
instruction to defer lasting marks until defeat.

### 3. Make defeat survive the Luck reset

**Observed:** `Loner3eWorld.strike` immediately refills both pools at defeat.
`Loner3eEngine.roll` adds `DEFEAT_NOTE`, asking the GM to settle consequences.
`check_conflict` rejects zero-Luck actors, but the automatic refill removes that condition.

**Risk:** The mechanical guard alone cannot prevent reopening the defeated contest. The
ending depends on the GM following its note and recording consequences. This is an exposed
boundary, not a claim that a live session has reproduced the failure.

**Decide:** What records a settled defeat, when recovery occurs, and what makes a genuinely
new conflict permissible? Distinguish defeat from automatic death; preserve fictional
outcomes such as capture, concession, or retreat.

**Acceptance examples:** A missed consequence cannot silently resume the same duel after
refill. A captured opponent cannot attack merely because Luck is full. A later escape can
create a new contest. Specify save/restore behavior if state changes are needed.

## Validate play quality before expanding scope

Run one short live encounter with a creative approach, a failed attempt, a continuing
exchange, and a defeat or withdrawal. Record the input, oracle result, state changes, and
next available choices. Ask whether a different action would change the stakes or odds,
whether consequences persisted, and whether the next decision was clear.

Use deterministic tests for selected state boundaries and regressions. Existing
`tests/loner3e/test_engine.py` and scripted UI checks in `qa/s_loner.py` establish behavior;
they do not demonstrate that unscripted AI play is enjoyable. Do not substitute prose
snapshots or more dice tests for the live pacing check.

## Scope and deliverable for the next session

Produce a spec with the three decisions above, concrete before/after examples, affected
files, acceptance checks, and any newly documented SRD deviations. Keep the oracle math,
existing player handoffs, and hidden-information boundary intact unless evidence requires
a change. Update `docs/LONER-3E.md` when implementation policy diverges from the SRD.

4e is a separate follow-up. As of this review, the author announces September 25 and says
the core oracle and Twist Counter remain unchanged despite “reworked” launch wording.
Omnibus bundles Core Rules, Companion, World Builder's Guide, and Character Builder's Guide;
it is not a separate engine. Compare final 4e text before adopting optional modules. This
report does not authorize a migration or speculative compatibility abstractions.

## Sources

- [Official 3e SRD](https://lonersrd.zotiquestgames.com/core/loner-3e.html): oracle,
  advantage/disadvantage, conflicts, Harm & Luck, and scene guidance.
- [4e announcement and author's clarifications](https://www.reddit.com/r/LonerRPG/comments/1wca9mn/loner_4e_arrives_september_25/).
- [Omnibus contents](https://zotiquest.substack.com/p/loner-omnibus-and-adventure-anthology).
