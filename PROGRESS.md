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
