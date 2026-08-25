# Refactor plan

Phase 0 shipped as `920d5c9`. Start with **Phase 0b** below: one wrapper class deleted, no design
decision, about 20 minutes.

Baseline as of writing: suite green. `src/aidm` is 8,638 lines across 30 modules. Expected end
state: about 450 fewer lines, every `isinstance(JsonValue)` re-validation gone, and one way into a
turn in each harness.

The domain design is good; the complexity sits in five places, one per phase:

| | Where | Phase |
|---|---|---|
| 1 | `Fact.data: dict[str, JsonValue]` — typed values dumped into JSON, then dug back out | 1 |
| 2 | Two turn envelopes — `turn/run.py` and `app/mcp.py` build the same `Exchange` | 2 |
| 3 | Two authoring drivers holding the same draft | 3 |
| 4 | Two copies of sheet boilerplate, with a third and fourth engine promised | 4 |
| 5 | Three doors into one turn in code mode | 2b |

There is no dead code beyond what Phase 0 already removed.

---

## The four invariants every phase must preserve

Check these against your diff before every commit. If a phase would weaken one, stop and ask.

1. **The model proposes, Python decides.** Resolvers mutate a draft; only a revalidated commit
   replaces state.
2. **A turn commits whole or not at all** (builtin), **or per accepted tool call** (code mode) —
   and every intermediate commit is a legal state. Keep the per-call commit: the viewer follows it.
3. **The Narrator never receives unrevealed canon.** `VisibleScene` carries no unrevealed entity by
   construction; a fact reaches the Narrator only when `fact.narrator is not None` today
   (`fact.told` after Phase 1). Player-facing mechanic cards pass through that same gate.
4. **Each engine owns its mechanics.** Core persists `mechanics` and `PendingDecision.payload` as
   opaque payloads it never reads. Do not teach core about engine types.

---

## How to work (read once, then keep the commands nearby)

Run everything from the repository root **with `UV_CACHE_DIR` unset** — setting it breaks the suite.

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

**Golden fixtures.** `tests/core/fixtures/` pins the Director tool schemas, the role prompts, the
saved-state shape and one full turn. Any phase that changes a schema or a prompt will fail those
tests. That failure is the point: it shows you exactly what the model will now read.

```bash
AIDM_GOLDEN_REGEN=1 uv run pytest tests/core/test_golden_schemas.py tests/core/test_golden_prompts.py tests/core/test_golden_state.py tests/core/test_golden_turn.py
git diff tests/core/fixtures    # READ THIS before committing. Never regenerate blind.
```

If a fixture diff shows a change you did not intend, your refactor changed behaviour. Revert, do not
accept the fixture.

**Evals.** Only Phase 5 changes what a Director tool schema looks like. Before and after that phase:

```bash
uv run python evals/turn_eval.py run --label before-stake-flatten
# ... make the change ...
uv run python evals/turn_eval.py run --label after-stake-flatten
uv run python evals/turn_eval.py compare --baseline before-stake-flatten --candidate after-stake-flatten
```

**Module moves.** `tests/core/test_package_boundary.py` holds a `FORBIDDEN` table keyed by package
path. Every phase that adds or moves a file must update that table in the same commit, or the test
will silently stop checking the moved file.

**Commit rhythm.** One commit per numbered step where the suite is green. Do not batch a phase into
one commit; the golden diffs become unreadable.

---

## Phase 0 — Free deletions (shipped, `920d5c9`)

Nothing here needs a design decision. Each item is dead or unused.

**Files:** `src/aidm/engines/core.py`, `src/aidm/state/play.py`, `src/aidm/turn/run.py`,
`src/aidm/ui/game.py`, `src/aidm/config.py`, `src/aidm/state/entities.py`.

1. **Delete `TurnRecord.steps`.** `engines/core.py:48` declares it, `turn/run.py:392` splices it into
   the trace, and nothing ever appends to it. Delete the field and the `*log.steps` splice. The
   `StepTrace` model and `TurnTrace.steps` stay — `run.py` populates those directly.
2. **Delete `Advancement.id`.** `engines/core.py:437` sets `id: ClassVar[Slug] = "advancement"` and
   no subclass overrides it. It is read once, at `ui/game.py:434`, as a tab label. Replace with the
   literal `"advancement"` there and with `"advancement.md"` in `Advancement.__init__`.
3. **Move `Slug` to one place.** `config.py:9` re-declares the same regex as
   `state/entities.py:33`. `config.py` is the leaf every layer may read, so put `SLUG_PATTERN`,
   `SLUG_MAX` and `Slug` there and have `state/entities.py` import them.
4. **Leave `llm.py` alone.** See "Two settled decisions" below.
5. **Optional nit:** `Engine.director_toolsets` is a tuple that is length 0 or 1 everywhere. Leaving
   it a tuple is fine. Skip unless it annoys you.

**Verify:** full suite green, no fixture regeneration needed.
**Done when:** `grep -rn "log.steps\|Advancement.id" src` returns nothing.

---

## Phase 0b — Delete `CharacterOverlay` (about 20 min, no design decision)

`content/model.py:90` is a class with exactly one field:

```python
class CharacterOverlay(Frozen):
    character: dict[str, JsonValue]
```

so every engine file on disk opens with a `"character"` key wrapping the whole file, and every
reader in the app spells `character.overlay.character`. Nothing reads the wrapper itself — the two
`check_overlay` implementations are handed `overlay.character` and validate that.

1. **Replace the wrapper with the dict.** `Character.rules: dict[str, JsonValue]` and
   `CreatedCharacter.rules`, read straight out of `<engine>.json`. Delete the class.
2. **Unwrap the two files under `characters/kael/`.** `loner3e.json` and `twentyfourxx.json` lose
   one level of nesting; their contents do not change. This breaks any hand-written character
   elsewhere, which is the intent.
3. **Update the six readers:** `content/io.py:86,99`, `app/launch.py:59`, `ui/create.py:138`, and
   the `CreatedCharacter(...)` construction in both engines (`loner3e/engine.py:188`,
   `twentyfourxx/engine.py:301`). `io.py:99` writes `json.dumps(created.rules, indent=2)` now that
   there is no model to dump.

**Verify:** full suite.
**Done when:** `grep -rn "CharacterOverlay\|overlay.character" src tests` returns nothing.

**Expected delta:** about −15 lines, one indirection gone from five call sites.

---

## Phase 1 — Typed facts and resolver-built events (about 1.5 days, the big win)

This is the largest deletion in the plan and the one that most improves the code you will read for
the next year. Do it before the harness work; it shrinks the files Phase 2 edits.

### The problem, concretely

`state/actions.py:22` builds a dice fact with `kept`, `faces`, `rolled` in scope as ints. Then
`engines/core.py:155-210` proves they are ints again:

```python
kept = fact.data["kept"]
if not isinstance(kept, int):
    raise ValueError(f"a dice_rolled fact carries a non-int kept value: {kept!r}")
```

The same shape repeats in `counter_effect`, `_ints`, `_help_badge`, `question_events`,
`attempt_events`, `luck_test_events` — 12 `isinstance` branches across 22 `fact.data` reads. All of
it exists because a `MechanicEvent` is *re-derived from facts after the fact*, by a name-keyed
dispatch: both engines override `player_events` and switch on the `EventCause` they are handed
(`loner3e/engine.py:270`, `twentyfourxx/engine.py:424`).

This is the same mistake the maintainer already ruled on once for chips: **presentation is set where
the fact is built, never rebuilt from a name-keyed table afterwards.** Apply the same rule to events.

### The target shape

```python
# state/play.py
class MechanicEvent(Frozen):
    """Player-facing: no field for model-authored free text, so a canon leak has no channel."""

    title: str
    badges: tuple[EventBadge, ...] = ()
    dice: tuple[DiceEvent, ...] = ()
    outcome: str = ""
    effects: tuple[str, ...] = ()
    icon: str = "casino"
    # `source` is DELETED — see step 1 below.


# state/facts.py
class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    kind: str
    trace: str
    told: bool = False  # was `narrator: str | None`; it was always `trace` or None
    entity_id: EntityId | None = None
    event: MechanicEvent | None = None  # replaces `chip: Chip | None`
    # `data: dict[str, JsonValue]` is DELETED
```

The narrator gate stays in exactly one place:

```python
def player_events(facts: Sequence[Fact]) -> tuple[MechanicEvent, ...]:
    return tuple(f.event for f in facts if f.event is not None and f.told)
```

### Steps

1. **Delete `MechanicEvent.source`.** Grep proves the UI never renders it: `ui/game.py`'s
   `_mechanic_event` reads `icon`, `title`, `badges`, `dice`, `outcome`, `effects` and nothing else.
   Only three test assertions read it (`tests/core/test_pipeline.py:79,83,107`). Rewrite those to
   assert on `event.title`. **This changes the save format** (`Exchange.events` is persisted) —
   that is expected and correct here; old saves fail loudly, as the project intends.
2. **Replace `Fact.narrator: str | None` with `Fact.told: bool`.** It is set in exactly two places
   (`state/facts.py:47` and `engines/core.py:315`) and is `trace` or `None` at both. Update
   `narrator_lines` to `tuple(f.trace for f in facts if f.told)`. Suite green here.
3. **Add `Fact.entity_id: EntityId | None`.** `entity_fact` already puts it in `data`; promote it to
   a field. Rewrite the two readers, `_seed_created` and `_reached` in `engines/core.py:402-419`, to
   use the field.
4. **Fold `Chip` into `MechanicEvent`.** Rename `Fact.chip` to `Fact.event`, type it
   `MechanicEvent | None`, and delete the `Chip` class. Every existing `Chip(title=..., icon=...)`
   call site becomes `MechanicEvent(title=..., icon=...)` — same two arguments. Put the free
   function above in `state/facts.py`; delete `Engine.player_events`, `EventCause` and both engines'
   overrides; point the two callers at it — `engines/core.py:362` (`apply_tool_call`) and
   `turn/run.py:488` (`_resume`).
5. **Move the composite events to their resolvers.** In `engines/loner3e/rules.py`, delete
   `question_events` and `_twist_event`; build the Oracle and Twist `MechanicEvent`s at the end of
   `resolve_question`, where `chance`, `risk`, `outcome`, `position`, `edge`, the dice tuples and
   the counter changes are all still in scope, and attach them to the `question_answered` and
   `twist_due` facts. Do the same in `engines/twentyfourxx/rules.py` for `attempt_events`,
   `luck_test_events`, `_skill_badge`, `_help_badge`, `_hindered_badge`.
   - **Preserve the gate:** an effect line derived from another fact must still check that fact's
     `told`. `_strike`'s counter facts are the case that matters. `tests/core/test_context_boundary.py`
     and `tests/core/test_player_events.py` will catch you if you drop it.
6. **Delete `Fact.data` and everything that read it.** Now removable from `engines/core.py`:
   `dice_event`, `counter_effect`, `_ints`, `dice_by_slot`, `require_dice_slot`, `chipped`,
   `EventCause`. Also removable: the `slot: str` parameter of `roll_pool` in `state/actions.py` and
   every `slot=` argument. `DiceEvent` stays — build it from the `roll_pool` return value directly.
**Verify:** full suite — fix the `fact.data[...]` assertions it flags, and delete the now-meaningless
`assert fact.narrator is None or str(fact.data) not in fact.narrator` at
`tests/core/test_engine_contract.py:64`. Then regenerate `test_golden_turn` and `test_golden_state`
and read the diff: the fixture's facts change shape, the *narration* and the *state* must not.

**Done when:** `grep -rn "fact.data\|\.chip\|EventCause\|player_events" src` returns nothing.

**Expected delta:** about −170 lines in `src`, and all 12 `isinstance` branches gone.

### Two things not to do here

- Do not make `Fact` a discriminated union. After step 6 the only readers of a fact's insides are
  `entity_id` (a field) and a few `kind == "..."` checks inside one resolver.
- Do not type `PendingDecision.payload`. It is saved, and it is the engine's private data; core
  validating it breaks invariant 4. `Engine.check_pending` already validates it on load.

---

## Phase 2 — One turn envelope, and notes you take instead of slice (about half a day)

### The problem

`turn/run.py:419-429` and `app/mcp.py:291-311` are the same block:

```python
draft.world.pending_notes = draft.world.pending_notes[shown:]
draft.history = (
    *draft.history,
    Exchange(prompt=..., place=..., lines=..., events=..., decision=...),
)
draft.turn += 1
state = draft.committed()
```

And `pending_notes` is bookkept by a saved index in **three** places (`run.py:373,388`,
`mcp.py:231,266-268`, `mcp.py:291`), with the subtle rule "only what the prompt already rendered is
spent; a note a tool wrote after that steers the next turn too."

### Steps

1. **Replace the index with a take.** Add to `Game` in `state/model.py`:

   ```python
   def take_notes(self) -> tuple[str, ...]:
       """Notes are read once; a note a tool writes after this steers the next turn."""
       notes, self.world.pending_notes = self.world.pending_notes, ()
       return notes
   ```

   Then give `SceneSnapshot.from_game` a `notes: tuple[str, ...]` parameter, so it stops reading
   `world.pending_notes` itself at `turn/context.py:78`. Its two callers pass different things:
   `run.py:366` (the director's snapshot) passes `draft.take_notes()`; `run.py:394` (the narrator's,
   built from the same draft later in the turn) passes `()`. `mcp.py`'s `scene()` takes them the
   same way as `run.py:366`, and its `answer_decision` calls `take_notes` after `consume_answer` and
   prints what it got. Delete `Turn.notes_shown`, both `shown = len(...)` locals, and all three
   slices. Phase 2b then moves the take to `start_turn`.
2. **Extract the envelope.** Add to `turn/run.py`:

   ```python
   def close_segment(
       draft: Game, prompt: str, lines: tuple[Line, ...], events: tuple[MechanicEvent, ...]
   ) -> Game:
       """The one place a segment becomes history: builtin and code mode differ only in when."""
   ```

   It appends the `Exchange` — reading `place` off `draft.world.require(draft.player_location)` and
   `decision` off `draft.pending` itself, so neither caller passes them — bumps `draft.turn`, and
   returns `draft.committed()`. `run_segment` returns that state; `Harness.end_turn` still hands it
   to `session.commit(state, TurnTrace(...))` afterwards.
3. **Stop there.** Do not build one turn object over both harnesses: they differ in draft lifetime
   by design, and they already share the tool definitions (`mcp.py:566`) and `gated_toolsets`.

**Verify:** full suite; `tests/core/test_decisions.py` pins the notes rule.

**Expected delta:** about −60 lines, and one invariant that can no longer drift between harnesses.

---

## Phase 2b — One way into a turn in code mode (about 3 hours)

Do this after Phase 2: it uses `Game.take_notes`.

### The problem

Code mode has three doors into one turn. `scene()` renders the picture, but its PLAYER ACTION
section is the literal placeholder `ACTION_IS_IN_THE_CHAT` (`mcp.py:70`). `answer_decision`
re-implements the consume-and-note block that `consume_answer` already owns for builtin. And the
player's action finally arrives at `end_turn(prompt=...)` — after every tool call it should have
informed.

### Steps

1. **Add `start_turn`.**

   ```python
   class StartTurn(ToolArgs):
       prompt: str
       """What the player did, in their words."""
       option_id: OptionId | None = None
       """Exact id of the listed option their words chose, when a decision is open."""
   ```

   It drafts and calls `consume_answer` exactly as `run_segment:364` does, with the same three
   inputs that function already distinguishes: the bare `prompt` string when nothing is pending,
   `Answer(option_id=...)` when the player's words chose a listed option, and `Answer(text=prompt)`
   when a decision is open and they answered in their own words. Then it commits and records
   `answered`, `suspended_at_start` and the taken notes on `Turn` — the dataclass at `mcp.py:151`.
   It returns what `scene()` returns, built by the same `render_scene(...)` call at `mcp.py:225`
   with `prompt` passed where `ACTION_IS_IN_THE_CHAT` used to go, followed by what a closed answer
   resolved.
2. **Delete `answer_decision`, `AnswerDecision` and `ACTION_IS_IN_THE_CHAT`.** `_unavailable`'s
   pending branch names `start_turn` instead. `Answer`'s own "an option or text, never both"
   validator is the only copy left.
3. **`end_turn(lines)` only.** The prompt comes off `Turn`, so it cannot disagree with the one the
   scene rendered. `end_turn` and every director tool refuse with a `ModelRetry` naming `start_turn`
   when no turn is open — today a driver can roll dice without ever having called `scene()`.
4. **Keep `scene()`, and give the turn its notes.** `Turn` gains `notes: tuple[str, ...]`, taken by
   `start_turn` through `Game.take_notes`. `scene()` renders `turn.notes` first, then whatever
   `world.pending_notes` holds now. Without this, an agent compacted mid-turn calls `scene()` and
   sees no rules notes at all, because `take_notes` already emptied them — a regression Phase 2
   would otherwise introduce here.
5. **Update the two prose surfaces.** `PREAMBLE` in `mcp.py` and steps 4-6 of
   `.claude/skills/playing-aidm/SKILL.md` become: `start_turn(the player's message)` → director
   tools one at a time → `end_turn(lines)`.

**Verify:** full suite. In `tests/core/test_code_mode.py` four calls to `answer_decision` become
`start_turn`, and every `end_turn` call drops its prompt.

**Expected delta:** about −40 lines, one MCP concept gone, and the decision path shared with builtin
instead of reimplemented beside it.

---

## Phase 3 — One authoring driver (about half a day)

### The problem

`app/authoring.py` ends with two parallel lifecycles for one job:

| | builtin (UI) | code mode (MCP) |
|---|---|---|
| holder | `AuthoringSession` (l.577) | `AuthoringRun` + `ScenarioRun` + `GrowthRun` (l.628-676) |
| grow a world | `author_extension` (l.502) | `growth_run` + `finish_growth` |
| write to disk | `AuthoringSession.write` | `ScenarioRun.write` |
| check | `scenario_refusal` | `scenario_refusal` |

Both hold `draft` + `playing` + `brief`, both call `scenario_refusal`, both call `write_draft`.

### Steps

1. **Make `AuthoringRun` the single holder.** It already has `draft`, `playing`, `brief`, `toolset`
   and `refusal()`. Keep `ScenarioRun` (adds `settings`/`slug`/`premise`/`document`/`engines` and
   `write()`) and `GrowthRun` (adds `base` and `patch()`).
2. **Give `AuthoringRun` an optional agent.** Add `agent: Agent[ScenarioDraft, str] | None = None`
   and `history: list[ModelMessage]`, plus the `async def send(instruction)` currently on
   `AuthoringSession`. Builtin builds the run *with* an agent; code mode builds it without one and
   drives the same `toolset` itself.
3. **Delete `AuthoringSession`.** `ui/create.py:353` constructs it; point that at
   `scenario_run(...)` plus the agent, and at `run.write()`. Two of its fields have to survive the
   move onto `AuthoringRun`/`ScenarioRun`, or behaviour is lost silently: `busy: bool`, which the UI
   binds to, and the `art_style` override at `authoring.py:621` — the form's style wins over
   whatever the author wrote — which `ScenarioRun.write` does not do today.
4. **Delete `author_extension`.** `runtime.GameSession._extend` becomes: build a `GrowthRun` via
   `growth_run(...)`, `await run.send(briefing)`, then `self.apply_growth(run.patch())`. That is the
   same three lines code mode already runs, in the same order.
5. **Keep the draft trio.** `ScenarioDraft`, `ScenarioPatch` and `ExtensionPatch` look like three
   shapes of one world but are not: the draft is deliberately laxer than `WorldState` so a
   half-written world does not fail validation, and `ExtensionPatch` exists to materialize additions
   as *unknown* canon. Both earn their keep. Leave them.

**Verify:** full suite.

**Expected delta:** about −80 lines.

---

## Phase 4 — A sheet-shaped engine base (about half a day)

### The rule for this phase

> **Nothing moves to the base unless the two engines' versions are identical today, modulo one named
> ClassVar.** If it merely looks similar, it stays in the engine.

By that rule these move, and nothing else does:

| method | loner3e | twentyfourxx | differs by |
|---|---|---|---|
| `check_overlay` | `Sheet.model_validate(rules)` | same | `sheet_type` |
| `opening_mechanics` | `Mechanics(sheets=actor_sheets(...))` | same | `mechanics_type`, `sheet_type` |
| `validate` | `check_sheets(...)` **+ a pack check** | `check_sheets(...)` | loner calls `super()` then adds |
| `seed` | new `Sheet(milestones=...)` | new `Sheet(jobs=...)` | the ledger counter |
| `describe` | `describe_entity(Mechanics.of_game(state), e)` | same | `mechanics_type` |
| `Advancement.earned` | `...completed.current` | byte-identical | nothing |

### Steps

1. **Add `SheetEngine` in a new `src/aidm/engines/sheets.py`.**

   ```python
   class SheetEngine[S: SheetBase, M: SheetMechanics[S]](Engine):
       """An engine whose mechanics are one sheet per actor; the shelf's shape."""

       sheet_type: ClassVar[type[SheetBase]]
       mechanics_type: ClassVar[type[SheetMechanics[SheetBase]]]
   ```

   with `check_overlay`, `opening_mechanics`, `validate` and `seed` implemented once.
   `Loner3eEngine.validate` keeps its pack check by calling `super().validate(state)` first.
   `seed` has an ordering constraint worth spelling out: create the actor's default sheet **first**,
   because `Advancement.ledger` reads it out of `mechanics.sheets`; then bring the newcomer level
   with the game by setting `self.advancement.ledger(draft, entity.id).current` to
   `SheetMechanics.of_game(draft).completed.current`, so jobs closed before they joined are not
   owed. `Engine.advancement` is `Advancement | None` (`engines/core.py:97`), so guard it — skip the
   ledger when it is None.
2. **Move `earned` to `Advancement`.** `return SheetMechanics.of_game(state).completed.current` —
   `completed` is core's own field on `SheetMechanics`, so the base can read it. Delete both
   overrides and the `@abstractmethod`.
3. **Move the sheet helpers with it.** `SheetBase`, `SheetMechanics`, `actor_sheets`,
   `check_sheets`, `require_sheet`, `pool`, `adjust`, `spend`, `counter_fact`, `render_counters` all
   move from `engines/core.py` to `engines/sheets.py`. This is the "new file buys a boundary" test
   passing: the boundary bought is *the family of sheet-shaped engines*, and it is where a third
   engine will start.
**Verify:** full suite. `tests/core/test_engine_contract.py:102` builds a bare `Engine` subclass, so
`Engine` must stay usable without `SheetEngine`.

**Expected delta:** about −60 lines now, and roughly 35 lines saved per future engine.

---

## Phase 5 — Config roles and a flat `stake_attempt` (about 2 hours)

Two independent, small, high-clarity wins. Do them in either order.

1. **Replace `ROLE_DEFAULTS` + the merge in `Settings.role`.** `config.py:71-75` holds the defaults
   dict and `config.py:120-136` hand-merges it with a partial `RoleConfig` pulled from
   `Settings.roles` (`config.py:105`). Declare the four roles as named fields instead, in the same
   file, replacing that `roles: dict[Role, RoleConfig]` field:

   ```python
   class Roles(BaseModel):
       director: RoleConfig = RoleConfig(max_tokens=8192, reasoning_effort="low")
       narrator: RoleConfig = RoleConfig()
       advisor: RoleConfig = RoleConfig()
       scenario_creator: RoleConfig = RoleConfig(max_tokens=32768, reasoning_effort="medium")
   ```

   `nested_model_default_partial_update=True` is already set on `Settings`, so
   `ROLES__DIRECTOR__MODEL=x` keeps the director's other defaults with no code. Env var names are
   unchanged. `Settings.role(name)` collapses to `getattr(self.roles, name)` plus the existing
   api-key check. Deletes `ROLE_DEFAULTS`, the `model_fields_set` merge, and the `dict[Role, ...]`.
   `tests/core/test_config.py` pins the merge behaviour — update it to pin the new one. `Role` stays:
   `Settings.role(name)` still takes it, and `run.py:493` still passes one.

2. **Flatten `stake_attempt`.** It is the only Director tool that takes two arguments, which forces
   Pydantic AI to nest a whole `Attempt` under `$defs` — 12.3 KB of 24XX tool schema, versus 8.0 KB
   for loner3e. Replace with one model:

   ```python
   class StakedAttempt(Attempt):
       risk: str = Field(min_length=1, description="One-line cost of a bad roll, shown to the player.")
   ```

   Then `stake_attempt(ctx, attempt: StakedAttempt)` is flat — Pydantic AI inlines a single model
   argument, which is why every other tool already has no `$defs` — and `_with_skills` in
   `engines/twentyfourxx/engine.py:89-95` loses its `inside="Attempt"` branch. That leaves
   `with_enum`'s `inside` parameter and its `$defs` branch (`engines/core.py:386-388`) with no
   caller: delete both. `_enumerated` itself stays; `run.py:173` still uses the flat path.

3. **Give `goal` back its one job.** `Attempt.goal` is described to the model as "The actor's goal
   and the risk they face, in one line", while `stake_attempt` takes `risk` as its own argument. So
   a staked attempt asks for the risk twice, in two places, and the two can disagree. Cut the
   description to the goal alone; `StakedAttempt.risk` from step 2 is where a risk is named. The
   cost is that an unstaked `roll_attempt` no longer records what was at stake in its trace — which
   is consistent with what `roll_attempt` is for: an NPC's roll, or a player whose own words already
   accepted the risk. It is a prompt change, so it rides the same fixture regeneration and the same
   eval run as step 2.

**Verify:** this is the one phase that changes what the model reads. Regenerate
`tests/core/fixtures/schemas/twentyfourxx/director_tools.json`, read the diff, and run the eval
before/after as shown in "How to work". A schema shrink should not regress accuracy; if it does, the
nesting was doing something and you revert step 2.

---

## Phase 6 — Split the three files that do two jobs (about half a day, pure moves)

Do this **last**. Moving code before the earlier phases would produce a large diff that hides real
changes. Only three files qualify; the repository's own rule is that a new file must buy a boundary.

1. **`app/mcp.py` (723 lines) → `app/codemode.py` + `app/mcp.py`.** `Harness` is the code-mode game
   controller; `ToolArgs`/`ServerTool`/`SERVER_TOOLS`/`build_server`/`serve` are the MCP transport.
   `tests/core/test_code_mode.py` already "drives the MCP handlers as plain functions" — it is
   asking for this boundary. Keep the `ServerTool` table: MCP is a string-keyed protocol, so a
   name→handler map is the protocol's shape, not a smell.
2. **`app/authoring.py` (715, ~570 after Phase 3) → `app/authoring.py` + `app/authoring_run.py`.**
   Draft, patch, briefs and refusals in the first; toolset, agent and the run classes in the second.
3. **`engines/core.py` (527, ~350 after Phases 1 and 4) → keep, plus `engines/packs.py`.** After the
   earlier phases, `core.py` holds the `Engine`/`Advancement`/`CharacterCreation` contracts, the
   `DirectorContext`/`TurnRecord` types, and `apply_to_draft`/`transact`/`apply_tool_call`/
   `sequential_toolset`/`with_enum`. That is one job: *the engine contract and how a tool call
   reaches it*. Only `pack_step`/`pack_paths`/`load_packs` (~35 lines) are a different job — move
   those to `engines/packs.py`.

**Do not** relayout the package tree. Module count is a settled decision; a new file must buy a
boundary, and only these three do.

**Verify:** update `FORBIDDEN` in `tests/core/test_package_boundary.py` in the same commit as each
move, then run the full suite. No fixture regeneration should be needed — if a golden fixture moves,
you changed behaviour during a "pure move".

---

## Two settled decisions (do not re-open)

1. **`llm.py`'s `RepairedToolArgs` stays.** It repairs malformed gpt-oss tool arguments. The
   maintainer still runs gpt-oss-120b in rotation alongside deepseek-v4-flash and code mode, so this
   is live insurance, not dead code. Settled 2026-08-25.
2. **The Director's tool gating stays.** Deleting `DirectorTool.applies`, the two `.prepared(...)`
   narrowings and `with_enum` (~130 lines) and letting `ModelRetry` refuse illegal calls has been
   proposed. That plumbing exists so a weak model performs, which is this project's decision rule,
   so it stays unless an eval on gpt-oss-120b shows accuracy holds and `director_calls` does not
   rise. The pending-decision filter in `gated_toolsets` stays either way — nothing in
   `actions.move` or `apply_to_draft` refuses a core call while the rules wait on the player, so it
   is an integrity boundary, not an efficiency one. Settled 2026-08-25.

---

## Order and budget

| Phase | What | Est. | Risk |
|---|---|---|---|
| 0 | Free deletions | 45 min | none — **shipped `920d5c9`** |
| 0b | Delete `CharacterOverlay` | 20 min | none |
| 1 | Typed facts, resolver-built events | 1.5 days | medium — touches both engines and the goldens |
| 2 | One turn envelope, `take_notes` | 0.5 day | medium — the notes rule is subtle |
| 2b | `start_turn` in code mode | 3 hours | low — but it changes the MCP protocol and the skill |
| 3 | One authoring driver | 0.5 day | low |
| 4 | `SheetEngine` base | 0.5 day | low |
| 5 | Config roles, flat `stake_attempt`, `goal` | 2 hours | low, but needs an eval run |
| 6 | Three file splits | 0.5 day | none — pure moves |

Total: about 4.5 focused days. Suite green at the end of every numbered step.
