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
