# Redesign: structured turn plans instead of tool-driven mutation

Self-standing implementation plan. It assumes no prior knowledge of this repository: read the
Background and Design sections before touching code, then execute the phases in order. Every phase
ends with commands that must pass before the next phase starts.

## Objective

Replace the Director's iterative tool-calling with **one structured `TurnPlan` output**, resolved
deterministically by engine code, and remove the Referee from the default turn. The Maintainer
and Creator stay exactly as they are — the narration-driven canon growth loop is the heart of the
project, and the eval failures were never theirs. Measure before and after with the existing eval
suite; the numbers land in `baseline.md`.

Why: the eval suite (`scripts/evals/`) shows the Director failing multi-step tool protocols —
rolls without follow-through, spells cast without spending slots, rests narrated without
`recharge`, the `advancement-ready` tag never added (0% even on claude-sonnet-4.5). The procedure
the model keeps dropping is deterministic; it is written as prose in
`src/aidm/engines/dnd5e/director.md`. This redesign moves it into code. It also removes the
Director's serial tool round-trips and the Referee round, cutting the critical path to
director → narrator, with Maintainer/Creator unchanged after them.

## Background: the repository today

Run everything from the repo root. Commands that must always pass:

```bash
uv run pytest            # deterministic, no network
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Layout (only what this plan touches):

| Path | What it is |
|---|---|
| `src/aidm/core/base.py` | `Entity`, `Frozen`/`Mutable` bases, `Slug`, `SAVE_VERSION` |
| `src/aidm/core/world.py` | `GameState` (draft/commit transaction), `WorldState`, `Fact`-emitting mutations (`add`, `reveal`, `move`) |
| `src/aidm/core/facts.py` | `Fact`: one thing that occurred; `trace` for the log, `narrator` for the Narrator |
| `src/aidm/core/sheet.py` | `Sheet` (numbers/counters/tags/notes/refs) — the universal rules state; `SheetDelta` used by advancement |
| `src/aidm/core/dice.py` | `DiceExpr` validated dice strings, `terms()` parser |
| `src/aidm/core/tools.py` | Director world tools (`discover`, `move`, `take_item`…) + `DirectorNotes`, `RefereeVerdict`, `TurnContext` |
| `src/aidm/core/mechanics.py` | Director sheet tools (`roll`, `adjust`, `spend`, `recharge`, tags, notes, `read_content`) |
| `src/aidm/core/engine.py` | The `Engine` dataclass every engine builds |
| `src/aidm/core/enginepack.py` | `load_engine`: builds an `Engine[Sheet]` from `spec.json` + packs + markdown prompts |
| `src/aidm/core/packs.py`, `content.py` | Lenient content records (`LenientRecord`: text/numbers/notes/tags/options), scenario/character loading |
| `src/aidm/workflow/pipeline.py` | The turn script: director → referee → narrator → maintainer → creator |
| `src/aidm/workflow/prompts.py` | All prompt rendering (`SceneSnapshot`, Narrator-only `VisibleScene`) and role instruction strings |
| `src/aidm/workflow/roles.py` | `Stage`: one configured pydantic-ai agent |
| `src/aidm/workflow/session.py` | `GameSession` (submit/commit/save) and `Runtime` (composition root) |
| `src/aidm/core/turn.py` | `Turn` trace entry, `GrowthRequest`, `screen_growth` |
| `src/aidm/engines/story/` | Story engine: `engine.py` shim, `spec.json`, `director.md`, `advancement.md` |
| `src/aidm/engines/dnd5e/` | 5e engine: same shape + `packs/srd-2014/*.json` |
| `scripts/evals/run.py`, `probes.py` | Live-model eval harness: runs the director stage alone against scenario probes |

Invariants that survive unchanged (from `CLAUDE.md` and `docs/ROADMAP.md`):

- The model never writes state. State evolves by draft → mutate → revalidate-whole-copy → commit.
- The Narrator's input type (`VisibleScene`) has no field an unrevealed-canon leak could travel
  through. Do not weaken it.
- Facts are the one truthful record of what occurred.
- One composition root (`Runtime`); engines are plugins built from data.
- A save refuses a stale `SAVE_VERSION` rather than converting.

## Design

### The new turn

```text
player input
  → DIRECTOR: one structured TurnPlan          (only tool: read_content)
  → validate plan against untouched state       (ModelRetry with the precise reason)
  → draft = state.draft()
  → engine resolves plan.action on the draft    (rolls, costs, intrinsic outcomes — pure code)
  → apply outcome branch + unconditional effects
  → revalidate draft, render narrator evidence from facts
  → NARRATOR: prose from resolved facts
  → MAINTAINER + CREATOR: unchanged             (grow canon from the narration)
  → commit
```

Only the Referee is deleted. Its guarantee ("was a roll made, cost paid, outcome applied")
becomes unrepresentable: the resolver *is* the procedure. The Maintainer and Creator steps,
prompts, and models stay exactly as they are in `pipeline.py` today.

### Two kinds of conditionality — keep them apart

1. **Intrinsic** consequences of an action (attack hits → damage roll → hp adjust; player setback
   → growth mark) live in the engine's resolver function. The model never states them.
2. **Fiction** consequences the model attaches ("on failure the guard calls for help") live in the
   plan as flat, outcome-keyed effect lists. The engine declares the legal outcome labels per
   action; the resolver picks exactly one after rolling. No nesting, no conditional expressions.

### New core types

New module `src/aidm/core/effects.py`. One typed effect vocabulary, replacing both the mutation
tools in `tools.py`/`mechanics.py` and (eventually) overlapping `SheetDelta` ops. Discriminated
union, exactly like `DeltaChange` in `sheet.py`:

```python
class Reveal(Frozen):
    op: Literal["reveal"] = "reveal"
    entity_id: EntityId

class MoveActor(Frozen):        # actor (or the player, actor_id=None) to a location
    op: Literal["move-actor"] = "move-actor"
    location_id: EntityId
    actor_id: EntityId | None = None

class TakeItem(Frozen): ...      # loose item here → player inventory
class DropItem(Frozen): ...      # carried item → current location
class GiveItem(Frozen): ...      # carried item → actor here
class GainImprovisedItem(Frozen):  # minor uncanonical object, name only
class AdjustCounter(Frozen):     # entity_id, counter, delta, reason  (clamped)
class SpendCounter(Frozen):      # entity_id, counter, amount         (refuses below minimum)
class AddTag(Frozen):            # entity_id, tag_id, name, text
class RemoveTag(Frozen):         # entity_id, tag_id
class SetNote(Frozen):           # entity_id, key, text ('' clears)
class SetNumber(Frozen):         # entity_id, key, value (key must exist)

type Effect = Annotated[Reveal | MoveActor | ... , Field(discriminator="op")]
```

One pure function, ported from the existing tool bodies (keep the exact fact wording and the
leak guards — `mechanics._fact` narrates nothing for unknown entities; acting on an actor
reveals them, acting on an item does not):

```python
def apply_effect(draft: GameState[R], effect: Effect,
                 default_rules: Callable[[Entity], R]) -> list[Fact]
    # raises ValueError with a model-readable reason on any precondition today's
    # tools raise ModelRetry for
```

There is deliberately **no** separate `check_effect`: preconditions would exist twice and
drift. Plan validation checks effects by trial-applying them to a throwaway draft — the exact
pattern `ProposalSpec.violation` already uses in `core/engine.py`.

`recharge` is deliberately **not** an effect: it needs the engine's refill map, so it becomes the
5e `Rest` action. `roll` is not an effect either: rolling belongs to resolvers.

New module `src/aidm/core/plan.py`:

```python
class TurnPlanBase(Frozen):
    intent: str                                   # for the Narrator, as DirectorNotes.intent today
    tone: str
    speaker_id: EntityId | None = None
    effects: tuple[Effect, ...] = ()              # unconditional world/sheet consequences
    branches: tuple[OutcomeBranch, ...] = ()      # fiction consequences keyed by outcome

class OutcomeBranch(Frozen):
    outcome: Slug                                 # a label the engine declares for the action
    effects: tuple[Effect, ...]
```

(A tuple of labelled branches, not a mapping: constrained-key mappings emit JSON schemas that
native structured-output backends handle poorly, and `FrozenMap` is for pack data.)

New named entities are **not** in the plan: introducing canon from narration stays the
Maintainer's job, and the Creator still fleshes each accepted request out.

Engines subclass with their action union (and any bookkeeping flags):

```python
class StoryPlan(TurnPlanBase):
    action: StoryAction | None = None

class Dnd5ePlan(TurnPlanBase):
    action: Dnd5eAction | None = None
    milestone_earned: bool = False   # replaces the free-form advancement-ready tag call
```

`Engine` (in `core/engine.py`) gains three members; `toolsets` and `director_instructions`
stay (the director toolset shrinks to `read_content` alone, which must remain engine-built —
it closes over that engine's `Content`):

```python
plan_type: type[TurnPlanBase]                     # for NativeOutput
check_plan: Callable[[GameState[R], TurnPlanBase], str | None]
resolve_action: Callable[[GameState[R], TurnPlanBase, Random], list[Fact]]
```

Two wiring realities a beginner must know up front:

- **Give all three defaults during the migration** (e.g. a `plan_type` of `TurnPlanBase` and
  resolvers that refuse every action), removed in Phase 7 — otherwise the tree cannot stay
  green between Phases 2 and 4, since both engines construct `Engine` before they grow plans.
- **Resolvers need `Content` and `EngineSpec`**, which are created inside `load_engine`
  (`enginepack.py`). Pass them as factories — `check_plan=lambda content, spec: ...`-style
  parameters that `load_engine` calls, the same pattern `offered` already uses. And because
  the registry erases engines to `AnyEngine`, resolver callables must accept `TurnPlanBase`
  and narrow with `isinstance` (fail fast on a foreign plan); basedpyright will refuse a
  `StoryPlan`-typed parameter.

`check_plan` runs in the director stage's output validator against the *untouched* committed
state: unknown ids, illegal speaker (`check_speaker` in `tools.py` already exists), action
preconditions (taken-out actor, no such weapon), branch labels not legal for the chosen action,
and a trial-apply of every effect on a throwaway draft. Any reason → `ModelRetry(reason)` → the
model retries from clean state. This is the advancement pattern (`proposals.py` + 
`ProposalSpec.violation`) generalised to the turn — read those ~60 lines first; they are the
template for everything here.

`resolve_action` mutates the draft: it runs the action's procedure (rolls via `rng`, using
`dice.terms` — lift `_evaluate` and `_rolled` out of `mechanics.py`), applies intrinsic effects,
selects the outcome label, applies the matching branch's effects via `apply_effect` (a missing
branch is fine — not every outcome needs fiction consequences), and returns the facts. With
`action=None` it applies no branch (a plan with branches but no action is a `check_plan`
refusal).

The pipeline (not the engine) then applies `plan.effects` and hands the facts to the Narrator
exactly as today (`narrator_evidence`); Maintainer and Creator run after the narration,
unchanged.

### Story actions (implement first — smallest vocabulary)

From `src/aidm/engines/story/director.md`, the whole game is one procedure:

```python
class Risk(Frozen):
    act: Literal["risk"] = "risk"
    actor_id: EntityId               # PLAYER_ID or an actor here
    approach: Literal["bold", "subtle", "clever", "empathetic"]
    difficulty: Literal["risky", "demanding", "extreme"]     # -0 / -1 / -2
    helping_tag_id: Slug | None = None    # on the actor's sheet, or on an item they carry
    hindering_tag_id: Slug | None = None  # on the actor's sheet
    stakes: str                      # what is attempted, in a few words (the roll's reason)

type StoryAction = Risk            # a union of one, ready to grow
```

Resolver: refuse (in `check_plan`) if the actor's `stress` is at maximum (TAKEN OUT — the
existing eval `story-taken-out-cannot-risk` checks this). Roll `2d6 + approach + 1(helping) −
1(hindering) − difficulty` once, `vs 7`. Outcome labels: `strong` (≥10), `mixed` (7–9),
`setback` (≤6). Intrinsic: a `setback` on the player adjusts the player's `growth` +1. Stress
harm and lasting tags stay **fiction** effects the model puts in branches, because their size is
a judgment call.

### 5e actions

```python
class Attack(Frozen):
    act: Literal["attack"] = "attack"
    attacker_id: EntityId
    target_id: EntityId
    weapon_item_id: EntityId | None = None      # a carried item whose sheet refs a weapon record
    attack_bonus: int | None = None             # for monster stat-block attacks (prose-only in the pack)
    damage: DiceExpr | None = None              #   — the model copies both off the rendered block
    two_handed: bool = False
    mode: Literal["normal", "advantage", "disadvantage"] = "normal"

class CastSpell(Frozen):
    act: Literal["cast-spell"] = "cast-spell"
    caster_id: EntityId
    spell: str                                   # content ref "pack/collection/index", as rendered
    slot_level: int | None = None                # None = cantrip
    target_id: EntityId | None = None

class Check(Frozen):                             # ability checks and saving throws
    act: Literal["check"] = "check"
    actor_id: EntityId
    bonus: int                                   # the model works the modifier out from the sheet
    dc: int
    reason: str
    mode: Literal["normal", "advantage", "disadvantage"] = "normal"

class UseFeature(Frozen):                        # spend a limited-use counter
    act: Literal["use-feature"] = "use-feature"
    actor_id: EntityId
    counter: Slug
    heal: DiceExpr | None = None                 # e.g. Second Wind's "1d10 + 5": rolled by the
                                                 # resolver, applied to the actor's hp

class Rest(Frozen):
    act: Literal["rest"] = "rest"
    actor_id: EntityId
    label: str                                   # validated against spec.recharge

class Improvise(Frozen):                         # escape hatch for anything not modelled above
    act: Literal["improvise"] = "improvise"
    dice: DiceExpr
    vs: int | None = None
    reason: str
    mode: Literal["normal", "advantage", "disadvantage"] = "normal"

type Dnd5eAction = Annotated[Attack | CastSpell | Check | UseFeature | Rest | Improvise,
                             Field(discriminator="act")]
```

**Outcome labels** (what `check_plan` allows in `branches` and the director prompt teaches):
any action that rolls against a target number — `Attack`, `CastSpell` with an attack or save,
`Check`, `Improvise` with `vs` — has exactly `success` and `failure`. `UseFeature`, `Rest`,
and `Improvise` without `vs` roll nothing contested and allow no branches. For a save-based
spell the labels follow the *caster's* perspective: `success` means the target failed its save.

`Attack` validation: exactly one of `weapon_item_id` or (`attack_bonus` + `damage`); a weapon
must be carried by the attacker and resolve to a weapon record. Resolver for the weapon path
computes everything from data: ability modifier (`(score − 10) // 2`; STR melee, DEX ranged,
better of both for the `finesse` tag), `proficiency-bonus`, target `armor-class`, damage dice
from the record's structured numbers (`damage-dice-count`/`damage-die`, the `two-handed-*` pair
when `two_handed` and the record has the `versatile` tag). Roll to-hit vs AC; on success roll
damage dice **plus the same ability modifier** (the eval `melee-damage-window` asserts the
1d8+3 window, not 1d8) and adjust the target's `hp` negatively. On failure: nothing. The
model-supplied path uses `attack_bonus` and `damage` as given.

`CastSpell` needs a small normaliser in `src/aidm/engines/dnd5e/content5e.py`:

```python
class SpellFacts(Frozen):
    level: int | None            # None = cantrip; parsed from notes["level"]
    attack: bool                 # notes has "attack"
    save_ability: str | None     # parsed from notes["save"], e.g. "DEX save for half" → "dexterity"
    half_on_save: bool
    damage: DiceExpr | None      # dice regex out of notes["damage"] ("1d10 fire" → "1d10")
    heal: DiceExpr | None
    scaling: tuple[tuple[int, DiceExpr], ...]   # notes["scaling"]: "level 5: 2d10, ..." / "slot 2: ..."
    concentration: bool          # "concentration" in tags or text header

    @classmethod
    def from_record(cls, record: LenientRecord) -> "SpellFacts | None":  # None = unparseable
```

Look at `packs/srd-2014/spells.json` while writing the regexes; the notes keys are stable
importer output (`level`, `attack`, `save`, `damage`, `heal`, `scaling`, `range`). The dice
regex must keep whole expressions, constants included — magic-missile's damage is `"3d4 + 3"` —
and treat a "+ spellcasting modifier" suffix as a flag the resolver substitutes, not a parse
failure. Cover the spells the eval scenarios actually cast first (open
`scripts/evals/scenarios/*spell*.json` and `scripts/evals/characters/` and list them).
`check_plan` refuses an unparseable spell with "resolve it with `improvise` instead", so
coverage can grow later without blocking play.

Two formulas the resolver owns (the evals assert them exactly — `save-for-half` checks a DC of
precisely 8 + proficiency + modifier):

- spell attack bonus = `proficiency-bonus` + spellcasting ability modifier
- spell save DC = 8 + `proficiency-bonus` + spellcasting ability modifier

The spellcasting ability is not on the sheet's numbers: it sits in the caster's class record's
`notes["spellcasting"]` (`"INT"`, `"CHA"`…), reached through the sheet's `classes` ref — write
one small lookup for it.

Resolver order: spend `slot-{N}` first (refusal kills the whole action — this is the guarantee
the old prompt begged for), then attack roll or target save, then damage/heal with the scaling
row for the slot actually spent (cantrips scale by caster level), then a `concentration` note
when the record is tagged for it.

`Rest` resolver ports `Mechanics.recharge`. `Improvise` resolver is `roll` as it exists today:
evaluate, compare `vs`, emit the fact; its branches carry whatever follows. `milestone_earned`
resolves to `AddTag(advancement-ready)` on the player unless already carried (then it is ignored,
not an error).

### Prompts

`prompts.py` keeps `SceneSnapshot`/`VisibleScene`/all render functions. Changes:

- `CORE_DIRECTOR` rewritten: same world-orientation paragraphs (ids, here/elsewhere, prefer
  canon), then: *you answer with one plan — the single action resolved this turn, its fiction
  consequences keyed by outcome, and unconditional consequences. You never state a roll's
  result: branches for outcomes that do not occur simply never apply.* Named-entity creation is
  not the Director's job (beyond `GainImprovisedItem`); the Maintainer handles it after
  narration, as today.
- Each engine's `director.md` shrinks to: the sheet vocabulary section (keep), what each action
  means and when to pick it, how to fill its fields (e.g. work out a check's `bonus` from the
  sheet; copy a monster's attack line into `attack_bonus`/`damage`), and what belongs in
  branches vs never in the plan (no damage, no hp, no slot bookkeeping — the engine does those).
  Field descriptions in the action models carry the per-field rules; the markdown carries only
  what spans fields.
- `render_referee` and `REFEREE` are deleted. The Narrator, Maintainer, and Creator prompts are
  untouched.

`read_content` stays, as the Director's only tool (rules text lookups are real I/O, the one
thing tools are still for). It closes over each engine's `Content`, so it stays engine-built:
move it and its two render helpers (~40 lines) into `enginepack.py`, where the toolset is
assembled — no new module. After that `mechanics.py` and the mutating half of `tools.py` are
deleted (their bodies live on in `effects.py` and the resolvers — port, don't rewrite).

### Pipeline, session, traces

- `pipeline.py`: `Cast` becomes `director`, `narrator`, `maintainer`, `creator`. The script:
  `director_step` (structured plan, validated) → `resolve_step` (pure code: draft, resolve,
  effects) → `narrator_step` → `maintainer_step` → `creator_step`, the last two unchanged.
  `TurnWorkspace` replaces `notes` with the plan; `Turn` (in `turn.py`) replaces
  `notes: DirectorNotes` with `plan: dict[str, JsonValue]` — the typed plan dumped at record
  time — and keeps `growth`/`created`/`rejected`. **Not** `plan: TurnPlanBase` with
  `SerializeAsAny`: trace entries are read back through the engine-agnostic `TRACE_ADAPTER` in
  `store.py`, where an engine subclass's extra fields would hit `Frozen`'s `extra="forbid"`
  and crash every resume. (`Record.rules` gets away with it only because `GameState` is loaded
  through the engine's own `state_type`.)
- `DirectorNotes`/`RefereeVerdict` and `referee_step` are deleted.
- Bump `SAVE_VERSION` in `base.py` (trace entries changed shape; stale saves must be refused).
- `session.py` and the UI need no structural change — `role_names` comes from the script, and
  the trace panel renders whatever `Turn` holds; adjust field access where it names `notes`.

### What deliberately does not change in this pass

- Prompt scope (every hidden entity still rendered to the Director). GPT's proposal §7 is a
  separate, later experiment — changing it now would blur the eval comparison.
- Advancement (`proposals.py`, `SheetDelta`) — already the target pattern. `SheetDelta` and `Effect`
  stay separate for good: three of their five shared ops differ on purpose (a delta `SetNumber`
  grows a sheet with keys it does not hold, where the effect refuses them; `GrantCounter`/`AddRef`
  have no effect counterpart), so a merged type needs mode flags and grows.
- Content pack format, importer scripts, scenario/character files, `Sheet`, `GameState`.

---

## Phase 0 — harness prep (≈30 min)

The eval harness must time runs so before/after latency is comparable.

1. In `scripts/evals/run.py`: add `duration_s: float = 0.0` to `RunRecord`; wrap the `_turn` call
   in `run_case` with `time.perf_counter()`. Add mean duration to `CaseRecord`/`SuiteRecord`
   (e.g. `mean_duration_s`) and one line in `summarise`.
2. `uv run pytest && uv run ruff check && uv run basedpyright` still pass (the harness is not
   under pytest, but imports from `aidm` are checked).

Commit: `feat(evals): time each run`.

## Phase 1 — baseline (≈1–2 h wall clock, mostly waiting)

Needs `OPENROUTER` credentials in `.env` (see `core/config.py`; the director role defaults to
`openai/gpt-oss-120b`).

1. Run the full suite **twice** (drift is a known unknown — IDEAS.md records a 9.6-point swing):
   `uv run python scripts/evals/run.py` — twice. Results land in `scripts/evals/results/` and
   never overwrite.
2. Write `baseline.md` at the repo root, concise:

```markdown
# Baseline — tool-calling director
commit: <hash>   date: <date>   model: openai/gpt-oss-120b   retries: 3

| metric | run 1 | run 2 |
|---|---|---|
| overall | | |
| completion | | |
| interpretation | | |
| mean duration/turn (s) | | |
| by tag: checks / combat / conditions / rest / spells / story | … | … |

Worst cases (run 1 → run 2): <the ~5 lowest, with their one-line failure reasons>
Drift between runs: <max per-tag delta> — deltas below this are noise for the comparison.
```

Commit: `docs(evals): baseline before the structured-plan redesign`.

## Phase 2 — core types (≈half a day)

1. `core/effects.py`: the `Effect` union and `apply_effect`. Port each body from
   `tools.py`/`mechanics.py`; keep fact kinds, trace wording, and the reveal/leak rules
   identical (tests compare traces).
2. `core/plan.py`: `TurnPlanBase` (`plan.py` must not import `workflow`).
3. `core/engine.py`: add `plan_type`, `check_plan`, `resolve_action` **with migration defaults**
   (see Design) so both engines keep constructing; the old tool-era fields stay untouched until
   Phase 5.
4. Tests: new `tests/core/test_effects.py` — for every effect: one apply case asserting the fact
   and the state change, one refusal case asserting the raised reason. Mirror the structure of
   the existing `tests/core/test_tools.py` / `test_mechanics.py`.

Gate: all four commands pass. Commit.

## Phase 3 — Story engine (≈half a day)

1. `Risk`/`StoryAction`/`StoryPlan`, `check_plan` (taken-out guard, tag-held guard, legal
   outcome labels) and `resolve_action` (the 2d6 procedure, growth-on-setback intrinsic) — all
   in `engines/story/engine.py`; at ~55 lines today it has room, and one engine file is the
   lean shape. Split only if it nears the 1000-line cap (5e will need the split; Story won't).
2. Wire into `build_story_engine` via `load_engine`: give `load_engine` optional
   `plan_type`/`check_plan`/`resolve_action` parameters alongside `offered`/`check`, the
   resolver ones as factories taking `(Content, EngineSpec)` (see Design); optional with the
   migration defaults so dnd5e keeps building until Phase 4.
3. Rewrite `engines/story/director.md` per the Prompts section.
4. Update `tests/story/test_story_engine.py`: drive `check_plan`/`resolve_action` directly with a
   seeded `Random` — no model needed for the procedure itself.

Gate + commit.

## Phase 4 — 5e engine (≈1–2 days; the bulk of the work)

1. `engines/dnd5e/content5e.py`: `WeaponFacts.from_record` (structured numbers + tags) and
   `SpellFacts.from_record` (notes regexes). Unit-test both against the real pack records the
   evals touch (load `packs/srd-2014/` directly in `tests/dnd5e/`).
2. `engines/dnd5e/actions.py` + `resolve.py`: the six actions, `Dnd5ePlan.milestone_earned`.
   Keep `resolve_action` under 100 lines by giving each action its own function.
3. Rewrite `engines/dnd5e/director.md`.
4. Tests in `tests/dnd5e/`: per action — a success path, a failure path, a `check_plan` refusal.
   Seed `Random` for exact roll assertions.

Gate + commit.

## Phase 4.5 — one engine shape, and worked examples in the prompt (≈half a day)

Why: with both engines landed, they disagree on structure. Story is one 201-line `engine.py` doing
content, actions, resolution and advancement at once; 5e is `engine.py` + `actions.py` +
`content5e.py` + `resolve.py`, and nothing tells a reader which shape is the shape. An engine is
the one thing a future contributor writes from scratch, so its skeleton must be learnable once.
This phase moves code and adds examples. It changes no rule, no fact, and no trace wording.

### The layout, identical in both engines

| file | holds |
|---|---|
| `engine.py` | the `load_engine(...)` call and `PLUGIN`, and nothing else (~25 lines) |
| `actions.py` | the action models, the engine's plan type, its outcome labels, its example plans |
| `resolve.py` | `check_plan` and `resolve_action` |
| `advance.py` | `offered` and `check` — the `ProposalSpec` half, today buried in both `engine.py`s |
| `content.py` | pack-record normalisers. 5e only: Story ships no packs, so the file's absence is the information |
| `spec.json`, `director.md`, `advancement.md` | unchanged |

1. Rename `engines/dnd5e/content5e.py` to `content.py`; move `_offered`/`_check`/`_level_ref`/
   `_milestone_reached` out of `engines/dnd5e/engine.py` into `advance.py`, and Story's `_offered`/
   `_check` likewise. Split Story's `Risk`/`StoryPlan` into `actions.py` and its `_check_plan`/
   `_resolve_action` into `resolve.py`.
2. One rule keeps the package acyclic: **no sibling imports `engine.py`** — it is the assembly
   root. Sheet-key constants two modules share live with whichever module owns the vocabulary:
   `advance.py` owns `ADVANCEMENT_READY` and `LEVEL`, and `resolve.py` imports them from there.
3. Do not make `core` discover these modules by name. Loading `<pkg>.resolve:check_plan` by string
   is plugin magic that fights explicit collaborators and the acyclic-import rule; `Engine`
   already requires `plan_type`/`check_plan`/`resolve_action`, and that is the enforcement. What
   this phase adds is a convention a reader can see, not a type.
4. Do not move rules into `spec.json`. Templates, the recharge map and the collection list are
   genuine tables; `2d6` versus 7, or `8 + proficiency + modifier`, is procedure, and expressing
   procedure as data grows an interpreter bigger than the code it replaces.

### Worked examples

The field descriptions teach one field at a time; nothing yet shows the model a whole filled plan.
Each engine gains one example **per action**, in a new `examples.json` beside `director.md`: a JSON
array of plan objects, each written lean (only the fields it sets, discriminators included).

Prompt data, not code: sixty lines of nested constructors per engine buries the action models a
reader came to `actions.py` for. The guarantee an instance would have given is kept by validating
every entry against the engine's `plan_type` while `load_engine` reads it, so an example that
drifts from its action fails every test that builds the engine instead of misleading the model.

1. `core/enginepack.py`: `_examples(engine_dir, plan_type)` reads, validates, and renders the file
   under a short header, and `load_engine` appends the block to `director_instructions`. That keeps
   the assembly in the one place that already reads `director.md`, so Phase 5's `prompts.py`
   rewrite needs no part of this.
2. One example per action, each showing the branches that action allows (and none for the
   uncontested ones) — the labels are the thing models get wrong.
3. Test: for each engine, the rendered instructions name each `act` exactly once, and the action
   union is no longer than the acts the test lists. That is what keeps examples from rotting as
   actions grow.

Note for Phase 6: examples change how the model is steered, so the re-eval measures the redesign
*and* the examples together. The per-tag numbers still say where a miss lives, but a verdict cannot
attribute the delta to the architecture alone.

Gate + commit: `refactor(engines): one shape per engine, and examples in the prompt`.

## Phase 5 — pipeline rewire (≈1 day)

1. `pipeline.py`: insert `resolve_step` after `director_step` (resolve action → apply outcome
   branch → apply `plan.effects`); narrator/maintainer/creator steps unchanged. Director stage:
   `NativeOutput(engine.plan_type)`, output validator calling `engine.check_plan` (the
   `proposals.py` `legal` validator is the template), toolset = `read_content` only.
2. `turn.py`: `Turn.plan` replaces `notes`; bump `SAVE_VERSION` in `base.py`.
3. Rewrite `CORE_DIRECTOR`; delete the referee prompt and step; delete `mechanics.py` and the
   mutating tools in `tools.py`; move `read_content` per the design.
4. `scripts/evals/run.py` in the **same phase** (it imports `DirectorNotes`, `RefereeVerdict`,
   `director_step`, `referee_step`, and basedpyright checks `scripts/` — deferring this breaks
   the gate): the director stage yields a validated plan, then reuse the real `resolve_step` on
   the draft so the probes keep checking the same committed draft + facts. **Scenario JSON and
   probes must not change** — comparability is the point.
5. Update `tests/core/test_pipeline.py`, `test_tools.py` (largely superseded by
   `test_effects.py`), `test_context_boundary.py`, `tests/ui/`. Stub roles with `FunctionModel`
   returning a `TurnPlan` JSON, as the existing pipeline tests stub `DirectorNotes`.
6. Play one manual turn per engine: `uv run aidm`, load the whispering-vault scenario, attack
   something, cast a spell, take a risk. Read the trace panel: facts must show the full
   procedure.

Gate + commit.

## Phase 6 — re-eval and verdict (≈1–2 h wall clock)

1. Run the suite twice, same model, same flags as Phase 1 (the harness was rewired in Phase 5).
2. Optionally **add** one new scenario exercising `milestone_earned` (no existing scenario tags
   advancement — the free-form `advancement-ready` path was measured at 0–33% only in older,
   since-deleted cases). Adding a scenario is allowed; changing an existing one is not, and a
   new scenario counts toward no baseline comparison.
3. Append to `baseline.md`: the same table for the redesign, plus a delta row and a short
   verdict paragraph. Success criteria:
   - `interpretation` ≥ baseline + 15 points, and no tag regresses below baseline − drift.
   - `rest` and `spells` tags — the protocol-failure tags — each ≥ 0.8.
   - mean duration/turn ≤ half of baseline.
   If criteria fail, the numbers say where: a low tag maps to one resolver or one prompt
   section. Iterate there; do not revert the architecture on a first miss.

Commit: `docs(evals): structured-plan results vs baseline`.

## Phase 7 — cleanup (≈half a day)

1. Delete dead code the migration left: the Phase 2 migration defaults on `Engine` and
   `load_engine` (make `plan_type`/`check_plan`/`resolve_action` required), referee config
   keys, unused prompt renderers. `grep` for `DirectorNotes`, `RefereeVerdict`,
   `world_toolset`, `Mechanics(`.
2. Update `docs/ROADMAP.md` (the "four sequential role calls" weakness and the referee sections
   are now stale) and strike the resolved loose ends in `IDEAS.md`.
3. Full gate; final commit.

## Phase 8 — investigate the residual failures (≈half a day)

The Phase 6 verdict (in `baseline.md`) left four failure signatures, all stable across three
suites now that drift is 4 points instead of 28. None was diagnosed beyond its probe message —
that is this phase. Investigate first; change a prompt only once a captured plan shows *why* the
model wrote what it wrote.

What is failing, pooled over 207 turns:

| signature | cases | evidence so far |
|---|---|---|
| conditions 0/18 | `condition-lifted`, `condition-rider` | no `remove-tag`/`add-tag` ever appears in effects or branches; the rider's attack roll does happen |
| rest 72% | `long-rest-recharge` (44%) | `slot-1` left at 0 — the turn completes but no `rest` action resolves |
| wrong attacker | `monster-attack-on-player` (44%) | the plan attacks the rat instead of resolving the rat's attack on the player: rat hp −5, wanted 0 |
| healing edge | `healing-clamped-at-max` (89%) | one run in nine leaves hp delta 0 |

1. **Capture the plans.** The results JSON records probe failures but not what the Director
   answered, so every hypothesis below is currently unverifiable. Add the dumped plan (and the
   retry reasons it burned) to `RunRecord` — results are gitignored, so the schema is free to
   grow. Re-run the four cases with `--runs 9`; read the plans, not the rates.
2. **Classify each miss** against exactly three suspects, in this order: the schema steers wrong
   (the model cannot find where a condition goes — an `actions.py` field description problem);
   the prompt never teaches it (`director.md` names the effect ops but shows no condition being
   added or lifted — `examples.json` has no branch carrying `add-tag`); or `check_plan` refuses
   something legal and the retries wander (visible as burned retries in the captured plans).
   For `monster-attack-on-player` the suspect is different: the prompt's reading of *who acts
   this turn* — check whether `CORE_DIRECTOR` ever says an NPC can be the turn's actor.
3. **Fix in the owning file only** — a `director.md` section, an `examples.json` entry, a field
   description. Resolver changes need the captured plan to prove the resolver wrong first.
   Scenario JSON and probes stay untouched: comparability is still the point.
4. **Re-measure**: the touched cases at `--runs 9` for signal, then one full suite (drift now
   permits a single-suite read) appended to `baseline.md` with one line per fix landed.
5. **Duration, separately and last**: 8.9s pooled vs the 7.8s criterion, with per-run means of
   11.0/8.4/7.1 on identical code — the spread is provider-side. Check whether the director's
   `reasoning_effort`/`max_tokens` in config buy anything before concluding routing decides it;
   do not gate the phase on this.

Gate + commit: `docs(evals): residual failures diagnosed` (or the fixes' own message if they land
in the same pass).

## Risks the implementer should expect

- **One big schema also strains small models.** The mitigation is already in the design: field
  descriptions on every action, `check_plan` reasons that read like instructions, and retries.
  If a specific action keeps failing validation, its schema is too clever — split or flatten it.
- **Apply-time failures.** `check_plan` validates against pre-state; a branch effect can still
  refuse at apply time (e.g. `SpendCounter` after the action already drained the pool). That
  fails the whole turn loudly and commits nothing — correct, rare, acceptable. Do not add
  mid-resolution retries.
- **Spell coverage.** `SpellFacts` will not parse everything. That is the design: unparseable →
  `improvise`. Grow coverage from eval/trace failures, not speculatively.
