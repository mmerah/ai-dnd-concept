# Plan

The phased plan for what is built next, in order. Rewritten 2026-08-13 after the recentering
decision: the project ships official, freely licensed, LLM-as-GM-friendly tabletop engines
only. Loner 3e is the shipped engine; 24XX and Cairn 2e sit on a docs-only shelf until one is
wanted. Each phase carries enough detail to implement without prior context; only the next
unshipped phase needs full resolution. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 3 — Shrink and comply (~2.5–3 days)

Two audits (2026-08-13, full-tree) found ~500 LOC of pure waste, ~250 lines of prose living in
Python, per-engine boilerplate that the shelf engines would paste twice more, and one genuine
loner3e rules bug plus prompt prose the SRD doc *claims* exists but no prompt contains. This
phase is both audits' accepted findings, sequenced so every persisted-byte change lands in one
commit with one `SAVE_VERSION` bump and one golden regeneration. Behavior is otherwise
unchanged: no feature is removed, and outside steps 7–9 no fixture may move.

Verified groundwork the steps rely on:

- `DiceExpr`, `MAX_LENGTH`, `_parseable` in `state/dice.py` have zero references anywhere.
  `roll(bonus=…)` and multi-term parsing (`ConstantTerm`) have exactly one caller:
  `tests/probe/probe_engine.py:102`.
- `Counter.recharge` / `Counter.minimum` are never set by any engine or content file; they
  appear only as serialized defaults in save/state fixtures. `Thread.kind`, `Memory.tags`,
  `Memory.turn` are written (scenario / `pipeline.py:70`) but read by nothing.
- `available_tags` (`engines/loner3e/resolve.py:72`) reads sheet tags for the acting actor
  only; an opponent's Skills/Frailties/Gear can never be cited as leverage or trouble.
  `scenarios/whispering-vault/world.json:75` works around this by duplicating the rat's skill
  as a core trait.
- The `TraitChange` docstring (`state/effects.py:54`) says "edge, or burden" and is injected
  into the Director's JSON schema every turn (`fixtures/schemas/loner3e/turn_plan.json`).
  `state/base.py:69` and the `(edge)`/`(burden)` prefixes in `characters/kael/base.json` and
  the whispering-vault world carry the same dead vocabulary.
- The golden turn fixture has no conflict exchange (`opponent_id` is always null), so the Luck
  reset (step 9) moves no golden fixture; its coverage is unit tests in `tests/loner3e/`.
- No prompt anywhere contains the SRD's scene moods (Dramatic/Quiet/Meanwhile) or Sibylline
  Responses guidance, although docs/LONER-3E.md:900 and :933 claim the Scene Director carries
  both.

Steps, one commit each:

1. **Delete dead dice generality** (−45). Remove `DiceExpr`, `MAX_LENGTH`, `_parseable`,
   `ConstantTerm`, multi-term parsing, the `bonus=` parameter, and the `"disadvantage"`
   `RollMode` literal (loner3e flips *which side* gets advantage instead — `resolve.py:191`;
   nothing ever passes disadvantage). Port the probe engine off `bonus=`: roll `"1d6"` and add
   the stat in code, adjusting its tests' expected traces. Golden dice traces are unaffected
   (production only ever rolls `"1d6"`).
2. **State-layer dedup** (−45). Collapse `_add/_remove/_untag/_reveal_relation`
   (`state/apply.py:229-289`) into one mode-table function — trace strings must be preserved
   byte-exact; `tests/core/test_effects.py` is the guard, and no golden fixture contains a
   relation change. Move `entity_fact`/`explained_fact` (`apply.py:72-95`) into
   `state/facts.py` and rewrite the hand-rolled `Fact(...)` blocks in `world.py:285-323` and
   `apply.py:292-331` onto them; the two fact dialects exist only because `apply` imports
   `world`.
3. **App/UI dedup** (−80). In `app/launcher.py`: one `_one(options, id)` lookup helper
   replacing the four `next((o for o in xs if o.id == y), None)` copies; collapse
   `ScenarioOption`/`CharacterOption` into `ContentOption` with a `subtitle: str`; delete
   `LauncherModel` (it redeclares `state/base.py` `Frozen` in a layer allowed to import it).
   Merge `FileSaves`/`FileTraces` (`content/store.py:116-179`) into one class with two
   suffixes, and drop `_StoredVersion` (use `SaveShell` for saves, inline the trace probe).
   Pass `Settings` into `GameSession` and `run_turn` instead of six scalars (update
   `loner3e_test_support.py`, the second construction site). In `ui/`: one
   `page_header(title, badge=None)` in `panels.py` used by `app.py`, `home.py`, `create.py`;
   `functools.partial` for the two hand-written handler-closure factories in `home.py`; fold
   `stage()` into the `Stage` dataclass (`turn/roles.py:51-112`). Covered by
   `tests/ui/test_launcher.py` and the UI suite; no fixtures move.
4. **Split `turn/prompts.py`** (±0). Move lines 10–185 — `Exit`, `BaseScene`,
   `SceneSnapshot`, `VisibleScene`, `check_speaker`, `_placements` — verbatim into
   `turn/scene.py`; imports only. `test_context_boundary.py` asserts on
   `VisibleScene.model_fields` (a leak boundary): repoint its import, change nothing else.
5. **Core prompt prose → files** (−145). The constants at `prompts.py:450-595`
   (`RULES_DIRECTOR`, `SCENE_DIRECTOR`, `CORE_ADVISOR`, `NARRATOR`, `WORLDKEEPER` and the
   `_DIRECTOR_*` pieces) become `src/aidm/turn/prompts/*.md` read via the same
   `loader.engine_text` path as `director.md`. One file per shipped constant; a piece shared
   by two constants stays its own file joined in code. Trap: the Python constants use
   `\`-continuation, which joins lines *without* a newline — the files must reproduce the
   assembled strings byte-identically, and `fixtures/instructions/loner3e/*.txt` is exactly
   the guard that fails on a mis-transcription. No fixture may move in this step.
6. **loner3e content packs: SRD + AP01, selectable** (revised decision — see below). New
   `engines/loner3e/pack.py`: a strict frozen Pydantic model — `name`, `source` (URL),
   `license` (attribution line), `concepts`/`skills`/`frailties`/`gear` as non-empty tuples of
   `{id, label, detail}` (`detail` may be empty — AP01 entries are bare phrases), and optional
   `twist_subjects`/`twist_actions` (exactly six strings each when present). Two files:
   - `packs/srd.json` — today's values verbatim: the four curated tables from
     `create.py:8-106` and the twist table from `resolve.py:17-24` split into subject and
     action columns. Same ids, labels, strings → existing creation fixtures unchanged.
   - `packs/ap01-fantasy.json` — the four d66 creation tables (36 entries each) transcribed
     verbatim from
     <https://lonersrd.zotiquestgames.com/adventure_packs/AP01_fantasy.html>, slugified ids,
     empty details. AP01 has **no twist table**, so the file omits the twist fields; its
     names/spells/factions/seeds tables are authoring-time content the engine does not
     consume — not vendored. Verified 2026-08-13: the AP01 page states only
     "© Roberto Bisceglie"; the SRD site's own license statement is CC BY-SA 4.0. Treated as
     covered because it ships inside the SRD site; step 10's licensing note names the
     ambiguity.
   The engine loads and validates every `packs/*.json` once in `__init__` (fail fast;
   exactly one pack — srd — must carry the twist columns, and the resolver reads them from
   it, still rolled resolver-side). *Selection* is creation step 0: `Loner3eCreation.steps`
   already takes `picks`, so a first `CreationStep` ("Choose a table set": one option per
   pack, label from `name`) makes the later steps come from the chosen pack, and `create()`
   resolves labels against it. No overlay change, no persisted bytes, no SAVE_VERSION —
   the chosen options land in the character overlay as plain strings exactly as today.
   Update `tests/ui` creation flow tests and `tests/loner3e/test_create.py` for the new
   first step. While in the engine: kill the delegation shim (`rules.py:34-41`'s three
   methods that only forward to `mechanics.py`) and replace the per-engine `read`/`write`
   wrappers (`mechanics.py:112-117`) with a `read_mechanics(state, Model)` helper in
   `engines/counters.py` beside the existing `write_mechanics` (−25 now, −25 per future
   engine).
7. **Compliance prose** (moves instruction/prompt fixtures, no persisted bytes). In
   `engines/loner3e/director.md`: Sibylline Responses (never re-ask an answered question;
   reframe rather than force a roll; when no outcome fits, read it as *yes, but…*). In the
   scene-director file from step 5: the SRD's three scene moods — Dramatic, Quiet, Meanwhile —
   as the vocabulary for its pacing judgment. In `advancement.md`: one sentence that a
   lingering enemy from a milestone is recorded as a thread and its entity, not a sheet
   change. In the narrator file: replace "never recite hit points, armour class, modifiers"
   (5e residue) with system-neutral wording. Regenerate `instructions`/`prompts` fixtures,
   read the diff.
8. **The save-shape commit** — every persisted-byte change, one `SAVE_VERSION` bump (56→57):
   - *Opponent tags visible*: `available_tags` merges `mechanics.sheets[...].tags()` for every
     actor among `carriers` (present actors are already in `place`'s children; the opponent is
     already revealed by `resolve_question`). Delete the duplicated rat trait at
     `scenarios/whispering-vault/world.json:75` — the sheet skill now reaches the resolver.
   - *Vocabulary*: `state/effects.py:54` and `state/base.py:69` docstrings lose
     "edge"/"burden" for SRD terms (these docstrings are the Director's schema text — rule 2's
     probe is not needed, the schema *shrinks* in vocabulary only). `(edge)`/`(burden)`
     prefixes in `characters/kael/base.json` and the whispering-vault world become
     `(skill)`/`(frailty)`; the `test_effects.py:141` comment follows.
   - *Vestigial fields*: delete `Thread.kind`, `Memory.tags`, `Memory.turn` (drop the write at
     `pipeline.py:70`), `Counter.recharge` and `Counter.minimum` (field, validator, render
     line); edit the scenario world's `"kind": "quest"` thread and any authored memory tags.
   - Bump `SAVE_VERSION`, `AIDM_GOLDEN_REGEN=1`, update `FIXTURE_SAVE_VERSION` in
     `test_golden_state.py`, and read the diff: expect removed keys, changed trait/docstring
     text in schemas, the rat trait gone — dice traces and outcome labels must not move.
9. **Luck resets when a conflict ends** (SRD: Luck "resets after conflicts"). `_strike`
   (`resolve.py:153-163`) already knows the one conflict end the engine can see — a side
   hitting 0. Reset both participants' luck to maximum there, keeping `defeat_note`; the
   Director's `counter-change` stays the documented fallback for conflicts that fizzle without
   a knockout. Unit tests in `tests/loner3e/`; no golden movement (no conflict in the turn
   fixture).
10. **Docs and licensing.** docs/LONER-3E.md: the delegation claims at :900 and :933 become
    true statements pointing at the prose landed in step 7; rewrite the Deviations list —
    drop what steps 7–9 closed, add the previously unnamed ones: the Twist Counter is hidden
    from the player, concept is a closed five-option menu (SRD wants a free phrase), one
    change per milestone (SRD allows several), and the 5W+H framing table is not rolled.
    README gains a Licensing section naming the CC BY-SA 4.0 files (docs/LONER-3E.md, the
    loner3e engine's prose and packs, the SRD-derived content) with attribution to Roberto
    Bisceglie / Zotiquest Games, and noting that `packs/ap01-fantasy.json` derives from the
    AP01 page, whose own footer states only a plain copyright while the SRD site declares
    CC BY-SA 4.0 — treated as covered, flagged for a one-line confirmation email if the
    maintainer wants certainty. The license of the rest of the code is the maintainer's open
    decision; the section says so rather than inventing one.
11. **Comment trim pass** (repo-wide, no behavior change). Apply CLAUDE.md's comment rules to
    every production and test file: delete comments that narrate control flow, restate a name
    or type, or give historical counts; keep constraints, tradeoffs, invariants. Docstrings
    consumed by schemas or prompts are runtime behavior — step 8 already handled the two that
    change; this step must not touch any docstring that reaches a fixture.

Done when: the suite is green on every step's commit, production LOC is down ~500 (≈4,550
from 5,059), `packs/srd.json` drives creation and twists, and docs/LONER-3E.md's deviations
list matches the code again — only architecture-forced deviations (per-thread milestones, one
question per turn, Diceless appendix) and named design calls remain.

## Phase 4 — Redesign refactor (~1–2 weeks)

The full plan lives in REFACTOR.md; this entry sequences it. A ground-up refactor of the
engine contract, agent roster, capability shape, hooks/clocks, typed overlays, and content
packs — approved 2026-08-13, explicitly superseding this file's "speculative engine-prep
refactors: rejected" and "engine-configurable turn pipeline: deferred" entries below (the
maintainer chose the full redesign, with 24XX implemented at the end as the proof).

Summary: roster merges the two Directors into one (3 in-turn roles, Worldkeeper survives, live
probe gates the merged schema); `Advancement` generalizes to a subject-aware `Subsystem` with
one generic trace entry (NPC advancement falls out; combat stays engine-internal — a
`CombatState` in the engine's mechanics payload, never a subsystem);
threads gain optional clocks and hooks become repeating and engine-effect-capable; engines
declare a typed overlay model (`rules_type`) and split `commit` into pure `validate` + `seed`;
packs load from a user-facing `Settings.packs_dir` with pack identity in saves; `roll_pool`
replaces `RollMode`. Nine phases, each separately committable; refactor phases net ~flat LOC
(adversarial recompute — any decrease is a win); phase 9 ships the 24XX engine as the
architectural proof that a new engine touches nothing outside its package but one
registration line.

Done when: REFACTOR.md's acceptance bar holds and 24XX plays a turn. Phase 5's creator script
then binds to `ScenarioWorld` + `Engine.rules_type` + `write_scenario`, all landed here.

## Phase 5 — Proposal study resolved: two amendments to REFACTOR.md step 5

Two external refactor proposals (GEMINI-PROPOSAL.md, GPT-PROPOSAL.md — deleted 2026-08-14
after adjudication, in git history) were evaluated against the post-step-3 tree. Everything
in them is already shipped (steps 1–3), already scheduled (steps 4–9, phases 6–7), or
rejected on verified grounds — the roster and Worldkeeper questions in particular were
already adjudicated in REFACTOR.md with the live-probe evidence. Two items were adopted.
Both amend REFACTOR.md step 5 (threads/clocks/hooks): **implement them inside that step**,
not as a phase of their own — this phase closes when step 5 lands with these semantics.

1. **`fire_hooks` becomes a bounded drain** (GPT's reaction queue, verified gap). As
   step 5 stands, a hook that ticks a clock to full can never fire the filled-clock hook:
   matching scans only the facts passed in (`state/apply.py:273`), facts produced by a fired
   hook's own effects are never rescanned, and facts do not survive the turn — so the chain
   is not "one turn late", it is dead. Change `fire_hooks(draft, facts, apply)` (the
   signature step 5 already gives it) to run its existing one-pass body in rounds: round 1
   matches the input facts; every fact the round's fired hooks produced (each `hook_fired`
   fact and its effects' facts) becomes the input of the next round; stop when a round fires
   nothing, or after `MAX_HOOK_ROUNDS = 3` rounds (depth for fact → clock-filling hook →
   thread-advancing hook, with one round of slack). Within a round, hooks keep authored
   order and fire at most once against the round's facts, exactly as today; the
   `fired_hooks` once-guard, `Hook.once`, `hook_failed` handling, and note appending are
   unchanged. If the final round still produced facts, append one
   `Fact(source=CORE, kind="hooks_capped", trace="hook chain stopped after 3 rounds")` —
   never a silent stop. Both of step 5's call sites (post-resolve and post-Worldkeeper
   report) call the same drain; the second call site stays, because the report lands after
   narration.
2. **`clock_filled` in the fact data** (the authoring surface for the above). Step 5 puts
   clock values into the `thread_advanced` fact data; write them as `clock_current`,
   `clock_maximum`, and `"clock_filled": current == maximum`, and omit all three keys for a
   clockless thread. A filled-clock hook then matches
   `{"kind": "thread_advanced", "data": {"thread_id": "...", "clock_filled": true}}` —
   one boolean instead of the maximum duplicated across two fields. Subset matching is
   untouched.

Tests, added to step 5's list: a hook ticking a clock to full fires the filled-clock hook in
the same transaction; two repeating hooks authored to feed each other stop at the round cap
with the `hooks_capped` fact; a hook matching on `clock_filled: true` fires only when the
tick fills the clock. No golden movement beyond what step 5 already regenerates.

## Phase 6 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at
authoring time. This is a script, not the app: agentic workflows are fine outside the turn
loop, where speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the shared format already exists and
   is the validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`). Give it one read-only tool returning whispering-vault's
   `world.json` as the worked example, and put the authoring bar in the instructions: 4+
   locations connected by relations with at least one hidden and one `locked` way, 2+ NPCs with
   at least one unrevealed, one secret item, at least one thread with hooks that advance it on
   `entity_discovered` facts, hook `note`s that steer the Director, and `detail.hook` on every
   entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then validate the world alone — a `Scenario` per
   shipped engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the
   engine's normal mechanics validation. Any `ValueError` goes back to the agent as a retry
   message, max 3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per shipped engine, output that engine's strict
   authored-overlay model, prompted with the generated world and engine-provided authoring
   guidance/defaults. Re-run step 2's loop with each generated overlay in place — the overlay
   is what `begin_game` exercises beyond shared structure.
4. Files land in `scenarios/<slug>/` only after every shipped engine validates. The script
   prints a summary (entities, relations, threads, hooks per engine) and the author reviews the
   diff before committing — generated content merges by the same review as hand-written
   content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under every shipped engine. Quality beyond
validity is judged by playing it, not asserted by the script. PDF/notes ingestion is a later
input mode for the same script, not a separate system.

## Phase 7 — Media: scene illustrations (~2–3 days)

Presentation only, outside mechanical truth: the game must be indistinguishable with media
disabled, and a failed generation must cost nothing but a log line.

1. `MediaConfig` on `Settings`: `enabled: bool = False`, `provider: ProviderName = "openrouter"`,
   `model: str` (an image-capable model id). `src/aidm/app/media.py`:
   `illustration_request(state: GameState, narration: str) -> str` builds the image prompt
   deterministically — location name and brief, the `here` entities' briefs, the narration — **no
   model call decides whether to illustrate**; a Producer role is not built until a deterministic
   builder proves insufficient. `async generate(prompt, config) -> bytes | None` calls the image
   API and returns None on any failure (logged, never notified).
2. Wiring, at the boundary: after the commit in `GameSession.submit`, when media is enabled,
   schedule generation as a background asyncio task writing
   `saves/<slug>.media/turn-<n>.png`. The turn returns without waiting. `restart()` discards the
   media directory alongside the save.
3. UI: the chat panel shows the image above its exchange when the file exists; refresh on next
   submit (simplest) picks up late arrivals, a `ui.timer` only if that feels bad in practice. No
   gallery, no regeneration button.
4. Tests: the request builder is pure — one test on its output for a known state; the generate
   path is not tested live (network rule). Voice, portraits, and ambient audio are later phases
   of the same shape, none specced until wanted.

Done when: with media enabled a turn grows an illustration within seconds after the narration,
and with it disabled (the default) nothing in state, saves, prompts, or tests differs.

