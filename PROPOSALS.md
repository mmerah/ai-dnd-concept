# Proposals: code pattern quality before MVP0

Scope: `src/aidm` only. Baseline: `ruff`, `ruff format --check`, `basedpyright --strict` and 807 tests
all pass. `src` is 10,179 lines.

Method. Four reviewers read every file (one lead, three independent lenses). Every accepted
proposal was then implemented in a scratch worktree and measured: `wc -l` over `src` and `tests`,
ruff, basedpyright, pytest. A proposal survives only if it removes lines and reads simpler. Most
did not. Estimates from reading were optimistic every time; this file reports measured numbers only.

**Result.** Three changes survive, together **−20 lines in src** (10,179 → 10,160 with one added
comment), +2 in tests, all checks green, prompt and schema goldens byte-identical. They are
landed on this branch, with the two decisions below taken as recommended. Everything else was measured and cut; the
reasons are in the second table so nobody re-proposes them.

---

## Landed (implemented, measured, green)

| # | Change | src | tests |
|---|--------|-----|-------|
| S1 | Inline `hire_prompt` into `write_sheet` in the three hiring engines | −9 | 0 |
| S2 | Move seam tool prose and argument models to `engines/tools.py`; fold `hiring.py` away | −4 | +2 |
| S3 | `filled()` and `joined()` replace six open-coded "drop the empties and join" blocks | −7 | 0 |

### S1. Inline `hire_prompt`

**Plain English.** Each hiring engine has a `hire_prompt` method with exactly one caller, its own
`write_sheet`. Inlining removes a named indirection the reader has to chase, and `write_sheet`
reads top to bottom.

**Files.** `engines/tunnelgoons/engine.py` (−3), `engines/breathless/engine.py` (−2),
`engines/twentyfourxx/engine.py` (−3 for this item). No test references `hire_prompt`.

**Feature impact.** None. Same prompt text; the worldsmith prompt goldens do not change.

### S2. `engines/tools.py`

**Plain English.** Every family and engine keeps its tool descriptions and argument models in a
`tools.py`. The seam alone kept them in `base.py` (beside `Gauge`, `Thing`, `World`) and in a
one-tool module called `hiring.py`. One module, one kind of content, like the other six.

**What moves.** From `base.py`: `REVEAL`, `KILL`, `JOIN_PARTY`, `LEAVE_PARTY`, `ACTOR`,
`DROP_ITEM`, `Attempt`, `Reveal`, `Kill`, `JoinParty`, `LeaveParty`, `DropItem`, `AskWorld`.
From `hiring.py` (deleted): everything. `UNKNOWN_ID` and `IS_DEAD` stay in `base.py`; they are
refusal text the worlds use, not tool prose. `base.py` shrinks by 37 lines and its import list
loses the tool vocabulary. About ten import lines repoint in `src` and four in `tests`.

**Feature impact.** None. Pure relocation; `git diff -- tests/core/fixtures` is empty.

**D-S2, taken.** `tests/engines/test_hiring.py` is renamed `test_hire_tool.py`: the module it named no
longer exists.

### S3. `filled()` and `joined()`

**Plain English.** Three `rows()` methods build a tuple of `(label, value)` pairs and filter out
the empty values with a four-line scaffold; three `required()` methods build a `parts` tuple and
join the non-empty ones. Two one-line helpers name the idiom.

```python
# core/views.py, beside the Rows alias
def filled(*pairs: tuple[str, str]) -> Rows:
    return tuple(pair for pair in pairs if pair[1])


# engines/base.py, with the other free functions
def joined(*parts: str) -> str:
    return ", ".join(part for part in parts if part)
```

**Files.** `core/views.py` (+4), `engines/base.py` (helper +4, `Sheeted.required` −1),
`loner3e/world.py` (−5), `breathless/world.py` (−4), `twentyfourxx/world.py` (−4),
`tunnelgoons/world.py` (−1).

**Feature impact.** None. Same filter, same order; the master prompt goldens do not move.

**D-S3, taken.** No docstrings on the helpers (with them the delta was −5); the names and one-line
bodies say it.

---

## Also landed, free

- `core/model.py:108`: one comment on `Game.generation`'s `exclude=True` ("in flight only, never
  saved; `restore` refuses a save that carries one"). +1 line. The `restore` guard is live and
  tested (`tests/engines/test_seam.py:87`), not dead as one reviewer claimed.
- `scenes/worldsmith.py`: `scene_unmet` becomes `_scene_unmet` (one caller). 0 lines.
- `ui/widgets.py`: `_notify` moves below the last public function, per the module layout rule.
  0 lines.

---

## Measured and cut

Each of these was implemented fully, checked, and counted. Numbers are net `src` lines.

| Proposal | Predicted | Measured | Why it is cut |
|----------|-----------|----------|---------------|
| P1 Engine typed by its world, delete `world_of` | −25 | not possible | PEP 695 forbids a bound that names a sibling type parameter (`W: World[P, M]` is rejected by basedpyright: "TypeVar constraint type cannot be generic"). The only spellable bound is `World[Any, Any]`, which turns every world access in the families into `Any`. The three leaf overrides are the minimal typed narrowing. |
| P2.1 Pass-through tools as lambdas (7 sites) | −12 | **+18** | A `master_tool(..., lambda d, a, _: ...)` call exceeds the line limit, so ruff formats each binding to 6–8 lines; the method it replaced was 3. The reverse direction (method everywhere) is +24. The current mixed spelling is the line minimum. |
| P2.2 `Hiring` mixin, delete `hires` flag and dead stub | −6 | **+15** | `hiring.py` needs eight imports and a class header to re-express three bare method bodies; every hiring engine grows a three-line header with two generic bases and real MRO subtlety (`super()` from `Hiring.master_tools` lands on the family, not `Engine`). Also reorders the `hire` tool in the three `master_tools.json` goldens. |
| P2.3 `Carrier[I]` for the duplicated `drop_item` | −6 | not possible | `ItemSheet[I]` is invariant and the real sheets are subclasses with extra fields; four spellings tried, all rejected without `Any`. Even if typeable, the bindings grow more than the two 3-line methods shrink. |
| P2.4 Fold the duplicated `author` | −22 | not built | Would add four hooks and a fourth type parameter to remove two explicit 18-line bodies. Left by decision. |
| P3 `Busy(Refusal)` instead of string-matching the gate message | −14 | **0** | `_run` must swallow `Busy` for four callers and raise it for one (`_opened`), which needs a `retry_busy` boolean on `_run`: a flag that changes whether a function raises, in exchange for a string comparison. It also silences the "another game is taking a turn" toast unless the string comparison comes back. |
| P3 `check_filing` raises `ValueError`; `chosen_option` → `require_option`; `PackSet.chosen` → `selected` | 0 | 0 | Correct and free, but they remove no lines and are not applied. Do them opportunistically in any commit touching those files. |
| P4.1 `required`, `notes`, `carried` as properties | 0 | **+10** | Ten `@property` lines against about twelve call sites losing two characters. |
| P4.2 Delete the positional-only `/` on abstract methods | 0 | **+4 src, +8 tests** | The markers are load-bearing. Ruff's ARG rule makes overrides rename ignored parameters (`_picks`, `_words`); `reportIncompatibleMethodOverride` then requires matching names, and positional-only is what makes the mismatch legal. Deleting them produced 12 type errors, fixed only by eight `del picks` lines. Keep the markers; add them to `new_game`, `master_sections`, `narrator_view`, `player_view` only when an override needs one. |
| P5.1 UI bare `self.x: T` annotations to the class body | 0 | **+6** | Three comments and three blank lines, and `GamePage.__init__` no longer lists the page's surface in one place. |
| X1 `GameService._phase` context manager | −8 | **+6** | `_turn` still needs its own `try/finally` for `self.turn`, so the reader follows two nesting mechanisms instead of one. |
| X2 Derive `CatalogEntry.rules/look` on the catalog | −10 | **+5** | Two accessors, an `engines` field and a `SaveOption.engine` field outweigh four construction lines; every read gains a hop and `_saved_card` gains a parameter. |
| X4 Delete the `restore` generation guard | −2 | **+1** | The guard is live: `exclude=True` affects serialization only, and a test hand-edits a save to smuggle one in. Only the comment survives. |

---

## Two facts the exercise established

1. **This codebase is at its line floor under strict typing and ruff's formatter.** Ten of thirteen
   "simplifications" a careful reader proposes come back larger once formatted and type-checked.
   Any future refactor proposal should be measured the same way before it is planned.
2. **Two things that look like drift are mechanisms.** The positional-only `/` on some abstract
   methods (lets overrides rename ignored parameters) and the mixed lambda/method spelling of tool
   bindings (each is the shorter form for its body length). Both deserve a one-line note in
   CLAUDE.md so the next reviewer does not re-flag them.

Both lines are now in CLAUDE.md:
- "A positional-only `/` on an abstract method lets an override rename a parameter it ignores."
- "A tool binding is a lambda when it fits on one line, else a method."
