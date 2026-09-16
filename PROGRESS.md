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

## Phase 2: the engines, the leak scan and the test prune

Landed the five steps that touch an engine's tool table, the worldsmith renderers and the
hidden-name scan, then pruned the wiring tests and the triple-covered rules.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,200 | **10,182** | about 10,198, at most 10,208 |
| `tests` | 12,260 | **12,145** | about 12,122, at most 12,150 |
| `qa` | 2,104 | **2,104** | unchanged |

`tests` lands inside the plan's cap even though phase 1 started it 30 lines above the plan's
assumption; `src` is 16 under target. Neither number is padded and the arithmetic is exact:
`src` is 10,200 minus step 1 (−3), step 2 (−11) and the five cuts the reviews added (−8), plus
step 3 (+2) and the `world_of` rename (+2). `tests` is 12,260 minus the prune (−113, five more than
the plan's −108 because part A's rewrites orphaned four imports) minus the two signatures the
review's `world_of` cleanup collapsed (−2).

### Decided off-plan

1. **The scan's self-exclusion rule changed from map key to `id`, as `PLAN.md` step 3 requires be
   recorded.** `scenes/worldsmith.py` used to exclude an entity from its own watcher set by **map
   key** (`other != entity_id`); `leaked_names` excludes by **`other.id`**, which is what the rooms
   original did. The two agree for every well-formed draft. They can disagree only about a misfiled
   cast entry — one whose key is not its `id` — which reaches the scan because `scene_unmet` appends
   "cast entries under their own id" **without returning early**. Such a draft is refused either way,
   so the change cannot leak a spoiler; excluding by `id` is the correct rule and the one kept.
2. **`rest` was an eighth pure forwarder and the plan's inventory missed it.** `PLAN.md` step 2
   names seven methods to dissolve and six to leave alone with a measured reason.
   `TunnelGoonsEngine.rest` is in neither list, resolves no id and rolls no dice, and as
   `master_tool("rest", REST, NoArgs, lambda d, _a, _: world_of(d).rest())` the registration is 83
   columns — well inside the 110 the plan measured as the cut-off. Dissolved with the other seven.
3. **`Engine.master_tools`'s `shared` local, its annotation and the `hires` branch all went.**
   Step 2 had to annotate `shared: tuple[MasterTool[G], ...]` so the checker could solve `G` for an
   untyped lambda. Returning the tuple directly lets the method's own return annotation do that
   work, and the `hire` tool appends as `*((...,) if self.hires else ())` on the registration line.
   The annotation step 2 added is gone, and the method is two lines shorter than the plan's shape.
4. **`Engine.opening_sections` was orphaned by step 1 and is deleted.** `render_opening` was the
   seam's only reader; both families declare the attribute themselves and now pass it positionally
   at their own call sites, so the seam was declaring a contract it neither used nor enforced.
5. **The bound getter is `world_of`, not `world`.** The plan writes `world = self.world_of`, but
   `self.world` already means the world *type* in the same classes (`scenes/engine.py:82`,
   `rooms/engine.py:56`) and `world` means a world *instance* in twenty other methods. One
   identifier for a type, an instance and a function is the naming `CLAUDE.md` forbids. Cost: +2
   lines, because `meanwhile`'s registration crosses 100 columns and ruff wraps it.
6. **Step 2 opened a coverage hole and it is closed.** Moving every `move` test below the tool layer
   left nothing checking that the new lambda forwards `a.with_ids`: writing `world_of(d).move(a.to_id,
   ())` type-checks and keeps the whole suite green. `tests/tunnelgoons/test_tools.py` now drives one
   `with_ids` case through `change(ENGINE, draft, "move", ...)`; breaking the lambda on purpose was
   confirmed to fail it.
7. **`SceneEngine.glossary` is gone; `Loner3eEngine` overrides `master_sections` instead.** It was
   a hook returning `()` with one implementer, which `CLAUDE.md`'s "do not add an abstraction until
   two things need it" forbids. The glossary section was last in the family's tuple, so appending it
   after `super().master_sections(state)` keeps the prompt's section order — the loner3e `master.txt`
   golden is unchanged, which is the proof. The maintainer settled this against the reasons recorded
   below, which are kept for the record: `master_sections` no longer shows the whole section order in
   one place, and `sheet_sections` beside it is the identical hook shape with two implementers, so
   the family's two section hooks now differ in kind. Net −3.
8. **Three tests were renamed for what is left of them**, two by the plan's own rule and one beyond
   it. `test_the_familys_tools_are_offered_in_order` became
   `test_a_member_joins_and_leaves_the_party`;
   `test_the_master_is_shown_the_hidden_canon_and_the_tags_in_play` became
   `test_the_master_is_shown_the_whole_cast_met_or_not` — not "hidden canon", because `a ledger` is
   injected with `known=True` and only `The Secret` is hidden;
   `test_the_bar_refuses_a_scene_that_lists_the_player_or_the_party` became
   `..._lists_a_party_member`, since the player half went with the block the prune deleted.

### Refuted, with the reason

- **`TwentyfourxxEngine.hire_check` stays.** It is not a forwarder: it resolves
  `self.packs.chosen(draft.packs)` once, outside the closure it returns. Inlining the lambda moves
  that work inside the check, which the worldsmith runs again on its one retry.
- **`RoomEngine.starting_items` and `TwentyfourxxEngine.world_of` stay**, on the reviewers' own
  measurements: the first has no net cut (tunnelgoons would duplicate `new_game`'s body instead),
  and the second needs a world type parameter on `SceneEngine` — more generics, not fewer, which is
  `PLAN.md`'s "Not built" P3(a).
- **The `_ =` discard prefixes stay.** 267 of them across `tests/`; `reportUnusedCallResult` is off
  and no ruff rule asks for them, so they are a repo-wide convention to settle on its own, not this
  phase's to unwind.
- **Six forwarders stay, as the plan measured.** `kill` because `twentyfourxx/engine.py` overrides it
  to run `_succession`, and a seam lambda would drop that in silence; `join_party` (111 columns),
  `leave_party` (115), `move_item` (111), `ship_upgrade` and `use_med_kit` because past 110 columns
  ruff breaks a registration one argument per line, so the lambda costs more than the method.

### Known and accepted

- **`tests/core/fixtures/` did not move**, which is what every step in this phase was shaped to
  guarantee: same tool names in the same order with the same schemas, and the four `worldsmith.txt`,
  `master.txt`, `narrator.txt` and `turn/*.json` goldens byte-identical to the phase 1 commit.
- **`take_lead`'s lambda is reached by no test through the tool table**, and neither was the method
  it replaced. `tests/twentyfourxx/test_world.py` tests `world.take_lead` and
  `schemas/twentyfourxx/master_tools.json` pins the registration; this is a pre-existing gap the
  phase neither widened nor closed.
- **The QA harness plays all four shipped scenarios with 0 issues** (`qa/run_all.sh loner goons
  breathless 24xx`), which is the only check that drives the rewritten tool table end to end,
  including 24XX succession. `qa/` references none of the deleted symbols and `uv run basedpyright
  qa` is clean — the phase 1 standing consequence, checked by hand as it requires.
