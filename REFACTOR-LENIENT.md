# Refactor plan — lenient engines on a generic sheet substrate

One refactor, four phases (0–3). Each phase leaves `uv run aidm` playable and the gates green.
Do not start a phase before the previous one is committed.

## The decision

Content becomes lenient, mostly-prose data with a handful of numbers; agents interpret it; the
code that remains is a generic sheet-and-ledger substrate every engine shares. An engine —
including 5e — becomes data plus a small Python shim.

- **The model never writes state.** Every change flows through a typed tool into the turn's
  draft, committed by whole-copy revalidation. Unchanged from today.
- **Code owns randomness and arithmetic-with-consequences.** Dice are rolled by the engine;
  counters clamp and refuse (no spending an empty pool, no HP above max). Unchanged.
- **The model owns rules interpretation *and* derived math.** Which bonus applies, what a DC
  is, what a spell does — the Director reads the sheet's raw numbers and the content's rules
  text, computes modifiers itself, and calls generic tools. Attack bonuses and save DCs stop
  being code.

The schema stays strictly typed (Pydantic V2, forbid-extra); the *semantics* are lenient — a
counter named `rage` and a counter named `momentum` are the same type, their meaning lives in
content text and role instructions.

**CLAUDE.md survives with exactly one amended Design rule** (a phase-1 step, same commit as the
substrate). The first Design rule bullet currently ends "…the model never writes state and never
decides an outcome." Replace that bullet with:

> - The model acts only through typed tools. A tool validates, resolves deterministically, and
>   records facts against the turn's draft; the model never writes state; every roll and every
>   ledger change goes through a tool that validates and records facts.

Interpretation quality replaces type-level guarantees, so it is *measured*: phase 0 builds a
live-model eval harness, and phase 3 (the typed-5e deletion) merges only inside recorded,
pre-written pass-rate thresholds.

A later "engine referee" role (post-Director rules verification, on `docs/ROADMAP.md`) is out of
scope; the design keeps it possible by recording every tool call's facts in the `Turn` trace, so
a verification stage can be added without touching the substrate.

## Phases and budgets

Baseline: **8,497 src lines** at commit `1de5b18` (core 1,410 / workflow 1,129 / ui 474 /
story 1,168 / dnd5e 4,316). Record `find src -name '*.py' | xargs wc -l | tail -1` in every
phase's commit message. If a step grows the total beyond its budget, simplify before committing.

| Phase | Outcome | src budget | Effort |
|---|---|---|---|
| 0 | Eval harness under `scripts/evals/` (live model, outside pytest) | 8,497 (unchanged) | ~1 day |
| 1 | Substrate: Sheet, mechanics toolset, engine-spec loader, dice in core | ≤ 9,150 (rises ~580) | ~1–2 days |
| 2 | Story on the Sheet + generic proposal-based advancement | ≤ 8,400 | ~2–3 days |
| 3 | 5e on the Sheet; lean importer; typed 5e engine deleted (eval-gated) | ≤ 4,400 | ~3–4 days |

Honest end state: **~4,000–4,300 src** (−4,200 to −4,500). `scripts/` ~1,983 → ~800 (importer
~400 + evals ~350–400). `tests/` (4,203 today) sheds ~1,500–2,000 lines, mostly `tests/dnd5e/`.

Gates after every phase:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Global rules:

- One commit per phase, on a branch off `main`.
- Move files with `git mv`. When a phase says delete, delete — no deprecated aliases.
- `SAVE_VERSION` (`src/aidm/core/base.py:30`) bumps once per phase that changes persisted state
  (phases 2 and 3). Old saves are refused by `src/aidm/core/store.py:_require_save_version`,
  never converted.
- Pack schema changes regenerate the vendored pack from the upstream checkout in the same
  commit (see "Importer and regression").
- Ride-alongs only where the new shape makes them one-liners; each is named in its phase.

---

## The substrate (what phase 1 builds)

### `src/aidm/core/sheet.py` (~170 lines) — the one payload type

```python
class Counter(Mutable):
    current: int
    maximum: int | None = None      # None = unbounded (wealth, xp)
    minimum: int = 0                # Ironsworn momentum needs -6
    recharge: str | None = None     # a label from the engine spec: "short-rest", "scene-end"
    # validator: minimum <= current, and current <= maximum when maximum is not None

class SheetTag(Frozen):
    id: Slug
    name: str
    text: str = ""                  # the constraint or benefit, in prose

class Sheet(EngineRules):           # inherits `kind: Kind`; no per-kind subclasses
    numbers: dict[Slug, int] = {}       # strength 16, armor-class 14, level 3, bold 2
    counters: dict[Slug, Counter] = {}  # hp, slot-1..slot-9, rage, stress, growth
    tags: list[SheetTag] = []           # conditions, edges/burdens, gear qualities
    notes: dict[Slug, str] = {}         # freeform state: {"concentration": "hold-person"}
    refs: tuple[ContentRef, ...] = ()   # content backing this entity (class, monster, gear)
    # validators: tag ids unique; numbers and counters share no key (the misname guard —
    # `hp` cannot exist as a number on one actor and a counter on another)
```

One `Sheet` per entity of any kind — actors, items, and locations (location state, NPC memory,
party membership become notes/tags/numbers with zero schema work). `GameState[Sheet]` replaces
both engines' rules unions in phases 2–3; `rules_of`, `Record`/`WorldState`, transactions, and
the leak boundary in `src/aidm/core/world.py` are untouched.

Also in this file, all pure:

- `SheetDefinition(Value)` — the authored shape (numbers/counters/tags/notes/refs, counters as
  frozen `CounterTemplate`s) with `.runtime(kind, template) -> Sheet`, merging over the engine
  template. This is what `characters/` and `scenarios/` overlays validate against.
- `render_sheet(entity: Entity, sheet: Sheet) -> str` — the generic `entity_state`: numbers,
  counters as `cur/max`, tags with their text, notes, refs *by name only*. Full record text
  enters the turn through the `read_content` tool, never the scene render — that is the prompt
  budget: per-entity renders stay a few lines regardless of pack size.
- `SheetDelta` + `apply_delta` land here in phase 2 (see phase 2).

### `src/aidm/core/mechanics.py` (~240 lines) — the engine-neutral Director toolset

A `FunctionToolset[TurnContext[Sheet]]` joining `world_toolset()` from `src/aidm/core/tools.py`,
following its conventions (`ModelRetry` on bad input, `deps.record(facts)` return, trace/narrator
split on every `Fact`):

1. `roll(dice, vs=None, mode="sum", reason)` — the engine rolls. `dice` is a `DiceExpr`
   (`core/dice.py`); `mode` is `"sum" | "keep-highest" | "keep-lowest"` (advantage and
   disadvantage without a second call); `vs: int | None` compares the total and reports
   SUCCESS/FAILURE. The fact's `data` records **each individual die** (Story's 2d6 read, crit
   spotting), the total, `vs`, and the model-written `reason`. Narrator line: reason + outcome
   when `vs` is given (Director-authored text already reaches the Narrator via
   `DirectorNotes.intent`; this adds no new class of channel).
2. `adjust(entity_id, counter, delta, reason)` — clamps to `[minimum, maximum]`, emits the
   change that actually landed (0 = no fact). Refuses an unknown counter key with a `ModelRetry`
   listing the entity's actual counters — **tools never create counters**.
3. `spend(entity_id, counter, amount)` — refuses (not clamps) when `current - amount < minimum`.
4. `recharge(entity_id, label)` — refills every counter whose `recharge` is in the spec's
   `recharge[label]` list (see spec below; a 5e long rest must refill short-rest pools too).
5. `add_tag(entity_id, tag: SheetTag)` / `remove_tag(entity_id, tag_id)` — refuse duplicates /
   unknown ids.
6. `set_note(entity_id, key, text)` — empty text deletes the key.
7. `set_number(entity_id, key, value)` — refuses a key not already on the sheet; the fact
   records before → after. For lasting changes the fiction establishes (new armor, a permanent
   blessing), never for outcomes — the instructions say so, and hp-like values are counters, so
   the ledger stays out of its reach.
8. `read_content(ref)` — read-only; returns the record's name, numbers, and full `text`.
   Missing ref → `ModelRetry` with the `ContentMiss` summary.

Targeting rules match today's 5e tools: an actor target resolves through `require_actor_here`
and is revealed first (the `mechanics.reveal` pattern); items and locations must exist, are not
force-revealed by `set_note`/`set_number`, and those facts carry `narrator=None` while the
entity is unknown.

### `src/aidm/core/dice.py` — `git mv` from `src/aidm/engines/dnd5e/dice.py`

Moved intact in phase 1 (5e still imports it); the port is earned by its new core consumer,
`roll`. In phase 3, when `spells.py` dies, delete the now-consumerless `MOD` machinery:
`ModifierTerm`, `substituted`, `_self_contained`, `_positive`, `SelfContainedDice`,
`PositiveDice`, `Magnitude` (~35 lines). What remains: `terms`, `DiceTerm`/`ConstantTerm`,
`is_constant`, `DiceExpr`.

### `src/aidm/core/packs.py` addition (~25 lines) — the one record shape

```python
class LenientRecord(Record):                # Record already carries index + name
    text: str = ""                          # the rules text, markdown
    numbers: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP   # {"level": 3, "ac": 13, "slot-cost": 1}
    tags: tuple[Slug, ...] = ()
    options: tuple[ContentRef, ...] = ()    # for records that ARE a choice: the legal picks
    choose: int | None = None               # how many of options; validator: set iff options set
```

Strict, forbid-extra — the leniency is that everything mechanical beyond a few numbers lives in
`text`. `options` are full `ContentRef`s (a bare slug is ambiguous across collections); the
phase-2 proposal check enforces them mechanically. `PackFormat`/`validate_pack`/`read_pack`/
`write_pack` are reused as-is. Add `source_commit: str | None = None` to `Manifest` in phase 3
(see "Importer and regression").

### `src/aidm/core/enginepack.py` (~170 lines) — engines become data

An engine directory under `src/aidm/engines/<id>/` (package data, like the pack today):

```
engine.py        # the shim (Python, ~40-60 lines)
identity.py      # ENGINE_ID (unchanged)
spec.json        # EngineSpec: sheet templates, recharge labels, collection names
director.md      # engine rules procedure, appended to CORE_DIRECTOR as today
advancement.md   # advisor instructions for the proposal flow
packs/<pack-id>/ # zero or more lenient content packs (Story ships none)
```

`EngineSpec` (strict `Value` model): `templates: FrozenMap[Kind, SheetTemplate]` (a
`SheetTemplate` is default numbers + `CounterTemplate`s per kind), `recharge: FrozenMap[str,
tuple[str, ...]]` (label → labels it refills; 5e: `{"short-rest": ["short-rest"], "long-rest":
["short-rest", "long-rest"]}`), `collections: tuple[CollectionName, ...]`.

`load_engine(engine_dir, pack_paths=None, *, ...hooks) -> Engine[Sheet]` builds:

- `state_type=GameState[Sheet]`; `default_rules` instantiates the kind's template (this also
  covers Maintainer-grown entities);
- `entity_rules` for authored entities: validate the overlay as `SheetDefinition`, merge over
  the template; when it names a `ref`, copy the record's `numbers` onto the sheet — a number
  whose key the template declares as a counter becomes that counter with
  `current = maximum = value` (giant-rat `{"hp": 7, "ac": 12}` → hp counter 7/7, ac number 12);
- `validate_state`: every sheet carries at least its template's number and counter keys, and
  every `ref` resolves in the loaded content — the second half of the misname guard;
- `toolsets={"director": mechanics_toolset(content, spec)}`;
- `director_instructions` from `director.md`;
- `entity_state=render_sheet`;
- pack format `lenient_format(spec.collections)` — every collection holds `LenientRecord`.

The shim keeps the plugin exactly as `src/aidm/core/registry.py` expects (core imports the
module by name and reads `PLUGIN` — the sanctioned discovery exception; `enginepack` imports
nothing from `engines/`, so the graph stays acyclic):

```python
# engines/<id>/engine.py
ENGINE_DIR = Path(__file__).parent

def _build(config: Settings) -> Engine[Sheet]:
    section = PackPathsConfig.model_validate(config.engines.get(ENGINE_ID, {}))
    return load_engine(ENGINE_DIR, section.pack_paths, proposal=...)

PLUGIN = EnginePlugin(id=ENGINE_ID, build=_build, badge=("D&D 5E", "red-9"))
```

Until phase 2 removes them, `load_engine` also takes the engine's existing
`advance`/`advancement_available`/`advancement_panel` as pass-through arguments — core never
grows a NiceGUI import.

---

## Phase 0 — eval harness first

Built before anything moves, so the typed engine's behavior is the recorded baseline. Live
model, network allowed, run manually, **never in pytest or CI** — pytest stays deterministic
and offline.

Layout:

```
scripts/evals/
  run.py           # CLI: uv run python scripts/evals/run.py [--only <tag>] [--runs N]
  probes.py        # the era adapter (below)
  scenarios/*.json # one scenario per file
  results/         # committed run records: <date>-<git-sha>.json
  BASELINE.md      # recorded rates + the written phase-3 gate thresholds
```

**Scenario file** (strict Pydantic model in `run.py`):

```json
{
  "id": "melee-basic",
  "engine": "dnd5e",
  "tags": ["combat"],
  "scenario": "whispering-vault",
  "character": "kael",
  "setup":  [{"probe": "set_hp", "entity": "cloister_rat", "value": 4},
             {"probe": "reveal", "entity": "cloister_rat"}],
  "prompt": "I swing my longsword at the rat.",
  "checks": [{"probe": "hp_delta", "entity": "cloister_rat", "min": -12, "max": 0},
             {"probe": "attack_roll_happened"},
             {"probe": "hp_delta", "entity": "player", "min": 0, "max": 0}],
  "runs": 3
}
```

**Runner**: compose the real `scenarios/` + `characters/` content into an initial state
(`authored_world` + `engine.initial_world`), apply `setup` through probes, build a
`TurnContext(draft=state.draft(), rng=Random(seed), facts=[], default_rules=...)`, render the
director prompt with `prompts.render_director(SceneSnapshot.of(draft), ...)`, and run only the
director stage from `default_cast(engine, load_settings())` — narrator/maintainer/creator are
not under test. Then evaluate `checks` against the draft and the recorded facts.

**Probes** (`probes.py`, ~60 lines): `set_hp`, `reveal`, `hp_delta`, `counter_value`,
`has_condition`, `slots_remaining`, `attack_roll_happened`, `no_state_change`. Each probe reads
whichever state shape the checked-out code has (typed `StatBlock`/`Progression` now, `Sheet`
counters after phase 3) — scenarios and expectations survive the migration unchanged; only
probe internals are edited in phase 3. Expectations are outcome-level (ledger deltas, roll
occurrence) precisely because tool names and fact kinds change across the migration.

**Scoring**: a run passes iff every check holds; each scenario runs `runs` times (default 3 —
live models are stochastic); suite pass rate = passed runs / total runs, reported overall and
per tag. `run.py` writes `results/<date>-<sha>.json` (rates + per-scenario detail) and prints
the summary.

**Scenario set — combat-heavy, ~20 scenarios, at least 12 tagged `combat`** (interpretation
misses concentrate where arithmetic chains: to-hit → damage → riders). Required coverage:
player weapon attack (proficiency + ability mod arithmetic), monster attack on the player,
attack against high AC (miss handled, no damage), damage dice quoted from monster text, spell
attack cantrip, leveled spell spends the right slot, upcast damage scaling, save-for-half, a
condition rider (poisoned/prone), concentration replacing a previous spell, casting on an empty
slot (graceful refusal), healing clamped at max HP, dropping to 0 HP, advantage via
keep-highest, Second-Wind-style self-heal with level scaling, short-rest recharge. Non-combat:
ability check DC selection, long-rest recharge, level-up offer, note/tag bookkeeping.

**The gate mechanism**: `BASELINE.md` is written in this phase and contains (1) the typed
engine's recorded pass rates (overall and `combat`) with commit sha and date, (2) the written
thresholds for phase 3 — e.g. "phase 3 merges only if the lenient engine's `combat` rate is
within 10 points of baseline and at least 80% absolute" — committed *now*, before any code
moves, so the phase-3 decision is a check against a pre-registered number, not a judgment made
under sunk cost. Phase 3 appends its measured rates next to the thresholds before merge.

Verification: `uv run python scripts/evals/run.py` completes against the live model;
`BASELINE.md` records the rates; all four gates stay green (evals are additive).

---

## Phase 1 — substrate

Build `core/sheet.py`, `core/mechanics.py`, `core/enginepack.py`; `git mv
src/aidm/engines/dnd5e/dice.py src/aidm/core/dice.py` (update its importers:
`engines/dnd5e/{tools,mechanics,rolls,spells,procedures,ruleset}.py` and
`content/records/*`). Amend CLAUDE.md's first Design rule as quoted above, in this commit.
Nothing is deleted; both engines run unchanged. Src *rises* ~580 lines; phases 2–3 pay it back.

Ride-along: `tests/core/test_shipped_content.py` — for each engine id, load the real
`scenarios/whispering-vault` + `characters/kael` via `load_scenario`/`load_character`, build
`authored_world` and `engine.initial_world`, assert it validates. Deterministic, offline. This
is the standing guard that overlay re-authoring (phases 2–3) and pack regeneration never break
composition.

Tests (new, offline): `tests/core/test_sheet.py` — Counter clamp/minimum invariants, tag-id
uniqueness, the numbers/counters key-collision refusal, `SheetDefinition.runtime` merging.
`tests/core/test_mechanics.py` — each tool against a draft with seeded `Random`: `adjust`
clamps and refuses unknown counters, `spend` refuses insufficient pools, `recharge` follows the
label map, `roll` keep-highest with a seeded rng, reveal-on-target behavior, `set_number`
refuses unknown keys. `tests/core/test_enginepack.py` — spec parsing, template instantiation,
record-numbers → sheet mapping, `lenient_format` round trip through `read_pack`/`write_pack`
on a tmp-path fixture pack.

Verification: gates green; `uv run aidm` plays a 5e and a Story turn exactly as before; LOC
recorded in the commit message (≤ 9,150).

---

## Phase 2 — Story on the Sheet, and advancement as a proposal flow

Story proves the substrate carries a whole engine; the proposal flow lands in the same phase so
Story's growth never needs a throwaway interim panel.

### 2.1 Story re-expressed

`src/aidm/engines/story/` (1,168 lines) becomes spec + prose + shim (~60 lines of Python):

- Approaches → `numbers` (`bold`, `subtle`, `clever`, `empathetic`); stress →
  `counters["stress"]` (min 0, max per actor); growth → `counters["growth"]` (0..3);
  edges/burdens/bonds and conditions → `tags` (kind spelled in the tag text, e.g. "(burden)");
  gear benefits → item `tags`.
- The risk procedure moves to `engines/story/director.md`: roll 2d6 via `roll` (the fact
  reports both dice), *the Director* adds approach ± helpful ± hindering − difficulty into the
  expression (e.g. `roll("2d6+1")`), reads 10+/7–9/6− as strong/mixed/setback, marks growth
  with `adjust(player, "growth", +1)` on a player setback, applies stress via
  `adjust`/`spend`, records conditions via `add_tag`.
- **Delete**: `state.py`, `tools.py`, `rules.py`, `advancement.py`, `presentation.py`, `ui.py`.
  Keep `identity.py`; rewrite `engine.py` as the shim.
- Re-author `characters/kael/story.json` and `scenarios/whispering-vault/story.json` as
  `SheetDefinition` payloads (same authored facts, new shape).
- What is genuinely lost, accepted with eyes open: code no longer verifies that a claimed
  helpful tag exists before granting +1, no longer auto-marks growth, no longer bans risks
  while taken out, and no longer computes the outcome band — all four become instructions the
  evals watch. Add 2–3 Story scenarios to `scripts/evals/scenarios/` covering exactly these.

### 2.2 The proposal flow (generic, engine-agnostic)

- `core/sheet.py` gains `SheetDelta`: a frozen tuple of typed items, each with a `why: str` —
  `SetNumber(key, value)`, `GrantCounter(key, current, maximum, minimum, recharge)`,
  `ChangeCounter(key, delta | new_maximum)`, `AddTag(tag)`, `RemoveTag(tag_id)`,
  `AddRef(ref)`, `SetNote(key, text)` — plus `apply_delta(sheet, delta) -> tuple[Fact, ...]`
  (pure mutation of a draft's player sheet; ledger invariants revalidate on commit).
- `src/aidm/core/engine.py`: **delete** `advance`, `advancement_available`,
  `advancement_panel`, and the `AdvancementPanel`/`AdvancementSubmit` type aliases from
  `Engine`; add `proposal: ProposalSpec`:

  ```python
  @dataclass(frozen=True, slots=True)
  class ProposalSpec:
      offered: Callable[[GameState[Sheet]], AdvancementOffer | None]  # None = nothing pending
      instructions: str                                               # from advancement.md
      check: Callable[[GameState[Sheet], LenientRecord | None, SheetDelta], str | None]
  ```

  `AdvancementOffer(Frozen)`: `record: ContentRef | None` (the level row whose `options`
  bind the picks; None for free-form growth like Story's) and `prompt: str` (what the panel
  shows). Engines with typed state (5e until phase 3) pass a `ProposalSpec` that raises —
  their old panel path is gone, so **5e level-up is offline for this one phase**; that is the
  cost of not building interim plumbing twice, and it is why phases 2 and 3 are adjacent.
  *(If that gap is unacceptable, do 2.1, 2.2 and phase 3 on one branch and merge together —
  the commits stay separate, the app is only released after phase 3.)*
- **Delete** `AdvancementDecision` from `src/aidm/core/base.py`; `GameSession.advance` in
  `src/aidm/workflow/session.py` becomes `apply_proposal(delta: SheetDelta)`: run
  `engine.proposal.check`, `apply_delta` on a draft, commit, append an `Advance` trace entry
  (its shape in `core/turn.py` is facts-only and does not change).
- New `src/aidm/workflow/proposals.py` (~110 lines): one `Stage` from
  `settings.role("advisor")` (a new role name; `Settings.roles` already accepts it with zero
  config code), output type `SheetDelta`, deps `None`. Its prompt renders: the offer's record
  text and options (via content), the player's current sheet (`render_sheet`), and the
  player's typed intent. An illegal delta re-runs with `check`'s message as `ModelRetry`. The
  advisor sees only the player's own sheet and the offered record — no unrevealed canon by
  construction, so the context-boundary suite is untouched.
- `src/aidm/ui/panels/advancement.py` becomes the one generic panel (~140 lines): intent
  textbox → Propose → list each delta item with its `why` → Confirm calls `apply_proposal`;
  errors surface via `ui.notify` as today. `ui/app.py` wiring updates accordingly.
- Story's `ProposalSpec` (in its shim): `offered` returns a free-form offer when
  `counters["growth"].current == 3`; `check` (~15 lines) enforces the old caps — approach
  numbers ≤ +3, stress maximum ≤ 7, growth reset to 0 included in the delta — the one place
  Story keeps Python beyond the shim scaffold.

`SAVE_VERSION` bump (Story payload shape changed).

Tests: `tests/story/` rewritten small — shipped-content composition (already guarded),
template/spec assertions. `tests/core/test_proposals.py` with `FunctionModel`: an illegal
delta (ref outside `options`, cap exceeded) is retried with the `check` message; confirm
commits exactly the proposed delta; a rejected proposal leaves committed state untouched.
Delete `tests/story/test_story_rules.py` and the advancement/presentation tests of deleted
code.

Verification: gates green; play a Story turn with a risk and a growth advancement end-to-end
in `uv run aidm`; run the Story eval scenarios and record the rate in `results/`; LOC ≤ 8,400.

---

## Phase 3 — 5e on the Sheet; the typed engine deleted

**Entry gate**: re-read `scripts/evals/BASELINE.md`. **Exit gate**: before merge, run the full
eval suite against this branch, append the measured rates to `BASELINE.md` next to the
thresholds, and merge only inside them. Outside them: stop, diagnose (instructions? tool
shape? model?), and only proceed with a written revision of the threshold section explaining
why.

### 3.1 Re-expression

`src/aidm/engines/dnd5e/` (4,316 lines) → ~110 (shim + identity + `ProposalSpec` hook):

- **Delete outright**: `access.py`, `advancement.py`, `bestiary.py`, `features.py`,
  `mechanics.py`, `presentation.py`, `procedures.py`, `progression.py`, `rolls.py`,
  `ruleset.py`, `spells.py`, `state.py`, `tools.py`, `ui.py`, `values.py`, and the whole
  `content/` package (`pack_ruleset.py`, `registry.py`, `vocabulary.py`, `records/*`).
- Their jobs move to:
  - sheet counters/numbers — hp, `slot-1..slot-9` as nine counters (recharge `long-rest`),
    feature use pools as counters, abilities/ac/level/proficiency-bonus as numbers, monster
    ac/hp/attack bonuses as record `numbers` the loader maps onto sheets;
  - record `text` — what features, spells, and monster actions do, damage dice included;
  - `engines/dnd5e/director.md` — the procedure, e.g.: "An ability modifier is
    (score − 10) / 2, rounded down. An attack is `roll` of 1d20 + ability modifier +
    proficiency-bonus (if proficient) vs the target's armor-class; on a hit, `roll` the
    weapon's damage and `adjust` the target's hp by the negative total. A spell spends its
    slot with `spend` before any effect. Never state an outcome you did not get from `roll`;
    never change a pool except through `adjust`/`spend`. Use `read_content` before applying
    a spell or feature you cannot quote."; conditions become tags whose names follow the
    SRD conditions records;
  - level rows as lenient records — `levels/fighter-3` = `text` + `numbers` (hp-die,
    proficiency-bonus, slot maxima) + `options`/`choose` for its picks, so the proposal
    `check` still enforces pick legality mechanically — the one thing lenient data keeps
    encoding as data;
  - `advancement.md` — advisor guidance (roll-or-average HP policy, ASI rules as prose).
- 5e `ProposalSpec` in the shim: `offered` reads the `advancement-ready` tag (the Director is
  instructed to `add_tag` it when the story earns a level, replacing today's `level_up`
  tool) and maps `numbers["level"] + 1` plus the class ref to the level record; `check`
  verifies picks against `options`/`choose` and that the tag is present and removed by the
  delta.
- Re-author `characters/kael/dnd5e.json` as a `SheetDefinition` (attributes, hp, refs to
  class/race/background/features, decisions now simply refs held) and
  `scenarios/whispering-vault/dnd5e.json` (giant-rat by monster ref, unchanged in spirit).
- Trim `core/dice.py`'s `MOD` machinery (named in the substrate section).
- `SAVE_VERSION` bump.

### 3.2 Importer

`scripts/srd/` (1,931 lines incl. `upstream/`) rewritten to ~400: read the same upstream
checkout, emit `LenientRecord`s — name, prose (desc lines joined as markdown), the few numbers
(spell level, slot-cost, uses, monster ac/hp/attack bonuses, level-row numbers), `options` as
refs, `choose`. The classification layer (`feature_mechanics.py`, 206 lines) and
`corrections.py` entries that existed to force a mechanics class die. `scripts/import_srd.py`
keeps its interface and its `SAVE_VERSION` auto-bump. Regenerate
`src/aidm/engines/dnd5e/packs/srd-2014` in this commit.

### 3.3 Tests

`tests/dnd5e/` rewritten small: the byte-identical round-trip test (keep the name
`test_a_loaded_pack_writes_back_byte_for_byte`), a pack census against the regenerated
manifest, kael + whispering-vault composition under the 5e engine (already guarded by
`test_shipped_content.py` — extend its assertions to the sheet's canonical keys: `hp`,
`slot-*`, `armor-class`), a template-derived monster sheet from the real giant-rat record, and
a proposal-flow test with `FunctionModel` proposing a fighter level with an out-of-options
pick (retried) and a legal one (committed). Delete the rest of `tests/dnd5e/`; `tests/core/`
integrity and context-boundary suites must pass untouched.

Verification: gates green; the eval exit gate above; play a combat turn and a level-up in
`uv run aidm`; LOC ≤ 4,400 recorded in the commit message.

---

## Phase 3.5 — the Director is carrying too much

Not a rollback. Phase 3's thesis held: engines are data, a pack plus a ~70-line shim, and the same
substrate runs two rulesets. What phase 3 also measured is the bill for it, and phase 3.5 is where
that bill gets paid.

**The evidence, on the frozen 21-scenario 5e suite, same model and `retries=3` throughout:**

| Tree | interpretation | completion | combat |
|---|---|---|---|
| typed 5e (baseline) | 74.2% | 95.2% | 67.8% |
| lenient, lean pack (2 runs) | 87.3 / 89.5% | 100 / 90.5% | 95.6 / 82.2% |
| lenient, enriched pack (1 run) | **63.3%** | 95.2% | **66.7%** |

The enriched pack put every record's mechanics into the per-turn render — damage dice, save DCs,
upcast ladders, monster attack lines — and interpretation fell 25 points against a run-to-run drift
of 2.2. The dominant failure is not wrong arithmetic. It is **`0 rolls against a target number`**:
the Director did not act at all, on turns whose prompt named the action. Three more turns died with
`Tool 'roll' exceeded max retries`. That is the *under-acting* signature phase 2 recorded for small
models, now appearing in the model this project keeps, as its context grew.

The reading: more correct content in front of the Director does not buy more correct play, and past
some point it costs. The rules-facing role is being asked to read a large disorganised context,
choose a procedure, do the arithmetic, and emit well-formed tool calls, all in one pass. Phase 3.5
splits that load. **It plans; it does not prescribe** — the three sections below state intent and
constraints, and the implementation plan is written separately against them.

### 3.5.1 A referee role

The Director fails in two ways the substrate can see: it emits a tool call the schema refuses until
retries run out, and it ends a turn without having called a tool the turn plainly needed. Both are
mechanical, both are detectable from the turn's own record, and neither needs the rules to be
re-encoded in Python to catch.

A referee is a second role placed **before or after the Director** — the plan decides which, and the
choice is itself part of the work. Before, it constrains what the Director is asked to do; after, it
checks what the Director did against the facts recorded in the `Turn` trace and can send the turn
back. The substrate was built for the second option: every tool call already records its facts, and
`docs/ROADMAP.md` has carried "engine referee" since phase 2 for exactly this.

- **Target**: completion at or near 100%, and the `0 rolls` class of failure caught rather than
  committed. Interpretation should rise as a consequence, not as a separate ambition.
- **Constraint**: the referee never writes state. It rules, retries, or reports; the Director's
  tools remain the only path into the draft, and the narrating role's context boundary is untouched.
- **Constraint**: it must not become the typed engine again. A referee that hard-codes 5e arithmetic
  has undone phase 3. It reads the same content the Director reads.
- **Cost to weigh**: another sequential model call per turn, on a pipeline that already makes four.

### 3.5.2 Context organisation

Read the director prompt as a human. It is confusing and disorganised — sections in no deliberate
order, the same fact reachable three ways, entity renders and instructions interleaved without a
hierarchy a reader could hold. The enriched pack made an existing weakness load-bearing rather than
creating a new one.

- **Target**: a prompt whose structure a person can follow at a glance — what is happening, who is
  here, what this actor can do, what the rules say, what is being asked.
- **Constraint**: `SceneSnapshot` and the Narrator-only `VisibleScene` in `workflow/prompts.py` stay
  the single place context is projected; this is a reorganisation, not new plumbing scattered
  through the pipeline.
- **Constraint**: the leak boundary is not negotiable. Whatever is reorganised, the narrating role
  still cannot see unrevealed canon.
- **Open question the plan must answer**: whether the fix is ordering and headings alone, or whether
  the render must also become selective — `docs/ROADMAP.md`'s prompt-aware renderer, expanding a
  spell only when the turn reaches for it. The measurement decides; do not assume less content is
  the answer, because the lean pack scored well *and* left the Director guessing damage dice.

### 3.5.3 Instructions and tool descriptions

`director.md` grew by accretion across three phases and has never had a writing pass. The tool
docstrings in `core/mechanics.py` are the Director's only description of its own instruments, and
they carry no examples — worked examples in a tool description are among the cheapest known
improvements to tool-calling reliability, and this project has never tried them.

- **Target**: fewer, sharper instructions; each tool described with at least one concrete call.
- **Constraint**: `core/mechanics.py` is shared by every engine, so its docstrings stay
  engine-neutral. 5e-specific wording belongs in `engines/dnd5e/director.md`.
- **Constraint**: these docstrings are runtime behaviour, per CLAUDE.md — a change to them is a
  change to the prompt, and is measured, not eyeballed.
- **Known lever, already proven twice**: placement. A rule the Director never reaches does not fire.
  Phase 2 moved a buried precondition to the front of its procedure and went 33% → 100%; phase 3
  moved the advancement trigger out of the last section for the same reason.

### How phase 3.5 is judged

The same frozen 21-scenario suite, `--only dnd5e --runs 3`, run twice, compared against the three
trees in the table above — **not** against the typed baseline, which phase 3 already cleared. Change
one thing at a time and measure it; the whole point of the phase is that this project can no longer
tell which of several simultaneous changes moved a number. Budget is not the constraint here: `src`
may grow, and a referee that buys 30 points of completion is worth more than the lines it costs.

## Closing out

Not a phase: what phases 0–3 knowingly left, gathered here so it is not rediscovered. Written
during phase 2, from what the live runs taught.

The director model question is **settled**: four models were compared during phase 2 and
`openai/gpt-oss-120b` stays, so the phase-3 gate compares like with like and needs no second
baseline. If that is ever revisited, re-baselining is only possible *before* phase 3 deletes the
typed engine — see "If you change the director model" in `scripts/evals/BASELINE.md`. Everything
below can wait until the deletion is done.

1. **Eval coverage the earlier phases owe.** Phase 0 named two required scenarios it could not
   write and assigned each to the phase that creates the capability: advantage via `keep-highest`
   (created in phase 1) and concentration replacing a spell (created in phase 3). Neither exists.
   Write both and record their rates.
2. **The one-sided story checks, and what a run record keeps.** Two of the three story scenarios
   also pass when the Director does nothing, so a model that never rolls scores 67% on the suite —
   the phase-2 model comparison hit exactly that and could not rank the small models because of it.
   Add a probe that counts every `dice_rolled`, not only the contested ones, so "did not roll" and
   "rolled without `vs`" stop reading alike; and record the turn's fact traces on a failed run,
   because `RunRecord` keeps failures only, which is why that question is currently unanswerable.
3. **The player's `armor-class`.** Phase-0 finding 3: it was hard-coded to 10 in the typed engine,
   never derived from dexterity or worn armour. Phase 3 is supposed to make it a number the content
   and the level rows set; confirm it did, because nothing fails loudly if it did not.
4. **The engine referee** (`docs/ROADMAP.md`). Phase 2 measured a precondition an instruction could
   not make stick — the Director rolled for a taken-out actor in 4 of 6 runs. That is the shape of
   miss a post-Director verification stage exists to catch, and the substrate already records every
   tool call's facts in the `Turn` trace for it. Decide whether the interpretation rates justify
   building it; if they do, it is a role, not a rewrite.
5. **Two limits the proposal flow accepts**, worth revisiting only when a third engine wants them:
   a proposal writes the player's sheet and nothing else (Story lost its gear-acquisition
   advancement), and `choose` is an exact count, so "pick up to two" cannot be offered.
6. **Prove "engines are data" with a third engine.** The claim is that ironsworn or a homebrew
   ruleset costs a pack plus a ~40–60 line shim. Until one exists, that is untested, and the
   substrate's assumptions have only ever been checked against the two engines that shaped it.

---

## Importer and regression

The vendored pack `src/aidm/engines/dnd5e/packs/srd-2014` is generated from an external
checkout of `5e-bits/5e-database` (not vendored — see the memory note). Rules, standing:

1. Any commit that changes the pack schema reruns `scripts/import_srd.py <checkout>` and
   commits the regenerated pack together with the schema change. Keep `write_pack` formatting
   (`indent=2, ensure_ascii=False`, trailing newline, spec order) so diffs stay reviewable.
2. **Pin the upstream commit hash.** Phase 3 adds `source_commit: str | None = None` to
   `Manifest` in `src/aidm/core/packs.py`; the importer records `git rev-parse HEAD` of the
   checkout there. The npm version string alone ("5.10.0") lets content churn smuggle into
   schema commits and break the byte-identical baseline mid-refactor; regenerations within
   this refactor must use the identical hash.
3. The `read_pack → write_pack` byte-identical round trip stays the format regression
   (`tests/dnd5e/test_content.py` today; keep the test through the phase-3 rewrite).
4. `characters/kael` and `scenarios/whispering-vault` overlays must compose after every
   regeneration — `tests/core/test_shipped_content.py` (added phase 1) is the check. After
   phase 3 the kael sheet references records by `ContentRef`; a regeneration that renames an
   index breaks this test, which is the point: fix the overlay in the same commit, knowingly.

## What this buys

- **Engines are data**: ironsworn (datasworn's published JSON maps onto `LenientRecord`
  almost directly — moves/assets/oracles are prose + small numbers, imported via the srd
  pattern with a pinned pre-1.0 version), homebrew, or "5e with a twist" need content plus a
  ~40–60 line shim.
- **The pack format is the ingestion format**: a future scenario/PDF creator's output *is* a
  lenient pack; location state, NPC memory, quests-as-notes land on the Sheet with no schema
  work.
- **~4,300 fewer src lines** and one engine philosophy instead of two typed unions plus a
  substrate; concentration, temp HP, and prepared casting stop being schema work (a note, a
  counter, and instructions respectively).

## What it costs (accepted, measured)

- **5e math fidelity is a model property.** Attack bonuses, DCs, upcast damage are computed by
  the Director from raw numbers and instructions. Phase 0 measures it; the phase-3 thresholds
  bound it; a rules-literate player will still catch misses the ledger cannot.
- **Weaker save semantics.** The Sheet validates shape, not meaning. The misname hazard
  (`hp` vs `hit-points`) is closed structurally where it matters: templates create canonical
  keys, `validate_state` requires them, and tools refuse keys that do not exist — but a
  *template* typo is still only caught by tests and evals.
- **Legality thins out.** Picks are still checked against `options`; subtler constraints the
  typed engine encoded (resource-pool aliasing, replacement lineage, prerequisites) become
  prose the advisor can miss and `check` cannot see.
- **Prompt weight moves to tool round-trips**: scene renders stay bounded (refs by name), but
  a rules-heavy turn now spends `read_content` calls and their latency.
- Verification shifts from "the compiler rejects bad content" to "the tools refuse bad
  arithmetic" plus out-of-band evals — pytest guards the ledger and the boundaries, evals
  guard the interpretation.
