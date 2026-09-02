# PROGRESS — campaigns with a home base

One entry per phase. Standing decisions live in `PLAN.md`; this file records what each phase did
that the plan did not say.

## Phase 1 — the seam and `engines/hub.py`

- `src` lines: 9,548 before, 9,801 after (target about 9,720). The overage is `hub.py` at 147
  lines against the plan's guess, mostly the two verbatim prompt briefs and the check functions.
- Split as A1 (fields, `hub.py`, `scenes.py`) → A2 (seam, app, tests, regen) → B (ui).
- Off-plan decisions:
  - `CatalogEntry.kind` defaults to `"one-shot"`: character entries share the type and have no
    kind to give. `SaveOption.kind` is required.
  - `closed_jobs` raises `ValueError("a debrief with no job before it")` rather than indexing
    past the end: the engines' validators refuse that shape, so here it is a bug, not a case.
  - `tests/ui/test_launcher.py` and `tests/twentyfourxx/test_worldsmith.py` gained
    `kind="one-shot"` at their `new_scenario`/`build_scenario` calls; PLAN 1.7 did not name them.
  - The no-arrival-brief test is renamed `..._extends_on_a_lineless_exchange`: it now asserts
    the turn counter moved.
- Reviews: Fable reviewer and an Opus reviewer (no `codex` on the machine). Fixed: raw booleans
  in `check_hub`'s message, the empty-runs guard in `check_hub`, one-letter comprehension names
  in `hub.py`, the stale `extend` docstring, the duplicated `close_segment` tail in `_install`,
  the test name.
- Refuted:
  - Rename `check_packs` to `validate` in the three scene engines: PLAN 2.1 and 3 already rename
    it to `check_game(packs, state)` in each engine's own phase.
  - Move `SHIPPED` into the constants block by inlining `shipped()`: PLAN 1.7 names
    `shipped(engine_id)` as a public helper, and a constant built from it must follow it.
  - Guard `move_on` with `transition_available()`: a row with an intent is offered only when the
    way is open (settled decision 10), the same contract the existing Move on button relies on.
  - Delete the uncalled `hub.py` functions until Phase 2: settled decision 7 writes them here.
- Awaiting the maintainer's call: both reviewers note `job_start(hub, stops)` never reads `hub`.
  PLAN 1.2 and 2.1 name that signature, so it was kept.
- Known and accepted: `uv run aidm` serves the home page; a played turn needs the real CLIs and
  was not smoke-tested in the remote container (the scripted-spawner tests cover the turn).

## Phase 2 — 24XX

- `src` lines: 9,801 before, 9,929 after (target about 9,870, which assumed Phase 1 at 9,720).
  The engine grew 1,450 → 1,578 (target about 1,580; cap 2,000).
- One implementer, as planned. Content: `scenarios/amber-tap` (the hub is the bar itself).
- Off-plan decisions:
  - `TwentyfourxxWorld.jobs()` beside `job_runs()`: four call sites walked
    `closed_jobs(hub, stops())` by hand.
  - `SceneCanon`'s validator calls `check_hub` on a one-run tuple instead of the three checks
    PLAN 2.1 spells out; they are the same checks.
  - The `Jobs done` panel is on every campaign sidebar, empty before the first return (the
    sidebar renders "nothing"); `Board` shows at the hub only.
  - `_with_board(guidance)` joins `BOARD_GUIDANCE` for both the opening and the return.
  - `tests/twentyfourxx/test_worldsmith.py`'s `opening_canon` call gained `kind="one-shot"`.
- Reviews: Fable reviewer and an Opus reviewer (no `codex` on the machine). Fixed: the false
  comment on `SceneDraft.offers`, a double negative in `_scene_unmet`, two `result` locals, the
  duplicated guidance join, the repeated `closed_jobs` walk, the panel list built by `append`, the
  canon validator cut.
- Settled decision 8 changed on the maintainer's call: `HubDraft` no longer re-declares `offers`
  as required and bounded (the pydantic pyright plugin refuses a required override of a defaulted
  field, and `Field(...)` does not help); `_scene_unmet` checks the two-to-three count on every
  hub draft instead. Both reviewers asked for this; PLAN.md 8 and 2.2 now say so. Tunnel Goons'
  `ReturnDraft` keeps the structural bound: it inherits nothing.
- Known and accepted: `uv run aidm` serves the home page (HTTP 200); a played campaign turn needs
  the real CLIs and was not smoke-tested in the remote container.

## Phase 2b — the shape, refined

- Added to the plan after Phase 2 on the maintainer's review of the play: five refinements, made
  once before Phases 3 and 4 copy the shape. `src` lines: 9,929 before, 9,970 after (target about
  9,990). The engine 1,578 → 1,599.
- Decisions the maintainer made here, now in PLAN.md (settled 6, 9, 13 and section 2b): `pitch` is
  the fixer's words and an offer's button plays `TAKE_JOB`; a job's opening scene carries `job`, a
  short paragraph (at least 80 characters), read by the master as `THE JOB`; the worldsmith gets
  one brief per moment (taking, away, returning) and may grow an offer out of the ledger; the
  hub's question is headed `WHAT THIS PLACE IS ABOUT`; the return card reads `Home: ...`; the
  panel is `Jobs`; `BOARD_GUIDANCE` is a range, not a recipe. The field is named `job` because
  "job" is the code word in every engine; an engine's prose keeps its SRD word.
- Off-plan decisions: `JOB_ASK` in `hub.py` is the one copy of "who wants what done, what done
  looks like, what it pays", used by `TAKE_BRIEF` and the bar; `BRIEFS: dict[Moment, str]` is
  module-level; `HUB_BRIEF` is `AWAY_BRIEF`. Every scene that leaves the hub is a job, free text
  included, so `job` is required on all of them (PLAN item 2 now says so).
- Reviews: Fable reviewer and an Opus reviewer. Fixed: the PLAN targets for Phases 3–5 (2b's lines
  carried forward), a tautology in 2b.3, `docs/HUB-SPECS.md`'s stale "Jobs done" and pitch lines,
  settled 13 naming the wrong title for the `Home:` card, `MIN_JOB` 40 → 80, the second Amber
  Tap pitch, and three cuts (`label` in `install_scene`, the inlined `moment`, the module-level
  `BRIEFS`).
- Refuted: fold `WRITE_HUB_SCENE` into `RETURN_BRIEF` as its only user. PLAN 4.3 has Tunnel
  Goons' `_render_return` use `RETURN_BRIEF` bare, so the split gains its second user in Phase 4.
- Known and accepted: `turn/` fixtures did not change; they hold facts, not scenes.

## Phase 3 — Breathless and Loner

- `src` lines: 9,970 before, 10,227 after (target about 10,200). Breathless 1,343 → 1,468,
  Loner 1,407 → 1,539 (target under about 1,560 each).
- Split as planned: A (Breathless) and B (Loner) in parallel, one working tree, both running the
  regen; the orchestrator's final regen moved nothing beyond their own fixtures. Content:
  `scenarios/waystation` (a rail depot turned safe house) and `scenarios/buried-bell` (a
  relic-hunters' guild hall), both played by Kael.
- Off-plan decisions:
  - Loner gets no `BOARD_GUIDANCE`. PLAN 3.2 lists that difference for Breathless only, but the
    constant quotes 24XX's SRD job-finding table and rule 10 says verify against the SRD: Loner's
    prints none.
  - Loner's worldsmith and view tests live in a new `tests/loner3e/test_hub_play.py`; the engine
    had no `test_worldsmith.py` or `test_views.py` to extend.
  - Loner's `install_scene` on a return yields `(*closed, job_closed, opened)`: the conflicts
    closed before the move keep their place ahead of the job card.
- Reviews: Fable reviewer and an Opus reviewer (no `codex` on the machine). Fixed: the
  Waystation hub `question` had a settleable second clause; the single-use `campaign` local in
  both `render_opening`s; `loner3e_test_support.py`'s public function after its private ones;
  one `opening_canon` campaign test per engine (the authoring path had none).
- Decided after the phase, on the maintainer's call: both reviewers note the hub code is now a third
  identical copy across the scene engines (`_scene_unmet`'s hub tail, `render_worldsmith`'s hub
  block, `install_scene`'s `HubDraft` branch, `master_sections`' tail, the two optional panels,
  `at_hub`/`stops`/`job_runs`/`jobs`/`exchanges`, plus `MIN_JOB` and `ONE_SHOT_OPENING`). Kept
  because settled 7 keeps anything bound to an engine's world type in the engine with no type
  parameter, protocol or callback, and `hub.py`/`scenes.py` are outside this phase. The pure
  pieces (the `where` heading expression, `MIN_JOB`, `ONE_SHOT_OPENING`) could move to `hub.py`
  without touching settled 7. The maintainer agreed with the reviewers: PLAN.md Phase 4b moves
  all of it into `hub.py` and `scenes.py` once Tunnel Goons shows what it shares, and settled 7
  now says shared code takes plain values, never a world.
- Known and accepted: `uv run aidm` serves the home page (HTTP 200); a played campaign turn
  needs the real CLIs and was not smoke-tested in the remote container.
