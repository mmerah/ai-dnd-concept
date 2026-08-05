# Refactor progress

Plan: `REFACTOR-LENIENT.md`. One commit per phase; gates green before each commit.

## Phase 0 — eval harness — done, staged, not committed

- [x] `scripts/evals/probes.py` — era adapter: 12 probe models, resolved against today's typed state
- [x] `scripts/evals/run.py` — case model, runner, three-way scoring, results writer, CLI
- [x] `scripts/evals/characters/{bram,elowen}/` — eval-only fighter and wizard fixtures
- [x] `scripts/evals/scenarios/*.json` — 21 cases, 15 tagged `combat`
- [x] Every setup verified offline; every numeric bound verified by Monte Carlo against the real
      resolution code (`procedures.swing`, `spells.cast`, `features.use`)
- [x] Baseline measured twice against identical code, both records committed to `results/`
- [x] `scripts/evals/BASELINE.md` — rates, measured drift, pre-registered phase-3 thresholds
- [x] Gates green: 182 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean

Baseline at `e174637`, `openai/gpt-oss-120b`, `retries=3`, 63 turns per suite, mean of two runs:
**interpretation 74.2%, completion 95.2%, combat 67.8%, overall 70.6%.**

### Decisions taken

- **Three numbers, not one.** The first runs showed most failures were
  `UnexpectedModelBehavior: Tool 'X' exceeded max retries`, not bad arithmetic. A single blended rate
  would gate the refactor on this model's function-calling reliability, so every run is now recorded as
  completed / passed / failed and the suite reports **completion**, **interpretation** (pass rate among
  completed turns — the rules-reading signal) and **overall**.
- **Bands sized from measured drift, not guessed.** Two runs of identical code drifted 1.6–6.3 points on
  the three gate metrics, and up to 33 points on tags with ≤6 runs. Hence 12/10/12-point bands, and a
  tag-level rather than scenario-level collapse condition — at 3 runs a scenario swings 100%→33% on one
  turn, so a per-scenario floor would fire on noise.
- **Reuse `director_step`/`TurnWorkspace` from `aidm.workflow.pipeline`** instead of re-rendering the
  director prompt in the runner, so the eval exercises the code path the app uses.
- **Eval-only characters under `scripts/evals/characters/`.** Shipped `kael` carries only a lantern, so
  `procedures._held_weapon` refuses him every swing, and he casts nothing — no shipped character can
  exercise the arithmetic chains the eval exists to measure. `bram` (fighter, longsword + shortbow) and
  `elowen` (wizard) fill that gap; `kael` still covers the three non-mechanical cases, keeping shipped
  content in the suite. The scenario is always the shipped `whispering-vault`.
- **Probe vocabulary is written in post-refactor terms** (`pool` = `hp` / `slot-N` / feature index,
  `tag` = a condition name or `advancement-ready`, `set_number` keys like `armor-class`). Today those
  resolve into `StatBlock`/`Progression`; after phase 3 they are literally `Sheet` keys, so phase 3
  edits probe internals and touches no scenario file.
- **Typed 5e cannot express a starting level above 1** (`Dnd5eCharacterData` has no level field), so the
  `set_level` probe plays the level-ups out through `engine.advance`, answering each pending choice with
  its first legal option.
- **`pyproject.toml` gained `scripts/evals` in basedpyright's `extraPaths`**, matching how `scripts` and
  each `tests/` directory are already listed.

### Findings to carry into phase 1

1. **Multi-action turns are the largest single source of failures** — the director casts twice, swings
   twice, or adds a `damage` call after an `attack`, even when the prompt says "and do nothing else this
   turn". `single-action-discipline` scores 100%, so it *can* hold to one action. An explicit
   one-action-per-turn line in the phase-1 director procedure is the cheapest available win, and this
   suite will show whether it landed.
2. **Tool-argument compliance costs ~5% of turns** at `retries=3`. The lenient toolset in
   `core/mechanics.py` should prefer flat, obvious argument shapes over the fussier ones that fail today
   (`damage`'s `Magnitude`, `rest`'s enum). Watch `completion`, not just `overall`.
3. **The player's `armor-class` is hard-coded to 10** in `engines/dnd5e/engine.py`'s `initial_world` —
   never derived from dexterity or worn armour. When 5e moves onto the Sheet, `armor-class` has to be a
   number the content and the level rows actually set, or every player character stays at AC 10.
4. **Two required coverage items are unmeasurable today** and must gain scenarios in the phase that
   creates them: advantage via keep-highest (phase 1's `roll(mode=...)`) and concentration replacing a
   previous spell (a phase-3 `Sheet` note).

## Phase 1 — substrate — done, staged, not committed

- [x] `git mv src/aidm/engines/dnd5e/dice.py src/aidm/core/dice.py`, importers moved to absolute
      `aidm.core.dice` (11 src files, 3 test files); the file itself is byte-identical
- [x] `core/sheet.py` (146) — `Counter`, `CounterTemplate`, `SheetTag`, `SheetTemplate`, `Sheet`,
      `SheetDefinition.runtime`, `render_sheet`
- [x] `core/mechanics.py` (370) — `Mechanics` toolset: `roll`, `adjust`, `spend`, `recharge`,
      `add_tag`, `remove_tag`, `set_note`, `set_number`, `read_content`
- [x] `core/enginepack.py` (107) — `EngineSpec`, `load_engine`
- [x] `core/packs.py` — `LenientRecord` + `lenient_format`
- [x] CLAUDE.md's first Design rule amended as the plan quotes
- [x] Tests: `tests/core/test_sheet.py`, `test_mechanics.py`, `test_enginepack.py`, and the
      ride-along `test_shipped_content.py` (both engines compose shipped kael + whispering-vault)
- [x] Adversarial review pass applied (below)
- [x] Gates green: 200 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean
- [x] **src 9,149 lines** (budget ≤ 9,150; baseline 8,497)

Both engines still build and run unchanged; nothing was deleted.

### Decisions taken

- **`load_engine` takes the engine id as an argument** rather than reading it from `spec.json`.
  `identity.py` stays the single source of the id the plugin registers, so a spec and a plugin
  cannot disagree.
- **`mechanics.py` takes the recharge map, not the `EngineSpec`.** `enginepack` imports `mechanics`;
  passing the spec back would close the cycle, so the leaf shape (`Mapping[str, Sequence[str]]`)
  crosses instead.
- **`add_tag` takes flat arguments** (`tag_id`, `name`, `text`) rather than the plan's nested
  `SheetTag`, per the phase-0 finding that nested tool arguments cost ~5% of turns.
- **`read_content` takes the ref as one `pack/collection/index` string** — exactly the spelling
  `render_sheet` shows — so the model copies rather than decomposes. Authored overlays still use the
  structured `ContentRef` object; only the tool boundary is flat.
- **`roll` evaluates the whole expression twice for `keep-highest`/`keep-lowest`** and reports the
  dropped total in the trace, so advantage never needs a second call.
- **Notes and numbers carry `narrator=None` always**, not only while the entity is unknown: they are
  bookkeeping, and the fiction behind them is already the Director's `intent` to write.
- **`Sheet.refs` numbers land through the template** — a key the template declares a counter becomes
  that counter full (`hp: 7` → 7/7); any other key becomes a number.

### Review pass

- **Fixed a hole in `validate_state`**: the missing-key check unioned the template's numbers and
  counters before subtracting the sheet's, so a sheet holding `hp` as a *number* satisfied a
  template that declares `hp` a *counter* — the exact crossover the misname guard exists to refuse.
  Each side is now checked against its own.
- **Fixed `runtime` precedence**: a key the author declares as a counter and a backing record ships
  as a number raised "both a number and a counter" instead of letting the author win. Record numbers
  now skip any key the definition itself states.
- **Two invariants moved to load time**: `CounterTemplate` validates that it instantiates, so a bad
  `spec.json` fails when the engine loads rather than on the turn that first grows an entity; and a
  counter with a `recharge` label but no `maximum` is refused, since `recharge` can never refill it.
- Cut: `read_content` now uses `Content.get`, single-use constants and `EMPTY_TEMPLATE` inlined,
  a misleading docstring and four tests deleted or merged (director-instructions wiring, a
  tautological `player.known`, two validator tests, one single-use fixture).

### Carried into phase 2

1. `load_engine` is not wired to an engine yet — phase 2's Story shim is its first consumer, and the
   `advance`/`advancement_available`/`advancement_panel` pass-throughs die with it in 2.2.
2. No `director.md` exists yet; the one-action-per-turn line from phase-0 finding 1 goes into the
   first one written.
3. `EngineSpec.collections` carries no entity kind, so `CollectionSpec.entity` (the 5e kind guard on
   authored refs) has no lenient equivalent — accepted, as the plan's "legality thins out".

## Phase 2 — Story on the Sheet, advancement as a proposal flow — done, staged, not committed

- [x] Story is data + a 55-line shim: `spec.json` (approach numbers, stress/growth counters),
      `director.md` (the risk procedure), `advancement.md` (advisor guidance), `engine.py`
- [x] **Deleted**: `story/{state,tools,rules,advancement,presentation,ui}.py` (1,089 lines)
- [x] Re-authored `characters/kael/story.json` and `scenarios/whispering-vault/story.json` as
      `SheetDefinition` payloads (same authored facts: approaches, stress cap, edges/burdens, gear)
- [x] `core/sheet.py` — `SheetDelta` (7 typed changes, each with a `why`), `apply_delta`,
      `player_sheet`
- [x] `core/engine.py` — `AdvancementOffer`, `ProposalSpec`, `offer_violation`; **deleted**
      `advance`, `advancement_available`, `advancement_panel`, `Transition`, `entered_text` and the
      panel aliases. `AdvancementDecision` deleted from `core/base.py`
- [x] `workflow/proposals.py` (69) — the `advisor` role, its instructions, the one legality rule
      (`violation`) shared by the retry and the commit, and the prompt renderer
- [x] `workflow/session.py` — `advance` → `offer` / `propose` / `preview` / `apply_proposal`
- [x] `ui/panels/advancement.py` (86) — the one generic panel: intent → Propose → the drafted
      changes with their reasons → Confirm
- [x] 5e keeps building: its shim passes a `ProposalSpec` that offers nothing and refuses
      everything; `dnd5e/ui.py` deleted
- [x] `SAVE_VERSION` 24 → 25
- [x] Evals: probes read `Sheet` payloads as well as typed 5e, `dice_rolled` with a `vs` counts as a
      contested roll, and three `story` scenarios were added
- [x] Gates green: 197 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean
- [x] **src 8,200 lines** (budget ≤ 8,400; phase 1 left 9,149)

Played end to end in `uv run aidm`: three risk turns earned 3 growth, and the advancement panel
raised `bold` 2 → +3 and spent the marks (`saves/` trace confirms one `Advance` entry).

Story evals measured twice at `654154e`, recorded in `BASELINE.md` and `results/`: **overall 66.7%,
completion 100%**, identical scenario by scenario across both runs. `story-risk-single-roll` 100%
(the risk procedure carries), `story-no-risk-needed` 66.7%, **`story-taken-out-cannot-risk` 33.3%**
— the Director rolls for a taken-out actor in 4 of 6 runs. Of the four checks Story stopped
enforcing in code, that is the one that actually regressed.

**The cause was the wording.** Hoisting the ban into `A RISK` as a precondition, stated once, took
`story-taken-out-cannot-risk` from 33.3% to **100% in 6 of 6 runs on the same model**, and the suite
from 66.7% to 88.9% (`87a6b17`, two runs, identical). A precondition has to be read before the
procedure it guards.

Four director models were then compared on the same suite and wording — `gpt-oss-120b`,
`claude-sonnet-5`, `deepseek-v4-flash`, `granite-4.1-8b`. Rates and the reading are in
`BASELINE.md`; the short version is that failures split by direction (the strongest model
over-acts, the small fast ones under-act), `gpt-oss-120b` fails in neither and stays the director
model, and the phase-3 gate therefore needs no second baseline. It also showed the story suite
cannot yet rank models: two of its three scenarios pass when the Director does nothing. Beyond both sits the
roadmap's engine referee (`docs/ROADMAP.md`), which is the structural answer to a precondition an
instruction cannot make stick: a post-Director check would catch "rolled for a taken-out actor"
whatever the model did.

### Decisions taken

- **The offer carries its content, not a ref.** `AdvancementOffer` holds `prompt`, `text`,
  `options`, `choose` — already resolved — so neither the panel nor the advisor reaches into a
  pack. `load_engine` hands `Content` to the engine's `offered`, which is the one place that reads
  it. `ProposalSpec.check` therefore takes `(state, offer, delta)` and no `LenientRecord`.
- **The mechanical half of legality is core's, not each engine's.** `offer_violation` checks the
  picks against `options`/`choose` *and* trial-applies the delta to a copy, so the advisor retries
  on anything `apply_delta` would refuse and no engine repeats those checks. `check` is left with
  the engine's own caps — Story's is 12 lines.
- **The advisor retries through pydantic-ai, not a hand-rolled loop**: an output validator raises
  `ModelRetry` with the violation, so the role's configured `retries` govern it like every other.
- **`SetNumber` writes a key the sheet does not have; counters must be granted.** Advancement is
  where a sheet grows, and the player reads every change before confirming — but a counter needs
  bounds, so `GrantCounter` is explicit and `ChangeCounter` refuses an unknown key.
- **`Record.rules` became `SerializeAsAny`.** With one payload type shared by every engine, dumping
  a foreign payload silently serialised it down to a blank `Sheet` and the commit accepted it. The
  integrity suite caught it; the annotation makes the foreign fields survive the dump so
  forbid-extra refuses them. This restores a guarantee the typed unions gave for free.
- **5e level-up is offline for this phase**, as the plan accepts: `offered` returns None so the
  panel simply says nothing is on offer, and `check` raises. `AdvancementDecision` and `Transition`
  moved into `dnd5e/advancement.py`, which phase 3 deletes whole.
- **Story keeps no recharge labels.** Stress comes back through the fiction (`adjust`), not through
  a rest, so `spec.json` maps nothing and `recharge` refills nothing for Story.
- **The probe vocabulary now spans both eras.** `pool`/`tag`/`set_number` resolve against `Sheet`
  counters, tags and numbers when the payload is a sheet, and against `StatBlock`/`Progression`
  when it is typed 5e — so the 5e scenarios and the new Story ones run from one suite.

### What Story stopped verifying in code

Accepted with eyes open, per the plan. Three of the four are now eval scenarios
(`story-risk-single-roll`, `story-taken-out-cannot-risk`, `story-no-risk-needed`). The fourth — a
claimed helpful tag that does not exist — is not reachable by outcome-level probes, because the
`+1` lives inside the dice expression the Director wrote; `BASELINE.md` records why no probe was
built for it.

### Limits this shape accepts

- **A proposal writes the player's sheet and nothing else.** Story's old `acquire_gear`, which
  created a carried item, is no longer expressible; gear now arrives through the fiction (the
  Maintainer creates the item, the Director tags it). An engine whose advancement touches a
  companion or the world would need more than a `SheetDelta`.
- **`choose` is exact, not a maximum.** "Pick up to two" cannot be offered; a record that means it
  has to be split into offers that each take a fixed count.

### Review pass

- **The legality rule became `ProposalSpec.violation`** — `offer_violation` and the workflow's
  `violation()` were two names for halves of one rule; the method holds the whole rule where the
  spec lives, and the deps type is now `AdvisorContext` (the proposal is the delta, not the deps).
- **Fixed: the trial-apply now revalidates the trial sheet.** `apply_delta` never raised on a
  delta that leaves an invalid sheet (`SetNumber` on a counter key — the misname crossover — or a
  counter maximum below its minimum), so such a proposal passed the advisor's retry and only blew
  up as a ValidationError at commit. The retry now catches everything the commit would refuse.
- **Fixed: `restart()` clears `drafted`** — a stale draft survived a restart and reappeared in the
  panel when growth next filled.
- **Fixed: the review panel no longer crashes on a stale draft** — a turn between propose and
  confirm can change the sheet under the draft, and `preview` raised mid-render.
- Cut: the picks-vs-options rule gained the test the plan asked for; the shipped-content
  value-pinning test in `tests/story/` deleted (composition is `test_shipped_content`'s job,
  merging is `test_sheet`'s); `preview` copies the player's sheet, not the whole state.
- **Instruction text stays split on purpose**: engine-owned procedure is data (`.md` in the engine
  dir, loaded by `load_engine`), core role text is code (`prompts.py`/`proposals.py` constants
  coupled to the output types and renderers beside them). 5e's `DIRECTOR_INSTRUCTIONS` is the one
  outlier and phase 3 deletes it with its module.

### Carried into phase 3

1. 5e's `ProposalSpec` is a stub. 3.1 gives it the real one: the `advancement-ready` tag opens the
   offer, the level record's `options`/`choose` bind the picks.
2. `dnd5e/advancement.py` still exports `status`/`Section`/`benefit_sections`/`plan_sections`,
   reachable only from its own tests now that the panel is gone. They die with the module.
3. `probes._actor` is still the typed-5e-only path, used by `set_level`; phase 3 deletes it along
   with `_resource`, `_progression` and the `attack_rolled`/`dc_rolled` fact kinds.
4. Story's template is per kind, so every NPC carries an unused `growth 0/3` counter in its render.
   Harmless, and the price of templates keyed by kind rather than by entity.
5. `phase 3 entry gate`: re-read `scripts/evals/BASELINE.md` before starting.

## Phase 3 — 5e on the Sheet, the typed engine deleted — done, staged, not committed

Entry gate read: baseline `interpretation 74.2%`, `completion 95.2%`, `combat 67.8%`, bands 12/10/12
plus "no tag above 50% falls to 0".

- [x] 5e is data + a 71-line shim: `spec.json` (actor template, recharge labels, 22 collections),
      `director.md` (the whole 5e procedure), `advancement.md` (advisor guidance), `engine.py`
- [x] **Deleted**: `access, advancement, bestiary, features, mechanics, presentation, procedures,
      progression, rolls, ruleset, spells, state, tools, values` and the whole `content/` package
      (3,937 lines), plus 14 test modules under `tests/dnd5e/`
- [x] Importer rewritten: `scripts/srd/` 1,931 → 784 (`upstream.py` 255, `project.py` 414,
      `build.py` 115); `feature_mechanics.py`, `choices.py` and `corrections.py` are gone
- [x] Pack regenerated from `5e-bits/5e-database` v5.10.0 at `3f5593e`, same 22 collections and the
      same record counts, now `LenientRecord`s; `Manifest.source_commit` pins the hash
- [x] Overlays re-authored as `SheetDefinition`: `characters/kael`, `scenarios/whispering-vault`,
      and the eval-only `bram` and `elowen`
- [x] `core/dice.py` trimmed to `terms`/`DiceTerm`/`ConstantTerm`/`DiceExpr` (112 → 57)
- [x] `SAVE_VERSION` 25 → 26 (bumped by the importer, as it does on every shipped regeneration)
- [x] Evals: probes read `Sheet` only; `--only` accepts an engine id so the gate runs the baseline's
      21 scenarios and nothing else
- [x] Gates green: 83 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean
- [x] **src 4,161 lines** (budget ≤ 4,400; phase 2 left 8,200; baseline was 8,497 — **−4,336**)
- [x] **Exit gate measured and passed** — `run.py --only dnd5e --runs 3`, three runs recorded in
      `BASELINE.md` (`results/2026-08-05-1b1f3b0-oss-120b-{a,b,c}.json`); the gate holds on all
      three, and run C records a 25-point interpretation regression from the content pass

Measured three times, `openai/gpt-oss-120b`, `retries=3`, 63 turns per suite. Twice on the lean
pack: **interpretation 87.3 / 89.5%, completion 100 / 90.5%, combat 95.6 / 82.2%** — every gate
condition met, two of them above the band on the good side. Once on the enriched pack that the two
review passes produced: **interpretation 63.3%, completion 95.2%, combat 66.7%**. That run still
passes the pre-registered gate (−10.9 / 0.0 / −1.1 against a 12/10/12 band, no tag collapsed), but
it is 25 points of interpretation below the lean runs against a measured drift of 2.2, and the
failure is `0 rolls against a target number` — the Director not acting at all. `BASELINE.md` carries
the full reading. **The content enrichment is a measured regression, and phase 3.5 in
`REFACTOR-LENIENT.md` is the response**: a referee to carry completion, a reorganised context, and a
writing pass over instructions and tool descriptions.

Two results the phase-0 findings pre-registered:

- **One action per turn landed.** `save-for-half` was 0% at baseline because the director cast
  burning hands twice; it is 100%/67% now, and `spells` rose 25 points.
- **`level-up-offer` is still 0%, and that now has an answer.** Phase 0 wrote that if the rate held
  at 0 after the tool changed, the instructions were the cause. The tool changed completely
  (`level_up` → `add_tag("advancement-ready")`) and the rate did not move, so it is the instruction.
  The suspect is placement — ADVANCEMENT is the last section of `director.md` — which is the phase-2
  wording lesson in another form. Fixing it edits the thing under test, so it is a follow-up with
  its own measurement, not part of this commit.

`uv run aidm` boots and the shipped game composes; a live combat turn and a level-up in the UI are
still to be played by hand, because both need the model.

### Decisions taken

- **The pack keeps all 22 collections and all 2,201 records.** A uniform prose projection is simpler
  than choosing a subset, the census stays comparable to the typed pack, and refs render by name so
  pack size costs no prompt budget.
- **Numbers only where prose cannot carry them**: monsters (`armor-class`, `hp`, the six abilities,
  `proficiency-bonus`), classes (`hit-die`), races (`speed`), level rows (`level`,
  `proficiency-bonus`, `slot-1..9`, class-specific whole numbers). Spells, weapons and features
  carry **none** on purpose: a record's numbers land on the sheet of any entity that refs it, so a
  `spell-level` on five known spells would collide into one meaningless number on the caster.
- **A level row's `options` are its picks, flattened.** Each feature the level grants contributes one
  pick — its own ref, or its subfeature options where the feature *is* a choice — and `choose` is the
  number of features. `fighter-1` offers the six fighting styles plus Second Wind and takes 2. What
  it cannot express is which pick belongs to which slot, so two fighting styles and no Second Wind
  would pass: that is the "legality thins out" the plan accepts, and `advancement.md` says it in prose.
- **The actor template holds only what every 5e actor has** — six abilities, `armor-class`, an `hp`
  counter. Slots, feature pools, `level` and `proficiency-bonus` are authored per character, so a
  giant rat's render is four lines instead of carrying nine empty slot counters.
- **`corrections.py` is deleted, not ported.** Its only entries fixed the rogue's *cumulative*
  ability-score-bonus ladder, a field the typed progression diffed and the lenient level row does not
  emit — the ASI shows up as the feature the level grants.
- **`is_constant` went with the `MOD` machinery**, though the plan listed it as surviving: its last
  consumer was `spells.py`, and a helper nothing calls is not worth keeping.
- **`--only` matches an engine id as well as a tag or scenario id.** The gate compares the same 21
  scenarios before and after, and the phase-2 story scenarios now live in the same directory.
- **Kael's proficiencies are refs, not decisions.** The typed `decisions` map is gone; skill
  proficiencies are `proficiencies/*` refs the Director can read, and language picks were dropped as
  flavour the rules never consulted.

### What phase 3 stopped verifying in code

- Which spell a caster knows, whether they are proficient with a weapon, and whether a pick belongs
  in the slot it was made for. All three are prose the Director and the advisor read.
- A monster's attack bonus and damage dice are quoted from its text rather than computed, so a
  misread line is a wrong number the ledger cannot catch. The `*-damage-window` scenarios are what
  measures it.

### Review pass (adversarial, after the gate was measured)

**The measured rates no longer describe the staged code.** The pass below changed the pack, one
`director.md` sentence, and the render the Director reads, so the phase-3 rates in `BASELINE.md`
belong to `1b1f3b0`, not to this tree. `BASELINE.md` says so in place; re-run the 5e suite twice
and append before merge.

- *(Superseded by the content-shape pass below — notes no longer copy; they render beside the
  ref.)* **The pack is actionable again, through one new channel: `LenientRecord.notes`.** A ref
  copies a record's notes onto the backing sheet exactly as it copies numbers, so the mechanics
  a role acts on sit in the scene render with no `read_content` round-trip: a weapon's
  `damage=1d8 slashing (two-handed 1d10 slashing)`, an armour's
  `armor=AC 16. Strength 13 required. Disadvantage on Stealth.`, a monster's
  `attacks=Bite +4 to hit, 1d4+2 piercing` (dragons include `DC 18 DEX, 12d8 acid, half on save`
  breath lines, from upstream's structured `attack_bonus`/`dc`/`damage` fields), a class's
  `saving-throws` and `spellcasting` ability.
- *(Superseded likewise: the discipline now binds only `numbers`.)* **The collision discipline
  extends to notes and is now written down** on `LenientRecord` and in `scripts/srd/project.py`:
  only records that back one entity carry numbers or notes; spells and features stay bare
  because a caster refs many of them onto one sheet.
- **Pack regenerated once** from the pinned `3f5593e` checkout; the importer's auto-bump was
  hand-reverted so `SAVE_VERSION` stays 26 — phase 3 spends one bump in total.
- Cuts: module docstrings that toured files (`srd/build.py`, halves of `probes.py`,
  `import_srd.py`, `upstream.py`), two dataclass docstrings and a duplicate comment in
  `probes.py`, one restating docstring in `fivee_test_support.py`.
- Left deliberately: the level-row `options`/`choose` flattening (a grouped-picks offer would fix
  the two-fighting-styles hole but costs a core `AdvancementOffer` restructure plus panel and
  advisor changes — not worth it while `advancement` sits at 0% for instruction reasons);
  `LenientRecord.tags`, still empty pack-wide *(superseded below — tags are populated and
  rendered now)*; equipment records' cost and weight stay prose.

### Content-shape pass (third review — actionability over line count)

The brief: sharper pack fields the engine can act on, complexity welcome in `scripts/srd/`. This
pass replaced the copy-notes channel above with a render channel, which broke the collision
constraint that kept spells and features bare.

- **Notes and tags no longer copy onto sheets — they render beside the ref.** `_backing` copies
  only `numbers`; `render_sheet` takes a resolver from `load_engine` and shows each ref as one
  line: name, `[ref]`, the record's notes, then its tags. Sheet notes are runtime bookkeeping
  only (concentration), so `set_note` can no longer edit a weapon's damage line. The advisor
  prompt uses the engine renderer too (`render_proposal` takes the engine).
- **The projection principle, applied pack-wide**: upstream int → `numbers` (single-backing
  records only), upstream bool → `tags`, dice/enums/lists → `notes`, sentences → `text`. No
  prose was regexed; every fact comes from a structured upstream field. Spells carry
  level/attack/save/damage/heal/scaling/area/range and component tags; weapons damage +
  property tags + range numbers; armor `armor-base`/`dex-limit`/`strength-minimum` +
  `add-dex-modifier`/`stealth-disadvantage`; monsters speeds, senses, save/skill bonuses, xp,
  immunity notes, multiattack and limited-use; level rows known-spell counts and sneak-attack
  dice; subclasses their domain-spell table; dragonborn traits their breath weapon.
- **Three importer bugs found by the survey and fixed**: multi-AC monsters truncated to
  `armor_class[0]` (archmage lost mage armor 15), breath-variant dragons' breath lines dropped
  entirely (`actions[].options` was unread), and damage-less save actions (aboleth's Enslave)
  omitted from `attacks`.
- **Readers**: the per-entity render (every turn, all roles' visible entities), `read_content`,
  and `director.md` (THE SHEET, AN ATTACK, A SPELL, A CHECK OR A SAVE, `set_number` armour
  arithmetic). Elowen's full render is ~1.5k chars with five spells inline — a spell turn no
  longer needs a `read_content` round-trip for its numbers.
- **What stayed prose, on purpose**: a monster's `attacks` note is one key (action names are not
  slugs; a semicolon list reads fine); armour keeps its formula sentence in text; features other
  than choices carry no dice (upstream has none — extracting Second Wind's `1d10 + level` would
  mean regexing 407 descriptions, i.e. rebuilding the deleted `feature_mechanics.py`).
- Cost: src 4,200 (+39 over the measured tree, budget ≤ 4,400), `scripts/srd/` 784 → 1,309.
  Pack regenerated from the pinned `3f5593e`, census unchanged (2,201 records); `SAVE_VERSION`
  auto-bump hand-reverted each time — still 26, phase 3's single bump.

### Content-completion pass (fourth review — every structured upstream field, audited)

All 22 collections were audited field-by-field against the pinned `3f5593e` upstream JSON. The
projection rules held: upstream int → `numbers` (single-backing records only; items are their own
entities, so equipment numbers are collision-free), bool → `tags`, dice/enums/lists → `notes`, a
choice a record *is* → `options`/`choose`, sentences → `text`; never regex `desc` prose.

- **Monsters**: choice-shaped multiattacks (`action_options`, 33 monsters — the bandit captain's
  `2x Scimitar + 1x Dagger or 2x Dagger`), one/two-handed damage variants (choice-shaped `damage`,
  16 monsters — the wight's `1d8+2 slashing (one handed) or 1d10+2 slashing (two handed)`; these
  were dropped entirely before, not even prose), save-gated damage riders (the assassin's
  `7d6 poison (DC 15 CON, half on save)`), the androsphinx's staged Roar, spell lists and slot
  counts as `spells`/`slots` notes (36 casters), `forms` note (18 lycanthropes/vampires,
  semicolon-joined because form names carry commas), worn armor named in the AC line
  (`15 (armor: Studded Leather Armor)`, 34 monsters) plus the three `desc`-only AC entries, and
  the 45 lore paragraphs appended to `text`.
- **Equipment**: `cost-gp`/`cost-sp`/`cost-cp` numbers on everything priced (unit-named keys —
  every upstream price is whole in its own coin; one normalized copper key would misstate 15 gp
  as 1500), ammunition `quantity` (4 bundles), vehicle `speed` (ft/round) / `speed-mph` /
  `capacity-lb` numbers. Weapon damage is **both** channels: `damage-dice-count 1` + `damage-die 8`
  numbers (a `two-handed-damage-*` pair on the five versatile weapons, the type a tag; the
  blowgun's flat 1 is one one-sided die so the same keys always spell the roll) *and* the
  `damage=1d8 slashing` note the render shows. A pass had replaced the note with the numbers
  alone, which made the Director concatenate a count and a die into an expression on the turn it
  swings — `roll` takes an expression, so it now copies one, and the numbers stay for a rules
  checker that wants the parts.
  **Fix**: melee weapons no longer project `Range: 5 ft.` or `range-normal 5` — upstream gives
  every melee weapon `range.normal: 5` as baseline reach (reach weapons included), which misread
  as a ranged distance; `throw_range` is untouched.
- **Magic items**: `variants` note on the 21 parents (`Potion of Healing … Supreme Healing`), a
  `variant` tag on the 123 children.
- **Spells**: `classes`/`subclasses` notes — previously nothing in the pack connected a class to
  its castable spells.
- **Classes**: multiclassing block (AND-prerequisites, the fighter's OR-choice, granted
  proficiencies and skill picks), spellcasting start level (`CHA (from level 2)` on paladin and
  ranger).
- **Levels**: sorcerer `creating-spell-slots` note (the Font of Magic table), and upstream's
  `9999` sentinel now reads `rage-count=unlimited` instead of landing as a literal 9999 number.
- **Features**: the warlock's 32 invocations as an `invocations` note (flat upstream list — how
  many to know is the level row's `invocations-known`, so `options`/`choose` cannot carry it),
  `parent` note on the 84 choice-option children.
- **Races/traits**: every creation choice is now `options`/`choose` — human/half-elf bonus
  language, high-elf cantrip (14 wizard cantrips), extra language, dwarven tool proficiency,
  half-elf skill versatility (2 of 18) — each trait carries at most one choice in this dataset
  and the importer fails fast if that stops holding; traits carry `races`/`subraces`/`parent`
  notes; races their `age` prose, subrace list and language-choice line.
- **Backgrounds**: `starting-gold 15` number, the holy-symbol category pick, and the
  personality/ideals/bonds/flaws tables (ideals with their alignments) in `text`.
- **Proficiencies**: `reference` in the text — `Armor proficiency: Light Armor.`

**Deliberately not projected**, with reasons: `image`/`url`/`option_type` fields (presentation
and API plumbing); monster `hit_dice` (redundant with `hit_points_roll`); telepathy (inside the
`languages` prose string — no structured field exists upstream); spell material gp-cost/consumed
(prose inside the `material` string); magic-item attunement/charges (prose-only upstream);
weapon `weapon_category` (equal to `category_range` minus the range word); proficiency
`races`/`classes` backlinks (the forward links are already projected); the grimlock's
"or 10 ft. while deafened" blindsight clause and the rogue's nested expertise choice-of-choices
(one record each, prose still carries them); pack `contents` as names not refs; equipment
`weight` (already on the text line, floats don't fit `numbers`).

Cost: `scripts/srd/` 1,309 → 1,671, tests +52 (`test_content.py` 101 → 152); src Python
unchanged — only `director.md` moved (+2 lines net). Pack regenerated from the pinned
`3f5593e`, census unchanged (2,201); `SAVE_VERSION` hand-reverted to 26 again.

### Carried out of phase 3

1. **`level-up-offer` at 0%, six runs for six — the hoist is applied, the measurement is owed.**
   The ADVANCEMENT section (last in `director.md`, after everything a normal turn needs) moved into
   the opening rules block with near-identical wording — the same fix shape that took phase 2's
   buried precondition from 33% to 100%. The trailing section is gone. Re-measure the suite; it is
   a change to the thing the gate just measured, and `level-up-offer` is the scenario to read first.
2. **The two owed eval scenarios** (advantage via `keep-highest`, concentration replacing a spell)
   are written *after* the gate, so the suite the gate compares stays frozen. Closing-out item 1.
3. `docs/5E_EXTENSION_ROADMAP.md` describes an architecture two refactors old (`aidm_5e`,
   `domain/reducer.py`, `SAVE_VERSION` 16) and now also names deleted modules. It should be deleted
   or rewritten; that is not phase 3's call to make silently.
4. The `max-hp` probe key is the one place a scenario still names something the sheet does not have —
   it resolves to the `hp` counter's maximum. Left as is: renaming it would edit scenario files the
   gate is measured on.
