# PROGRESS

One entry per `PLAN.md` phase: the counts it moved, what was decided off-plan, and what is known
and accepted.

## Phase 1: the edges

Landed the ten decided simplifications that touch no engine tool table, no worldsmith renderer and
no hidden-name scan.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,248 | **10,200** | about 10,210, at most 10,220 |
| `tests` | 12,226 | **12,260** | about 12,230, at most 12,242 |
| `qa` | 2,104 | **2,104** | unchanged |

`src` came in 10 under the target and `tests` over it. Both are explained below; neither is
padding, and each was measured, never estimated.

**`tests` is 18 over the plan's cap, and this entry is the "stops and says so" the plan asks for.**
The overrun is two tests, `test_media_off_asks_for_no_art_and_hides_what_an_earlier_run_cached` and
`test_speech_off_asks_for_no_clip_and_hides_what_an_earlier_run_cached`. Step 4 replaced six
`| None` guards the type checker enforced with four `config.enabled` branches that nothing
exercised: both media fixtures build with `enabled=True`, and the two tests the step renamed only
assert `.config.enabled is False` on a freshly opened object. "Media off and speech off still mean
no art request, no speech request and no cached art shown" is the phase's own done-when, and after
step 4 nothing proved it. Both new tests were checked by deleting the gate and watching them fail.
The plan's `tests` budget assumed step 4 needed no new test; that assumption was wrong.

`src` at 10,200 is within two lines of **phase 2's** target of "about 10,198". Phase 2 should
re-measure rather than chase that number: the difference came from review findings folded into this
phase (the drift rule moving into `ScenarioMeta`, `GameService.history()`, `DecisionOption`'s two
projections and a magic trailing comma), not from any phase 2 step.

### Decided off-plan

1. **`Runtime.call` had a third caller the plan missed, and deleting it broke the QA harness.**
   Step 11 says the two forwarders "exist only for the MCP path". `qa/agents.py:124` called
   `self._runtime().call(name, args)` on every scripted master tool call, so the deletion left it
   raising `AttributeError` on the first call of every QA turn. **Step 1 removed `qa/` from
   `[tool.basedpyright] include` in the same phase, so the one gate that would have caught this was
   taken down by the same commit, and the step's own proof (`import art, agents`) is import-time and
   cannot see an attribute call inside a method.** `qa/agents.py` now reads `runtime.turn` itself.
   The forwarders stay deleted: `app/mcp.py` is the only production caller and it holds the
   `Runtime` already. **Standing consequence: after this phase, a signature change in `src/` that
   breaks `qa/` surfaces only when the harness runs. Grep `qa/` by hand for every symbol a phase
   deletes, or run `uv run basedpyright qa` explicitly — it still works, it is just no longer in
   `include`.**
2. **Step 11's two test moves became one deletion and one five-line addition.**
   `tests/app/test_mcp.py::test_master_tools_over_the_mcp_endpoint` already asserted, verbatim, that
   a tool call with no turn open returns an error result carrying `NO_TURN` and that `tools/list` is
   empty between turns. Moving `test_no_tool_runs_before_a_turn_is_open` there would have duplicated
   it, and what would have been left of it in place (`assert runtime.turn is None`) is the wiring
   `CLAUDE.md` forbids testing, so it was deleted outright.
   `test_the_surface_publishes_for_the_engine_whose_turn_is_in_flight` carried one assertion nothing
   else made — a tool-less decoy engine installed *first*, so that reading `runtime.engines` instead
   of the turn would publish the wrong table — and that moved into the existing MCP test.
3. **Step 9's `check_drift` became a method, and the step went from +4 lines to −7.**
   `ScenarioMeta.drift` had exactly one caller, which did nothing but join its tuple into a
   `Refusal`. `CLAUDE.md` says a function whose first argument is one of our objects is a method, so
   the rule now lives on `ScenarioMeta.check_drift` beside the fields it compares, and `app/launch.py`
   holds no drift rule at all. The unified message says "differs from the one on disk", not the
   plan's "the selected scenario": both callers compare a save's embedded meta against the scenario
   file on disk, and the launcher path selects nothing. No test pins the prefix.
4. **Step 10 left `DecisionOption` alone.** The plan hoists `tag` and `headline` onto it, but no
   `DecisionOption` or `PendingOption` ever reads either — only `Subject` does — and `tag` had a
   single reader, `headline` itself. `Subject` now carries one `headline` property with the tag
   f-string inlined, and inherits `id`/`label`/`detail` from `DecisionOption`, which is the field
   dedup the step was for. `views.py` −8 instead of −12, `play.py` unchanged instead of +8.
5. **Step 3's stated trade, as the plan requires.** `Settings._keys_present` now lists the three
   roles as a literal. `for_name`'s `match` still flags a fourth `Role` at type-check time, but this
   literal does not: **a fourth role added to the `Role` alias in `config.py:21` would silently skip
   its api-key check.** That is the price of deleting the `get_args` reflection, and it does not buy
   a line — it buys one less piece of reflection.
6. **Two guards were kept that the plan's arithmetic deleted.** `GameService.illustrate` builds a
   `NarratorView` and a `PlayerView` and schedules a task before `Illustrator.illustrate` can return;
   with media off — the default — that is two strict model constructions and a task per turn for
   nothing, so the guard stayed at the caller. `Reader.clip` and `Reader.read` likewise now test
   `config.enabled` *before* `_planned` hashes the model and every `(voice, text)` line, which
   `newest_clip()` reaches on three render paths. `media.py` already gated before its work; speech
   now matches it. Cost: +3 lines against the plan's shape.

### Settled against the plan

Three things the plan's shape left open were settled on the cleanest reading rather than the
written one. All three were raised by the reviewers.

7. **`reject_duplicate_keys` is gone; `core/io.py:parse_unique` replaces it.** Plan step 2 called it
   "a rename and never a deletion", and the rename did make the discarded `decode` call legible —
   but it left the real hazard in place: rejecting a doubled key and validating the text are two
   steps that must always run together, and nothing said so. `parse_unique(model, raw)` does both,
   `read_model` and `spawn.ask` each call it in one line, and the pair can no longer be separated.
   The double parse stays load-bearing: strict mode reaches a tuple field only from JSON text, so
   validating `decode`'s result is not an equivalent.
8. **`Runtime.require_turn()` owns "no turn open is a refusal".** Deleting `Runtime.call` pushed
   that rule into `app/mcp.py` and `qa/agents.py` both, while step 9 of the same phase was merging
   a duplicated rule for exactly this reason. `require_turn` is not the pure forward step 11
   deleted — it resolves an optional and carries the message — and both call sites are one line.
9. **`Helping` is back in `engines/twentyfourxx/engine.py`, as a `NamedTuple`.** The plain tuple
   step 6 asked for cost two positional reads (`helping[0]`, `helping[1]`) that name nothing, which
   `CLAUDE.md` forbids. A `NamedTuple` is three lines against the frozen dataclass's six, keeps
   every read named, lets `staked.append(helping)` stay one line because it really is a tuple, and
   un-wraps `_pool`'s signature back onto one. It is the first `NamedTuple` in the tree; the shape
   is a pair used as a pair, which is what the type is for.

### Known and accepted

- **The tag and headline f-strings now exist in `core/views.py` and `engines/base.py` both.** Plan
  step 10 forbids a shared helper — "three lines to save none" — so this is a knowingly duplicated
  four lines.
- **`tests/support/table.py` asserts rather than refusing** when a tool is called outside a turn: a
  harness bug, not a refusal anyone reads.
- **`Illustrator.open` and `Reader.open` are now one-caller constructor wrappers.** Inlining them
  moves ten lines of field-reading into `Runtime._open`, already the longest method in the file.
