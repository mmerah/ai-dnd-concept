# PROGRESS

One entry per phase: line counts before and after, decisions made off-plan, and refuted review
findings with the reason.

## Phase 1 — core and the engines

| | before | after |
| --- | --- | --- |
| `src` | 10,069 | 10,020 |
| `tests` | 10,363 | 10,368 |
| `qa` | 1,759 | 1,759 |

655 tests before, 656 after: the one added test is the scene game's refusal of the player's own id
to `join_party`. No golden under `tests/core/fixtures/` moved, and none was regenerated. The three
strings a test asserts moved with their tests: the party-duplicate message, that refusal, and the
cards hired members carry.

`src` lands at −49 against the plan's estimate of about −56. Three of the seven are measured and
named under "Decisions made off-plan" below; the rest is the plan's own "about".

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
- **`twentyfourxx/engine.py`, `_pool`.** The plan spells the pair as `helping[0]` / `helping[1]`
  throughout. `roll` does. `_pool` unpacks once (`helper, helper_args = helping`) inside the single
  block that reads the pair eight times; indices there would be less readable, not more.
- **`scenes/engine.py`, `chosen_packs`.** Reads `self.packs.installed` through a local. Inlining it
  is 108 characters, so the "cut" would add a line rather than remove one.

### Refuted review findings

Two adversarial Opus reviews ran (no `codex` on this machine, and the run asked for Opus reviewers
only). Both returned *phase complete: yes*.

- **`_open_way` re-resolves the forward way its callers already hold, and `here` is always
  `self.current`.** Refuted: PLAN phase 1 step 5 gives the signature and body verbatim, and says in
  the same breath that both callers keep their own lookup — `move` needs the way itself for the
  locked check and for the ways-out refusal, `unlock_way` refuses differently.
- **`check_risk` should be `_check_risk` in the private run.** Refuted: PLAN step 2 puts it "in the
  public-function run under the classes", and the repo already spells this family public —
  `check_unique`, `check_filing`, `check_named`, `check_spread`, `check_picks`, `check_map`,
  `check_extension`, `check_scene`.
- **`roll` reads `helping[0]` / `helping[1]` positionally.** Refuted: that is PLAN's prescribed
  shape for `roll`; see the `_pool` note above for where it does not hold.
- **Inline the `packs` local in `loner3e.glossary`.** Refuted by measurement: inlined, the
  comprehension is 117 characters and wraps to four lines, one more than it replaces.
- **`loot_check` should take PLAN's two-line shape.** Refuted by the type checker; see above.

### Fixed from review

- The why-comment in `loner3e.glossary` now sits above the `entries` tuple whose omission of
  `concepts` it explains, not above the `spelled.update(...)` call.
- `PROGRESS.md` created — both reviews' top finding.

### Known and accepted

- `uv run basedpyright` reports ~1,100 errors, every one of them in `qa/`, because `playwright` is
  not installed in this container. `uv run basedpyright src tests` is clean. No phase 1 step touches
  `qa/`.
- Left for the maintainer to settle: `tunnelgoons/engine.py`, `roll`. PLAN step 5 prescribes
  `ds = npc.hp.current if npc is not None else (args.difficulty or 0)`. `difficulty` is
  `Field(ge=1)`, so `0` is never a real Difficulty Score and the `or 0` can only fire in the state
  `Roll._one_target` makes impossible — where it resolves the roll as a guaranteed success instead
  of failing. CLAUDE.md holds that an unreachable state is a bug, not a message. The `level_up`
  precedent PLAN cites is not parallel: there `None`/`None` is a legitimate state that opens a
  decision. PLAN's line is what landed.
