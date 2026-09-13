# PROGRESS

One entry per phase: line counts before and after, decisions made off-plan, and refuted review
findings with the reason.

## Phase 2 — the app, the settings and the pages

| | before | after |
| --- | --- | --- |
| `src` | 10,031 | 10,020 |
| `tests` | 10,368 | 10,412 |
| `qa` | 1,825 | 1,825 |

656 tests before, 659 after. The three added tests are the three behaviours this phase introduced
that nothing asserted: `Settings` is frozen, a facts-only tick spares the whole page
(`whole_page`), and a drawn icon still holds its claim while its file is written. A fourth
assertion joined an existing test: the killed spawn is reaped. No golden under
`tests/core/fixtures/` moved, and no text a role or the player reads changed.

`src` lands at −11 against the plan's estimate of about −4. `qa/run_all.sh` was run against a
pristine worktree at the phase-1 commit and again after, and reports the same issues in the same
scenarios (`loner` 2, `create` 1, all pre-existing).

### Decisions made off-plan

- **`ui/theme.css`, the gap scale.** Every one of the ten rules carries `!important`, which the
  plan does not ask for. Measured: `theme.css` is injected inside `@layer overrides`, NiceGUI's own
  `nicegui.css` is unlayered, and an unlayered `.nicegui-row, .nicegui-column { gap:
  var(--nicegui-default-gap) }` (1rem) beats a layered rule whatever the specificity — in the QA
  chromium a layered `gap: .4rem` computes to 16px and the same rule with `!important` to 6.4px.
  Without it the plan's step would have been dead CSS and every gap on every page would have become
  1rem. Costs one comment line.
- **`ui/create.py`, the discard hook.** The plan says
  `ui.context.client.on_disconnect(self._discard_uploads)`. In the pinned nicegui 3.16
  `on_disconnect` also fires on a reconnect, before the client is really dropped, so a backgrounded
  tab or a wifi blip would `rmtree` the upload of a page still open and leave `write` refusing for a
  document the uploader still shows. Registered `on_delete` instead, which fires only when the
  client is discarded. The two trailing resets in `_discard_uploads` went with it: the object dies
  with the page.
- **`ui/game.py`, the refresh flag.** The comparison the plan spells inline in `poll_turn` is a free
  function, `whole_page(now, seen)`, in the public run beside `draft_spent` and `near_end` — which
  is where CLAUDE.md puts a function that is unit-tested on its own, and it is the only way to test
  a flag whose failure mode (computing it after `self.seen = now`) is silent. +4 lines.
- **`tests/app/test_master_tools.py`.** In no part-brief's file list, and part A's brief said it
  changed no test file, but the now-awaited `_kill` calls `process.wait()` and that file's
  `FakeProcess` had no `wait`. It gained one, and the reap is now asserted.
- **`app/providers.py`, `close_posting`.** Guarded with `if posting.cache_info().currsize:`: the
  pool is lazy so an offline run builds none, and the plan's shape would have constructed a client
  at every shutdown only to close it.
- **`app/spawn.py`, the `shield` comment.** The reason first written for it was wrong: after
  `hush`'s single cancel the `finally` is no longer cancelled and a bare `await process.wait()`
  would complete. The `shield` earns its place against the *second* cancel — `Tasks.close` cancels
  a task `hush` already cancelled — and the comment now says that.

### Refuted review findings

Two adversarial Opus reviews ran (no `codex` on this machine, and the run asked for Opus reviewers
only). Both returned *phase complete: yes*. Every finding was fixed except one cut:

- **Delete `Tasks.settled`; let `drain` await `gather(*service.tasks.running)`.** Refuted: phase 2
  step 1 names `settled` in the `Tasks` shape, and the alternative moves asyncio plumbing into
  `tests/support/table.py` for a class whose whole point is that it owns those tasks. Its one
  caller being a test is what `drain` is for.

### Known and accepted

- `uv run basedpyright src tests` is the gate. Plain `uv run basedpyright` also walks `qa/`, which
  needs `uv sync --group qa` (that group is now installed in this container, so `qa/` type-checks
  too; phase 1 recorded ~1,100 errors there from the missing `playwright`).
- The pages keep their half-built constructors, as the plan says. Nothing here touched them.
- `GameService` still does five jobs; only the task nursery moved out.

## Phase 1 — core and the engines

| | before | after |
| --- | --- | --- |
| `src` | 10,069 | 10,031 |
| `tests` | 10,363 | 10,368 |
| `qa` | 1,759 | 1,759 |

655 tests before, 656 after: the one added test is the scene game's refusal of the player's own id
to `join_party`. No golden under `tests/core/fixtures/` moved, and none was regenerated. The three
strings a test asserts moved with their tests: the party-duplicate message, that refusal, and the
cards hired members carry.

`src` lands at −38 against the plan's estimate of about −56. The phase first landed at −49; the
maintainer then asked for every open review item to be fixed the cleanest way regardless of what
the plan says, and three of those fixes cost 11 lines. The budget was explicitly subordinated to
clarity; see "Fixed from review" below for what each bought.

### Decisions made off-plan

- **`breathless/engine.py`, `loot_check`.** The plan's shape drops the `found: Die | None`
  annotation, and without it basedpyright widens `Die` to `int`, so the `loot_options(granted=...)`
  call no longer type-checks. Carrying the annotation on one line is 102 characters against the
  100-character limit. Kept the pre-bound `found` with an `if`/`else`: same six lines as the
  annotated conditional would need, and green. Costs 2 lines against the plan.
- **`tunnelgoons/world.py`, `Adventurer.level`.** The plan wraps the card on the line that builds
  it. That line is 105 characters, so `card = self.card_line(card)` stays its own statement. The
  rebind (not a `card=` keyword) is what the plan asks for and is what keeps the name in the trace.
  Costs 1 line against the plan.
- **`scenes/engine.py`, `chosen_packs`.** Reads `self.packs.installed` through a local. Inlining it
  is 108 characters, so the "cut" would add a line rather than remove one.

### Refuted review findings

Two adversarial Opus reviews ran (no `codex` on this machine, and the run asked for Opus reviewers
only). Both returned *phase complete: yes*.

- **`check_risk` should be `_check_risk` in the private run.** Refuted on the repo's own
  convention, re-checked after the plan was set aside: `check_named` in `scenes/world.py` is also
  called only from its own module and is also public, so a private spelling here would make
  `check_risk` the odd one out of `check_unique`, `check_filing`, `check_named`, `check_spread`,
  `check_picks`, `check_map`, `check_extension` and `check_scene`.
- **Inline the `packs` local in `loner3e.glossary`.** Refuted by measurement: inlined, the
  comprehension is 117 characters and wraps to four lines, one more than it replaces.
- **`loot_check` should take PLAN's two-line shape.** Refuted by the type checker; see above.

### Fixed from review

- The why-comment in `loner3e.glossary` now sits above the `entries` tuple whose omission of
  `concepts` it explains, not above the `spelled.update(...)` call.
- `PROGRESS.md` created — both reviews' top finding.
- **`tunnelgoons/engine.py`, `roll`.** The plan's `(args.difficulty or 0)` turned the state
  `Roll._one_target` makes impossible into DS 0 — a guaranteed success. It now raises `ValueError`,
  which is what CLAUDE.md asks of an unreachable state: a bug, not a message, and so not a
  `Refusal`. No test: the guard is unreachable through the validator, so there is no behaviour to
  assert. +1 line.
- **`rooms/world.py`, `_open_way`.** Took the way its caller has already resolved instead of
  re-resolving it, and dropped the `here` parameter, which was `self.current` at both call sites.
  Same length, one lookup fewer, one impossible argument fewer.
- **`twentyfourxx/engine.py`, the helping pair.** `helping[1].risk` said nothing about what index 1
  held, and `_pool` spelled the same value a second way. A frozen `Helping` record with `who` and
  `terms` replaces seven positional reads and the re-unpack. `@dataclass(frozen=True, slots=True)`
  over a shorter `NamedTuple`, because that is what every other value record here uses. +10 lines.

### Known and accepted

- `uv run basedpyright` reports ~1,100 errors, every one of them in `qa/`, because `playwright` is
  not installed in this container. `uv run basedpyright src tests` is clean. No phase 1 step touches
  `qa/`.
- Four steps of the plan were deliberately not followed to the letter, all recorded above. Phase 2
  should not read this file as evidence that the plan's shapes are binding where they cost clarity.
