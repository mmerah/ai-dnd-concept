# PROGRESS

Tracks `PLAN.md`. One section per phase; closed phases are recorded in git history, not here.

## Phase 2.9 — simplification pass — in progress (Steps 1–2 done)

`SIMPLIFICATION_PLAN.md`, six steps, decided 2026-08-27 with every candidate verified against the
code. Ships: launch loses `engine`, `SavedGame` folded into `Game`, `pack_type` required, Advisor
role deleted, one turn lifecycle, MCP wrapper types, note-only thread bug, authored JSON without
defaults, two file moves, housekeeping. Scratched with numbers recorded there: entity split by
kind, typed authoring tools, one tool type, stateful MCP surface, engine-as-composition.

### Step 1 — bug, docs, housekeeping — DONE

- `src/aidm/state/model.py`: `AdvanceThread._moves_something` accepts a note-only patch (added
  `and self.note is None` to the guard, reworded the error to name "its note").
- `tests/core/test_actions.py`: added a note-only `AdvanceThread` round-trip test;
  `tests/core/test_pipeline.py` updated the one assertion that matched the old error text.
- `evals/turn_eval.py`: one-line header noting the 1000-line file cap is waived for this eval
  script.
- `README.md` and `docs/MEMORY-SYSTEM.md`: qualified the Narrator's "no unrevealed canon" claim as
  builtin-mode only — code mode holds it by prompt, not by type.
- `docs/ROADMAP.md`: dropped the stale "UI growth" bullet (character sheet, journal and
  known-world panel all ship in `ui/panels.py`); the Trace/State weaknesses now say they are
  expansions inside the `dev` tab, matching `ui/game.py`.
- `PROGRESS.md`: deleted the DONE phase sections (Phase 0, Phase 1, Phase 2, Single-engine
  scenarios, Phase 2.5, Tightening round); git history is the record.
- `src/aidm/harness/codemode.py`: reworded the `Harness` docstring off "composition root" (that's
  `Runtime`, `app/runtime.py:338`) to what it is: one game, one lock, one turn in flight.
- Verified: 277 passing, `ruff check`, `ruff format --check`, `basedpyright` clean.

### Step 2 — three independent model cuts — DONE

Done in order 2c → 2a → 2b, smallest first, as the plan specifies.

- **2c, `pack_type` required** (`src/aidm/engines/core.py`): `pack_type: ClassVar[type[BaseModel]]`
  with no `None`; `pack_models()` is abstract; the `"plays no content packs"` branch of
  `pack_refusal` (`authoring/draft.py`) is gone. Engines keep loading their own typed `self.packs`
  — loading in the base was tried and reverted: a narrowed `packs` override is a strict-pyright
  error, and the only way round was a `cast` in each engine.
  - `tests/core/test_engine.py` `BareEngine` and `tests/core/test_engine_contract.py` `Undeclared`
    declare `pack_type` and an empty `pack_models()`.
- **2a, engine dropped from the launch slug** (`src/aidm/app/launch.py`): `LaunchTarget` loses
  `engine`; slug is `<scenario>--<character>`, `path` is `/game/{slug}/{scenario}/{character}`.
  `LauncherController.selected_engine` is now a derived `@property` over
  `catalog.scenario(selected_scenario).engines[0]`; `_select_engine()` is gone; `new_game()` and
  `resume()` no longer take or pass an engine.
  - `app/runtime.py`: `GameSession.__post_init__` drops the `engine.id != target.engine` check
    (the field no longer exists); `Runtime._open` now loads the scenario before building the
    engine (`engine = self.engine(scenario.engine, target.scenario_id)`), since the engine id
    comes from the scenario now.
  - `ui/app.py`: the game route drops from 4 segments to `/game/{slug}/{scenario}/{character}`;
    `as_engine_id` stays imported only where `/create/{engine}` still needs it.
  - `harness/codemode.py`: `_target` parses `<scenario>--<character>` (2 parts); `OpenGame.slug`
    docstring updated to match.
  - `.agents/skills/playing-aidm/SKILL.md`: slug example updated (`.claude/skills` symlinks
    to it).
  - Stayed, per plan: `SaveOption.engine`, `_save_refusal`'s engine check, `engine_ids`/
    `as_engine_id`/`EngineOption`/`catalog.badge`, characters' `engines`.
  - Test literals: the 7 locations the plan named in `test_code_mode.py`/`test_launcher.py`, plus
    the same mechanical `LaunchTarget(...)` drop in `test_settings.py` and
    `loner3e_test_support.py` (not named individually in the plan, same shape).
- **2b, `SavedGame` folded into `Game`**:
  - `src/aidm/state/model.py`: `Game` is a pydantic `Mutable`, not a dataclass —
    `mechanics: SerializeAsAny[Mutable]`, `player_id: CheckedEntityId`, `turn: Field(ge=0)`, and the
    player-playable check as `@model_validator(mode="after")`. `committed()` revalidates `mechanics`
    on its own concrete type first (`Mutable` forbids extra fields, so a whole-dump validation would
    reject every engine field), then validates the rest through one `Game.model_validate` over a
    dump with `mechanics` excluded and the revalidated instance reattached.
  - `src/aidm/content/io.py`: `SavedGame`/`from_game`/`game()` deleted. `FileStore.save(slug, state:
    Game)` dumps directly; `FileStore.load(slug) -> str | None` returns raw file text. New
    `SaveHeader(extra="ignore")` holds the six fields the launcher reads before an engine exists:
    `engine`, `scenario_id`, `character_id`, `scenario`, `turn`, `mechanics`.
  - `src/aidm/engines/core.py`: `Engine.restored(raw: str) -> Game` parses the JSON, validates
    `mechanics` through `self.mechanics_type`, then `Game.model_validate` with that substituted.
  - `src/aidm/app/launch.py` and `app/runtime.py` read a `SaveHeader` wherever they need a save's
    engine before building one; `GameSession.commit`/`ui/panels.py:state_panel` save/dump `state`
    directly. All 17 `SavedGame.from_game(x)` call sites collapsed to `x` (or to
    `x.model_dump_json()` at sites that needed raw JSON for a round trip or a diff).
  - Deviations: `tests/core/test_store.py`'s field-mirror test is deleted, per the plan.
    `tests/core/test_code_mode.py:_saved` and `test_extension.py` now route a loaded save through
    the open session's `engine.restored(...)` before reading `.world`/`.pending`/etc., since
    `store.load` returns raw text and only an engine's `mechanics_type` can turn that back into a
    `Game`. `tests/core/test_session.py` and `tests/ui/test_launcher.py` swap the generic
    `updated()` helper for `state.model_copy(update={...})` on `Game` specifically: `updated()`
    round-trips through a plain dict, which hits the same `Mutable`-forbids-extra-fields wall as a
    naive `committed()` would have. `test_launcher.py`'s stale-save test moves its corruption from
    `history` to `scenario.premise`: `SaveHeader`'s six-field read no longer parses `history` up
    front, so that field's staleness now surfaces at resume (`Engine.restored`) instead of at the
    catalog listing — an intentional narrowing from the plan, not a regression.
- **Adversarial review (Opus), fixes applied:** the catalog now parses a save whole through
  `engines/core.py:parse_save` (header-only parsing had let a corrupt body reach `/game`), and
  the stale-save test corrupts `history` again; `Engine.restored` owns the wrong-engine check, so
  `GameSession` parses the file once; `SaveHeader` drops `mechanics`; `pack_type` is probed at
  build like `mechanics_type`; `check_player_playable` inlined into `Game`'s validator; tests use
  `.committed()` instead of the non-validating `model_copy`; `_saved` helper reads the store off
  the harness; stale "engine and character" wording in README, the home page and `plans/L3`.
- Verified: 276 passing, `ruff check`, `ruff format --check`, `basedpyright` clean.

## Phase 3 — L6 Cairn Barebones — not started (after Phase 2.9)
## Phase 4 — L5 Fate Condensed — not started
