# PROGRESS — PLAN.md Phase 3

Baseline before Phase 3: `uv run pytest` 282 passed, tree clean at `f40c646` (Phase 2).

**Order swap:** 3.3 runs before 3.2. PLAN 3.2 gives `AuthoringTool.apply` the signature
`(WorldState, args)`, but the draft only holds a `WorldState` after 3.3. Doing 3.2 first would
need a throwaway `WorldState` wrapper around the old `ScenarioDraft` dicts.

## Step 3.1 — one character file per engine (item 11) — DONE
- [x] `Character` flat per Target shapes; `CharacterProfile`/`CharacterOverlay` deleted
- [x] `content/io.py`: `characters/<id>/<engine>.json` read/load/write; `PROFILE_FILE` gone
- [x] `begin_game` uses `character.mechanics` and refuses an engine mismatch;
      `Engine.character_mechanics` and all three `_character_mechanics` shims deleted
- [x] each `creation.create` builds `mechanics` through its own engine state model
- [x] `Illustrator.icon_dirs` is an ordered `tuple[Path, ...]`; generated icons land under
      `saves/icons`, so authored content dirs stay authored-only
- [x] `characters/kael/base.json` deleted; three full `Character` files written
- [x] full check green: 281 passed (−1: deleted overlay test), ruff, format, basedpyright
- Golden fixtures unchanged, as PLAN predicted: loner3e `twist_pack` moving out of the player
  sheet to a top-level `Loner3eState` field yields a byte-identical merged blob.
- Deviations: `core_test_support.py:character()` kept (5 live callers, now a one-liner);
  tests read `mechanics` through the engine state model, not chained `JsonValue` subscripts;
  `authoring/prompts/scenario_rules.md` reworded — it now shows the whole `mechanics` blob.

## Step 3.3 — draft on `WorldState` (item 10) — DONE
- [x] `ScenarioDraft` → `Draft{meta, player_parent_id, art_style, world}`; `Draft.scenario`
      revalidates the world, because dict writes on it skip validation
- [x] new `world/authoring.py:diff(base, draft, mechanics_merge) -> Play`
- [x] `ExitLink`, `ExtensionPatch`, `extension_patch`, `apply_patch` and helpers deleted;
      `GrowthRun.play()`, `apply_growth(play)`
- [x] full check green: 281 passed, fixtures unchanged
- Deviation from PLAN: the mechanics delta is **one level deep**, not top-level. PLAN said
  "keys of `draft.mechanics` not in `base`", which drops every added sheet — `sheets` is a
  top-level key the base already holds. The new test
  `test_a_grown_npc_brings_its_sheet_into_the_live_game` fails against PLAN's shallow version.

## Step 3.2 — authoring bar, prompts, growth trigger are engine property (item 9) — DONE
- [x] `AuthoringTool` + reshaped `AuthoringBrief` (`bar_prompt` is text, not a file name)
- [x] `world/authoring.py` gains `MIN_*`, the three `unmet` sets, `Connect`/`connect`,
      `rooms_brief`; the four scenario prompts moved to `world/prompts/`; `walk` restored to
      `world/topology.py` for the reachability rule 2.1 dropped
- [x] `Engine.authoring_brief` + `Engine.growth_due`; `authoring_instructions` and
      `authoring_context` deleted, its body kept as `authoring_guidance(text, packs, chosen)`
- [x] `authoring_toolset` wraps `brief.tools` through `Tool.from_schema`, the same way
      `turn/run.py:as_tool` wraps a Director tool; the inline `connect` is gone
- [x] harness publishes the union of every engine's authoring tools
- [x] full check green: 281 passed, fixtures unchanged
- Assembled authoring instructions are **byte-identical** to before (checked for all three
  engines x whole/opening/extend).
- Deviations: `rooms_brief` takes no `packs` — the engine closure already folds them into
  `guidance`. `blank_authoring` refuses only a real clash (same tool name, different `args`
  model) rather than PLAN's `check_tool_names`, which takes an `Engine` and checks Director
  tools; all three rooms engines share one `connect`.
- Known-inert: the "`player_parent_id` names a location" rule cannot fire through
  `scenario_refusal` today — `Draft.scenario()` refuses a null id first and `validate_rooms`
  refuses a bad placement first. It is kept because it is the rooms brief restating what
  `Scenario` gave up at 2.1, and PLAN 4.4's non-rooms engine makes the split load-bearing.

## Phase 3 done
Full check green from the repo root with `UV_CACHE_DIR` unset: 281 passed, ruff, format,
basedpyright. `src/` is 9359 lines. Golden fixtures never moved. Next: PLAN Phase 4.


## Adversarial review round (2026-08-30)

Two defects and five cuts, all fixed before commit. `src/` 9359 -> 9363 lines (the two
defect guards cost lines; the cuts paid most of it back).

**Defects**
- `patch_refusal` never guarded `patch.mechanics`. A growth pass could write `sheets.player`
  and overwrite the live character's luck/stress/twist with model-invented values, and the
  engine model revalidated the clobber as legal state. New in Phase 3: the deleted
  `ExtensionPatch` carried no mechanics at all. Now a settled second-level id gets the
  existing "the live game already holds ..." refusal, and any top-level key written whole
  (`twist`, `twist_pack`) gets the scenario-wide one.
- `write_character` refused per file, so a second person under an existing character id
  dropped their file into the first one's folder and the catalog named them wrong. Now a
  sibling file's `name` must match. That also makes `read_characters` picking `written[0]`
  honest, because every file in a folder agrees on the name.

**Cuts**
- `_start_unmet` deleted: unreachable in every path, present and future. `Draft.scenario()`
  refuses a null `player_parent_id` first, `validate_rooms` refuses a bad placement first,
  and a non-rooms brief will simply not carry the rule.
- `_mechanics_delta` moved from `world/authoring.py` to `engines/core.py:mechanics_delta`,
  beside the `mechanics_merged` it mirrors. `world/` now touches the blob only as an opaque
  value, so PLAN's "core never opens the blob" invariant holds.
- One `type Mechanics` in `state/model.py` beside the field it types; both duplicates gone.
- `rooms_growth_due` replaces three identical engine lambdas and their `frontier` imports.
- Two comments that restated their code deleted; Loner's authoring prompt swept from the
  dead `rules` dialect to `mechanics.sheets`.

**Coverage the phase had missed**
- `load_character`'s engine and id/folder refusals, and `begin_game`'s character-engine
  refusal, had no test. Added.
- Deleting `test_delta_is_the_canon_...` had removed the only proof that growth threads
  reach the live game. `_opened` is asserted again.

Not changed, deliberately: the `authoring_brief` signature comment (a Protocol would add
code to delete a legal one-line why), and character-id-as-identity, which is PLAN's design
and bigger than a fix.
