# Refactor: one concrete state model, engines as data + hooks

Self-standing implementation plan. It assumes no prior knowledge of this repository: read the
Background and Design sections before touching code, then execute the phases in order. Every phase
ends with commands that must pass before the next phase starts.

## Objective

Collapse the speculative generality the codebase carries — the `R: EngineRules` type parameter,
the 12-callable `Engine` bag assembled through closure factories, the three-module engine
machinery, the double parse of 5e mechanics — and reorganize the packages so a reader can predict
where things live. After this plan:

- `Sheet` is *the* rules payload, concretely, everywhere. No generics, no casts, no `isinstance`
  re-narrowing in resolvers, tests, or evals.
- An engine is one directory: data files (`spec.json`, `director.md`, `advancement.md`,
  `examples.json`, optional `packs/`) plus Python declaring a plan type and four hook functions.
  The story engine is one `rules.py`; Ironsworn would be a copy of that shape.
- The 5e pack carries typed spell/weapon mechanics written by the importer, and the runtime
  regex layer that re-parses prose notes is deleted.
- Packages are named by what they hold: `state/`, `content/`, `turn/`, `engines/`, `app/`, `ui/`.

Expected size: roughly 800–1,200 lines removed across `src/`, `tests/`, `scripts/`.

## Behavior must not change — and how that is enforced

This is the plan's contract, stated up front because everything below serves it. The 5e engine's
resolution today — attack math, spell slots and DCs, rests, milestone advancement, fact wording,
leak guards — is correct and measured (see `baseline.md`); the refactor must be invisible to it.

What cannot change, and what proves it:

| Invariant | Proof |
|---|---|
| Resolver procedure: every formula, roll, cost, clamp, refusal string | Untouched files or pure moves; the existing exact-fact tests (`tests/dnd5e/test_resolve.py`, `tests/story/`, `tests/core/test_effects.py`) compare seeded-RNG facts and trace wording verbatim |
| Prompts, byte for byte (instructions *and* per-turn rendering — both are behavior in an LLM app) | New Phase 0 golden fixtures: every role's assembled instructions per engine, plus every prompt one scripted golden turn per engine renders, and the model-facing output schemas and tool definitions |
| Save and trace JSON, byte for byte, through Phases 1–3 | New Phase 0 golden fixtures: the initial `GameState` JSON for both engines, and the full `Turn` trace + post-turn save JSON of the scripted golden turn; `SAVE_VERSION` stays 28 until Phase 4 |
| Spell/weapon mechanics extracted from the pack | New Phase 0 parity fixture: `SpellFacts`/`WeaponFacts` for every record in the shipped pack, checked in; Phase 4's typed fields must reproduce it wherever today's parser succeeds |
| Narrator leak boundary (`VisibleScene` has no field a leak travels through) | Type unchanged; `tests/core/test_context_boundary.py` untouched |
| The model never writes state; draft → mutate → revalidate → commit | Transaction code (`GameState.draft/committed`) unchanged |

Phases 1–3 are representation-only: types, wiring, file layout. They delete *ceremony* (a type
parameter with one instantiation, closures re-plumbing values the engine already owns, three-line
modules), never *checks* — every validator, refusal, and guard survives, most of them verbatim.
Phase 4 is the only phase that touches 5e mechanics data, and it is gated by the parity fixture.
Where Phase 4 makes a previously unparseable spell resolvable (today it falls back to
`improvise`), that is a conscious, listed improvement — never a silent one.

A live eval run (`scripts/evals/run.py`) is *not* required by this plan: no prompt changes, so
there is nothing to re-measure. Running one suite after Phase 5 as confirmation is optional.

## Background: the repository today

Commands that must always pass, from the repo root:

```bash
uv run pytest            # deterministic, no network
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Layout (all of `src/` plus what this plan touches):

| Path | What it is |
|---|---|
| `src/aidm/core/base.py` | `Entity`, `Frozen`/`Mutable`, `Slug`, `SAVE_VERSION` |
| `src/aidm/core/world.py` | `EngineRules` base + `BareLocation`, `Record[R]`, `WorldState[R]`, `GameState[R]` (draft/commit transaction), `rules_of` |
| `src/aidm/core/sheet.py` | `Sheet` (numbers/counters/tags/notes/refs) — the universal rules payload; `SheetDelta` advancement ops |
| `src/aidm/core/effects.py`, `plan.py`, `facts.py`, `dice.py`, `turn.py` | Effect vocabulary + `apply_effect`; `TurnPlanBase` + `check_plan_base`; `Fact`; dice; trace entries |
| `src/aidm/core/engine.py` | `Engine[R]`: a 12-field dataclass of injected callables; `ProposalSpec`, `AdvancementOffer` |
| `src/aidm/core/enginepack.py` | `load_engine`: builds an `Engine[Sheet]` from `spec.json` + packs + markdown, wrapping the per-engine functions in closures over `EngineParts` |
| `src/aidm/core/registry.py` | Plugin discovery by module name; `AnyEngine = Engine[EngineRules]` + `cast` |
| `src/aidm/core/packs.py`, `content.py`, `store.py`, `config.py` | Pack format (`LenientRecord`, `PackFormat`/`CollectionSpec` — multi-class support exists but only `lenient_format` is used); authored scenarios/characters; saves/traces; settings |
| `src/aidm/workflow/` | `pipeline.py` (turn script), `prompts.py`, `roles.py` (`Stage`), `proposals.py` (advisor), `session.py` (launcher catalog + `GameSession` + `Runtime`, all three in one module) |
| `src/aidm/engines/story/` | 6 Python files, ~215 lines: `engine.py`, `identity.py`, `actions.py`, `advance.py`, `resolve.py` |
| `src/aidm/engines/dnd5e/` | Same shape + `content.py` (regex parsers turning pack `notes` strings back into `SpellFacts`/`WeaponFacts`) + `packs/srd-2014/` (23 collections, ~2,200 records) |
| `src/aidm/ui/` | NiceGUI launcher + game page + panels |
| `scripts/srd/` | `upstream.py` (5e-database schema) + `project.py` (one projection per record type) + `build.py`; `scripts/import_srd.py` regenerates the vendored pack and auto-bumps `SAVE_VERSION` |
| `scripts/evals/` | Live-model director evals; `probes.py` re-narrows `GameState[EngineRules]` and carries a duplicated `_level_ref` |

The ceremony this plan deletes, named precisely:

1. **The generic that never varies.** Both engines are `GameState[Sheet]`. The parameter exists
   for a hypothetical non-sheet engine that has never been written; meanwhile `AnyEngine` erases
   it and every consumer pays: `cast` in the registry, `rules_of` re-narrowing, `SerializeAsAny`
   on `Record.rules`, `state_type` threaded into `store.load`, `EngineParts` as first parameter
   of ~15 functions in `dnd5e/resolve.py`, `isinstance` plan-narrowing helpers per engine.
   CLAUDE.md's own rule — a port earns its place when the second implementation exists — says
   this goes. If a genuinely non-sheet engine ever appears, reintroduce the seam then.
2. **Three layers to assemble one engine.** `registry.py` (import by name, check, cast) →
   `engine.py` (dataclass of callables) → `enginepack.py` (`load_engine` wrapping the engine's
   functions in lambdas over `EngineParts`). One loader can do all of it, because with `Sheet`
   concrete, `initial_world`, `default_rules`, `validate_state`, `entity_state`, and the
   `read_content` toolset derive uniformly from `spec` + `content` — they are not per-engine
   variation and never were.
3. **The double parse.** `scripts/srd/project.py` has upstream structured data and flattens it
   into strings (`"damage": "4d4 acid"`, `"scaling": "slot 3: 5d4, ..."`); `engines/dnd5e/content.py`
   regex-parses those strings back at runtime, with `None` fallbacks that silently demote spells
   to `improvise`. Typed pack records make extraction a build-time guarantee.

## Design

### The engine contract after the collapse

One module (final home `engines/loader.py`, Phase 3) replaces `engine.py` + `enginepack.py` +
`registry.py`. An engine's Python declares one `PLUGIN`:

```python
@dataclass(frozen=True, slots=True)
class EnginePlugin:
    id: EngineId
    badge: tuple[str, str]
    engine_dir: Path                # spec.json, prompts, examples, packs/ live here
    plan_type: type[TurnPlanBase]
    check_plan: Callable[["Engine", GameState, TurnPlanBase], str | None]
    resolve_action: Callable[["Engine", GameState, TurnPlanBase, Random], list[Fact]]
    offered: Callable[["Engine", GameState], AdvancementOffer | None]
    check_delta: Callable[["Engine", GameState, AdvancementOffer, SheetDelta], str | None]
    record_types: Mapping[CollectionName, type[Record]] = field(default_factory=dict)
```

Two wiring notes: the hook annotations forward-reference `Engine` (which holds the plugin), so
they are quoted strings or PEP 695 lazy aliases — never a `TYPE_CHECKING` import, which
CLAUDE.md forbids. `record_types` maps a collection to its record class; empty means all-lenient,
exactly today's `lenient_format(spec.collections)`. It exists now so Phase 4 can say
`{"spells": SpellRecord, "weapons": WeaponRecord}` without reopening this contract.

The loader builds `Engine` = plugin + `spec` + `content` + assembled instructions, and derives
everything else as plain methods (`default_rules`, `initial_world`, `validate_state`,
`entity_state`, the director toolset, the shared advancement `violation` check — all current
bodies, moved not rewritten). Hooks take the `Engine` as their first argument: that *is*
`EngineParts`, without the parallel struct and the lambda wrapping. The four hooks keep their
current bodies and refusal strings verbatim.

Engine config (`Settings.engines[id]`) is read uniformly by the loader: one optional
`pack_paths` override for any engine, replacing `Dnd5eConfig`.

Plugin discovery stays import-by-name (`ENGINE_MODULES` → module's `PLUGIN` attribute) — the one
sanctioned import-graph exception — but with a typed `EnginePlugin` there is nothing left to
`cast`. Discovery's current consumers sit on the wrong side of the Phase 3 layering
(`store.py` calls `engine_ids()` for content listing; the UI imports `plugin_for(...).badge` and
`as_engine_id`), so they move off it rather than dragging discovery downward:
`read_scenarios`/`read_characters` take the engine-id tuple as a parameter (the composition root
supplies it), the launcher catalog carries each engine's badge so the UI renders data it was
handed, and route narrowing (`as_engine_id`) happens in `app/`. The boundary test keeps
forbidding `ui → engines`, now with nothing tempted to break it.

### The engine directory shape

Default shape is **one `rules.py`** holding the plan type, actions, hooks, and `PLUGIN` — the
story engine lands there (~180 lines) and is the template a new engine copies. An engine may
split when it nears the size cap: 5e keeps `actions.py`, `resolve.py`, `advance.py`,
`content.py`, with `engine.py` + `identity.py` collapsing into a ~20-line `rules.py` root that
only declares `PLUGIN`. No sibling imports `rules.py`; it is the assembly root.

### The package layout (Phase 3)

```
src/aidm/
  state/     base.py, world.py, sheet.py, effects.py, plan.py, facts.py, dice.py, turn.py
  content/   packs.py, authored.py (was core/content.py), store.py
  turn/      pipeline.py, prompts.py, roles.py, advancement.py (was workflow/proposals.py)
  engines/   loader.py, story/, dnd5e/
  app/       config.py, launcher.py (catalog + controller), session.py (GameSession + Runtime)
  ui/        unchanged internally; imports updated
```

Import order stays acyclic: `state ← content ← engines ← turn ← app ← ui`. `state/` is the
deterministic machine (no model, no I/O), `content/` is what gets loaded and persisted, `turn/`
is the AI pipeline, `app/` is composition. Names may be tuned during the move; the rule that may
not be tuned is one direction of dependency and no `core`/`workflow` grab-bags.

### Typed pack mechanics (Phase 4)

The spells and weapons collections get typed records, using the `PackFormat`/`CollectionSpec`
multi-class support that already exists:

```python
class SpellRecord(LenientRecord):
    level: int | None = None          # None = cantrip
    attack: bool = False
    save_ability: Slug | None = None
    half_on_save: bool = False
    damage: SpellAmount | None = None  # dice + with_modifier flag, as Amount today
    heal: SpellAmount | None = None
    scaling: tuple[tuple[int, SpellAmount], ...] = ()
    concentration: bool = False

class WeaponRecord(LenientRecord):
    damage: DiceExpr | None = None
    versatile_damage: DiceExpr | None = None
    ranged: bool = False
    finesse: bool = False
```

The importer computes these from *upstream structure* (`up.Spell.damage`, `up.Equipment.damage`),
not by parsing its own notes strings. The prose `notes`/`text` stay exactly as they are — they
feed `read_content` and sheet rendering. `engines/dnd5e/content.py` shrinks to thin lookups
(`weapon_of`, `spell_of`, `spellcasting_ability`) reading fields instead of running regexes;
`Amount.parsed`, `_scaling`, and the `SpellFacts.from_record`/`WeaponFacts.from_record` parsers
are deleted. A weapon or spell the importer cannot type keeps `None` fields and resolves exactly
as today: refusal → `improvise`.

Regeneration requires the external 5e-database checkout **at the commit pinned by
`manifest.json`'s `source_commit`** — regenerating from a newer checkout would smuggle content
churn into a schema change. `import_srd.py` already bumps `SAVE_VERSION`; Phase 4 is the only
phase that moves it.

### What deliberately does not change, in any phase

- `Sheet`'s fields, `Effect`/`DeltaChange` vocabularies, `TurnPlanBase`, `Fact`, dice.
- The pipeline: `Cast`, the five steps, `Stage`, retries, output validators, `history_window`.
- Every prompt string and every field description (they steer the model; the Phase 0 fixtures
  pin the assembled result).
- Scenario/character files, eval scenarios and probes' assertions, the UI's behavior.
- The save/trace design: a save names its origin; a stale `SAVE_VERSION` is refused, never converted.

---

## Phase −1 — start from a green, committed tree (blocking, ≈minutes once decided)

The working tree currently carries uncommitted changes (`scripts/evals/run.py`,
`src/aidm/engines/dnd5e/director.md`, `examples.json`, `src/aidm/workflow/prompts.py`,
`PROGRESS.md`) and `uv run pytest` fails in that dirty state while HEAD (3d7c936) passes.
Fixtures cut from this tree would enshrine unreviewed prompt changes as the golden truth.

1. The maintainer decides: land the in-flight work as its own commit, or revert it. Not this
   plan's call.
2. Full gate on the committed result. No fixture is generated before this is green.

## Phase 0 — behavior locks (≈half a day)

Write the fixtures that make "no behavior change" falsifiable before anything moves.

1. `tests/dnd5e/test_content_parity.py`: iterate every record of the shipped pack's `spells` and
   `weapons` collections, build `SpellFacts.from_record` / `WeaponFacts.from_record`, and compare
   against a checked-in JSON fixture `tests/dnd5e/fixtures/mechanics_parity.json` (record index →
   parsed facts or `null`). Generate the fixture with a small `if __name__ == "__main__"` block or
   a pytest `--regen` flag; committing it is the point.
2. `tests/core/test_golden_state.py`: for each engine, build the initial `GameState` for
   `whispering-vault` + `kael` (the existing test-support builders show how), `model_dump_json`
   it, and compare against checked-in fixtures. Assert `SAVE_VERSION == 28` in the same test with
   a comment naming Phase 4 as the only legitimate bumper.
3. `tests/core/test_golden_prompts.py`: assemble **every** role's instructions per engine — the
   director's (`CORE_DIRECTOR` + `director.md` + rendered examples), `NARRATOR`, `MAINTAINER`,
   `CREATOR`, and the advisor's (`CORE_ADVISOR` + `advancement.md`) — and compare against
   checked-in fixtures.
4. `tests/core/test_golden_turn.py`: one scripted turn per engine — `run_turn` from the golden
   state with `FunctionModel` stubs and a seeded `Random` (the existing pipeline-test support
   shows how) — comparing every rendered prompt (`ws.prompts`), the full `Turn` trace JSON,
   and the post-turn save JSON against fixtures. This is the lock on per-turn prompt rendering,
   trace shape, and sheet rendering; the instruction fixtures alone would miss drift there.
5. `tests/core/test_golden_schemas.py`: the plan type's JSON schema and the director toolset's
   tool definitions per engine, plus the `Growth`/`EntityDetail`/`SheetDelta` schemas. Every field
   description in them reaches the model exactly as the instructions do, and Phase 1 rewrites the
   modules that carry them.
6. Full gate: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.

Commit: `test: golden locks on prompts, state json, and pack mechanics`.

## Phase 1 — collapse the generic (≈1 day)

Mechanical, wide, and boring on purpose. No file moves in this phase — smaller diffs review better.

1. `core/sheet.py`: `Sheet(Mutable)` gains `kind: Kind` — declared **first** in the body, so the
   field order, and with it the serialized JSON, stays byte-identical to what inheriting from
   `EngineRules` produces today. `core/world.py`: delete `EngineRules`, `BareLocation`,
   `rules_of`; `Record.rules: Sheet` (drop `SerializeAsAny` — with one concrete class the dump is
   identical; `packs.py`'s separate `SerializeAsAny[Record]` is untouched, Phase 4 relies on it).
   `WorldState`, `GameState` lose the parameter. The `_kind_agrees` validator and the whole
   transaction stay verbatim.
2. De-genericize signatures across `core/` (`effects.py`, `plan.py`, `engine.py`,
   `enginepack.py`, `content.py`'s `compose_world`), `workflow/`, both engines, `store.py`
   (`load` drops `state_type` and calls `GameState.model_validate_json`), and `prompts.py`
   (`SceneSnapshot.of`). Keep parameter lists otherwise unchanged — `default_rules` still
   travels explicitly until Phase 2.
3. Delete the narrowing that existed only for erasure: `AnyEngine` + `cast` in `registry.py`
   (keep the module otherwise), `rules_of` call sites (`dnd5e/advance.py`, `scripts/evals/probes.py`
   — also delete probes' duplicated `_level_ref` and import the real one).
4. Tests: `tests/core/test_engine_contract.py` and `test_package_boundary.py` lose their
   erasure-shaped cases; everything else should pass untouched except import/type tweaks. The
   golden fixtures must pass **unchanged** — that is the phase's real gate.

Commit: `refactor(core): one concrete Sheet, no engine type parameter`.

## Phase 2 — one loader, four hooks (≈1 day)

1. Merge `core/registry.py` and `core/enginepack.py` into `core/engine.py` (final home moves in
   Phase 3): `EnginePlugin` per the Design; `Engine` built by one `build_engine(plugin_module,
   settings)`; derived behavior (`default_rules`, `initial_world`, `validate_state`,
   `entity_state`, `_director_toolset`, `_examples`, advancement `violation`) becomes methods or
   private functions — bodies moved, not rewritten. Delete `EngineParts`, `ProposalSpec`
   (its `violation` body survives as the shared advancement check), the `Offered`/`Check`/
   `PartsPlanCheck`/`PartsResolver` aliases, and the closure wrapping in `load_engine`.
2. Re-sign the four hooks in both engines to take `Engine` first (`parts.content` →
   `engine.content` etc. — a rename, not a rewrite). Keep every refusal string identical.
3. Story engine → one `rules.py` (merge `engine.py`, `identity.py`, `actions.py`, `advance.py`,
   `resolve.py`; delete the five). 5e: `engine.py` + `identity.py` → a `rules.py` declaring
   `PLUGIN`; `actions.py`/`resolve.py`/`advance.py`/`content.py` stay. Update `ENGINE_MODULES`.
4. Loader reads `pack_paths` from `Settings.engines[id]` uniformly; delete `Dnd5eConfig`.
5. `scripts/evals/probes.py` imports `ENGINE_DIR` from `aidm.engines.dnd5e.engine`, which this
   phase deletes — repoint it at the plugin's `engine_dir`.
6. Update `tests/core/test_enginepack.py` + support modules to the new construction; the golden
   fixtures again pass unchanged.

Commit: `refactor(engines): one loader, engines declare a plan type and four hooks`.

## Phase 3 — the package layout (≈half a day)

1. `git mv` per the Design table; `workflow/session.py` splits into `app/launcher.py` (catalog,
   options, controller) and `app/session.py` (`GameSession`, `Runtime`). `core/engine.py` (the
   merged loader) lands as `engines/loader.py`.
2. Rewire discovery's consumers per the Design: `read_scenarios`/`read_characters` take the
   engine-id tuple as a parameter, the launcher catalog carries badges, `as_engine_id` narrowing
   moves into `app/`. Update `tests/core/test_package_boundary.py` to the new package names —
   `ui → engines` stays forbidden.
3. `scripts/import_srd.py` hardcodes `SAVE_VERSION_FILE = src/aidm/core/base.py` as a *string*
   path — no type checker will catch the move. Repoint it to `state/base.py` in this phase, not
   when Phase 4 trips over it.
4. Rewrite imports; tests mirror the move (`tests/state/`, `tests/content/`, …) only where the
   old names (`tests/core/`) would mislead — renaming test packages is optional, not required.
5. Otherwise no logic edits of any kind in this phase. `git diff --stat` should show moves,
   import lines, and the consumer rewiring named above.

Commit: `refactor: packages named by what they hold`.

## Phase 4 — typed pack mechanics (≈1 day; needs the 5e-database checkout)

Blocked without a checkout of `5e-bits/5e-database` at `manifest.json`'s `source_commit`. All
other phases are independent of this one; it can land later or first (if after Phase 3, the two
script repoints named there must already be in).

1. A 5e-owned module: `SpellRecord`, `WeaponRecord`, `SpellAmount` per the Design, declared via
   the plugin's `record_types` (`spells` → `SpellRecord`, `weapons` → `WeaponRecord`, everything
   else lenient). `SpellRecord.scaling` keeps today's exact semantics: **one** shared ladder for
   damage and heal, slot- and character-level keys flattened into one integer key, precisely as
   `SpellFacts` reads it now — the shipped pack mixes both (36 slot-keyed, 10 level-keyed).
2. `scripts/srd/project.py`: `spell()` and `weapon()` emit the typed fields from upstream
   structure. The notes/text they already write stay byte-identical — and so do the weapon
   `numbers` (`damage-dice-count`, `damage-die`, `two-handed-*`): they back item sheets via
   `_backing` and sit inside the golden state JSON, so deleting them as "now redundant" would
   silently change every weapon-carrying sheet. Redundancy cleanup is out of this plan's scope.
3. Regenerate: `uv run python scripts/import_srd.py <checkout>`; commit the pack diff and the
   auto-bumped `SAVE_VERSION`; update the Phase 0 golden-state/turn fixtures and the
   `SAVE_VERSION == 28` assertion **in the same commit** (the version changed — the world
   content must not have).
4. `engines/dnd5e/content.py`: `weapon_of`/`spell_of`/`spellcasting_ability` read record fields;
   delete the regex parsers. Repoint the parity test: typed fields must equal the fixture wherever
   the fixture is non-null. Where the fixture is null but the record now types (the old regex
   missed), list each such record in the commit message; there should be few, and each is a spell
   that stops falling back to `improvise`.
5. Round-trip check stays green: `write_pack` → `read_pack` byte-identical on the new pack.

Commit: `feat(pack): importer writes typed spell/weapon mechanics; regex layer deleted`.

## Phase 5 — docs and loose ends (≈1 hour)

1. Strike the resolved IDEAS.md lines (codebase structure, "adding an engine should be easy",
   "bake more 5e stuff into the srd json", global config unclean if `app/` resolved it).
2. Update `docs/ROADMAP.md` where it names dead modules; `README.md` layout section if any.
3. Optional confirmation: one eval suite run, appended to `baseline.md` as a no-change check.
4. Full gate; final commit: `docs: layout and ideas after the collapse refactor`.

## Risks the implementer should expect

- **A hidden consumer of the generic.** basedpyright will find every one; fix at the consumer,
  never by re-adding erasure. The evals and tests are in-repo and covered by the gate.
- **Fixture brittleness.** The golden prompts fixture fails on *any* prompt edit — that is its
  job during this plan. If an unrelated prompt change must land mid-plan, regenerate the fixture
  in that same commit with the reason in the message; never regenerate silently. After Phase 5
  the golden prompt/state fixtures may be kept or dropped — the parity fixture stays.
- **Phase 4 upstream drift.** If the pinned checkout cannot be reproduced, stop; do not
  regenerate from a newer commit "close enough". The phase is independent and can wait.
- **The 1000-line cap.** 5e's `resolve.py` (~390) and a future merged module could approach it;
  the Design already answers this — 5e keeps its split files, only the assembly shims merge.
