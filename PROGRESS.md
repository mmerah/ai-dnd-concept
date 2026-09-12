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

Counts (`src` / `tests` / `qa`): 9,771 / 9,752 / 1,759 before; 9,932 / 9,891 /
1,759 after. Two passes: the plan's primary-plus-supplements shape landed first, then the
maintainer dropped `primary` (the SRD is always selected, so it carried nothing) and widened the
character to a selection of its own. Goldens: zero drift. Reviews: Fable and a second Opus
reviewer on the first pass, one Opus reviewer on the second (no `codex` on the machine). Smoke:
the offline QA harness creates a scenario through the new page and takes a turn on each shipped
scenario; the loner script's two issues reproduce on the HEAD baseline.

### The shape as landed

- `PackSelection(ids=(...))`: one ordered, unique, non-empty tuple, on `Scenario`, `Game` and
  `Character`; `None` for an engine that plays no packs (tunnelgoons). A scene engine refuses a
  selection without its SRD, an id it does not install, and two packs that both define one
  option id (`ScenePack.defined_ids`; breathless declares none, twentyfourxx its specialties and
  origins, loner3e all four lists).
- A character may start any scenario whose selection is a superset of its own
  (`SceneEngine.admit`, also run by `Runtime.new_scenario` before the worldsmith is spawned).
- Character creation pools options across the picked packs through one `multiple` creation
  step, `supplements`, joined into the pick with `MANY`; the step exists only when the engine
  ships more than the SRD. Skills stay the SRD's in breathless and twentyfourxx, whose rules fix
  them.
- The page composes a selection through `Engine.select_packs(supplements)`, since `ui` may not
  name a family's SRD; `SceneEngine.author` checks it again at the engine boundary.

### Decisions made off-plan

- `select` takes a built `PackSelection`, not `(primary, supplements)`; the plan's signature only
  re-parsed a value its caller held.
- `RoomEngine.validate` refuses a non-`None` selection: the seam made the field optional, so the
  rooms family checks its side of that boundary.
- `PackSelection.ids` is a field; `defined_ids()` and `select_packs()` are methods.

### Refuted review findings

- "One `ui.select` call for a single and a multiple step": the two handlers take different event
  types (`str` and `list[str]`), and one call would need a union callable under strict pyright.
- "The authoring path checks the selection twice": the page must compose the SRD it may not
  name, and `author` is the boundary the tests call directly.
- "Make the base `defined_ids` abstract": `ScenePack` is a concrete model and breathless declares
  no ids, so an abstract base would force an empty override where the default already says it.

### Known and accepted

- A scene-family character file with no `packs` is refused at launch; the three shipped kael
  files carry `{"ids": ["srd"]}`.
- Hidden-then-shown supplements on the character page: an id no longer offered is dropped from
  the pick by `_drop_stale`, as for single answers.
