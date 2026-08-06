# Collapse refactor — progress

Plan: `PLAN.md`. One section per phase; each ends green on
`uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.

## Phase −1 — green committed tree — DONE

- The in-flight work landed as its own commits (`f71aa7c`, `13804fc`); the tree at HEAD is green
  (100 tests). No fixture was cut before that.

## Phase 0 — behaviour locks — DONE

- `tests/core/golden_test_support.py`: `golden()` / `golden_json()` compare against a checked-in
  fixture, reporting a unified diff on drift, and rewrite only under `AIDM_GOLDEN_REGEN=1`.
  `tests/conftest.py` fails any run with that variable set, so a switch left exported in a shell
  cannot turn the locks into a rubber stamp. Regenerate in the commit that justifies the change.
- `tests/dnd5e/test_content_parity.py` + `fixtures/mechanics_parity.json`: `SpellFacts`/
  `WeaponFacts` for all 319 spells and 37 weapons of the shipped pack (1 weapon types to null).
  This is the Phase 4 gate and outlives the refactor.
- `tests/core/test_golden_state.py` + `fixtures/state/{story,dnd5e}.json`: the initial `GameState`
  JSON per engine, plus the `SAVE_VERSION` assertion. **Version is 28, not the 27 PLAN.md names**
  (the landed commits bumped it); Phase 4 is still the only phase that may move it.
- `tests/core/test_golden_prompts.py` + `fixtures/instructions/<engine>/*.txt`: assembled
  instructions for all five roles (director, narrator, maintainer, creator, advisor) per engine,
  read off the built `Stage`s, plus the rendered advisor prompt in `fixtures/prompts/`.
- `tests/core/test_golden_turn.py` + `fixtures/{prompts,turn,save}`: one scripted turn per engine
  (`FunctionModel` stubs, `Random(11)`) — the same fiction resolved by each engine's own action.
  Locks the four rendered turn prompts, the `Turn` trace JSON, and the post-turn save JSON. The
  turn runs from a state carrying two exchanges, and covers a roll, branch selection, an
  unconditional effect, history rendering, and one created entity.
- `tests/core/test_golden_schemas.py` + `fixtures/schemas/`: the plan type's JSON schema and the
  director toolset's tool definitions per engine, plus the `Growth`/`EntityDetail`/`SheetDelta`
  schemas. Added after review found that field descriptions and the `read_content` docstring —
  all model-facing, all touched by Phases 1-2 — could change with the whole suite green.
- Shared stubs (`plan`, `text`, `structured`, `scripted`) and the `game(engine_id)` builder moved
  into `core_test_support.py`; `test_pipeline.py` imports them instead of holding its own.
- Each lock was proven falsifiable: a prompt edit, a resolver constant change, a parser change, and
  three field-description edits each fail their own fixture and nothing else.
- Gate green: 115 passed, ruff clean, basedpyright 0 errors.

## Phase 1 — collapse the generic — DONE

- `core/sheet.py`: `Sheet(Mutable)` declares `kind: Kind` first, so the serialized field order is
  what inheriting from `EngineRules` produced. `core/world.py`: `EngineRules`, `BareLocation` and
  `rules_of` deleted; `Record.rules: Sheet` (no `SerializeAsAny`); `Record`, `WorldState`,
  `GameState` lost the type parameter. The transaction and every validator are untouched.
- **Not in PLAN.md, forced by the import graph:** `sheet_of`/`player_sheet` moved from `sheet.py`
  to `world.py`. With `Record.rules: Sheet`, `world` imports `sheet`, so `sheet` may no longer
  import `world`. Import lines changed in 17 files; the two bodies are now one attribute read.
- De-genericized across `core/` (`effects`, `plan`, `content.compose_world`, `engine`,
  `enginepack`, `store`), `workflow/`, both engines, `scripts/evals/`, and the tests.
- `Engine.state_type` deleted with the generic it erased: call sites construct `GameState(...)`
  and `GameState.model_validate_json(...)` directly. `FileSaves.load(slug)` drops its
  `state_type` parameter for the same reason.
- `registry.AnyEngine` + its `cast` deleted; `build_engine` returns `Engine` and keeps the
  `isinstance` check on the plugin's `object`-typed build.
- `dnd5e/advance._level_ref` is now public `level_ref`; `scripts/evals/probes.py` imports it
  instead of carrying its own copy, and its `_sheet` re-narrowing is gone.
- Only erasure-shaped test removed: `test_a_record_may_not_hold_another_engines_payload` (with
  `ForeignRules`) — with one concrete payload there is no foreign payload to refuse.
  `test_package_boundary.py` needed no change.
- Review pass: `story_game`/`dnd5e_game` now delegate to `game(engine_id)` — their reason to
  exist was the `Sheet`-typed return the collapse erased; `compose_world` lost its always-
  `WorldState` `world_type` parameter; two now-redundant `GameState` annotations deleted.
- Gate green: 114 passed (115 minus that one), ruff clean, basedpyright 0 errors. **The golden
  fixtures pass unchanged and were never regenerated** — the phase's real proof. Net −112 lines.

## Phase 2 — one loader, four hooks — DONE

- `core/registry.py` and `core/enginepack.py` are gone; `core/engine.py` is the one loader:
  `EngineSpec`, `AdvancementOffer`, a typed `EnginePlugin` (id, badge, engine_dir, plan type, four
  hooks), `Engine`, discovery (`plugins`/`engine_ids`/`plugin_for`/`as_engine_id`), and
  `load_engine(plugin, pack_paths)` / `build_engine(engine_id, config)`.
- `Engine` is data plus derived methods: `default_rules`, `initial_world`, `entity_state`,
  `renderer`, `validate_state`, `violation`, and the four hook forwarders. Every body was moved,
  not rewritten. `EngineParts`, `ProposalSpec`, the `Offered`/`Check`/`Parts*` aliases and the
  closure wrapping in `load_engine` are deleted; `engine.proposal.X` is now `engine.X`.
- Hooks take the `Engine` first (`parts.content` → `engine.content`). Refusal strings untouched.
- **Deviations from PLAN.md, both deliberate:** `EnginePlugin.record_types` is *not* introduced —
  nothing reads it until Phase 4 and an unused field is speculative; Phase 4 adds it in one line.
  `Engine.toolsets` (a one-key mapping) collapsed to `director_toolset`.
- **Both engines now have the same shape**, on the maintainer's call (PLAN.md wanted story
  collapsed into a single `rules.py`; one template for every engine reads better than a
  size-dependent one): `rules.py` declares `PLUGIN` and nothing else, `actions.py` the plan type,
  `resolve.py` the two turn hooks, `advance.py` the two advancement hooks. 5e adds `content.py`,
  the only difference. `engine.py`/`identity.py` are gone from both; `ENGINE_MODULES` names the
  two `rules` modules.
- `Settings.engines` is typed `dict[EngineId, EngineConfig]` with one `pack_paths` field, read by
  `build_engine`; `Dnd5eConfig` is gone.
- `scripts/evals/probes.py` lost its private pack read (`shipped_content`): the `Engine` it already
  holds exposes `content`. `scripts/srd/build.py` and the evals runner repointed.
- Tests: `test_enginepack.py` → `test_loader.py`, building an `EnginePlugin` over a tmp dir.
  Story's advancement test now goes through `engine.violation` (the shared check plus the engine's
  own), which is the path production takes.
- Gate green: 114 passed, ruff clean, basedpyright 0 errors. **The golden fixtures pass unchanged
  and were never regenerated.**

## Phase 3 — packages named by what they hold — DONE

- Layout now: `state/` (base, facts, dice, packs, sheet, world, effects, plan, turn),
  `content/` (authored.py, store.py), `engines/` (loader.py, examples.json, story/, dnd5e/),
  `turn/` (pipeline, prompts, roles, advancement), `app/` (launcher, session), `ui/`, plus
  `aidm/config.py`. `core/` and `workflow/` are gone.
- **Two deviations from PLAN.md's table, both forced by the import direction:**
  `packs.py` sits in `state/`, not `content/` — `Sheet` holds `ContentRef` and `render_sheet`
  reads a `LenientRecord`, so the pack format is *below* the state machine; putting it above
  would invert the arrow. `config.py` sits at `aidm/config.py`, not `app/` — `turn/roles.py`
  reads `Settings`, so config must be a leaf every layer can read, not a layer above `turn/`.
- `AdvancementOffer` moved from the loader to `state/sheet.py`, beside `SheetDelta`: the
  advancement panel renders it, and `ui` may not import `engines`.
- Discovery's consumers moved off it: `read_scenarios`/`read_characters` take the engine-id
  tuple, `LauncherCatalog` carries an `EngineOption` per engine so `show_engine_badge` takes the
  badge it was handed, `as_engine_id` lives in `app/launcher.py`, and `build_engine` (the only
  reader of `Settings.engines`) lives in `app/session.py` — so `engines/loader.py` imports no
  config at all and exposes `load_engine(plugin, pack_paths)`.
- `workflow/session.py` split: `app/launcher.py` (catalog, options, controller, `LaunchTarget`)
  and `app/session.py` (`build_engine`, `GameSession`, `Runtime`).
- `test_package_boundary.py` now states the whole direction as one table
  (`state ← content ← engines ← turn ← app ← ui`) and asserts that only `loader.ENGINE_MODULES`
  names a concrete engine. `ui → engines` stays forbidden, and now nothing in `ui/` imports an engine module at all.
- `scripts/import_srd.py`'s hardcoded `SAVE_VERSION` path repointed to `state/base.py`; the evals
  and SRD scripts follow the new module names.
- Test packages were **not** renamed (`tests/core/` still holds the cross-cutting suites): the
  golden fixtures are anchored under `tests/core/fixtures/`, and moving them buys nothing.
  README's layout section and one ROADMAP path were refreshed — pulled forward from Phase 5
  because they named deleted directories.
- Gate green: 117 passed, ruff clean, basedpyright 0 errors. Golden fixtures again unchanged.

## Adversarial review pass — DONE

Run against the staged Phases 2–3 diff; everything below is folded in and green.

- **One real regression, fixed:** `EngineConfig` was a plain `BaseModel`, so a typo in a settings
  engine section (`pack_pathz`) was silently ignored where `Dnd5eConfig(Value)` used to refuse it.
  It is `extra="forbid"` again.
- `check_delta` narrowed to `(state, delta)`: neither engine read the `Engine` or the offer it was
  handed, and the shared `violation` already judges the offer. Two `del` lines and a wider
  contract than anyone uses, gone.
- `narrator_evidence` + `NOTHING_MECHANICAL` moved to `state/facts.py`. Its only input is
  `Sequence[Fact]`; it was in the loader by accident of history.
- `test_every_registered_engine_builds_itself` trimmed to the build loop: the two other asserts
  restated `Engine.id`'s one-line body and a field's type.
- `load_catalog`'s local `offered` renamed `engine_options` — it collided with the advancement
  hook of the same name.
- Docstrings the review cut that carry a *why* were restored: the authored models' on-disk file
  mapping (`world.json` / `<engine>.json` / `base.json`), the overlay-typo rule, the launcher's
  deliberate skip of half-written content, and `_StoredVersion`'s reason for defaulting to 0.
- Reported and **not** acted on: moving `Settings` back under `app/` would mean `turn/roles.py`
  taking its role config from the composition root instead of reading `Settings` — a real
  improvement, but a turn-pipeline change, not a layout one. Left for a later phase.
- `src/` is 55 lines lighter than HEAD across Phases 2–3, with 9 modules deleted and 3 added.

## Phase 4 — typed pack mechanics — DONE

- Unblocked: `5e-bits/5e-database` cloned and checked out at `manifest.json`'s `source_commit`
  (`3f5593e`, v5.10.0). **Before touching anything**, the importer was run against it and the
  output diffed against the shipped pack: byte-identical across all 23 files. Every later claim
  rests on that baseline.
- `engines/dnd5e/records.py` (new): `SpellAmount`, `SpellRecord`, `WeaponRecord`, and the `ABILITIES`
  abbreviation map moved off `content.py` — the importer and the engine now share one definition.
  The records *are* the facts types: `damage_at`/`heal_at`/`dice` are methods on them, so no second
  model is parsed out of the first.
- `EnginePlugin.record_types` landed in one line as Phase 2 predicted, with
  `packs.pack_format(collections, record_types)` replacing `lenient_format`, which is deleted.
  5e declares `{"spells": SpellRecord, "weapons": WeaponRecord}`; the story engine passes nothing
  and stays all-lenient.
- `scripts/srd/project.py` emits the typed fields from upstream structure, never from its own notes.
  `_equipment_text` was extracted so `weapon()` builds a `WeaponRecord` without duplicating the
  cost/weight/prose assembly. The importer **fails fast** where the old parser degraded silently: an
  unknown save ability, or a `MOD` term anywhere but trailing, raises at build time instead of
  demoting the spell to `improvise` at play time.
- Pack regenerated: only `spells.json` and `weapons.json` changed, and only by the added fields —
  every pre-existing field is byte-equal on all 319 spells and 37 weapons. `SAVE_VERSION` 28 → 29.
- **The parity gate passes with `mechanics_parity.json` unmodified.** All 356 records reproduce the
  fixture exactly, and the one weapon that typed to null (no damage dice) still does.
  PLAN.md expected a short list of spells that stop falling back to `improvise`: **the list is
  empty.** The old regex parser succeeded on every shipped record, so this phase is pure
  representation — the improvement is that the guarantee is now build-time, not that any spell moved.
- `content.py` 196 → 41 lines: three lookups reading fields. The regexes, `Amount.parsed`,
  `_scaling`, `_scaled` and both `from_record` parsers are gone.
- `resolve.py`: `SpellFacts` → `SpellRecord` throughout, and the `_spell` wrapper is deleted with
  the refusal it carried (*"the rules for X are not written in a form this engine resolves"*) —
  `spell_of` now returns a typed record or raises, so that branch was unreachable. The weapon guard
  folds the dice lookup into its existing check; its refusal string is untouched.
- Golden fixtures: 6 regenerated, one line each — `save_version` only. Prompts, schemas and trace
  shape did not move, which is the point: the new fields reach the resolver, never the model, since
  `_record_text` and `_ref_line` render named fields only.
- Gate green: 117 passed, ruff clean, basedpyright 0 errors.

### Adversarial review pass (fable) — folded in

- **Two claims in this section were false and are corrected above.** `lenient_format` was *not*
  deleted — the edit silently no-op'd and nothing type-checks an unused public function; it is
  deleted now. And the "new" round-trip test duplicated
  `tests/dnd5e/test_packs.py::test_a_loaded_pack_writes_back_byte_for_byte`, which already
  round-trips the shipped pack through the typed `pack_format()`; the duplicate is removed.
- `test_content.py` trimmed to the method logic — `dice()`'s versatile pick, `damage_at`/`heal_at`
  thresholds, `bonus()`. Asserts that only restated a field already locked per-record by
  `mechanics_parity.json` are gone.
- `records.ABILITIES` → `ABILITY_BY_ABBREVIATION`: it maps `"INT"` → `"intelligence"`, and the old
  name collided with `project.ABILITIES` (the six ability names), which had forced an import alias.
- `pack_format` lost a single-element-loop trick that bound a local inside a dict comprehension;
  the plain loop is the same length. `SpellLevel` and `_Ladder` inlined at their one use each.
- Reported and **not** acted on: the importer walks the damage ladder twice, once for prose notes
  and once for the typed fields — the notes could be rendered *from* the typed fields, deleting
  `_ladder`/`_dice` (~15 lines), but byte-identity would have to be proven. PLAN.md scopes
  redundancy cleanup out of this phase; left as a follow-up.
- Reviewer confirmed the duplication between `notes`/`numbers` and the typed fields is load-bearing,
  not dead weight: weapon `numbers` reach sheets via `_backing` (and `_weapon_dice` derives the
  typed dice *from* them, so the two cannot drift), while `notes`/`text` are the model's view.
- The importer re-run after every review edit still reproduces the shipped pack byte for byte.

## Typed pack, all collections — DONE

Follow-on to Phase 4, on the maintainer's call: every collection typed the way spells/weapons
were, notes/numbers gone as generic bags, the model's view rendered from typed fields.

- **(c)** `content.py` merged into `records.py` and deleted: 5e now differs from story by one
  extra module. `weapon_of`/`spell_of`/`spellcasting_ability` unchanged in behaviour.
- **(a)** The importer's spell prose renders *from* the typed fields (`SpellAmount.prose`,
  `scaling_prose`); the parallel ladder walk (`_ladder`/`_dice`/`_spell_damage`) is deleted.
  Proven by importer-output byte-identity against the pre-change pack.
- **(b) architecture:** `Record` (state/packs.py) gained `text`/`tags`/`options`/`choose` — they
  are structural and every consumer (advancement, rendering) reads them on any collection — plus
  two overridable methods, `sheet_numbers()` and `noted()`, both empty by default. Typed records
  subclass `Record` and compute both from typed fields. Core (`_backing`, `_record_text`,
  `_ref_line`, advance, probes) calls the methods polymorphically — no 5e knowledge in `state/`
  or `loader.py`, and the story engine is untouched. The candidate sketch survived contact whole;
  the one addition it needed was moving the four structural fields onto the base so advancement
  and the `read_content` render read any collection.
- All 22 collections typed across `records.py` (16 record classes, one per collection but for
  `gear`/`tools`; open-ended per-class ladders and monster proficiencies stay
  `FrozenMap[Slug, int]` fields — typed values, honest keys).
  Five text-only collections (conditions, languages, alignments, feats, proficiencies) validate
  as plain `Record`, so a stray bag fails at load.
- **Byte-equality of the model view** was the gate for every increment: a script diffed
  name/text/tags/options/choose/`noted()`/`sheet_numbers()` (order-sensitive) for all ~2,200
  records against the pre-change pack. **One accepted change:** the blowgun's damage renders
  `1d1 piercing` instead of `1 piercing` — the same normalization its sheet numbers already
  made. Everything else is byte-identical.
- `mechanics_parity.json` passes **unmodified**: `attack`/`half_on_save` became derived
  properties over `attack_type`/`save_success`, so the resolver and the parity extraction are
  value-identical; the test now spells the fixture's keys explicitly.
- Importer fail-fasts added: scaling step must agree with spell level (leveled = slot,
  cantrip = character level), breath-weapon damage type must match its trait, two-handed damage
  implies versatile, unknown attack types and save outcomes raise.
- `SAVE_VERSION` 29 → 35 (one bump per green increment). Golden fixtures changed by their
  `save_version` line only — prompts, schemas, trace shape, and sheet renders did not move.
- Gate green after every increment: 117 passed, ruff clean, basedpyright 0 errors.

### Adversarial review pass (opus) — folded in

- **`LenientRecord` is deleted.** It had zero production users once every collection was typed:
  the `_choice_is_whole` validator and the four structural fields had already moved to `Record`,
  so all it still carried was the `numbers`/`notes` bags and the two overrides returning them.
  `pack_format` now defaults an unmapped collection to bare `Record`, which is what the five
  prose-only collections already ask for. `tests/core/test_loader.py` declares its own record
  class instead, so the loader tests now prove `record_types` works for *any* engine's shape
  rather than for a shape only the test used.
- `CollectionSpec` went with it: `PackFormat` is now `collection -> record class`. Its `classes`
  tuple never held more than one class, its `adapter` is `held.model_validate`, and its `entity`
  field was read by nothing.
- One dialect per concept in `records.py`: `_numbered` mirrors `_noted` (twelve
  `{} if x is None else {...}` blocks gone), `_save_note`/`_damage_note`/`_area_note`/
  `_bonus_note`/`_scaling_prose` are shared by the classes that had copies, `TraitRecord.
  save_success` takes the same `SaveSuccess` literal as `SpellRecord` (and the same
  set-together validator), and the importer narrows it through `_save_success` like the spell
  path. A render diff over all ~2,200 records — name/text/tags/options/choose/`noted()`/
  `sheet_numbers()`, order-sensitive — is byte-identical.
- The importer stopped building number bags to read one key back out of:
  `_passive_perception`, `_capacity_pounds` and `_vehicle_speed` return their values,
  `_damage_numbers` folded into `_weapon_dice`, `_feet_numbers` lost a dead `prefix`, and a
  monster's spellcasting is scanned once, not twice. Pack output stays byte-identical.
- `scripts/srd/project.py` stays at ~1,150 lines by decision, now stated in its docstring: a
  one-shot offline importer, not runtime code.
- Corrected here: this section claimed ~20 record classes (there are 16) and described
  `LenientRecord` as still carrying the bags.

## Consistency follow-ups — DONE

The four findings the opus review left to the maintainer, all taken. `SAVE_VERSION` 35 → 38.

- `advance.py` reads a level row as `LevelRecord` instead of the bare `Record`. No pack or fixture
  change; the stronger type was free.
- **Dragonborn `damage_type` casing.** `TraitRecord.damage_type` stored `"Fire"` where
  `SpellRecord`'s stored `"fire"`, and `_damage_note` carried a `.lower()` that existed only to
  compensate for that one caller. The trait now stores the `Slug` and the helper stops
  compensating. Ten draconic-ancestry traits' `damage-type` note reads `fire`, not `Fire` — the one
  accepted model-visible change.
- **`ClassRecord` stores slugs.** `saving_throws` and `spellcasting` held abbreviations
  (`"STR"`, `"INT"`) against the file's own convention — store the slug, render the abbreviation
  through `ABBREVIATION_BY_ABILITY`, as `SpellRecord.save_ability` already did. **The rendered notes
  are byte-identical** (`INT, WIS` / `INT`); only the stored fields changed. `spellcasting_ability`
  is now a plain field read: the last abbreviation lookup on the engine's read path is gone.
- **Languages, alignments, proficiencies and feats typed**, leaving `conditions` as the only
  genuinely prose-only collection. `_ability` (was `_save_ability`) is now the one importer helper
  for abbreviation → slug, fail-fast, shared by spells, traits, classes and feats.
- **Deliberately no `noted()` on those four.** The first attempt rendered the new fields as notes
  and put `category=Skills; reference=Athletics` beside every proficiency on Kael's sheet — in the
  director, narrator *and* advisor prompts — where the record's own name already reads
  `Skill: Athletics`. The fields are for code to act on; the model's view was already right. Their
  `text` is restored byte-identical, so the pack diff is added fields only and the model sees no
  change. A typed field earns its place by being actionable, not by being rendered.
- Gate green: 117 passed, ruff clean, basedpyright 0 errors. Parity fixture unmodified, golden
  fixtures moved only by `save_version`, importer still reproduces the shipped pack byte for byte.

## Next — Phase 5: docs and loose ends

Strike the resolved IDEAS.md lines, refresh `docs/ROADMAP.md` where it names dead modules, and
optionally run one eval suite as a no-change confirmation. README and one ROADMAP path were already
pulled forward in Phase 3.
