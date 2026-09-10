# PROGRESS

One entry per PLAN.md phase: `src` line counts before and after
(`find src -name '*.py' | xargs cat | wc -l`), decisions taken off-plan, refuted review findings
and why, anything known and accepted. Phases 1–3 landed in one commit, in one run.

## Phase 1 — CI and the toolchain

- `src` 10,162 → 10,162. `qa` 2,378 → 2,431 (annotations and three `TypedDict`s). `tests` unchanged.
- Off-plan: Playwright pinned to 1.56.0, the release whose bundled Chromium is build 1194, which
  `qa/drive.py` `CHROMIUM` points at; PLAN said "the version `/tmp/pw` installs today" and that venv
  did not exist on the machine that ran the phase. `actions/checkout@v5`, `astral-sh/setup-uv@v7`.
  CI syncs with `--locked` so a stale `uv.lock` fails the gate (review finding).
- Off-plan: `qa/run_all.sh` no longer honours `QA_PW`; the project venv is the one interpreter
  (review finding: an override nobody documents is config for a fixed value).
- Off-plan: `qa/drive.py` `log()` restores the call triples JSON flattened to lists, so `Spoken.calls`
  is the shape the scenarios index (review finding).
- The checker surfaced two live bugs in `qa/` and they were fixed in passing: `s_loner.py` compared
  a placeholder against a bare string constant (always true); `s_mcp.py` passed a list to a `bool`
  check.
- Known and accepted: with that `s_loner.py` check now live, the reload-mid-turn step races the
  scripted roles (the turn is over before the page reloads) and reports one issue; the game itself
  is fine after the reload. The scenario, not the app, needs a longer stall. `goons` runs clean.

## Phase 2 — The gate, the kernel and the room family

- `src` 10,162 → 10,116 (target about -60; the kernel split moved lines more than it deleted them).
  Tests 564 → 565 (one for `RoomEngine.advance`'s operation guard; one deleted with the
  unreachable `_apply` refusal, Decision 12).
- Off-plan: `worldsmith.md` and `rules.md` paths are module-level `Path` constants
  (`WORLDSMITH_PROMPT`, `RULES_PROMPT`) read through `read_prompt` at call time; the text constants
  `WORLDSMITH`/`SCENE_RULES` are gone as PLAN said. No module reads a file at import.
- Off-plan: `tests/core/test_builtin.py`'s `_Tools` stub holds a real loner3e state and delegates
  to `CHANGE_WORLD.call`, so its `change_tags` payload now carries `kind`/`gained`.
- Off-plan (review, maintainer's call): `Engine.family_rules` is abstract and appended
  unconditionally, not the concrete empty default PLAN step 10 wrote: both families override it
  with a file, so the default and its guard were dead. Decision 2's counts moved to 13 abstract
  and 18 concrete.
- Known and accepted: the room-family rules block lands at the end of `THE RULES OF THIS GAME:` in
  every TunnelGoons master prompt (golden `tests/core/fixtures/prompts/tunnelgoons/master.txt`,
  +9 lines); `tests/core/fixtures/schemas/` is byte-identical under the generic `ChangeWorld[C]`.

## Phase 3 — One vocabulary

- `src` 10,116 → 10,114 (target about -20; the renames were one-for-one and `Subject.row()` paid
  for `Action`). No golden moved.
- Off-plan: the row builder is `Subject.row()`, not `Thing.row()` as PLAN wrote: `here_panel` takes
  `Subject`s, and `Thing` reaches it through `subject()`. It also replaced the third hand-built
  `PanelRow` in the room engine's `Carrying` panel (review finding).
- Off-plan: `render_master`'s `engine_sections` is typed `Pairs` (review finding: a fourth spelling
  of the collapsed alias).
- `CLAUDE.md` carries the law under `## Code`.

## Phase 4 — Facts without kinds

- `src` 10,112 → 10,095 (target about -12). Tests 565 → 565: no test lost its feature; the
  `kind`-only assertions went, the tests around them kept their behaviour half. The four turn
  goldens moved by exactly the 21 removed `"kind"` keys.
- Off-plan: PLAN named five tests whose "only assertion was a kind" as going whole
  (`tunnelgoons/test_tools.py`, `breathless/test_tools.py`, `core/test_dice.py`); each carried a
  real assertion beside the kind line, so only the kind line went. Where a test picked one fact
  out of a list by its kind, it now picks by the property it asserts (`fact.dice`, a trace
  prefix) or by the constant (`WAY_UNWRITTEN`), never by position (review finding).
- Known and accepted: the comment above loner's `if not ended:` went with the flag; the bool says
  what the comment said.

## Phase 5 — The service's seams

- `src` 10,095 → 10,155 (target about +30; the palettes moved onto four engines, +35 of it, and
  the two accessor tests' stubs pay for the rest). `app/runtime.py` 511 → 449 (target about 440).
  Tests 565 → 574.
- Off-plan (review, measured): `self._retain(self._speaking)` stays in `_turn`. PLAN step 9 called
  it redundant and, in the same step, relied on `_background` holding the interjection task so the
  golden turn test's second narrator prompt comes from awaiting it; `drain()` gathers
  `_background`, so dropping the line fails `test_golden_turn` for 24XX. The two tests PLAN
  pointed at `_speaking` moved anyway.
- Off-plan: `_declarations` stays a module helper in `ui/theme.py`; after `_engine_block` was
  inlined it has two call sites in `_palette_css` (root and each engine block), which meets the
  bar. `seed` carries no docstring.
- Off-plan: `GameService.spawner` became `roles: Roles`; the three tests that swapped a wrapped
  spawner in now swap `Roles(wrapper, engine)`. `RoleSpawner` moved to `app/roles.py` beside it.
  `Roles.interject` returns `(spoken lines, proposal)` so the caller keeps the policy and
  `Engine.close` gets `SpokenLine`s without a second view.
- Refuted: "make `worldsmith()` a module function so `new_scenario` need not build a `Roles`" —
  PLAN step 12 names `new_scenario` as `Roles`'s second user by design.
- Known and accepted: the `uv run aidm` smoke here fetched home, the four game routes and
  settings over HTTP (all 200, no log errors); the drawn game page renders only after the socket
  connects, so the tick path is proved by the counting test, not the smoke.

## Phase 6 — Coverage, the sheeted base and hiring

- `src` 10,155 → 10,193 (target about -30: **missed by about 70**, PLAN rule 5 says so). Tests
  574 → 575, plus the two playthroughs and the hire-then-succession test (about +150 lines under
  `tests/`). Where it went: `Sheeted`/`ItemSheet`/`SheetedWorld` paid as PLAN said
  (`breathless/world.py` -38, `twentyfourxx/world.py` -39 against 51 new); the `Hiring` extraction
  did not come out "about zero": what left `base.py` (-29) and `seam.py` (-17) reappears in
  `hiring.py`, and each engine's 20-29 line HIRE block became 18-25 lines of typed hooks
  (`hireable`, `hire_prompt`, `install_sheet`, `hire_bar`), so the module's own `advance`,
  `_sign_on`, `check_request`, `unwritten`, the abstract declarations and imports are the net
  cost. Not padded and not golfed; the maintainer's call whether the one hire flow is worth it.
- Off-plan (Decision, brief-sanctioned): `SheetedWorld[C: Sheeted[Any], P: Sheeted[Any]]` spells
  the bound with `Any`, exactly as `G: Game[Any]` does and for the same reason: `Sheeted[S]` is
  invariant (`sheet` is a mutable field), so `Sheeted[BaseModel]` rejects `Survivor`, and a
  read-only `Protocol` bound cannot satisfy `SceneWorld`'s nominal `C: Person`. Both spellings
  were tried under basedpyright and failed.
- Off-plan: `ACTOR` moved from `engines/base.py` to `engines/hiring.py` with the rest of the
  hiring text ("a hired party member here who acts"); the three hiring engines' `tools.py` import
  it from there. Awaiting the maintainer's call (review finding: it describes `actor_id` on
  every roll tool, so it could stay in `base.py`).
- Refuted: "drop the `hireable` hook and call `world.require_hireable` from the mixin" — the base
  `World` no longer has `require_hireable` (its default body was dead, PLAN step 5) and TunnelGoons
  hires an `Npc` while its `P` is `Goon`, so the hook is the typed seam PLAN wrote.
- Refuted: "delete `return None` from `Engine.check_request`" — ruff B027 flags an empty method
  on an ABC; the line carries the reason.
- Known and accepted: `SheetedWorld` lives in `engines/hiring.py` beside `Sheeted` (PLAN step 5
  lists both as the mixin module's), so `tunnelgoons/engine.py` imports `scenes/world.py`
  transitively; no cycle, and the boundary test holds. A separate `engines/sheeted.py` would undo
  that at the cost of splitting the trio.
- `stub_worldsmith(answer)` lives in `tests/support/table.py`; the three per-file copies are gone.
