# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

Reset 2026-08-12 with the reorientation (CONCEPT.md): the D&D 5e engine is being removed in
favor of a first-party tag-based Oracle engine. The prior log — kernel refactor, world/mechanics
boundary, character creation, the full dnd5e build-out — lives in git history up to the commit
tagged before Phase 1's deletion.

## Phase 1 — Delete the D&D 5e engine — DONE 2026-08-12

- **Step 1 — the engine tree.** Deleted `engines/dnd5e/` (2,348 lines Python + 41.5k pack JSON),
  `scripts/srd/` + `scripts/import_srd.py`, `tests/dnd5e/`, the 22 dnd5e eval scenarios, the
  `bram`/`elowen` eval characters, every dnd5e golden fixture family, and the dnd5e overlays
  (`characters/kael/dnd5e.json`, `scenarios/whispering-vault/dnd5e.json` — folded in from step 3
  because the launcher catalog scans overlays). `ENGINE_MODULES` lost one line; `probes.py`
  dropped its dnd5e branches and the five dnd5e-only probe types no surviving eval used
  (`set_number`, `set_level`, `set_note`, `has_ref`, `note_value`). The launcher's withdrawn-save
  test now relabels a story save instead of building a real dnd5e state. 107 files,
  −58,586 lines. Committed (the one commit before the stage-only instruction).
- **Step 2 — `state/packs.py` leaves with its only consumer.** `AdvancementOffer.granted/options`
  are plain strings (prompts and panels only ever rendered them); `ENCODING` now comes from
  `content/store.py`; `ContentSlug` moved inline into `state/creation.py`. The whole
  `pack_paths` plumbing went with it: `Engine.__init__()` takes nothing, `EngineConfig`,
  `Settings.engines`, and `Settings.engine()` are deleted, `build_engine` ignores config. The
  two pack tests in `test_loader.py` and the probe boundary's `aidm.state.packs` entry deleted.
- **Step 3 — docs.** CONCEPT.md and DECISION.md carry the reorientation record (the ADR
  convention left with the uninstalled plugin, docs/adr/ deleted). ROADMAP.md rewritten where it
  named packs, spell preparation, or old plan phases; IDEAS.md dropped the SRD-extension idea;
  README rewritten story-only (one shipped engine, no pack `facts`, Oracle named as next). The
  stale eval `results/` (pre-reorientation, dnd5e-heavy, only same-hour-comparable) deleted.
- **Step 4 — the gate.** `SAVE_VERSION` 53 → 54; golden regen moved exactly one byte family:
  `save_version` in the three story fixtures, no prompt or schema golden. `rg -i dnd5e` over
  src/tests/scripts/content is clean (CONCEPT.md, DECISION.md, and PLAN.md keep the name as
  history). 96 tests, ruff, format, basedpyright all green; story and probe suites untouched
  throughout — the engine boundary held without a single core change.
- **Review pass (adversarial subagent + follow-ups).** Verdict on the diff: correct. Its fixes:
  README's intro still said "Story and 5e are both included" (now story-only), dead `_element()`
  in `ui/create.py`, dead `EVAL_CHARACTERS` lookup in `evals/run.py`, stale `aidm.state.sheet`
  in the probe boundary list, five stale "5e/packs/both engines" comments, `__pycache__` husks.
  Follow-ups applied on maintainer decision: `build_engine(engine_id)` dropped its dead
  `config` param (6 call sites), and `AttackRollHappened` → `ContestedRollHappened` (it counts
  contested rolls, not attacks; three scenario JSONs renamed with it). Kept deliberately:
  `add_tag`/`has_tag`/`branch_adds_tag`/`rolled_with_mode` probes and dice
  advantage/disadvantage — the Oracle engine's vocabulary. AGENTS.md/CLAUDE.md and docs lost
  the uninstalled plugin's conventions (`.scratch` tracker, ADRs, `docs/agents/`).

## Phase 2 — Oracle engine — DONE 2026-08-13 (staged, not committed)

- **Step 1 — mechanics + resolution.** `engines/oracle/` (7 modules, 3 prompt/example files, 636
  lines Python) plus one `ENGINE_MODULES` line. `Figure` is the one sheet shape the player and
  every NPC share — `concept`, `edges`, `burdens`, `gear`, and three `Counter`s (`fortune` max 6,
  `twist` max 3, unbounded `milestones`); only `fortune` appears in `counters()`, so `twist` is
  resolver-side and the model cannot move it. `resolve_question` reveals the actor, refuses the
  plan's tags against `available_tags` (sheet tags plus every trait on the actor, what they carry,
  their location, and whoever stands there), cancels leverage against trouble to a sign, and rolls
  Chance d6 against Risk d6 with at most one extra die a side. `outcome_for` is pure: the 36 pairs
  land `strong-yes 3 / yes 7 / yes-but 11 / no-but 5 / no 7 / no-and 3`.
- **Step 2 — the pacing and growth halves.** A tie ticks `twist` silently — the tally is never a
  fact, so the Narrator is not handed a number it is told never to recite — and every third tie
  resets it, emits a non-narrating `twist_due` fact, and appends `TWIST_NOTE` to
  `world.pending_notes`, which is the channel that actually reaches the Director next turn.
  `spend_fortune` pays one point resolver-side and rerolls both dice, keeping the better pair:
  the point is committed before the dice are seen, so it can never leave the actor worse off.
  Advancement is milestone-driven off resolved threads (`earned > milestones.current`) — never a
  model inferring a milestone from context — and buys one edge, one gear tag, or one burden
  dropped, against `MAX_EDGES`/`MAX_GEAR` of 4.
- **Step 3 — content, creation, tests.** `characters/kael/oracle.json` and
  `scenarios/whispering-vault/oracle.json` (the rat gets a sheet); creation is four
  `CreationStep`s (concept, 2 edges, 1 burden, 2 gear) over authored option tables. `tests/oracle/`
  holds 9 tests mirroring `tests/story/` plus the enumerable ladder table;
  `test_golden_prompts`/`test_golden_turn` gained their oracle rows, and the launcher and package
  boundary tests gained the second engine.
- **Step 4 — the gate.** Golden regen added the seven `oracle` fixture families and **moved no
  story byte** — the proof the engine boundary held again. No `SAVE_VERSION` bump: a new engine
  writes new saves, it does not reshape existing ones, so `FIXTURE_SAVE_VERSION` stays 54.
  113 tests, ruff, format, basedpyright all green. The scripted golden turn resolves a contested
  question through the dice table, fires the `vault-charted` hook, advances the thread, and admits
  a worldkeeper creation — Phase 2's done-when, met.
- **Deviations from PLAN.md, deliberate.** (1) No `conditions` tuple on the sheet: core `Trait`s
  already are temporary tags, are already taught in the shared effect vocabulary, already render
  in the scene, and `available_tags` counts them — a second tag system would have meant a second
  effect op doing the same job. (2) Creation picks from authored option tables rather than free
  text with AI-suggested options: free text needs a new core step type, a new role, and UI work,
  which is a feature, not part of an engine package sized like `story`. (3) Only actors carry a
  `Figure`; a significant object's tags reach the pool as core traits on the item.
- **Review pass (adversarial subagent, with Loner 3e / Ironsworn / GUMSHOE research).** Two real
  defects, both reproduced before fixing. (1) `net` counted raw list entries while the tag check
  was membership-only, so naming one real tag twice turned a disadvantage into a neutral — the
  model *could* invent a bonus. Now each side is a set of canonical tag names and a tag named on
  both sides cancels; a regression test pins it. (2) The twist counter sat on each sheet, so ties
  split across the player and NPCs each ticked a separate tally while `TWIST_NOTE` claimed "the
  dice have tied three times"; Loner keeps one Twist Counter, and it now sits on `Mechanics`.
  Renames for accuracy: `TWIST_EVERY` → `TIES_PER_TWIST` (it counts ties, not turns), `Figure` →
  `Sheet` with `Mechanics.figures` → `sheets` (the class is the sheet, not the character). No
  `SAVE_VERSION` bump: Oracle has never shipped a save and story's shape is untouched — regen
  moved only `state/oracle.json` and `save/oracle.json`.
- **Fidelity, checked against the sources.** Chance d6 vs Risk d6 is Loner's core; "tags cancel,
  never more than two dice a side, keep highest" is Loner verbatim, not invented; tie → yes-but
  plus a twist tick firing at three is Loner's Twist Counter at its own 6/36 rate. Two knowing
  divergences: Loner keys but/and to dice *values* (3/9/9/3/9/3 over 36) where this keys to
  *margin* (3/7/11/5/7/3), which buys a monotone ladder — a bigger margin is always better, which
  is what an engine whose Director writes per-outcome branches needs; and fortune-as-reroll is not
  Loner's Luck (a harm buffer inside its conflict procedure) but an original resource.
- **Step 5 — Harm & Luck, Loner's own.** `fortune` and its reroll are gone; `luck` replaces them
  as Loner defines it — one 6-point pool every actor starts full, spendable for nothing, a buffer
  and not a currency, so `spend_fortune` and its refusal left with it. `Question` gained a
  per-roll `opponent_id`: null for an ordinary question, and set only for one exchange of a
  conflict, at which point the engine reads `HARM` off the outcome (3/2/1 to the opponent across
  `strong-yes`/`yes`/`yes-but`, 1/2/3 back onto the asker across `no-but`/`no`/`no-and`) and
  moves the loser's luck itself — the model never writes a blow. A conflict exchange does not
  tick the twist tally, which is Loner's own carve-out. At 0 luck a `conflict_lost` fact fires,
  `defeat_note` reaches the Director through `pending_notes`, and the next exchange against a
  spent side is refused outright, so a defeated actor cannot be rolled at forever. No conflict
  object holds anything between turns: `opponent_id` lives for one roll, luck lives on the sheet,
  and putting luck back to full after a conflict is a `counter-change` the Director writes.
- **Step 5's gate.** `SAVE_VERSION` 54 → 55, because Oracle's persisted mechanics bytes changed
  and a save on disk names `fortune`. Regen moved the oracle families and nothing else but the
  three story `save_version` lines — checked, not assumed. `tests/oracle/` is 11 tests: the
  fortune-spend test is deleted rather than left limping, and two conflict tests replace it — one
  sweeping 200 seeds to pin harm to the loser and the twist to zero, one driving an opponent to 0
  luck and then asserting the refusal comes back through `check_plan`. 115 tests, ruff, format,
  basedpyright green.
- **Fidelity after Step 5.** Now faithful: Luck's size, its start-full-for-everyone default,
  its buffer-not-currency nature, the full 6-row damage table, twist not ticking on Harm & Luck
  rolls, and 0 luck as a story turning point rather than a death. Still divergent, knowingly:
  the but/and ladder stays keyed to margin rather than to dice values (Step 1's reasoning holds);
  luck refresh is Director-driven rather than automatic, because "resets after conflicts" needs a
  notion of a conflict ending that only a turn-spanning conflict object could hold; and Loner's
  other two conflict methods (one question, or a run of questions with no attrition) are simply
  what the engine already did, so they need no code. No oracle or interpretation tables are
  implemented — that is the Director's job by design.
- **Step 6 — the ladder, read off the SRD itself.** Fetched `lonersrd.zotiquestgames.com`'s
  Loner 3e core page rather than trusting a summary. "Consulting the Oracle" resolves in two
  steps: the comparison alone picks the side (Chance higher → yes, Risk higher → no), and only
  then do the *values* pick the modifier — both dice 4 or over adds "and", both 3 or under adds
  "but", a mixed pair leaves the answer plain. Equal dice are their own row, not a modifier case:
  they read "Yes, but…" flat and tick the Twist Counter, and "Twist Counter" confirms the answer
  stands whether or not the third tie fires the twist. So `outcome_for(chance, risk)` replaces
  `outcome_for(margin)` and the 36 pairs now land `yes-and 3 / yes 9 / yes-but 9 / no-but 3 /
  no 9 / no-and 3` — Loner's own distribution, where the old margin ladder gave
  `3 / 7 / 11 / 5 / 7 / 3`. Two consequences fall out: yes overtakes no 21 to 15 because ties
  answer yes, and `no-but` is now the *low* failure while `no-and` is the high one, so a conflict
  exchange that fails on small dice costs 1 luck where before it took 2 or 3. `strong-yes` is
  renamed `yes-and` to match the SRD's six names. The fact carries `chance` and `risk` in place
  of `margin`, because the pair is what decides now and the trace should say so. `HARM` is
  untouched — checked against "How Luck Loss Works" and identical row for row, as are Luck 6,
  the buffer reading, 0 luck as a turning point, and the twist's carve-out for Harm & Luck.
- **Step 6's gate.** No `SAVE_VERSION` bump: the ladder changes which outcome a roll lands on,
  not the shape of a persisted byte. Regen moved `turn/oracle.json` (the scripted seed now rolls
  5 against 4 — the SRD's own worked example — and lands `yes-and` where it landed `yes-but`),
  `save/oracle.json` and the prompt fixtures for the renamed label, and **no story byte**.
  115 tests, ruff, format, basedpyright green. The margin divergence Step 5 recorded is closed;
  what stays divergent is unchanged — Director-driven luck refresh, no oracle or interpretation
  tables, and no live probe of the reshaped fact data.
- **Outstanding.** (1) Working rule 2's live probe passed: a turn played cleanly under Oracle on
  2026-08-13. It was run against the pre-Harm/Luck schema, and `spend_fortune` has since become
  `opponent_id`, so one confirming turn on the new shape is owed — the risk is low (the Director
  answers through `ToolOutput`, not the `NativeOutput` path where gpt-oss-120b wrote zero effects)
  but the rule asks for a probe per reshaped schema, not per engine. (2) `read`/`write`/`begin`/
  `commit`/`apply`/`_move_pool` are now story's bodies twice over with the sheet type swapped,
  so the repository's own "a port earns its place
  on the second implementation" rule has come due: a generic sheet-holder over the `counters()`
  contract would take ~45 duplicated lines out. It costs a `SAVE_VERSION` bump to unify story's
  `actors` with oracle's `sheets`, so it belongs in its own change, not folded in here.
  (3) No GUMSHOE clue discipline exists anywhere: a core reveal can still sit in a success-only
  branch and be lost to a failed roll. CONCEPT §12.5 puts that invariant in World/Scenario rather
  than an engine, so it is unscheduled rather than misplaced — and no Ironsworn progress track or
  momentum is built either, PLAN Phase 2 having promised neither.
