# PROGRESS

One entry per phase of `PLAN.md`: the `src` line counts at start and end, decisions made off-plan,
refuted review findings and why, and what is known and accepted.

## Standing decisions

The two decisions that leave with `PROPOSALS.md`, quoted:

- "A base class where we own every implementation; a `Protocol` only where a test double or a
  foreign object must fit without inheriting."
- "The page polls the service; the service never calls the page."

## Phase 1 — the ground

`src` lines: 9,205 at start (`ae6be39`), 9,249 at end after the fold; the target was about 9,190. Tests: 472 to
475. Every golden under `tests/core/fixtures/` unchanged; `prompts/*`, `schemas/*`, `turn/*`,
`rules.md`, `worldsmith.md`, `master_tools.json`, `scenarios/`, `characters/` byte-identical.

What landed: §1.1 mechanical cleanups, §1.2 `Refusal` and `parse`, §1.3 the boundary test over
four engines and one `kill()` per world, §1.4 verbs, one reading verb, one stem per engine,
`engines/core.py` → `engines/base.py`.

### Decisions made off-plan

1. **`type` aliases, §1.1.1: only the four in `config.py`.** Measured on pydantic 2.13.4: a PEP
   695 `TypeAliasType` field is emitted in JSON schema as `$defs/<Alias>` plus a `$ref`, where an
   assigned alias is inlined. `Slug`, `CheckedEntityId`, `TagKind`, `Ability` and `Boost` sit in
   tool-argument models, so converting them changes `schemas/*/master_tools.json`. "How to work"
   rule 9 (`schemas/*` byte-identical throughout) wins; those five stay assigned aliases.
   `ui/settings.py` reads a `TypeAliasType` through as planned (`_unaliased`).
2. **`opening_canon(draft, source, cast_type)` and `build_scenario(..., cast_type)`.** With
   `revalidate_instances="always"` a bare `SceneCanon(...)` revalidates each `Loner3eSheet` cast
   entry as the unbound `C`'s bound, `Person` (`extra="forbid"` refuses `concept`). The canon is
   parametrized at runtime, `SceneCanon[cast_type]`, as `opening_draft` already parametrizes the
   drafts. PLAN §2.2.5 says `opening_canon(draft, source)` "stays a free function": Phase 2's
   engine method has `self.cast` at hand and should pass it.
3. **`parse` prefixes the error's `loc`** (`item: Field required`) when it is non-empty; PLAN
   §1.2.1 spelled `errors()[0]["msg"]` alone. A refusal that names no field is not actionable by
   the master, and the skip log for a stale save would name none.
4. **`core/io.py::_read_text` maps `UnicodeDecodeError` to `Refusal`**, as `decode` maps
   `JSONDecodeError`: a `ValueError` subclass the old `except ValueError` swallowed would
   otherwise escape the narrowed `except Refusal` and empty the home page for one bad file.
5. **Tunnel Goons `create_character` parses its payload** (`parse(TunnelGoonsPayload, {...})`)
   instead of keyword construction: the ability-sum rule lives in the sheet's validator, so a
   legal-per-pick split that does not sum to 3 raised `ValidationError` past the create page's
   narrowed `except Refusal`. Breathless and 24XX keep keyword construction (§1.1.7): their picks
   are fully checked before the payload is built. Breathless narrows `str` to `Skill` with a
   lookup over `SKILLS` (`_skill`) rather than a cast.
6. **Two extra renames by the same rule:** test support `_opened` → `_open_game`, and the
   test-local `FifthScenarioFile` → `FifthScenario` in `tests/core/test_seam.py`.
7. **`tests/core/test_tool_surface.py`: a second game in flight now crashes the call** rather than
   being routed as a refusal. PLAN §1.2.4 keeps `Runtime.playing` a `ValueError` (a bug, not a
   message), and the narrowed catches no longer turn it into a tool result.
8. Two tests that expected `ValidationError` from a boundary that now parses expect `Refusal`
   (`tests/core/test_integrity_boundaries.py::test_a_save_whose_payload_the_engine_rejects_is_refused`,
   `tests/core/test_decisions.py::test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused`).
   Every other `pytest.raises(ValueError)` stays (§1.2.6).

### Refuted findings and why

- `app/media.py::Illustrator` and `app/speech.py::Reader` dropped `frozen=True` (Opus review):
  PLAN §1.1.10 says so in those words. Refuted by the plan, not by taste.
- Breathless and 24XX should parse their payload like Tunnel Goons (Opus review): Breathless's
  skill steps exclude earlier picks (`tests/breathless/test_create.py::test_skill_steps_exclude_earlier_picks`),
  so `_three_skills` cannot fire on a checked pick; `TwentyfourxxPayload` has no validator.
  Keyword construction stays where no validator can refuse a checked pick.
- `breathless/creation.py::_skill`'s bare `next()` (Opus review): unreachable after
  `check_picks`, which holds the answer to the six skill ids. A message for an impossible state
  is a comment in code.
- `core/model.py`: drop `SerializeAsAny` from `payload` (Opus cut): payload shapes are Phase 3's
  (§3.4); not touched here.
- `deepcopy` in `tunnelgoons/engine.py::new_game` and `scenes/world.py::new_world` (Fable cut):
  left in place; the copy is cheap and the aliasing it prevents is not covered by a test.
- `app/launch.py::read_catalog`: `files.load(slug)` runs outside the skip `try`, so a non-UTF-8
  save file still takes the home page down. Not a regression of this phase (the old code had the
  same shape) and PLAN §2.7.4 restructures `read_catalog`; left for Phase 2.

### Known and accepted

- The line count is 59 over the plan's estimate: one `Refusal` import per raising module and the
  `parse`, `decode`, `_read_text` and `kill` bodies the estimate did not count. Nothing padded,
  nothing invented.
- A `Refusal` raised inside a pydantic validator is wrapped into a `ValidationError` (PLAN §1.2.4
  accepts this); `ask`'s `except ValidationError` still re-prompts a worldsmith whose draft
  builds an unvalidatable canon.
- Reviews: the implementing session had no `Agent` tool and no `codex`, so it ran the
  `/code-review` skill and `.claude/prompts/review.md` itself; the orchestrator then ran two
  independent `reviewer` agents (Fable and Opus) over the staged diff and folded both. Fixed
  from them: `Game.commit` goes through `parse`; `working()`'s docstring; `Ask` → `Spawn` in
  `app/spawn.py`; `ban-relative-imports = "all"` so `TID252` guards single-dot imports too;
  `build_scenario` called with keyword arguments; one test that a `type`-aliased `Literal`
  field is still a dropdown; the now-unreachable relative-import resolver in
  `tests/core/test_package_boundary.py` deleted.
- `uv run aidm` smoke: the home, settings and both game pages (`whispering-vault`, `amber-tap`)
  serve 200 on the staged tree. No tool call was played end to end (no CLI roles here); the
  refusal and crash paths are covered by `tests/core/test_tool_surface.py`.

## Phase 2 — the engine is the class

`src` lines: 9,249 at start (`4cafaae`), 8,690 at end of the implementation and 8,719 after the fold; the target was about 8,720. Tests: 476 to
476 (one user-packs test deleted with the feature, one non-UTF-8 save test added). Goldens:
`prompts/*`, `schemas/*`, `turn/*` byte-identical; `state/tunnelgoons*.json` and
`save/tunnelgoons.json` changed only in key order (`alive` follows `known` on every goon and
npc). `engines/<id>/` sizes: loner3e 676, tunnelgoons 1,327, breathless 635, twentyfourxx 709,
scenes 1,039. Tool counts unchanged (4, 6, 8, 6).

What landed: §2.1 `Thing`, `Person.line`, `Counter` methods, notes as a list, `Engine.tools` a
dict, `schema_text`, `option_of`/`chosen_option`, one `SRD_PACK`; §2.2 `engines/scenes/tools.py`,
`scenes/worldsmith.py` as the bar and the prompt, `SceneEngine` owning the shared arms,
`next_scene`, `master_sections` with `sheet_sections`/`glossary` hooks, the worldsmith flow and
both views, `SceneWorld.begin`/`join_party`/`leave_party`/`party_rows`/`party_panel`,
`Engine.compose`/`close`, the cached `_prompt`; §2.3–§2.5 every scene engine's resolvers and
creation as methods (`tools(packs)`, `Complications`, `Skills`, `Oracle` gone); §2.6 Tunnel
Goons' world methods and engine methods, `creation.py` gone; §2.7 `NarratorView.spoken` and its
two refusals, `Turn.consume`/`_apply`/`finish`, `str | Answer` gone end to end, `read_catalog`
restoring once inside the skip, `Engine.crossing(pursuit)`, `packs_dir` gone.

### Decisions made off-plan

1. **`opening_canon(draft, source, cast_type)` keeps its third parameter** (Phase 1 note 2): it
   stays a free function in `scenes/worldsmith.py`; `SceneEngine.build_scenario` passes
   `self.cast`. Nothing else knows the cast type at that point.
2. **`SceneEngine.write_next(draft, intent, worldsmith)` and `render_next(draft, intent,
   answer)` take the game, not the world.** PLAN §2.2.5 spells `world`, but `self.guidance(...)`
   reads `draft.packs`, which the world does not carry.
3. **`TunnelGoonsWorld.attach(region: Dungeon, start, *, known)`**, not `attach(draft: MapDraft,
   ...)` (§2.6.1): `MapDraft` lives in `worldsmith.py`, which imports `world.py`; naming it
   there would be a cycle. `attach` copies the region's `ways` lists: with `Dungeon.ways` a
   `list[Way]` (§2.1.3), sharing them let the anchor ways land in the draft too.
4. **A private name that gains a foreign caller loses its underscore.** The plan keeps
   `_AUTHORING`, `_take_loot`, `_roll_loot`, `_LEVEL_OPTIONS`, `_place_lines`, `_ways_lines`,
   `_lines` in their modules while the engine imports them; they are `AUTHORING`, `take_loot`,
   `roll_loot`, `LEVEL_OPTIONS`, `place_lines`, `ways_lines`, `lines_of`. `roll_loot` sits in
   `breathless/tools.py` beside `take_loot`, as §2.3.2 places it.
5. **`engines/tunnelgoons/creation.py` deleted**: §2.6.2 makes its three functions engine
   methods and §2.6.3 does not list it among the kept modules; `STARTING_ITEM_LIST` and
   `POINT_OPTIONS` moved to `engine.py`.
6. **`base.pack_options` inlined onto `SceneEngine.pack_options()`**: a one-line function whose
   one real caller was that method, and the only remaining hit of the `packs: Mapping` grep.
7. **`app/spawn.py`: the `Spawn` alias is the one deleted** (§2.7.3 names `Ask`, which Phase 1
   had already renamed to `Spawn`); `ask`'s spawn parameter is spelled inline.
8. **`FileStore.load` reads through `_read_text`**, so a save file that is not UTF-8 reaches
   `read_catalog` as a `Refusal` and is skipped with the log line (Phase 1's open note).
9. **`read_catalog` skips a save whose engine is gone with its own log line** rather than
   raising a `Refusal` to its own `except`.
10. **`Loner3eEngine` narrows through `draft.payload`** where it needs `Loner3eWorld.twist`;
    `SceneEngine.world(state)` returns the bound `SceneWorld[C, P]`.
11. **`Specialty` and `Origin` no longer redeclare `detail`**: as `DecisionOption` subclasses
    they inherit it with its `""` default (basedpyright refuses a required override); the packs
    supply it.
12. **`tests/core/test_tool_surface.py::_SilentEngine.crossing`** returns `None` under a pyright
    ignore: the double is a Loner engine that grows without a crossing, which is the test's point.
13. `NEXT-SPECS.md:133` says `Engine.over` where it said `player_over` (rule 10).

### Refuted findings and why

- `tunnelgoons/views.py::place_lines`/`ways_lines` should be `TunnelGoonsWorld` methods and the
  module deleted (Opus review): PLAN's Phase 2 done-when keeps `tunnelgoons/views.py` as the one
  remaining views module. Left for the plan's own sweep.
- `Loner3eEngine.change_world` should go through `self.world(draft)` (Opus review):
  `apply_change` is typed on `Loner3eWorld` (`loner3e/engine.py:193`), which `self.world`'s
  `SceneWorld[C, P]` is not; the comment on `SceneEngine.world` no longer claims to be the one
  narrowing.
- `attach`'s `start` parameter and moving `MapDraft` into `world.py` (Opus cut): a module move
  the plan does not ask for; left.
- `preview_character` narrowing (both reviews) was a real defect, not refuted: each scene
  engine's `_own(character)` narrows once and the payload is read off the narrowed file.

### Known and accepted

- The line count is 1 under the plan's estimate. Nothing padded, nothing invented.
- `Thing.label` and `Counter.change` compare against the `PLAYER_ID` constant, as §2.1.1 says;
  every engine files the player under it.
- `SceneEngine.__init__` reads `worldsmith.md` once per engine instance (three at start), where
  the module constant read it once at import.
- Reviews: the implementing session had no `Agent` tool and no `codex`; it ran
  `.claude/prompts/review.md` over the staged diff itself (`/tmp/phase-2/review-self.md`) and
  fixed three defects from it (`read_catalog`'s raise-to-catch, `attach`'s aliased lists,
  24XX `preview_character` reading the payload before the type check). The orchestrator then
  ran two independent `reviewer` agents (Fable and Opus) and folded both. Fixed from them:
  `_own` narrowing in the three scene engines' `preview_character`; 24XX `Pack` refuses a
  specialty or origin with no `detail` (a `model_validator`, since basedpyright refuses a
  required override of `DecisionOption.detail`); the 24XX weapon pick refuses instead of a bare
  `next()`; `SceneEngine.crossing` typed `str | None` like its base, so the test double needs
  no pyright ignore; `reload_settings` no longer rebuilds engines that read no setting;
  `FileStore.load` checks `is_file()` once; `roll_loot` reads the player off the draft;
  `NEXT-SPECS.md` says `AUTHORING`; one test that `compose` builds the accepted answer once.
- **Unmet done-when:** PLAN's Phase 2 asks `uv run aidm` to play a turn on every engine, write
  and install a Loner scene, and take and report a Tunnel Goons job. This machine has no CLI
  roles, so only the pages were smoked: `/`, `/settings`, `/create`, `/scenario` and the four
  game pages (`whispering-vault`, `amber-tap`, `buried-bell`, `salt-lantern`) serve 200. The
  turn, the option answer and the crossing are covered by `tests/core/test_pipeline.py`,
  `test_decisions.py` and `test_tool_surface.py`; the live play is still owed.

## Phase 3 — the shapes

`src` lines: 8,719 at start (`15037a2`), 8,493 at the end of the implementation and 8,502 after
the fold; the target was about 8,540. Tests: 477 to 467 (the golden state test and its eight fixtures deleted with the goldens, the three
"board/job with no hub" tests deleted as unrepresentable, the Breathless `_filled_out` and
payload tests deleted with the validator, seven tests added: `Campaign.since_start`, a canon with
jobs walked or opening away from the hub, a sheet short of six skills, a sheet rated off the
creation spread, a preview of a sheet that is not the player's, the player standing at the last
visit, a campaign opening without a board refused). Goldens: `prompts/*`, `schemas/*`,
`turn/*` byte-identical; `state/` and `save/` gone. `engines/<id>/` sizes: loner3e 616,
tunnelgoons 1,256, breathless 607, twentyfourxx 698, scenes 998. Tool counts unchanged.

What landed: §3.1 the goldens trimmed; §3.2 `Campaign` on `engines/hub.py` with every hub helper
as a method, `campaign: Campaign | None` on both canons and both worlds, `Job.closed()`; §3.3
`Loner3eSheet.tags`/`tagged`, `Goon.abilities`; §3.4 `Character[P]` as `id`/`engine`/`payload`,
`Named`, `CharacterHeader.payload`, `read_characters` reading headers, `Engine.check_character`
and the concrete `preview_character`, the four `*Payload` models and `player_*` builders gone,
`Survivor.skills`/`worn` exactly six, `Goon.kit`, `TunnelGoonsWorld.current` off the last visit;
§3.5 `ScenarioMeta.art_style`/`voice`/`with_premise`, `Engine.author(meta, ...)`,
`Runtime.new_scenario(engine_id, meta, ...)`. The eight `scenarios/*/world.json` and the four
`characters/kael/*.json` rewritten by throwaway scripts in `/tmp/phase-3/`.

### Decisions made off-plan

1. **`SerializeAsAny` dropped from `Game.payload`** (Phase 2's deferred item, §3.4): every
   `Game[P]` subclass binds `P` to the exact world it holds, and no caller passes a subclass;
   the suite is green without it and the goldens are unchanged.
2. **`TAG_KINDS` not kept** (§3.3.1 names it): nothing read it — the four sheet rows carry
   their own labels. A constant with no reader is dead code.
3. **`Goon.abilities` values are `Annotated[int, Field(ge=0)]`**: the three fields it replaces
   carried `ge=0`; a rename keeps its constraint.
4. **`TunnelGoonsWorld.walked_job() -> Job | None`** replaces `job_open`: `level_up`,
   `write_extension` and `install_extension` need the walked open job itself, not a bool and
   a second narrowing; every caller reads `walked_job()`.
5. **`Campaign.job_row()` holds the THE JOB row** once, read by both `sections` and `tail`;
   `render_next` passes `campaign.sections(...)` straight into the prompt.
6. **`TunnelGoonsEngine.render_job` and `render_return` take the `Campaign`** after
   `write_extension` narrows it once; §3.2.3 says "read `world.campaign`", and a `None` check
   inside each render would be a second narrowing of the same value.
7. **`core/io.py::_check_filed`** holds the two filing refusals `read_character` and the new
   `read_characters` share.
8. **`tunnelgoons/worldsmith.py::opening_canon`** refuses a campaign draft with no board
   (`Refusal("a campaign's opening needs a board")`) rather than falling through to a one-shot
   canon: `hub_refusal` bars it first, and a bar that is not repeated is a silent fallthrough.
9. **`twentyfourxx/engine.py::starting_items(kits)`** is a module function: it is the one
   piece of `player_operator` that was not a field copy, and `create_character` is its only
   caller. Tunnel Goons' twin is `Goon.starting_items(taken)`: it reads the goon's own `kit`.
11. **`Survivor._rated_spread`** keeps the "three d4, one d6, one d8, one d10" bar the deleted
    `BreathlessPayload` carried: a hand-written `breathless.json` is a file boundary, and
    `skills` is never written in play (`worn` is).
10. **`tests/core/core_test_support.py::the_campaign`** narrows a world's `campaign` once for
    the tests that built it.

### Refuted findings and why

- `write_character` reads `character.payload.name` through `Character[Any]` (self-review):
  the sanctioned bound (CLAUDE.md: `core` knows no world shape; `Named` is the header's view
  of the sheet).
- The self-review's refutation of a bar in `opening_canon` was overturned by the Fable review
  (decision 8).

### Known and accepted

- The line count is 47 under the plan's estimate. Nothing padded, nothing invented.
- `Goon.kit` rides in every save as a record of the start (PLAN §3.4.6 says so).
- A save or a character file from before this commit is stale and is skipped with a warning;
  no migration (CLAUDE.md).
- The done-when grep `\.hub\b` still matches the `from aidm.engines.hub import` lines and
  `place_unmet`'s `hub` parameter; no field named `hub` remains.
- Reviews: the implementing session had no `Agent` tool and no `codex`; it ran
  `.claude/prompts/review.md` over the staged diff itself (`/tmp/phase-3/review-self.md`) and
  fixed four of its six findings (decisions 2 and 4, a comment on `install`'s guard,
  `check_kind`'s message). The orchestrator then ran two independent `reviewer` agents (Fable
  and Opus) and folded both. Fixed from them: the Loner worldsmith guidance says `tags` by
  kind; `read_characters` takes a `Collection`; `opening_canon` refuses (decision 8);
  `Goon.starting_items` (decision 9); `Campaign.job_row` (decision 5); `job_open` deleted
  (decision 4); `read_characters` binds the file and the name once; `Survivor._rated_spread`
  (decision 11); the report-in guard binds `walked_job()` once; `SceneEngine.hub_rows` inlined
  into `render_next`.
- **Unmet done-when:** PLAN's Phase 3 asks `uv run aidm` to create and preview a character in
  every engine, take, play and close a campaign job, and skip a pre-phase save with a warning.
  This machine has no CLI roles, so only the pages were smoked: `/`, `/settings`, `/create`,
  `/scenario` and the eight game pages serve 200 on the staged tree. The create path is covered
  by `tests/*/test_create.py`, the job cycle by `test_hub_play.py`, the `*_worldsmith.py` tests
  and `tests/core/test_hub.py`, the stale save by `tests/ui/test_launcher.py`; the live play is
  still owed.

## Phase 4 — the chores

`src` lines: 8,502 at start (`1f99a82`), 8,568 at the end of the implementation and 8,580 after
the fold; the target was 8,520 to 8,600. Tests: 467 to 468 (the two crossing tests moved into
`test_turn.py`; one test added for the composer's opening rule, `_can_type`). Goldens: `prompts/*`, `schemas/*`, `turn/*` byte-identical; `scenarios/` and
`characters/` untouched. `engines/<id>/` sizes: loner3e 622, tunnelgoons 1,268, breathless 607,
twentyfourxx 698, scenes 1,023 (the sweep's longer names wrapped a few lines). Tool counts
unchanged.

What landed: §4.1 `GamePage` with seven `@ui.refreshable_method` panels and a `refresh()`, the
composer's four widgets set from one `player_view()` per poll (no `bind_*_from`), `LaunchForm`,
`CharacterForm`, `ScenarioForm`, `SettingsForm`, `scene_sidebar` and `journal_panel` plain
functions; §4.2 `tests/support/` (`table`, `loner`, `golden`, `golden_turn`, `breathless`,
`twentyfourxx`, `tunnelgoons`, `ui`), `pythonpath`/`extraPaths` on `tests`, the six seed hunts
pinned, `test_turn.py`/`test_master_tools.py`/`test_game_service.py`, the crossing tests in
`test_turn.py`, 103 `pytest.raises(Refusal)` where the source refuses; §4.3 the sweep over
`src` and `tests`, `Frozen`'s docstring states the contract.

### Decisions made off-plan

1. **`LaunchForm` is built only over a non-empty catalog**: its `scenario_id` is the first
   scenario, so `home_page` shows "No playable scenario was found." itself and builds the form
   otherwise; §4.1.1 placed that refusal inside the form.
2. **The seed hunt at `test_loner3e_engine.py:160` pins two seeds, not one**: that loop asserted
   the luck moved off whichever side lost for every seed; seed 0 (a 4-4 tie, the foe loses) and
   seed 1 (2 against 5, the player loses) keep both sides covered. The other five pin seed 0.
3. **`open_table` replaces `_open_game`** in `tests/support/table.py`: `support/loner.py`'s
   `open_game` calls it across modules (Phase 2 decision 4).
4. **`pytest.raises(ValueError)` stays where the raise is pydantic's** (a `ValidationError`
   wrapping a validator's `Refusal`, or a plain `ValueError` such as `Runtime.playing`,
   `storage_slug`, `Settings`' key check, `MasterTool`'s description check): 29 remain. Decided by
   running the suite with every raise read as `Refusal` and reverting the ones that failed.
5. **`GamePage.restart` runs `poll_turn()`** instead of setting `seen` and refreshing by hand,
   so the composer is set on the same path as every other change.
6. **The sweep's nouns**: `entity`/`entity_id`/`member`/`entry` in the scene worlds,
   `sheet` for a Loner resolver's subject, `draft` for a worldsmith draft where no game draft
   is in scope and `scene`/`extension`/`answer` where one is, `session` for a spawn session,
   `filed` for what a file or the cast already holds, `delta` for a counter move.
7. **`tunnelgoons/views.py::place_lines`/`ways_lines`** (the Phase 2 refuted item) stay free
   functions: no Phase 4 step touches that module beyond the sweep.
8. **The empty-catalog refusal keeps its card**: `home_page` opens the "New or current game"
   card around both branches and `LaunchForm.build` is gone (decision 1 had dropped the card).
9. **`GamePage._run` greys the composer before the play and re-sets it in a `finally`**, so a
   second Enter inside the poll window has nothing to hit and a refused play re-enables.
10. **`_observed` also samples `engine.ready(state)` and `player_view().over`**: a silent
    region install commits without an exchange, and the composer reads both.
11. **`_can_type(player, phase)` and `_placeholder(player, phase)` are module functions** read
    by `_set_composer`, so the opening rule has a test seam (`tests/ui/test_game.py`).
12. **`SettingsForm(settings, apply, boxes)`** takes its box map, as the brief spelled; the tests
    pass theirs in.

### Refuted findings and why

- Self-review: `open_game_for` passes an engine `open_table` would resolve itself — a shape moved
  verbatim from `core_test_support.py`; no phase step covers it. Left.

### Known and accepted

- The line count is 66 over Phase 3: the four page classes' `__init__`s and `self.` prefixes,
  and the sweep's longer names wrapping lines. Nothing padded, nothing invented.
- `GamePage.box`, `send`, `move_on_button`, `over_label` are annotated without a value and set
  by `composer`, which `build` always calls; no `| None`.
- The composer is set once per observed change (`phase`, facts landed, exchanges filed) rather
  than on NiceGUI's 0.1 s binding poll; `_run` polls once more when a play returns, so the
  composer re-enables within a second of the turn.
- `uv run aidm` exits with an anyio "cancel scope" traceback on SIGTERM from the MCP session
  manager's `AsyncExitStack`; measured on `1f99a82` too, so not this phase's.
- Reviews: the implementing session had no `Agent` tool and no `codex`; it ran
  `.claude/prompts/review.md` over the staged diff itself (`/tmp/phase-4/review-self.md`) and
  fixed five of its seven findings (decision 5, the `extension` and `answer` names, the
  `opening` local). The orchestrator then ran two independent `reviewer` agents (Fable and
  Opus) and folded both: decisions 8 to 12 above; the `npc`/`way` comprehension names that
  shadowed a live binding in `tunnelgoons/world.py`; the duel tie asserted explicitly in
  `test_a_tie_ticks_the_twist_only_outside_a_conflict`; `tests/support/ui.py` reads
  `REPOSITORY_ROOT`/`SCENARIOS` off `support.table`; the unused `shipped()`/`SHIPPED` deleted;
  `open_game_for` lets `open_table` resolve the engine; `GamePage.transcript` no longer
  optional; the placeholder ladder reads the same `player`/`phase` as `_can_type`.
- **Unmet done-when:** PLAN's Phase 4 asks `uv run aidm` to show two tabs on one game each
  refreshing their own panels, the composer enabling and disabling within a second of the turn,
  and the launcher, create and settings pages behaving as before. This machine has no CLI roles,
  so only the pages were smoked: `/`, `/settings`, `/create`, `/scenario` and the eight game
  pages serve 200 on the staged tree. Per-tab refresh rests on `refreshable_method` refreshing
  only the instance's targets; the composer's state on `_set_composer` from `poll_turn` and
  `_run`; the live play is still owed.
