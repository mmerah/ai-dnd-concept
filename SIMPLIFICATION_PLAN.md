# SIMPLIFICATION_PLAN — executed before PLAN.md Phase 3

Decided by the maintainer on 2026-08-27 after a full read of every module plus two second opinions,
with each candidate verified against the code (line counts, call sites, schema bytes). This file is
self-standing: what ships, in what order, and what was scratched with the number that scratched it.

Verify every step with `uv run pytest && uv run ruff check && uv run ruff format --check &&
uv run basedpyright`, `UV_CACHE_DIR` unset. Baseline is 271 passing. Tests are corrected minimally
to stay green; fixtures are regenerated only where a step says so.

**The bar (maintainer's words):** a change ships if it makes the codebase smaller, or — at
break-even or a small addition — clearly more consistent or maintainable. Turn lifecycle and the
two file moves ship on the second clause. The entity split, typed authoring tools and a single
tool type fail both: each adds a concept or duplicates a shape.

Already decided in conversation and not restated below: all six harnesses stay
(`builtin`/`external`/`claude`/`codex`/`opencode`/`pi`); Director and Narrator schemas are left
alone (their only trims are eval-measured and belong to L1 in `IDEAS.md`).

## Order

Six steps, one commit each, suite green after each. Estimates are for one person.

### Step 1 — bug, docs, housekeeping (about 1 hour)

1. **`AdvanceThread` note-only update is refused.** `state/model.py:_moves_something` rejects a
   patch that sets only `note`, while the field description ("or null to keep the current note"),
   the `advance_thread` command text ("status, stage, clock, or note") and the resolver
   (`state/actions.py` applies `note` unconditionally) all allow it. Add `and self.note is None` to
   the guard and reword the error. One test. Reproduced: `AdvanceThread(thread_id=…, note=…)`
   raises today.
2. `evals/turn_eval.py` (1019 lines): one-line header noting the 1000-line file cap is waived for
   an eval script.
3. **Hidden canon in code mode: decided as trusted mode.** Builtin narration cannot see hidden
   canon by type; code mode holds it by prompt only (`codemode.py:PREAMBLE`). `README.md:86` and
   `docs/ROADMAP.md:9` already say so; `README.md:29` ("It receives no unrevealed canon") and
   `docs/MEMORY-SYSTEM.md:35-37` state it unqualified. Qualify both with "in builtin mode; code
   mode holds this by prompt". The alternative — a narrator model call inside `end_turn` — was
   rejected: it needs an API key, and code mode's standing claim is that it needs none.
4. `docs/ROADMAP.md` § Direction: drop "character sheet, journal, known-world panel" — all three
   ship (`ui/panels.py:sheet_panel`, `journal_panel`). The two "Known weaknesses" UI lines are still
   true but say "tab"; they are expansions inside the single `dev` tab now.
5. `PROGRESS.md`: delete the done sections (phases 0–2.5, single-engine, tightening); git log is
   the record. Keep the open phases and the pointer to this file.
6. `harness/codemode.py:141`: `Harness` stops calling itself a composition root; `Runtime` is
   (`app/runtime.py:338`), and CLAUDE.md says there is one.

### Step 2 — three independent model cuts (about 1 day)

**2a. Drop `engine` from the launch slug, URL and `LaunchTarget`.** A scenario names one engine
since 2026-08-26, so `(scenario, character)` determines it. `LaunchTarget(scenario_id,
character_id)`; slug `<scenario>--<character>`; route `/game/{slug}/{scenario}/{character}`.
Verified scope, narrower than first proposed:

- Goes: `LaunchTarget.engine`, the 4-segment route in `ui/app.py:257`, `new_game()`'s 3-part slug,
  `codemode._target`'s 3-part parse and its `OpenGame.slug` docstring, the
  `GameSession.__post_init__` engine-vs-target check. About 25 lines in `src/`.
- Stays: `SavedGame.engine` on disk and `_save_refusal`'s engine check (`launch.py:241` — a scenario
  re-authored onto another engine must be refused before the page opens; `test_launcher.py:110-118`
  covers it); `engine_ids`, `as_engine_id`, `EngineOption`, `catalog.badge` (the create-character
  page `/create/{engine}` and the authoring form pick an engine before any scenario exists);
  characters keep `engines` because they ship one overlay per engine.
- `LauncherController.selected_engine` becomes a derived property over the chosen scenario;
  `compatible_characters` still filters by it.
- `Runtime._open` must load the scenario **before** building the engine, since the engine id now
  comes from it; `Runtime.engine` stays memoised on `(engine_id, scenario_id)`.
- No golden fixture changes: they are keyed by `engine_ids()`, not by slug. Seven test literals
  change (`test_code_mode.py:79,93,130,359,403`, `test_launcher.py:55,135`) plus the
  `LaunchTarget(...)` constructions there. `.agents/skills/playing-aidm/SKILL.md:14` names the slug.
- `content/io.py:read_scenarios` and `evals/turn_eval.py` need no change.
- Old saves stop resuming; stated policy.

**2b. Fold `SavedGame` into `Game`.** `content/io.py:SavedGame` mirrors `state/model.py:Game`
field for field (eleven fields, `from_game`/`game()` copying each way, and `test_store.py:24`
asserting the mirror) because `mechanics` is engine-typed at run time and JSON on disk. Verified:

- `Game` becomes a `Mutable` (it is a mutable dataclass today; `player_id` is reassigned on
  succession) with `mechanics: SerializeAsAny[Mutable]`; `player_id: CheckedEntityId`, `turn:
  Field(ge=0)` and the player-playable validator move onto it. Save JSON was checked byte-identical
  on the loner3e opening state — no fixture regeneration.
- `committed()` does **not** collapse to one `model_validate`: `Mutable` is `extra="forbid"`, so
  validating the whole dump against the base type rejects every engine field. Keep re-validating
  `mechanics` through `type(self.mechanics)`; `world` and the rest go through `Game`.
- `FileStore.load` returns raw JSON; `Engine.restored(raw)` validates `raw["mechanics"]` with
  `mechanics_type`, then `Game.model_validate`. The launcher reads five fields of a save before any
  engine is built (`launch.py:193-195,218-223,241`): give it a five-field `SaveHeader` model
  (`engine`, `scenario_id`, `character_id`, `scenario`, `turn`, plus `mechanics` for the parse
  check) rather than dict access under strict pyright.
- All 17 `SavedGame.from_game(x)` call sites collapse to `x`. Net about −40 lines and one concept.

**2c. `Engine.pack_type` required.** Both shipped engines and both planned ones ship packs, and
`PackSources.load` already refuses a source set without `srd`, so "an engine that plays no packs"
is a dead branch. Ships: `pack_type: ClassVar[type[BaseModel]]` with no `None`; the base
`__init__` loads `self.packs = sources.load(self.engine_dir / "packs", self.pack_type)` (both
subclasses read `self.packs` only after `super().__init__`); the `"plays no content packs"` branch
of `pack_refusal` goes. Two things the first proposal got wrong, verified:

- `pack_models()` stays as the one-line narrowing override (`Mapping[str, Pack]`): a base-declared
  `self.packs: Mapping[str, BaseModel]` reassigned narrower is a strict-pyright override error, and
  a generic `Engine[P]` is more type plumbing than the method it replaces.
- `authoring/draft.py:installed_pack_ids` is **not** replaced by listing file stems:
  `PackSources._from_files` skips a pack that fails to parse, so a stem list would offer an
  unloadable pack in the create-scenario dropdown. It stays (it lists what loads).
- `tests/core/test_engine.py:BareEngine` gains a `packs/srd.json` under its `tmp_path`;
  `test_engine_contract.py:Undeclared` declares `pack_type`.

### Step 3 — delete the Advisor role (about half a day)

The largest deletion; it removes two MCP tools and a session state before Step 4 touches the
harness, so it goes first.

**Today** a third LLM role turns "raise Shooting" into a typed proposal: `advisor_agent`,
`AdvancementContext`, `render_proposal`, `turn/prompts/core_advisor.md`, per-engine
`advancement.md`; `Advancement.offers/resolve/advance_refusal`, `AdvancementOffer`,
`DraftedAdvance`, `GameSession.offers/advancement_offered/propose/preview/apply_proposal`, the
advancement tab (`ui/panels.py:130-214`), `propose_advance`/`apply_advance`/`AdvanceArgs` in the
harness, `AdvanceApplied`, `Roles.advisor`, `test_proposals.py`, six golden fixture files. Counted:
about 442 production lines and 308 test/fixture lines.

**Ships:**

1. `ProposalBase` gains `subject_id: CheckedEntityId`; the engines' proposal types inherit it.
2. `engines/core.py:advance_command(advancement) -> Command`, built with `rule(...)` so `rng`
   reaches 24XX's credit roll. The resolver refuses when
   `earned(state) <= ledger(state, subject_id).current` — the same deterministic check `offers()`
   makes today — then runs `grant` and moves the ledger. The Director's toolset already retries a
   `ValueError` twice with the engine's message, which is the retry loop the advisor had. The
   command description carries the engine's rules text for the advance, so it rides on the tool,
   not on every turn's `director.md`; keep it to the rule.
3. Each engine adds `advance_command(self.advancement)` to `director_commands`. Cairn and Fate do
   the same when they land — one line instead of `proposal_type`/`ledger_key`/`occasion`/
   `offer_text`/`spent_why`, an `advancement.md` and a golden proposal fixture. Each still writes
   its `grant` (Cairn: one trait; Fate: lateral move plus stress-track resize) as its plan says.
4. `Advancement` keeps `ledger_key`, `ledger`, `earned`, `grant`; `offers`, `resolve`,
   `advance_refusal`, `AdvancementOffer` go.
5. When an advance is owed and `state.pending is None`, the two callers of
   `SceneSnapshot.from_game` (`turn/run.py:204`, `codemode.py:197,221`) append one `NOTES FROM THE
   RULES` line per owed subject — `"<name> <occasion>. <rules text> Call advance when the player
   asks."` `from_game` has no engine, so the note is built beside `take_notes()`, not inside it.
   The pending gate is the same one `GameSession.offers()` applies today.

**Deletes** everything listed under "today", the code-mode advance tests, and the
`advisor.txt`/`proposal.json` fixtures. One replacement test: note appears when owed → `advance`
lands → refused when not owed. `engines/core.py` drops about 66 lines.

**Accepted losses, recorded so they are not re-filed as bugs:** the confirm-before-commit dialog
(an advance is the one permanent sheet write with no undo; the Director may ask in prose first,
nothing enforces it), and a separate model config for advancement (it now runs on the Director's
budget, which already judges `position`, `edge` and `hindered`).

### Step 4 — one turn lifecycle, then the MCP wrapper types (about 1 day)

**4a. One turn lifecycle.** `turn/run.py:run_segment` and `harness/codemode.py:Harness.start_turn/
call_director_tool/end_turn` both sequence `consume_answer → DirectorContext + run_command →
close_segment`. Verified: the verbatim duplication is the eight-line `DirectorContext(...)` literal
plus three calls — about 12 lines — so net LOC is roughly zero. It ships because it leaves one
lifecycle and one composition root. Design, with the constraints the code imposes:

- A `Turn` in `turn/run.py`: `begin(engine, state, input, rng, commit) -> Turn`,
  `Turn.call(name, raw) -> str`, `Turn.finish(lines) -> Game`. `run_segment` becomes begin →
  director agent drives `Turn.call` → narrator → finish. `Harness` holds one `Turn | None` and
  forwards; its own `Turn` dataclass and `started()` go.
- `turn` may not import `app` (`tests/core/test_package_boundary.py:9`), so `Turn` holds a
  `commit: Callable[[Game], None]`, never a `GameSession`. Builtin passes a no-op and commits once
  in `GameSession.submit`; code mode passes `session.commit` and keeps its per-call commit (crash
  safety; the viewer reads the save).
- `Turn.picture()` covers `render_director` only; `WAITING ON THE PLAYER` and `GROWTH DUE` need
  `session` and stay in `Harness._picture`.
- `take_notes()` is destructive: notes live on the `Turn` so `scene()` re-renders them mid-turn
  (`test_code_mode.py:271-293`).
- One draft per turn. Code mode re-drafts committed state per call today; with one draft the
  per-call revalidation moves to commit. Equivalent, but a semantic change: `test_pipeline.py`'s
  "a director run that fails discards what the earlier tool call did" must still pass for builtin.
- `as_tool`'s deps type becomes `Turn`; `DirectorContext` is built per call. Code mode's
  `TurnTrace` still carries no `steps`; do not make the two uniform.
- `tests/core/test_succession.py` calls `close_segment`/`consume_answer` directly; keep them as
  module functions `Turn` uses.

**4b. MCP wrapper types.**

- `StartTurn.prompt` is silently discarded when `option_id` is set (`codemode.py:219`; the exchange
  records the option label). Replace `StartTurn` with `state/play.py:Answer`, which already
  enforces exactly-one-populated — after adding field descriptions to `Answer`, which has none
  (`ToolArgs` only works through attribute docstrings).
- `EndTurn(lines)` is `Narration` with a different name; publish `Narration`.
- `Summary` on `finish_growth`/`finish_scenario` is read by nobody: it is prefixed onto the string
  returned to the agent that wrote it. Both tools take `NoArgs`; `finish_scenario` already returns
  `summarize(scenario)`, `finish_growth` returns the fact trace. The builtin scenario agent's
  `ToolOutput(str, name="finish")` loses its string for the same reason. Update
  `.agents/skills/authoring-aidm/SKILL.md` and `growing-aidm/SKILL.md` where they name the argument.

**4c. One guard, not one tool type.** The three tool shapes (`Command`, `ServerTool`, the
authoring `FunctionToolset` closures) stay — see Scratched. The one real hole closes: `ServerTool`s
with no args ignore `raw`, so junk arguments pass silently. Route them through
`NoArgs.model_validate`.

### Step 5 — authored JSON and two file moves (about 2 hours)

**5a. Authored JSON without defaults.** `write_scenario` and `ScenarioDraft.as_json` (the readback
the authoring agent sees) dump every default and null. Add `exclude_defaults=True,
exclude_none=True` to both, authored content only; saves stay explicit. Measured: the readback
shrinks 10–17%; every lean dump re-validates; `Scenario.packs` has no default so it is always
written. **Do not regenerate the shipped `world.json`s** — they are hand-formatted (`"packs":
["srd"]` on one line) and a machine dump makes whispering-vault larger, not smaller. Known
tradeoff: a field the agent set explicitly to its default disappears from the readback.

**5b. `whole_text` and PDF extraction** move from `content/io.py` (34 lines and the only `pypdf`
import) to `authoring/draft.py`, their one caller. `tests/core/test_sources.py:5` follows. Pure
move, legal under the package boundary.

**5c. `engines/sheets.py`** takes `SheetBase`, `SheetMechanics`, `SheetAdvancement`,
`SheetEngine` **and** `complete_chapter`/`chapter_command` — they call `SheetMechanics.of_game`,
so left behind they make a cycle. 151 lines out; `core.py` lands near 490 after Step 3. Six import
sites change. A `game/` package holding `Game`, `GameSession` and `Turn` is not planned: only if
the tree still reads wrong after Step 4.

### Step 6 — close

Mark the steps done in `PROGRESS.md`; then PLAN.md Phase 3.

## Scratched, with the number that scratched it

Recorded so they are not re-proposed.

- **Split `Entity(kind=…)` into `Location` / `Actor` / `Item`.** 45 `kind` sites in `src/`; the
  split deletes about 25 lines of guards (`check_placement`, the exits guard) and adds about 61 —
  a shared base, three subclasses, discriminator plumbing — then rewrites 14 `require_kind` sites
  one-for-one as `world.actor/location/item`, because ids arrive from the model as bare strings
  and every consumer still narrows. `kind` stays in the JSON as the discriminator, so scenarios do
  not shrink. The "bad combinations" it would forbid are ones the engines use: 24XX starships are
  locations that hold items (`buy_gear onto_id`), and Loner gives an item a sheet when it is fought
  (`loner3e/rules.py:207`). Cairn and Fate need the opposite: `plans/L6:20-26` puts item mechanics
  on `traits`, `plans/L5:18-20` puts aspects on `traits` of an actor, a location or an item alike.
  Net +40..80 lines, ~55 touched sites, no new capability.
- **Typed authoring commands (`put_location`/`put_actor`/`put_item`/… instead of
  `write(ScenarioPatch)`).** Measured: 4 tools → 9; the write/patch/apply path ~180 lines → ~270,
  with `_upsert`/`_index`/`connect` all surviving; `schema_of(ScenarioPatch)` is 3 681 bytes and
  the per-kind args models sum to 5 673, because JSON Schema restates the shared fields per model
  (a discriminated union measures 4 625). The prompt spends two lines, not a section, on which
  field belongs where (`scenario_world.md:17,24`), and `exits` is never written through `write`
  at all — `connect` owns it. Growth's `patch_refusal` is one whole-patch check that would become
  five. Without the entity split above it is also a second, hand-synced copy of `Entity`.
- **One tool type across director, server and authoring tools.** `Command.call` takes a
  `DirectorContext`; server tools take a `Harness`, authoring tools a `ScenarioDraft`. Unifying
  needs `Command[D]` through six modules, a dead `during_suspension` on every non-director tool,
  and explicit args models for the authoring closures that today get their schema from docstrings
  (they do **not** go through `schema_of`). The deletable wrapper is 26 lines; the refactor adds
  30–60. Step 4c keeps the one guard worth having.
- **State-dependent MCP tool surface.** Already implemented: `Harness.started()` refuses a director
  tool outside a turn, `run_command` refuses during a suspension, `offered()` is dynamic per open
  game and `send_tool_list_changed` is sent (`mcp.py:196`). The only unimplemented part — hiding
  the authoring tools until a run opens — is blocked by the Claude SDK bridge dropping
  `list_changed` (`harness/claude.py:40-45`), and a call without a run is refused anyway.
- **`Engine` as composition instead of `SheetEngine` inheritance.** `SheetEngine` is generic in
  the sheet type and `Engine` is not, so `runtime`, `mcp`, `world` and `turn/run` type against
  `Engine` without a parameter. Fate and Cairn both subclass `SheetEngine` in their plans, which
  was the only condition for revisiting.
- **A full `domain/rules/application/adapters` tree.** The chain
  `state ← content ← engines ← turn ← authoring ← app ← harness ← ui` is enforced by
  `test_package_boundary.py` and was reorganised twice in August; directory moves alone buy
  nothing. Steps 5b and 5c are the two moves that do.
