# PROGRESS

One entry per PLAN.md phase: the `src` line counts before and after, decisions made off-plan, the
review findings refuted and why, and what is known and accepted.

## Phase 1 — the campaign layer and the commissions go; scope arrives (2026-09-05)

`src`: 9,367 → 7,965 lines (target 7,900–8,200). Tests: 560 → 425, all green. Every
`engines/<id>/` under 2,000 lines (scenes 863, rooms 737, twentyfourxx 660, loner3e 587,
breathless 577, tunnelgoons 363). Reviews: Fable and a second Opus reviewer; `codex` is not on
this machine.

### Decisions off-plan

- Step 14 (the scenario data) ran in part A rather than D: `Frozen` has `extra="forbid"`, so once
  `kind` left `ScenarioMeta` the four campaign scenarios failed to parse and no test that opens
  shipped content could run. The four remaining scenarios carry the PLAN's `scope` text verbatim.
- `RoomWorld.attach(region, start)` lost its `known` parameter (and `anchor` before it): the one
  production caller passes `known=False`, and the `known=True` path was the tavern's job region,
  alive only in a test. PLAN step 12 wrote the call as `attach(..., known=False)`.
- `SceneEngine.render_next(draft, intent)` lost its `answer` parameter: `write_next` is its only
  caller and always answers `NextDraft`, so "when the answer is a `NextDraft`" (PLAN step 10) was
  a constant. The arc line is appended whenever `world.arc` is set.
- `Turn.apply` folded into `Turn.call`, its only caller once `runtime._fulfil` went; the one test
  that drove it directly now calls `_apply`, as `test_decisions.py` already does.
- Three tests of the deleted "at least one cast member besides the player" bar
  (`test_master_tools.py` ×2, `test_launcher.py`) were re-targeted to the integrity refusal "ids
  that exist; these name nobody" rather than deleted: their subject was the re-prompt and the
  `way_unwritten` path, which stay.
- `_extension_unmet` returns one refusal on an empty region ("at least one new place") instead of
  two.
- NEXT-SPECS.md decision 5 got a dated line (the campaign layer is gone), its two citations of
  `docs/24XX.md` deviations follow the renumbering, and "the campaign has been played through
  once" became "the game has been played through once".

### Findings refuted (both reviewers), and why

- Move `named_unmet` out of `engines/base.py` (one caller): PLAN step 4 names `base.py` as its
  home and `test_engines_base.py` for its test. Left where the PLAN put it; a cut for the
  maintainer if Phase 2 brings no second caller.
- Type `apply_scene`/`install` on `NextDraft` and drop the `isinstance` branch: PLAN step 8 writes
  `apply_scene(draft: SceneDraft[C])` and "sets `run.recap` for a `NextDraft`". Kept as written.
- Replace `scope`'s `Field(description=...)` with a comment because no schema reads it: PLAN
  step 1 specifies that description. Kept.
- Fold `rooms/drafts.py` into `rooms/world.py`: PLAN step 12 keeps `drafts.py` with `MapDraft`.
  Kept.
- NEXT-SPECS.md's title "after the hub": the file is dated 2026-09-02 and says so in its first
  paragraph; the title is historical. Left.

### Known and accepted

- The Done-when grep has incidental prose hits, none a deleted concept: `ledger` (an entity in
  `test_context_boundary.py`, prompts in `test_master_tools.py`, "ledgers" in the loner3e
  goldens), "Skate Board" in `breathless/packs/srd.json`, "Offering" in a docstring.
- `tests/core/fixtures/turn/<id>.json` did not change: those files record a scripted turn's
  facts, not the game state, so step 17's "`scope` in `scenario`, no `commissions`" never applied
  to them. The four `master.txt` and four `master_tools.json` fixtures changed exactly as listed.
- `uv run aidm` prints an anyio "cancel scope" traceback on shutdown. It reproduces on the commit
  before this phase; not this phase's.
- The `/phase` skill's four commands, the smoke (`/`, `/scenario`, `/create`, `/settings` and a
  game page per scenario all answer 200) and the golden regeneration ran on the staged tree.

### External review of the PLAN, folded after the phase (2026-09-05)

A review of PLAN.md arrived as the phase started. Already resolved by the phase as run: step 14
moved into part A; both `author` paths pass `meta.scope` and build no campaign; `named_unmet`
imported from `base`; `render_history(world.records())`; the `begin`/`records`/`install_extension`
leftovers; the cast-bar tests re-targeted; the `test_seam` stub; `worldsmith.md`; the half-campaign
doc clauses. Folded now, in code: `test_render_history_binds_nothing` deleted (with `ChapterRecord`
gone the type makes binding impossible) and `tests/loner3e/test_worldsmith.py` deleted (its two
tests asserted prompt prose; `render_master`'s scope test is the one boundary test kept). Folded in
PLAN.md Phase 1 for the record: step 17's fixture expectations (turn fixtures are fact lists,
`master.txt` carries every `rules.md` edit), the Done-when grep narrowed to whole words in code and
prompts, the split note. Folded in PLAN.md Phase 2: the retry subsystem is cut (a failed
complication write clears the brief and files `UNWRITTEN`, as a failed pursuit does); the brief is
`Game.handoff` on the platform, not `SceneRun.complication` plus an `Engine.handoff` seam method;
`finish_job` keeps `skill` required (no empty-skill decision); the `COMPLICATION` prompt says what
`recap` means for a scene nobody left; `settle`'s pending-complication guard goes (dead behind
`HANDOFF_WAIT`); `take_job` returns a list. `take_job` and `world.job` stay: the maintainer's call,
kept as the review leaned. NEXT-SPECS.md line naming `scenarios/amber-tap` as a future host now says
"a 24XX scenario".
