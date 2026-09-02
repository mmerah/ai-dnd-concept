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
  without touching settled 7. The maintainer agreed with the reviewers: PLAN.md Phase 3b, before
  Tunnel Goons, moves all of it into a `SceneWorld` base class in `scenes.py` and world-free
  functions in `hub.py`; settled 7 now allows exactly that base class.
- Direction check after the phase (a Fable reviewer, ignoring every settled decision; report in
  the session's `/tmp/phase-3/direction.md`, outcomes in PLAN.md). Adopted, into Phase 3b: the
  base class before Phase 4; structural drafts (`SceneDraft`, `JobDraft`, `HubDraft`,
  `ReturnDraft`) in place of the bar's mode flags; debrief hygiene (hidden names checked, the
  card not re-told, second person, hub questions as standing pressure, one duplicate secret);
  the small cuts. Adopted with a change: job completion is the game master's verdict
  (`next_scene` with `job_done`; Tunnel Goons' `level_up`), not the worldsmith's guess and not
  the player's button, since the master holds the job's history. Adopted into Phase 4: the job
  stamp on visits (a stroll into an old dungeon opens no job), the debrief on the current tavern
  visit. Refused by the maintainer: buttons that skip the master turn to halve the spawns;
  latency has not been the problem, and the fixer's reply and one consistent turn shape are
  worth more. Also refused: a code-written debrief for Tunnel Goons (code would write
  player-facing prose).
- Known and accepted: `uv run aidm` serves the home page (HTTP 200); a played campaign turn
  needs the real CLIs and was not smoke-tested in the remote container.

## Phase 3b — the shared hub code, once

- `src` lines: 10,227 before, 10,115 after (target about 10,100). 24XX 1,599 → 1,460,
  Breathless 1,468 → 1,341, Loner 1,539 → 1,418; `hub.py` 171 → 216,
  `scenes.py` 164 → 385. (PLAN's 24XX baseline of 1,578 was stale; the tree held 1,599.)
- Split as A (opus: all of `src/`, content, regen) then B (sonnet: tests). Reviews: Fable reviewer
  and an Opus reviewer (no `codex` on the machine), both told to hunt for cuts on the maintainer's
  request.
- Off-plan decisions:
  - `SceneWorld.job_done` and `SceneWorld.job` properties: PLAN 3b.3 and 3b.5 wrote both walks
    inline, three times each.
  - `opening_canon(draft, source)` loses `kind`: a `HubDraft` is the campaign; `check_kind` in
    `check_game` still refuses a mismatch through the runtime's refusal.
  - `render_worldsmith(world, intent, guidance, answer)` takes the draft type `write_next`
    picked and derives `returning` from it.
  - The fixture regen reorders the world's keys in `state/` and `save/` (the base class's fields
    come first). A consequence of settled 7.
  - There are no worldsmith prompt or schema fixtures (PLAN 3b.7 expected some to lose `job` and
    `offers`); the one-shot schema was checked by hand instead.
- Folded from the reviews, beyond PLAN 3b.1–3b.2, all taking `SceneWorld` or plain values
  (settled 7): `worldsmith_prompt`, `hub_rows`, `settle` + `NEXT_SCENE`, `record_exchange`
  (`spent_note` and `scene_spent` folded in), `cast_unmet`, `hub_unmet`, `trail_panel`,
  `scene_rows(world)`, `MIN_SITUATION` in `scenes.py`, `last_seen` returning the prompt's own
  line; `check_hub` refuses `job_done` where no job is open. Cut from `hub.py`: `Moment`,
  `BRIEFS`, `JOB_ASK` (its second user, the bar, is structural now; both reverse Phase 2b
  off-plan decisions), `open_job` (no caller; Phase 4 stamps `Visit.job` instead), `jobs_rows`
  (inlined into `jobs_panel`), `stops_of`. `hub_sections`' `finished` is a required keyword.
- Decided against PLAN's letter, awaiting the maintainer's call: the `job_done` sentence PLAN 3b.4
  adds to `next_scene`'s tool description lives on the `NextScene.job_done` field description
  only, since the schema printed it twice; `master_tools.json` carries it once.
- Refuted from the fold: merging "Write the hub scene there." into `RETURN_BRIEF` (Phase 2b's
  refutation stands: PLAN 4.3 uses `RETURN_BRIEF` bare). `WRITE_HUB_SCENE` stays.
- Known and accepted: `uv run aidm` serves the home page (HTTP 200); a played campaign turn needs
  the real CLIs and was not smoke-tested in the remote container.

## Phase 4 — Tunnel Goons

- `src` lines: 10,115 before, 10,341 after (target about 10,250). The engine 1,285 → 1,511 (target
  about 1,420; cap 2,000). The overage is `worldsmith.py` (224 → 355): the return and job prompts,
  `ReturnDraft`, the three bars and the three-branch `install_extension` PLAN 4.3 names. `told_tail`
  moved to `core.py` (a wash).
- Split as A (sonnet: source, content, docs, regen) then B (sonnet: tests). Content:
  `scenarios/salt-lantern` (the tavern is the hub; Kael plays it). No new tool; `tools()` returns six.
- Off-plan decisions:
  - `REPORT_IN` and `REPORT_ROW` live in `views.py`, not `worldsmith.py`: `worldsmith.py` imports
    `views.py` for `entity_line`, and `views.py` needs the row.
  - "A job is open" means a walked job: `job_open(hub, stops)` in `world.py` is true only when a
    visit since `job_start` carries a job away from the hub. PLAN 4.3 and 4.4 read `visits[-1].job`;
    both reviewers showed that "Report in" pressed right after a take, before leaving, then failed
    after the worldsmith call ("a debrief with no job before it"). `REPORT_ROW`, the `REPORT_IN`
    guard, `level_up`'s verdict and `check_hub`'s "a job done with no job open" all read `job_open`.
  - A job write at the tavern with a walked job open is refused before any prompt ("report the open
    job first"): a typed intent there would re-stamp the visit and the second job would never reach
    the ledger. PLAN 4.4 relied on the sidebar alone.
  - The world validator does not require `visits[0]` to carry no job, nor a debriefed visit to carry
    one (PLAN 4.2's letter): the first take stamps `visits[0].job` where the player stands, and a
    report clears the job on the visit it debriefs. It holds `visits[0]` at the hub with no debrief,
    debriefs at the hub only, `job_done` only with a job open, and `closed_jobs` walking clean.
  - `TunnelWorld.jobs()` and `job_visits()` beside `stops()` (four and two call sites);
    `check_hub(hub, board, stops, job_done)` takes the stops the world already builds.
  - `attach` runs no bar; `write_extension` and `install_extension` each refuse first.
  - `opening_canon(draft, source, kind)` gains `kind`: the hub is the start only for a campaign.
  - `tests/tunnelgoons/test_worldsmith.py`'s renamed calls (`attach`, `way_open`,
    `extension_refusal`) were updated in part A so the suite stayed green between parts.
- Reviews: Fable reviewer and an Opus reviewer (no `codex` on the machine), both told to hunt for
  cuts. Fixed: the walked-job predicate (both), the re-stamp refusal (Opus), the three closures in
  `write_extension` and the unreachable `ReturnDraft` isinstance (both), `_start_unmet` shared by the
  map and tavern bars (both), `stops_of` deleted (both), `hub_world(with_map=...)` and `_kael(place)`
  in the test support, the `RETURN` constant, two stale test names (Opus).
- Refuted: dropping the second bar run inside `install_extension` because `write_extension`'s
  refusal already ran (Fable cut). `install` is a public `Transition` seam called by the runtime and
  directly by tests with drafts that never passed `write`, and the pre-phase `install_extension` ran
  the same bar through `apply_extension`; the check is pure and keeps `attach` safe for any caller.
- Awaiting the maintainer's call: the walked-job predicate and the re-stamp refusal change PLAN
  4.3/4.4's letter (`visits[-1].job`); both are recorded above and in the tests.
- Known and accepted: `uv run aidm` serves the home page (HTTP 200) listing The Salt Lantern with
  the campaign badge; a played campaign turn needs the real CLIs and was not smoke-tested in the
  remote container. The tests cover the take, the walk, the report and the verdict.
