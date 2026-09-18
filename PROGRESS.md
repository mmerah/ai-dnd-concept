# PROGRESS

One entry per phase of `PLAN.md`: the four line counts at its start and its end, the decisions
taken off-plan, the review findings refuted and why, and what is known and accepted.

## Phase 1: engines and packs

Counts, start → end: `src` 10,904 → 10,510 (target about 10,510); `tests` 12,403 → 12,365
(target about 12,263: the plan's count did not include the six tests the reviews asked for or
the boundary tests the parts added); `qa` 2,005 → 2,005; `scripts` 390 → 390; 795 → 781 tests
collected. One golden moved: `tests/core/fixtures/prompts/tunnelgoons/worldsmith.txt`.

Decisions off-plan:

- All three parts were implemented by opus, not sonnet: each touched ten or more source files
  with generic-typing and strict-pydantic subtleties.
- `Engine.pack_ids` is gone; `select_packs` prepends the SRD itself (one caller, no override).
- The pack `select` runs once, in `Engine.admit`, for both families; `SceneEngine.author` no
  longer selects on its own, and `RoomEngine.author` is covered too. `restore` keeps its own.
- `packs` is a distinct tuple at every file boundary: `core/model.py` `Packs` carries
  `check_unique`, which `PackSelection` used to carry.
- `RoomWorld.require_dweller` / `require_prop` resolve a dweller and a prop; `RoomEngine.
  meanwhile` and `require_member_here` call them, so the refusal texts have one home.
- `Engine.edited` refuses a `name`, `source` or `license` box.
- The scenario page's pack select is written back from `self.packs` when a choice is refused.
- The refusal order of `meanwhile` changed: the destination is resolved before the "stands with
  the player" / "is here with the player" checks. No test pinned the old order.

Refuted review findings:

- "`check_addable` should scan the rebuilt pack against every installed pack": 44 ids are
  shared across the shipped Loner packs, so that scan would refuse most written packs. Only a
  selection combines packs, and `select` refuses the overlap at `begin` and `restore`.
- "Inline `BOX_ROWS`": it sits beside `MONOSPACE`, a single-use constant of the same kind.

Known and accepted: an in-play game whose written pack is later edited into an id collision
with the other supplement in play is refused at the next `restore`, not mid-turn (before this
phase it failed on the next tool call).

## Phase 2: names and homes

Counts, start → end: `src` 10,510 → 10,483 (target about 10,505; the `RoleRunner` fold and
the `run_cli` log line took more than the plan measured); `tests` 12,365 → 12,387 (target about
12,378: one test added for the single log line); `qa` 2,005 → 2,004; `scripts` 390 → 390;
781 → 782 tests collected. Three goldens moved: `tests/core/fixtures/schemas/*/master_tools.json`.

Decisions off-plan:

- All four parts were implemented by opus, as in phase 1. Parts A1 (engine constants) and A2
  (app roles) ran in parallel on disjoint files; B1 (renames) and B2 (methods and rules) ran
  after them, one after the other.
- `RoleRunner.run` holds the provider `match` inside its one `timeout`; there is no
  `_answered`. `run_cli` still returns a `RunResult`; `run_builtin` returns `(text, rounds)`
  and the log detail ("cold", "resumed", "over N rounds") is phrased in `run` alone.
- `Thing.headline` keeps its own one-line format instead of reading `self.subject().headline`:
  the new property rule reads the object's own fields, and building a `Subject` per read is not
  that.
- `Pack.summary()` is a method: it joins the counts.
- `SceneWorld.offer()` returns `[WAY_OFFERED]` and `scenes/world.py` imports it from
  `scenes/tools.py`: a world method changes fields and writes the facts.
- The four tests of `ask` moved from `tests/app/test_spawn.py` to `tests/app/test_roles.py`
  with the function.
- `docs/24XX.md` and `qa/README.md` follow the `defend_with_id` / `item_ids` renames.
- `ui/game.py` reads no `Exchange.transcript`: its `transcript` is a NiceGUI scroll area.

Refuted review findings:

- "`ALREADY_BROKEN` / `BREAKS_HARMLESSLY` are model-facing constants in a `world.py`": they are
  refusal templates raised by world methods and sit beside their raise sites, as `UNKNOWN_ID`
  and `IS_DEAD` do in `engines/base.py`; `tools.py` is for what the master reads as an
  instruction. Known and accepted as the phase's exception beside the `*_UNWRITTEN` facts.
- "`TOLD` in `loner3e/world.py` is model-facing": it is the SRD's oracle answer table, read by
  the player on the roll card as much as by the master, and `loner3e/tools.py` imports
  `loner3e/world.py`, so moving it would make a cycle.
- "The `SceneProposal` field descriptions live in `scenes/world.py`": a description is the
  model's schema, not a module constant, and `scenes/worldsmith.py` imports `SceneWorld`, so
  the proposals cannot sit beside `check_scene`; `rooms/world.py` keeps `MapProposal` the same
  way, as the plan decided.
- "Rename `author_pack`'s `source` parameter to `document`": `source` is the source material in
  `Engine.author`, `render_worldsmith`, `Game.source` and `Scenario.source`; only the pack
  file's provenance field is spelled `source` on disk, and in code that is `origin` everywhere
  now.

Known and accepted: `Driver.secrets` stays a protocol property (a one-line read of a field).

## Phase 3: app, UI and tests

Counts, start → end: `src` 10,483 → 10,506 (target about 10,508); `tests` 12,387 → 12,065
(target about 11,990: three `test_roles.py` tests came back, see below, and the UI fixtures took
fewer lines out than the plan measured); `qa` 2,004 → 2,004; `scripts` 390 → 0; `tests/fixtures`
420 → 0; 782 → 762 tests collected. No golden moved.

Decisions off-plan:

- Four parts, all opus: A (app) and C1 (goldens-pinned deletions, `test_spawn`/`test_config`,
  the converter) ran in parallel on disjoint files; B (UI) then C2 (UI fixtures, launcher
  parametrization, support) followed.
- `Runtime` is a plain class with `__init__(settings, spawner=None)` and a `spawner` attribute,
  not a dataclass with an `InitVar` and a stored `roles`: the `InitVar` left `Runtime.spawner`
  as a class attribute equal to `None`, and `roles` already means role configuration
  (`Settings.roles`, `aidm.app.roles`).
- `_save_option` calls `check_drift` directly; `check_resumes` has one caller,
  `Runtime._resumed`, since the catalog builds its target from the save's own ids.
- `ui/app.py` exposes `mount(runtime)`, not `register_pages`: it also mounts the MCP endpoint,
  the dice sound and the lifespan hooks. The route table is a local of `mount`.
- `CreationStep.offers(answer)` is the one legality rule read by `check_picks` and `drop_stale`.
- `Engine.seeds` is a one-line pass-through, kept so `ui/` reads no `engine.packs`.
- `ui/settings.py` shows a field's `description` as the widget's hint through `_widget`, over a
  private `_box` that builds the widget; `_label` has no field to read.
- The three `test_roles.py` tests PLAN step 7 deleted are back, unchanged: the prompt goldens
  mask everything after `ANSWER WITH:` and the one interjection golden renders an empty sheet, so
  nothing else pinned which schema each render asks for or the non-empty companion sheet.
- The restart-refusal toast test stays its own test: it needs a held master spawn and a live
  `play` task, which the `_run` parametrization has no branch for.
- `tests/ui/test_app.py` and `test_create.py` moved onto the `page`/`notified` fixtures too.
- `qa/agents.py` read `runtime.turn` after `Gate` landed; basedpyright does not include `qa/`,
  and the QA harness (`qa/run_all.sh`) found it. What it still reports, the two loner findings
  ("unwritten card missing", "speaker name missing on the bubble") and the `create` scenario's
  timeout on a scenario written from an upload (the scripted worldsmith reads an empty schema
  section), reproduces identically on the phase 2 commit and is outside this phase.

Refuted review findings:

- "`Look` is a one-field wrapper; read `look.json` as a bare `Mapping` through a `TypeAdapter`":
  `look.json` is a file boundary and the rule is a strict model at each boundary; `read_model`
  reads models. The plan decided `Look.palette`; the reviewer offered the cut only if re-opened.

Known and accepted: the QA harness is the only check that covers `qa/agents.py` against the
runtime's surface; the plan's `src` target counted the `Gate`/`Busy` structure at about +17 and
it came to +13 with the plain `Runtime`.
