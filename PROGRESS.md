# PROGRESS

One entry per commit. Line counts are `find <dir> -name '*.py' | xargs cat | wc -l`.

## Phase 1: names and spelling

| dir   | before | after |
| ----- | ------ | ----- |
| src   | 9,827  | 9,817 |
| tests | 9,146  | 9,132 |
| qa    | 1,786  | 1,788 |

Full check green; app smoke green (home, settings, create and scenario pages serve). Reviewed by
two adversarial readers (Fable and Opus; no Codex on the machine).

### Decisions off-plan

- Step 6, `type TagKind` / `type Ability` / `type Boost` / `type AbilityScores`: done, with one
  change under it. Pydantic publishes a PEP 695 `type` alias as a `$defs` entry and a `$ref`, which
  `_collapse_nullable` cannot fold, so `LevelUp.ability` would have read as an `anyOf`. `schema_of`
  now inlines `$defs` before normalizing (`_inline_refs`, one test): every schema is one tree, no
  class name reaches a prompt, `T | None` folds everywhere. Every schema and prompt golden with
  a `$ref` in it changed accordingly (`Die`, `Skill`, `SkillDie`, `Chattiness`, `Line` and the
  cast classes inlined); the master tool schemas for loner3e and tunnelgoons are byte-identical
  to the pre-phase ones.
- Step 3, `Engine.answer` returns the tuple the tool call builds; only `SceneEngine.leaving` and
  `depart` moved to lists. A list there was re-tupled by `Turn._consume` in the same expression.
- Step 8, `_save_option` takes `store: FileStore`, not `raw`: the read's own refusal (a save that
  is not UTF-8) is still skipped with a warning, as the loop did.
- Step 8, `theme.install()`: `qa/server.py` is a second entry point that mirrors `start()`, so it
  calls `install()` before `ui.run` too (review finding).
- Step 1, `GameService.engine_title` / `engine_id` deleted: `ui/game.py` now reads
  `session.engine.title` and `session.engine.id`, which
  `tests/core/test_package_boundary.py::test_no_ui_module_reaches_through_a_session_into_the_engine`
  forbade. The test guarded exactly the facade the plan removes (phase 2 step 10 reads
  `session.engine.look.dice` too), so it is deleted with it.
- Step 8, `run_builtin` passes `tools` through: the two `tests/app/test_builtin.py` cases that
  handed a narrator run a `Tools` and asserted the gate dropped it now run the narrator as
  production does, with no tools (`ask` passes none). The refusal on a tool call is still tested.
- `tests/turn/test_decisions.py` uses the new `core.tools.NoArgs` instead of its own stand-in
  (review cut).

### Refuted review findings

- "`Pairs` belongs in `core/views.py`, the dependency now points the wrong way": PLAN step 6 moves
  it to `core/prompt.py`; `views` importing from `prompt` makes no cycle.
- "Fold `apply` and `set_engine` into one function": `set_engine` has three callers
  (`ui/app.py`, twice in `ui/create.py`) beside `apply`.
- "Inline `_landed`": PLAN step 8 keeps it and moves only the logging into the loop.
- "Drop the `facts` local in `SceneEngine.depart`": PLAN step 3 spells that shape.

### Known and accepted

- `Hiring.hire_check(self, _draft: G)` keeps the underscore: the base body reads nothing (ruff ARG).
- `dice_look`, `THEMES`, `Theme`, `NEUTRAL_DICE`, `HIRE_TOOL` and `AbilitiesDraft` stay for phase 2.

## Phase 2: edges and layers

| dir   | before | after |
| ----- | ------ | ----- |
| src   | 9,817  | 9,907 |
| tests | 9,132  | 9,256 |
| qa    | 1,788  | 1,788 |

Full check green; goldens byte-identical; app smoke green (home, settings, create, scenario and
the four shipped game pages serve). Reviewed by two adversarial readers (Fable and Opus; no
Codex on the machine). `uv sync --all-groups --locked` is needed before `basedpyright`: without
the `qa` group Playwright is unresolved and `qa/*.py` reports 1,100 errors.

### Decisions off-plan

Every review finding was folded; where a finding and the plan's letter disagreed, the cleaner
shape won, on the maintainer's instruction:

- `core/io.py` `write_text` converts `OSError` to `Refusal(f"{path.name} cannot be written: ...")`
  (one test). Before the phase `GamePage._run` caught `OSError` and showed it; with the callers
  narrowed to `except Refusal` a full disk on save would have escaped the page unhandled. The
  file write is the one edge PLAN step 1 did not list.
- No `parse_json` (PLAN step 4): one JSON door, `parse(model, decode(raw))`, as `app/builtin.py`
  already reads a provider reply. `ClaudeDriver.read_result` keeps its tail:
  `claude printed no JSON result: {output[-500:]}` is the only report when the CLI exits 0 with
  prose. `media._generate` decodes the reply the same way.
- `media._decode` returns a `GeneratedImage` and refuses on an unsupported data uri as it does
  on bad base64; `_generate` raises `Refusal("image reply held no image")` and its one handler
  logs a warning with the reason (no traceback: an edge is not a bug).
- `Claims` lives in `app/providers.py`, which media and speech both import; PLAN step 12 put it
  in `media.py`, which made speech depend on the image module.
- Speech catches `(HTTPError, OSError, wave.Error)`: nothing in its `try` raises a `Refusal`.
- `theme.set_engine` → `set_look`: it takes a `Look` now (PLAN step 10 kept the old name).
- `GamePage._send(playing: Callable[[str], Awaitable[None]])` reads the box once and hands the
  text to the closure; PLAN step 11 had `submit` and `act` each read it.
- `render_interjection(view, member: Companion, scenes, evidence)` reads `member.sheet` itself.
- `ScenarioForm._discard_upload()` holds the cleanup: `rmtree(..., ignore_errors=True)`, since
  it runs in a `finally` and a temp dir that will not delete must not replace the refusal the
  player was about to read.
- `Look.palette` is `Mapping[str, str]` with no default: a frozen value model on a class
  attribute must not hand out a dict four sessions share, and every engine passes one.
- `GameService.speaking` is `_speaking is not None and not _speaking.done()`: a member who has
  finished speaking is not speaking. `settled()` is `async def ... -> None` rather than
  `-> Awaitable[None]`: `gather` returns a `Future[list[None]]`.
- `GameService._narrated(draft, facts, prompt)` holds the one `except Refusal` around the
  narrator that `open` and `_grow` both need; PLAN step 11 spelled the handler inline twice.
- `theme.apply(look)` has no default: `page_header` is its one caller and always passes it.
- `TunnelGoonsEngine.level_up` tests `ability is None or boost is None` (was `and`): the
  `LevelUp` validator makes the two equivalent, and `or` narrows both for the fall-through
  without an `assert`; one comment says so.
- `Loner3eEngine.__init__` calls `twist_table()` once so a pack without twist columns fails at
  construction; `twist_table` keeps the one check, as `ValueError`.
- `tests/turn/test_turn.py`: the three "master crashed" stubs raise `Refusal`, since a spawn
  failure can no longer reach `Roles.master` as anything else.
- `tests/core/test_package_boundary.py`: the UI names no engine id at all now, so the test
  expects an empty set rather than `ui/theme.py`.
- `test_reload_settings_cancels_an_evicted_sessions_background_task` runs through public state
  (a member left speaking, then `reload_settings()`); `_StillSpeaking` records the cancellation
  so `test_a_new_turn_silences_the_member_still_speaking` still asserts the spawn was cancelled.

### Refuted review findings

- "`CatalogEntry.look` is set on character entries but only read for scenarios": one entry
  type for both; a required dataclass field is set on every entry.

### Known and accepted

- `SceneDraft`/`NextDraft` are `Mutable` state inside a `Frozen` `Scenario`; `new_game` deep-copies
  once so a restart reopens the file unchanged.
- `AbilitiesDraft` and `HIRE_TOOL` stay for phase 3.

## Phase 3, part A: the seam and the families

| dir   | before | after |
| ----- | ------ | ----- |
| src   | 9,907  | 9,903 |
| tests | 9,256  | 9,286 |
| qa    | 1,788  | 1,788 |

PLAN.md phase 3 steps 1 to 8. Full check green; goldens changed on the four
`schemas/*/master_tools.json` only (tool order seam, family, engine; the shared `reveal`/`kill`
texts). QA harness green on goons, breathless and 24XX; loner reports two issues ("no crash
notification", "no live turn after a reload mid-turn") that reproduce on the base commit and are
not this phase's. Reviewed by two adversarial readers (Fable and Opus; no Codex on the machine).
Part B (steps 9 to 16) is the next commit.

### Decisions off-plan

- Step 2, `world_of`: tunnelgoons overrides too (`-> TunnelGoonsWorld`), not only loner3e and
  24XX: `rest` and `level_up` call `TunnelGoonsWorld.rest()` and `next_to_level()`, which
  `RoomWorld[Npc, Goon]` lacks. Breathless alone inherits.
- Step 3, `Hiring`: a `type` alias over the write callable, not a one-field frozen dataclass;
  `hiring(...)` returns the closure and `write_hire` calls it (both reviews). `hireable(draft,
  entity_id)` did not move onto the seam: with `world_of` typed `World[M, P]`,
  `require_hireable` already returns `M`, so its two callers call the world directly.
- Step 4, `Reveal.entity_id`: the shared field text "Exact id of something hidden here." is the
  plan's; the three scene engines' `master_tools.json` change on it too, and the rooms family
  loses its ": an npc or an item" hint. Accepted: `RoomWorld.reveal_hidden` still reveals a
  `Prop`, and the master sees hidden items listed under HIDDEN HERE.
- Step 4, `World.join_party` is concrete (`self.join(self.require_member_here(entity_id))`):
  both families spelled it the same way (review finding). `leave_party` differs and stays abstract.
- Step 4, `RoomWorld.kill(entity_id)` refuses a dead player with "is already dead", as
  `SceneWorld.kill` does; one test.
- Step 6, the base validator also holds "the player cannot travel with themselves", before the
  member lookup: the player is never in `cast` or `npcs`, so the families' own check had become
  unreachable behind "is not known".
- Step 7, `open_chapter`'s pop now runs on every scene install too; two tests that installed a
  scene on a chapter with no exchanges give it one first.
- `tests/core/test_golden_turn.py` picks the family's own request by name rather than the first
  in dict order, since the seam's `hire` now comes first (families spread `super()` first).

### Refuted review findings

- None refuted outright. The `Reveal` wording finding is recorded above as an accepted loss
  rather than reworded: the field text is the plan's.

### Known and accepted

- `AbilitiesDraft`, `HIRE_TOOL`, `require_here(alive=True)`, `Gauge.change(owner, ...)`, the
  hand-built `DiceEvent`s and `ItemSheet.drop_item(item_id, owner)` stay for part B.
- The `hiring()` method on an engine returns the module-level `hiring(...)`: same name, no
  shadowing (a method is a class attribute; the call resolves in module scope).

## Phase 3, part B: the rules code

| dir   | before | after  |
| ----- | ------ | ------ |
| src   | 9,903  | 10,135 |
| tests | 9,286  | 9,533  |
| qa    | 1,788  | 1,788  |

PLAN.md phase 3 steps 9 to 16. Full check green; goldens changed as step 16 says: the three
`turn/*.json` with a single-die trace (`1d10` → `d10`), the tunnelgoons prompts on the Health row
coming first, the 24XX prompts on the Gear row leaving the sheet (`worldsmith.txt` too: the
player's line is in THE WHOLE CAST). QA harness green on goons, breathless and 24XX; loner reports
the two issues part A recorded as reproducing on the base commit. Reviewed by two adversarial
readers (Fable and Opus; no Codex on the machine). Implemented as three sequential shape rounds
(dice; owners and lookups; inventory and refusal helpers) then four parallel per-engine rounds.

### Decisions off-plan

- Step 9, dice labels: `roll_pool` with an empty label spells a same-faced pool `2d8`, where the
  card said `d8+d8` (a helped roll on the same die). The plan's "card labels keep their spelling"
  holds only because breathless and 24XX pass `label="+".join(...)` (review finding).
- Step 9, `roll` and `roll_pool` share a private `_rolled(...)` that builds the event once with
  its highlight, so `DiceEvent`'s validator runs on every event (review finding).
- Step 11, `SurvivorSheet.spend_stunt(owner: str)` takes the actor's name, as `ItemSheet.require`
  does, so the refusal still says whose breath must be caught.
- Step 12, `Pool` is a frozen dataclass, not a `Frozen` pydantic model: it holds live entities
  (`Survivor`, `Npc`) that pydantic must not copy. Breathless's `Pool` has no `item` field: `_wear`
  goes through `Survivor.wear_item(item_id)`, so the field was never read (review finding).
  `_pool`, `_wear`, `_line` and `_consequence` are module-level private functions where they read
  no engine state; 24XX's `_pool` stays a method for `resolve_skill` (review finding).
- Step 12, breathless `_wear(actor, args, pool)` rather than `_wear(sheet, pool)`: the item branch
  is `actor.wear_item(args.item_id)`, the owner method step 11 adds.
- Step 13, `require_living_here` checks presence before life, so a dead entity elsewhere is now
  refused as "not here" first; no test depended on the old order.
- Step 14, `Sheeted.line` appends `carried()` to the caller's detail with `; `, where
  `Survivor.line` replaced the detail (so a hired survivor's cast line lost "met; travels with the
  player"); `Survivor.carried` has no "backpack:" prefix. No golden shows a hired survivor.
- Step 15, `scene_unmet` is `[*_listing_unmet, *_cast_unmet, *_hidden_unmet]`: the messages
  inside the one refusal now group by kind (listed, stray, overlap; rewritten, misfiled,
  forbidden; situation, met) instead of the install order. Both reviews flagged the reorder;
  kept on the maintainer's call, the plain concatenation being the cleaner shape and the order
  prose.
- Step 9, `Rolled` has no `faces`: nothing read it and `event.faces` carries the pool for the
  tray (both reviews; the plan's shape had it; the maintainer's call).
- Step 15, the test that imported the private `_operators_unmet` is gone (phase 2: tests stop
  reaching private state); the refusal is covered through the `job` tool.
- The tunnelgoons `Adventurer.rows` puts Health first, so `GoonSheet.rows` is the sheet's alone.

### Refuted review findings

- "Tunnelgoons `Pool.faces` and `label` are constants": PLAN step 12 spells the field list.
- "`roll` and `_pool` both call `require_sheet()`": `_pool(world, actor, args)` is the plan's
  signature; the call is a field read behind a refusal.
- "Breathless `_consequence` returns `None`": the plan names `_wear` and `_consequence` both for
  breathless; the vulnerable note is what a dangerous fail does.
- "Drop `world` from `_line` and test `actor.id == PLAYER_ID`": 24XX's lead keeps their own id
  after `take_lead`, so `actor is world.player` is the check there; the three `_line`s stay alike.
- "`wear_item` looks the item up twice": `remove_item` is the sheet's one door that deletes.

### Known and accepted

- `Thing.change` and `Survivor.catch_breath` card the player by `self.id == PLAYER_ID`, as
  `Gauge.change` did; a 24XX lead who took over carries their own id and is carded by name.
- The 24XX `Pool` holds `helped_by` as the finished clause, not the helper's id and die.
