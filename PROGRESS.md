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
