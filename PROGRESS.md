# PROGRESS

One entry per phase: line counts before and after, decisions made off-plan, and refuted review
findings with the reason.

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
