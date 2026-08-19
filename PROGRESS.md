# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 — simplification

- Step 1 — stale eval results deleted. `evals/results/` holds only `step-11-baseline.json`.
- Step 2 — memory system and Worldkeeper deleted. A turn is Interpreter -> Director -> hooks ->
  Narrator; the conversation window is unbounded. `SAVE_VERSION` 81 -> 82. `docs/MEMORY-SYSTEM.md`
  records the shape a re-implementation takes.
  - Trap found, then half-undone. Folding a deleted memory into an entity's `brief` leaked
    canon and `test_pipeline` caught Elena's name in player prose — but only because it was
    folded into **Mara**, who is `known`. `VisibleScene.of` builds the Narrator's view from
    `player`/`location`/`inventory`/`here`/`known_elsewhere`, all `known`-filtered, so a hidden
    entity's `brief` reaches the Director and Interpreter and never the Narrator. The Mara/Elena
    line now lives on `elena.brief` (`known: false`); the golden `narrator.txt` not moving when
    it was added is the standing proof. `Thread.note` and `Hook.note` are Director-only too.
- Step 3 — `Resolution` deleted; a `Play` returns `tuple[Fact, ...]`. `check_draft` could not go
  in `transact.py` as planned: `advancement -> transact -> engine -> advancement` is a real cycle.
  It ended up in `state/world.py`, beside the `draft()` and `committed()` it wraps. PLAN's reason
  for hoisting it into `engines` — that `state/hooks.py` imported it — was false; nothing did.
- Step 4 — `TurnLog.fired` and `Resolved` deleted; `apply_to_draft` returns `tuple[Fact, ...]`.
  The hooks trace step filters `fact.kind.startswith("hook")` over `log.facts`. The reveal and
  thread-advance facts a hook causes stay in `turn.facts`, so showing only the markers is a
  dedupe. Note the missing underscore: `hooks_capped` does not match `hook_`, and filtering on
  the longer prefix silently hid the one signal that a hook chain was truncated.
- Step 5 — the trace is in-memory only. No `.trace.jsonl`, no `save_version` on a trace entry,
  no version gate on it. `SAVE_VERSION` unchanged: the save's own bytes did not move. The Trace
  tab reads `GameSession.entries`, which now starts empty each session. Nothing reads or unlinks
  an existing `saves/*.trace.jsonl` any more, `discard` included: delete them by hand once.
- Step 6 — `begin_game` and `build_engine` live in `app/registry.py`, beside the `engine_class`
  they build on. Nothing under `app/authoring/` imports `app.session` any more, which was the
  point; the interim `app/newgame.py` was deleted in the review pass.
- Step 7 — each engine is six modules; `tools.py` folded into `actions.py`, `director_toolset`
  last. `mechanics.py` stays: merging it would make `actions.py` and `rules.py` import each other.

### Phase 1 review pass

An adversarial review of the staged phase found one bug and ~120 lines the phase walked past.
All applied:

- The `hooks_capped` filter bug above.
- `engines/checks.py` deleted — one 19-line function alone in a module.
- `app/views.py::JournalView` deleted. Step 2 took its third field and left a two-field wrapper
  every caller immediately unwrapped — the same shape as the `Resolution` step 3 removed. A
  deletion that removes a field should check whether the container still earns itself.
- `app/newgame.py` folded into `app/registry.py`.
- `state/trace.py`: no `TraceEntry` is serialised since step 5, so the Pydantic discriminator
  went. `Applied.entry` was only ever read as a display label.
- The Mara/Elena line restored to `elena.brief`.
- A per-role `max_input_tokens` ceiling (`RoleConfig`, default 96k) checked before each model
  call in `run_turn`. `UsageLimits(count_tokens_before_request=True)` cannot do this here:
  `OpenAIChatModel` — the only model class aidm builds — inherits `Model.count_tokens`, which
  raises `NotImplementedError`, and the one override that exists (`OpenAIResponsesModel`) needs
  a network call. The guard estimates locally at 4 chars/token instead.

Not applied, still on the bone: the duplicated `transact` call in `session.py::preview` and
`apply_proposal`, `FileStore.load` reading and parsing the save twice, two pass-through
re-exports. `docs/ui-mock/index.html` still specifies a "Known memories" panel and a
`WORLDKEEPER` pipeline stage, and is the accepted Phase 5 UI reference.

Offline gate green throughout: 195 passed, ruff check, ruff format --check, basedpyright 0/0/0.
`src/` went 7,565 -> 7,277 lines across 65 files, a 3.8% reduction. Step 2 is 70% of it: the
memory deletion bought roughly a second off a 5.6s turn, and 192 lines came along. On tokens it
is a wash — the unbounded window overtakes the deleted round-trip's cost around turn 11, which
is what the new ceiling now fails loudly on.

## Next

Phase 1's two live checks are still outstanding — both need network and a maintainer at the
keyboard:

- `uv run python evals/turn_eval.py run --label phase1-no-memory` against `step-11-baseline`.
  A drop of one case at n=9 is noise; a drop across cases is not.
- `uv run aidm`: start a game, play three turns, resume it. Steps 2 and 5 both changed what a
  resume reads.

PLAN.md still holds the Phase 1 section; move it out once those two pass.
