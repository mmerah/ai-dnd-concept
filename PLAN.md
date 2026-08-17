# Plan

The phased plan for what is built next, in order. Phase 1 (the small Director contract) and the
2026-08-17 drastic simplification (Cairn 2e deleted, the wire contract cut to `roll` + `effects`)
shipped and live in PROGRESS.md. Phase 2 makes the engines rules-true by deleting the shared
abstractions that manufacture deviations, Phase 3 checks narration against facts, Phase 4 is the
scenario creator, Phase 5 media. Each phase carries enough detail to implement without prior
context; only the next unshipped phase needs full resolution. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted. `tests/core/test_golden_state.py` pins `FIXTURE_SAVE_VERSION` —
   bump both or the suite catches you.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 1 — One small Director contract

Shipped in full; see PROGRESS.md.

## Phase 2 — Engine-true mechanics (~4–5 days)

Several documented deviations are not fidelity compromises — they are *manufactured* by shared
abstractions: the global `counter-change` effect creates LONER-3E deviation 9, the fixed-menu
creation step creates LONER-3E deviation 8 and 24XX deviations 4 and 6, and the
one-advance-per-resolved-thread policy hardcoded in `ThreadAdvancement` creates LONER-3E
deviations 1–2 and 24XX deviation 1. This phase deletes the abstractions and the deviations
together, guided by one principle that every step below applies:

> **Python owns what the SRD makes algorithmic** — dice, resource ledgers, legality, outcome
> tables. **The model owns what the SRD explicitly leaves to player/GM judgment** — whether the
> fiction grants an edge, when a job is over, what a free-text trait says. Never convert a
> judgment into string-matching machinery just so Python can pretend to own it: the model already
> made the call when it chose what to write, and the matching only adds retries.

Each step ends with all four suites green and one commit. A step whose regenerated `save`, `state`
or `turn` fixtures move bumps `SAVE_VERSION` (and `FIXTURE_SAVE_VERSION`) once in that same
commit. After each step, update the engine doc(s) it names: delete the closed deviation entries,
renumber the rest, and fix the "Engine package" bullets so the docs describe the code as it now
is. Nothing may diverge silently.

### Step 1 — Engines own their effect vocabulary; `counter-change` dies (~1 day)

Today `vocabulary.py:19` hands **every** engine
`EngineEffect = WorldEffect | CounterChange` — a generic "move any named counter by any amount"
op. That is exactly the door LONER-3E deviation 9 walks through (the Director charging Luck for
arbitrary hazards, which the SRD never allows). Engines already declare their rolls in `actions`;
give them the symmetric declaration for effects, and replace `counter-change` with one small,
rules-true effect per engine.

1. **`src/aidm/state/effects.py`** — add a type guard so the base engine can route world ops
   without knowing any engine's own ops:

   ```python
   from typing import TypeIs

   def is_world_op(effect: Frozen) -> TypeIs[WorldOp]:
       return isinstance(
           effect, (Reveal, Move, GainImprovisedItem, TraitChange, RelationChange, AdvanceThread)
       )
   ```

   (Import `Frozen` from `.base`; keep the tuple in sync with `WorldOp` — it sits directly under
   the alias so a new op is added to both or neither.)

2. **`src/aidm/engines/vocabulary.py`** — delete the global union: remove
   `from .counters import CounterChange`, the `EngineEffect` alias, the module-level `EFFECTS`
   adapter, and the derived `EFFECT_CALLS`. In their place:

   ```python
   # Derived from the union, so an op the adapter takes cannot be missing from the card.
   WORLD_CALLS: Mapping[Slug, type[Frozen]] = {
       str(model.model_fields["op"].default): model for model in _members(WorldEffect)
   }

   def effect_adapter(own: Mapping[Slug, type[Frozen]]) -> TypeAdapter[Frozen]:
       members = (WorldEffect, *own.values())
       # A dynamic Union: the engine's declaration is the single source, so card and adapter
       # cannot drift. Nesting the already-discriminated WorldEffect keeps retry errors naming
       # the exact field (see PROGRESS.md, Phase 1 step 1).
       union = Union[members]  # pyright: ignore[reportInvalidTypeArguments]
       return TypeAdapter(Annotated[union, Field(discriminator="op")])
   ```

   `translate_effect(call, adapter)` and `translate(beat, actions, adapter)` now take the adapter
   as a parameter; `TypedBeat.effects` becomes `tuple[Frozen, ...]`. Keep the "spread `op` last"
   line and its comment exactly as they are.

3. **`src/aidm/engines/counters.py`** — delete `CounterChange` and `move_pool` (and the now-unused
   imports). `adjust`, `spend`, `counter_fact`, `pool`, `render_counters` stay: the new engine
   effects are built on them.

4. **`src/aidm/engines/sheets.py`** — delete the abstract `counters()` from `SheetBase`; it was
   only required so core could service `counter-change`. `SheetBase` stays as the (now empty,
   docstring-only) bound of `Engine[S: SheetBase]` and `SheetMechanics[S]`. Both engines keep
   their own concrete `counters()` — `describe_entity` uses it.

5. **`src/aidm/engines/loader.py`** — `Engine` gains a second declaration beside `actions`:

   ```python
   # What an `effects` entry may name beyond the world ops: this engine's own effects, by name.
   effects: ClassVar[Mapping[Slug, type[Frozen]]] = {}
   ```

   In `__init__`, build `self._effects = effect_adapter(self.effects)` and render the effects
   card from `{**WORLD_CALLS, **self.effects}`. `parse_effect` and `apply_effect` validate
   through `self._effects`; `_worked_plans` and `check_beat` pass it to `translate`. Replace the
   `CounterChange` special case in `apply` with:

   ```python
   def apply(self, draft: GameState, effect: Frozen) -> list[Fact]:
       """An engine with its own effects overrides this, falling through to super() for world
       ops."""
       if not is_world_op(effect):
           raise TypeError(f"{type(effect).__name__} is no effect this engine applies")
       return apply_effect(draft, effect)
   ```

6. **`src/aidm/engines/loner3e/`** — one new effect in `actions.py`:

   ```python
   class RestoreLuck(Frozen):
       """Put an actor's luck back to full, once a conflict is behind them and they have had a
       breather. The engine already refills both sides when a conflict ends at 0."""

       op: Literal["restore-luck"] = "restore-luck"
       actor_id: EntityId = Field(description="Exact id of the actor: the player, or an actor here.")
   ```

   Its apply function: `require_actor_here`, `Reveal` the actor, fetch the sheet with
   `require_sheet`, then `adjust(actor, "luck", sheet.luck, (sheet.luck.maximum or LUCK_MAX) -
   sheet.luck.current, "the conflict is behind them")` — already-full is a quiet no-op because
   `adjust` returns no fact for a zero delta. In `rules.py`: `effects = {"restore-luck":
   RestoreLuck}` and

   ```python
   def apply(self, draft: GameState, effect: Frozen) -> list[Fact]:
       match effect:
           case RestoreLuck():
               return apply_restore_luck(draft, effect)
           case _:
               return super().apply(draft, effect)
   ```

   **There is deliberately no luck-charging effect.** The SRD moves Luck only through Harm & Luck:
   a hazard the Director wants to bite is a `question` (usually with `opponent_id` when something
   hunts the actor), never a ledger poke. Delete LONER-3E deviation 9.

7. **`src/aidm/engines/twentyfourxx/`** — one new effect in `actions.py`:

   ```python
   class ChangeCredits(Frozen):
       """Move an actor's credits for gear bought, repairs paid, debts collected or pay earned —
       never for a roll's own outcome, which the engine settles itself."""

       op: Literal["change-credits"] = "change-credits"
       actor_id: EntityId = Field(description="Exact id of the actor: the player, or an actor here.")
       amount: int = Field(description="Positive to pay them, negative to charge them. A charge "
                           "the pool cannot cover is refused.")
   ```

   Add a `model_validator` refusing `amount == 0`. Its apply function: `require_actor_here`,
   `Reveal`, `require_sheet`; `amount > 0` goes through `adjust(actor, "credits", sheet.credits,
   amount, "paid")`, `amount < 0` through `spend(actor, "credits", sheet.credits, -amount)` so an
   overdraw is refused, not clamped. Register `effects = {"change-credits": ChangeCredits}` and
   override `apply` the same way.

8. **Prompts and docs.** In both engines' `director.md`, rewrite THIS ENGINE'S OWN EFFECT: Loner
   teaches `restore-luck` (and that hazards are questions, not ledger moves), 24XX teaches
   `change-credits`; update the worked JSON examples in those sections. Search `tests/` for
   `counter-change` and update the plans/tests it appears in to the new calls.
   `tests/core/test_counters.py` loses its `CounterChange`/`move_pool` cases and gains one apply
   test per new effect (refused overdraw, quiet no-op refill).

9. **Fixtures.** Regenerate `instructions` (the effects card changed) and whichever of
   `save`/`state`/`turn`/`prompts` the tests move; read the diff — only counter-change material
   may move. Bump `SAVE_VERSION` if `save`/`state`/`turn` bytes moved.

### Step 2 — Judgment in, string-matching out (~½ day)

Loner's `Question` makes the Director copy up to three exact `leverage` and `trouble` tag strings
so Python can count survivors into advantage/disadvantage (`loner3e/actions.py:120-124`). The SRD
says the opposite: tags are *not* numbers, and whether the fiction grants an edge is an intuitive
call. The model already controls the outcome by choosing which tags to list — the exact-match
refusal machinery adds retries without adding determinism. Same for 24XX's `helped`/`hindered`
exact-tag matching (`skill` stays exact: the die genuinely comes off the sheet).

1. **`loner3e/actions.py`** — on `Question`, delete `leverage` and `trouble`; add:

   ```python
   position: Literal["advantage", "neutral", "disadvantage"] = Field(
       default="neutral",
       description="Your judgment of the fiction: `advantage` when a skill, gear, trait or the "
       "situation gives the actor a real edge here; `disadvantage` when a frailty, an opposing "
       "tag or the situation works against them; `neutral` when neither clearly outweighs.",
   )
   edge: str = Field(
       default="",
       description="The tag or circumstance that decided the position, in a few words. Empty "
       "for neutral.",
   )
   ```

   In `resolve_question`: delete the `available_tags` call, the tag half of
   `_refuse_unless_ready` (keep the opponent checks), and the net-count block; the position is
   `action.position`, passed straight to `_pair`. Add `"edge": action.edge` to the
   `question_answered` fact data. Delete `available_tags` and `Sheet.tags()`
   (`loner3e/mechanics.py`).

2. **`twentyfourxx/actions.py`** — reword `helped` and `hindered` to judgment fields ("the
   circumstance that makes this easier/harder, in a few words; empty when nothing does") and
   delete `_known_tags` plus the tag loop in `_refuse_unless_ready` (keep `_require_skill` for
   actor and helper — those are mechanical). `pool_faces` is unchanged: it only tests truthiness.

3. **Delete `src/aidm/engines/tags.py`** — `carriers` and `tag_key` have no callers left.

4. **Prompts, examples, docs.** `loner3e/director.md`: replace the "Leverage and trouble cancel
   out" paragraph with position guidance — the sheet's tags and the scene's traits are what the
   judgment reads, one net edge at most, more tags never buy more than one die. Update both
   engines' `examples.json` (`leverage`/`trouble` → `position` + `edge`; 24XX's `helped` stays
   but is now free prose). Update both docs' "Plan (actions.py)" bullets. No deviation entry
   changes: the SRD makes this call intuitive, so the judgment fields are the *faithful* reading.

5. **Fixtures**: `instructions` (both cards moved), plus whatever turn/save plans the updated
   tests move. Bump if persisted bytes moved.

### Step 3 — Creation asks in three shapes (~1 day)

`CreationStep` forces every creation question into "pick N distinct options from a fixed menu".
That single shape *is* LONER-3E deviation 8 (Concept is a closed menu where the SRD asks for a
free phrase) and 24XX deviations 4 and 6 (an Alien picks its "invented" traits from a menu; a
Human cannot stack two increases onto one skill because picks must be unique).

1. **`src/aidm/state/creation.py`** — `CreationStep` gains `repeats: bool = False`; when true,
   `_check_chosen` skips the uniqueness check (count and legality still hold). Add:

   ```python
   class TextStep(Frozen):
       id: Slug
       prompt: str
       hint: str = ""        # placeholder examples, shown greyed in the input
       count: int = 1        # how many answers this step takes
       max_length: int = 100

   type AnyStep = CreationStep | TextStep
   ```

   Widen `Picks` to `Mapping[Slug, tuple[str, ...]]` (free text no longer fits `ContentSlug`).
   `check_picks` takes `Sequence[AnyStep]` and dispatches: choice steps as today; a text step
   requires exactly `count` answers, each non-empty once stripped and at most `max_length` long.

2. **`src/aidm/ui/create.py`** — `_step_widget` dispatches on step type. A `TextStep` renders
   `count` `ui.input`s (label = the prompt, numbered when `count > 1`; `placeholder=hint`),
   writing the stripped values into `picks[step.id]`. A `CreationStep` with `repeats=True`
   renders `choose` single `ui.select`s (one per pick) instead of one multi-select — Quasar's
   multi-select cannot hold the same value twice. The pack-switch pruning loop keeps a
   `TextStep`'s answers whenever the step id survives (there are no options to prune against).
   Extend `_shape` (include step kind, `hint`, `count`, `repeats`) and `_answer` (a text step's
   answer is its texts joined with ", ").

3. **`loner3e/create.py`** — the concept step becomes
   `TextStep(id="concept", prompt="Their concept, in one line", hint=<the first three pack
   concept labels joined with ", ">)`; `create()` takes the text as written. `pack.concepts`
   stays: it is the hint source, and the SRD offers its table as inspiration. Delete LONER-3E
   deviation 8.

4. **`twentyfourxx/create.py` and `pack.py`** — the Alien traits step becomes
   `TextStep(id="traits", count=origin.invents, hint=<the origin's example trait labels joined
   with ", ">)`; `create()` builds each invented trait as
   `Trait(id=text_slug(text, taken), name=text)` where `taken` is the trait ids already built.
   Delete `Origin._invented_traits_fit_the_menu` (the menu is now examples, not a bound). The
   origin `skills` increases step gains `repeats=True` — the existing `raised(skills.get(label))`
   loop already stacks d8 → d10 on a repeated pick, exactly the SRD's Human origin. Delete 24XX
   deviations 4 and 6.

5. **Tests**: `tests/loner3e/test_create.py` and the 24XX creation tests cover the three new
   behaviors — free concept text lands on the sheet, an invented trait need not be on the menu,
   a repeated Human increase stacks (and three-on-one-skill reaches d12), and `check_picks`
   refuses an empty or overlong text.

### Step 4 — One model owner per thread (~1–2 h)

Thread progression has two model owners: the Director's `advance-thread` effect (validated
against a trial draft before narration) and the Worldkeeper's `thread_moves` (applied after
narration with only a shallow retry, `turn/roles.py:117`). Keep the better-guarded owner, the one
that just watched the dice.

1. `src/aidm/state/turn.py`: delete `thread_moves` from `WorldkeeperReport` (and the now-unused
   `AdvanceThread` import). `src/aidm/turn/roles.py`: delete `_thread_moves` and its call.
   `src/aidm/turn/pipeline.py`: delete the `report.thread_moves` loop in `apply_report` (and the
   `apply_effect` import if now unused).
2. `src/aidm/turn/prompts/worldkeeper.md`: delete the THREAD MOVES section.
3. Regenerate `schemas/worldkeeper_report.json`, `prompts`, and the `turn`/`save` families; bump.
   Update `tests/core/test_worldkeeper.py`.

### Step 5 — 24XX gear is carried items, not sheet traits (~½ day)

24XX deviation 5: the comm and specialty kits land as traits, so they cannot be carried, handed
over, or broken as things. The substrate already exists — `CharacterProfile.items`
(`content/authored.py:93`) ships item entities with a created character, and `characters/kael`
proves the whole path (an item with `parent_id: "player"`, its quality as a trait *on the item*).

1. **`twentyfourxx/pack.py`** — kits get their own entry model:

   ```python
   class KitItem(Frozen):
       id: ContentSlug
       label: str
       detail: str = ""
       bulky: bool = False
   ```

   `Pack.starting_kit` and `Specialty.kit` become `tuple[KitItem, ...]`. In `packs/srd.json`,
   mark `"bulky": true` on the entries the SRD calls bulky.

2. **`twentyfourxx/create.py`** — kits leave `traits` and become
   `CharacterProfile(items=...)`: each entry is
   `Entity(id=EntityId(entry.id), kind="item", name=entry.label, brief=entry.detail or
   entry.label, known=True, parent_id=PLAYER_ID)`, with `traits=[Trait(id="bulky", name="Bulky",
   text="Heavy or awkward to lug; more than one may hinder at times.")]` when `entry.bulky`. The
   character's own `traits` are now only the invented origin traits. An id collision with a
   scenario entity fails `begin_game` loudly — that is the correct failure, not something to
   pre-empt here.
3. The creation preview already renders `carrying` rows (`ui/create.py:127`). Update the 24XX
   creation tests, delete 24XX deviation 5, and fix the doc's Creation bullet. `director.md`'s
   HARM AND DEFENCE and LOAD sections now describe reality (a break is a `trait-change` on the
   item; bulky is a trait on the item) — reword the two sentences that said kits are sheet
   traits.

### Step 6 — Advancement waits for the fiction's own boundary (~1 day)

`ThreadAdvancement.offers()` hardcodes "one advance per resolved thread per party member"
(`engines/advancement.py:41-51`) — the policy that *is* LONER-3E deviations 1–2 and 24XX
deviation 1. The SRD's trigger ("after a job" / "when the adventure ends") is a GM judgment; give
the Director a way to record it once, and let the engine count recorded boundaries instead of
resolved threads.

1. **Both `mechanics.py`** — `Mechanics` gains `completed: Counter = Counter(current=0)`: how
   many jobs (24XX) or adventures (Loner) the fiction has closed, game-wide.
2. **New engine effects** (the step-1 mechanism): 24XX `complete-job`, Loner `end-adventure` —
   both argument-free:

   ```python
   class CompleteJob(Frozen):
       """Record that the job is done — the fiction's own boundary, written once when the crew's
       engagement genuinely closes, usually alongside resolving its thread. Never for a mere
       scene ending."""

       op: Literal["complete-job"] = "complete-job"
   ```

   Apply: increment `mechanics.completed.current` and return one `Fact(source=CORE,
   kind="job_completed", trace="the job is done")` (Loner: `adventure_completed` / "the adventure
   has ended"). Register in each engine's `effects` mapping and `apply` override; teach both in
   `director.md` (one short paragraph next to `advance-thread`).
3. **`src/aidm/engines/advancement.py`** — rename `ThreadAdvancement` to `Advancement` (grep for
   every reference: `loader.py`, `roles.py`, both `advance.py`, tests). In `offers()`, replace
   `resolved_threads(state.world)` with `self.earned(state)`, a new abstract method; each engine
   returns `state.mechanics_as(Mechanics).completed.current`. Delete `resolved_threads` from
   `sheets.py`; both `rules.py` `new_sheet` newcomer ledgers start at
   `draft.mechanics_as(Mechanics).completed.current` instead.
4. **Loner's proposal becomes the SRD's full post-adventure update.** Rename `Milestone` to
   `Change` and drop its `why`; the proposal is now:

   ```python
   class AdventureGrowth(ProposalBase):
       """Everything this adventure changed on the sheet, at once, as the post-adventure update."""

       changes: tuple[Change, ...] = Field(
           min_length=1, max_length=4,
           description="Each change: a new skill, new gear, a new frailty, or one rewrite.",
       )
       why: str = Field(description="One short sentence the player reads before confirming.")
   ```

   `grant` loops the changes. Update `loner3e/advancement.md` and the `GROWTH` offer text
   (occasion: "finishes an adventure"). 24XX's single-skill `Advance` already matches its SRD
   ("increase one skill") — only its trigger changes.
5. Delete LONER-3E deviations 1 and 2 and 24XX deviation 1; renumber both lists and update both
   docs' Advancement bullets. Regenerate `instructions`/`prompts` and the `save`/`state`/`turn`
   families (the `Mechanics` shape moved); bump `SAVE_VERSION`. Tests: an offer appears only
   after the effect fires, a second effect earns a second offer, a Loner proposal with three
   changes lands all three, and the advisor schema fixtures regenerate.

Done when: both deviation lists are down to genuinely architectural entries (Loner: world-mapped
Goal/Motive/Nemesis, actor-only sheets, twist timing/counter scope/secrecy; 24XX: the compressed
advise-and-revise loop, fiction-side harm), `grep -r "counter-change\|leverage\|thread_moves"
src tests` finds nothing, and a full turn plays under both engines with the new calls.

## Phase 3 — Narration checked against facts (~1 day)

A mechanically perfect engine can still commit a narration that contradicts its own facts, and
nothing today would notice (ROADMAP.md). That silent desync is a worse accuracy failure for the
player than any remaining rules deviation.

1. A `checker` role in config (a small, cheap model is fine; add `ROLES__CHECKER__MODEL` support
   like every other role). Output model, somewhere role-adjacent like `turn/roles.py`:
   `class Verdict(Frozen): contradicted: bool; contradiction: str = ""` — the one sentence naming
   what the narration got wrong, empty otherwise. Instructions in `turn/prompts/checker.md`: you
   are shown WHAT HAPPENED (the evidence) and the narration; report a contradiction only when the
   narration *states a mechanical outcome* the evidence does not record, or the reverse of one it
   does — style, elaboration and staging are not contradictions.
2. In `run_turn` after the narrator: run the checker on evidence + narration. If `contradicted`,
   re-run the narrator once with one appended line ("Your last draft contradicted the record:
   {contradiction}. Rewrite it to match."), keep the second draft either way, and log (never
   fail the turn) if the recheck still objects. Trace both as `StepTrace` steps.
3. Working rule 2 applies: the `Verdict` schema is small, but one live `NativeOutput` probe comes
   before fixture work. Tests stub with `FunctionModel`: one contradiction path (narrator re-runs
   once), one clean path (no second call). Regenerate `prompts`/`turn`/`save`; bump.

Done when: a stubbed contradicting narration provably triggers exactly one retry, a clean one
none, and a live turn runs end to end with the checker on.

## Phase 4 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at
authoring time. This is a script, not the app: agentic workflows are fine outside the turn
loop, where speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the shared format already exists and
   is the validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`). Give it one read-only tool returning whispering-vault's
   `world.json` as the worked example, and put the authoring bar in the instructions: 4+
   locations connected by relations with at least one hidden and one `locked` way, 2+ NPCs with
   at least one unrevealed, one secret item, at least one thread with hooks that advance it on
   `entity_discovered` facts, hook `note`s that steer the Director, and `detail.hook` on every
   entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then validate the world alone — a `Scenario` per
   shipped engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the
   engine's normal mechanics validation. Any `ValueError` goes back to the agent as a retry
   message, max 3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per shipped engine, output that engine's strict
   authored-overlay model, prompted with the generated world and engine-provided authoring
   guidance/defaults. Re-run step 2's loop with each generated overlay in place — the overlay
   is what `begin_game` exercises beyond shared structure.
4. Files land in `scenarios/<slug>/` only after every shipped engine validates. The script
   prints a summary (entities, relations, threads, hooks per engine) and the author reviews the
   diff before committing — generated content merges by the same review as hand-written
   content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under every shipped engine. Quality beyond
validity is judged by playing it, not asserted by the script. PDF/notes ingestion is a later
input mode for the same script, not a separate system.

## Phase 5 — Media: scene illustrations (~2–3 days)

Presentation only, outside mechanical truth: the game must be indistinguishable with media
disabled, and a failed generation must cost nothing but a log line.

1. `MediaConfig` on `Settings`: `enabled: bool = False`, `provider: ProviderName = "openrouter"`,
   `model: str` (an image-capable model id). `src/aidm/app/media.py`:
   `illustration_request(state: GameState, narration: str) -> str` builds the image prompt
   deterministically — location name and brief, the `here` entities' briefs, the narration — **no
   model call decides whether to illustrate**; a Producer role is not built until a deterministic
   builder proves insufficient. `async generate(prompt, config) -> bytes | None` calls the image
   API and returns None on any failure (logged, never notified).
2. Wiring, at the boundary: after the commit in `GameSession.submit`, when media is enabled,
   schedule generation as a background asyncio task writing
   `saves/<slug>.media/turn-<n>.png`. The turn returns without waiting. `restart()` discards the
   media directory alongside the save.
3. UI: the chat panel shows the image above its exchange when the file exists; refresh on next
   submit (simplest) picks up late arrivals, a `ui.timer` only if that feels bad in practice. No
   gallery, no regeneration button.
4. Tests: the request builder is pure — one test on its output for a known state; the generate
   path is not tested live (network rule). Voice, portraits, and ambient audio are later phases
   of the same shape, none specced until wanted.

Done when: with media enabled a turn grows an illustration within seconds after the narration,
and with it disabled (the default) nothing in state, saves, prompts, or tests differs.
