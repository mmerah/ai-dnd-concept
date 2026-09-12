# PROGRESS

One entry per PLAN.md phase: `src` / `tests` / `qa` line counts before and after, decisions made
off-plan, refuted review findings and why, and what is known and accepted.

## Phase 1: the fixes, the decided requirements, the sweep

Counts (`src` / `tests` / `qa`): 9,990 / 9,498 / 1,788 before; 9,771 / 9,752 / 1,759 after.
The CSS moved 320 lines out of `src` into `ui/theme.css`; the new helpers (`publish`, `hold`,
`parse_json`, `resume`, `start`, `admit`, `Sheet`, `Struck`) and the tests for each new
behaviour make up the rest. Reviews: Fable and a second Opus reviewer (no `codex` on the
machine).

### Decisions made off-plan

- `publish`'s `write` is `Callable[[Path], object]`, not `Callable[[Path], None]`:
  `Path.write_text` and `write_bytes` return `int`, which basedpyright strict rejects for a
  `None`-returning callable.
- `Claims.hold` returns `Generator[bool]` and `Runtime.admit` returns `AsyncGenerator[None]`:
  basedpyright reports `@contextmanager` over an `Iterator` annotation as deprecated.
- `GameService.settled` stays beside `close`: `close` cancels what has not landed, and the
  golden turn and the speech test need every background task to land first. `drain`
  (`tests/support/table.py`) awaits `settled` then `close`.
- The golden turn test seeds `service.chatter` with its `SEED`: the interjection die no longer
  comes from the game's rng, so an unseeded chatter would make the twentyfourxx golden flaky.
- `tests/turn/test_turn.py` and `test_decisions.py` (seven sites) and
  `tests/app/test_master_tools.py` (two) play through `table.runtime.play(...)`: the tool gate
  now reads the admitted session's turn, so a turn played on the service alone lands nothing.
- `reload_settings` evicts every session before its first await, so a play arriving while the
  old sessions close cannot pass `admit`; `Runtime.close` iterates a snapshot for the same
  reason. `Runtime.restart` on the page returns on a refusal instead of opening again.
- The in-flight refusal is one constant, `IN_FLIGHT`, beside `NO_TURN`.
- `level_options` takes a `Slug`: its one caller passes `self.id`.
- `FIGHT_SEED` did not need re-seeding.
- The brief's `src` target of "under 9,700" was an estimate; 9,771 is the measured count.

### Refuted review findings

- "`decode(raw)` then `parse_json(model, raw)` at three boundaries reads as dead code; fold
  both into one `checked_json` helper": PLAN step 9 prescribes the two calls at each site and
  says `parse_json` does not replace `decode`. Left as the plan says; the maintainer may fold
  it later.
- "The scenario-models comprehension is now written in `LauncherCatalog.read` and
  `Runtime._open`": PLAN step 10 has each derive it from the engines itself. One line each.

### Known and accepted

- `Runtime.open` checks `unopened` before entering `admit`, so a second tab's timer returns
  silently while the first tab's opening is in flight, as the plan wrote it.

## Phase 2: D4, one explicit pack selection

Counts (`src` / `tests` / `qa`): 9,771 / 9,752 / 1,759 before; 9,874 / 9,847 / 1,759 after.
`PackSelection`, `selected`, `select`, `primary_pack`, `_check_installed`, `defined_ids` and the
create page's second select are the growth; `first_pack` and the two uniqueness validators went.
Goldens: zero drift (`selection.ids()` is still `("srd",)`). Reviews: Fable and a second Opus
reviewer (no `codex` on the machine). Smoke: the offline QA harness (`qa/run_all.sh create loner
goons breathless 24xx`) creates a scenario through the new page and takes a turn on each shipped
scenario; its first cold run flaked on the character page and the goons level card, and both
passed on rerun and on the HEAD baseline.

### Decisions made off-plan

- `SceneEngine.select(self, selection: PackSelection) -> PackSelection`, not
  `select(primary, supplements)`: its one caller, `author`, already holds the validated instance
  the page built through `parse`, so the plan's signature only re-parsed it. `author` runs
  `self.select(self.selected(packs))`; the plan named `select` as the authoring-time builder but
  not its caller.
- `ScenePack.defined_ids()` is the hook behind "an id that two selected packs both define": a
  family overrides it with the option lists whose ids it owns. Breathless overrides nothing
  (every breathless pack must carry the same six SRD skill ids), twentyfourxx declares
  specialties and origins (its skills are bound to exactly 17, so a supplement repeats them),
  loner3e declares all four lists.
- `SceneEngine.pack_options()` lists the SRD first and the create page defaults to the first
  option: `ui` may not import an engine family's `SRD_PACK`.
- `TwentyfourxxEngine.resolve_skill(selection, sheet, wanted)`: the selection is the first
  parameter, and `_pool` takes it too.
- `RoomEngine.validate` refuses a non-`None` selection: the seam made the field optional, so the
  rooms family checks its side of that boundary.
- The create page builds the Supplements select only when the engine offers more than one pack.
- `PackSelection.ids()` and `defined_ids()` are methods, not properties, as the plan wrote `ids()`.

### Refuted review findings

- "`self.supplements.value if self.supplements is not None else []` guards a branch that cannot
  occur": it can, once the Supplements select exists only for an engine with more than one pack.
- "The `Choose a table set.` guard is unreachable, the primary select is not clearable": PLAN
  step 4 asks for the refusal, and it costs two lines.
- "Make the base `defined_ids` abstract": `ScenePack` is a concrete model (the seam test's
  engine uses it as its pack) and breathless declares no ids, so an abstract base would force an
  empty override where the default already says it.

### Known and accepted

- A scene-family character file with no `pack` is refused at launch ("was made from no table
  set"); the three shipped kael files carry `"pack": "srd"`.
- `src` grew by 103 lines against the brief's estimate of about 60; the create page's second
  select is most of the difference.
