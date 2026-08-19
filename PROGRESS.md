# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 step 1 — dead pass-throughs and the dynamic registry

- `Fact.source` and the `CORE` constant are gone; a fact is `kind/trace/narrator/data`.
- `Resolution.outcome` and `Transacted.outcome` are gone. A roll's outcome is read from its own
  fact: `question_answered` (loner3e) and `attempt_resolved` (24xx) carry `data["outcome"]`;
  24xx's `_bad_luck` emits `luck_tested` with `data["trouble"]` only when it is not clear.
- `engines/registry.py` (import-by-name) is replaced by `app/registry.py` with a static
  `ENGINES` tuple. Engine's sheet type param is invariant, so the tuple needs one narrow
  `# pyright: ignore[reportAssignmentType]` per entry. Both `rules.py` files lost `ENGINE = ...`.
- SAVE_VERSION 73 → 74: traces are persisted and version-gated, so dropping `Fact.source` moved
  their bytes even though the save shape did not.

### Phase 1 step 2 — Hook and Memory shrunk

- `Hook(id, on_discover, note, reveals, advance_thread)`. `FactMatch`/`DiscoveryMatch`/
  `ThreadMatch`/`HookMatch`, `Hook.effects`, `Hook.once` and `effects.references()` are gone;
  a hook fires once, on one `entity_discovered` fact, and its reveals feed the next round.
- `content/authored.py` has one hook validator (`_hooks_name_authored_ids`). The domino check is
  gone with it: a chain of reveals is now bounded only by `MAX_HOOK_ROUNDS`.
- `Memory` lost its slug; `WorldState.memories` and `WorldDraft.memories` are lists. A memory's
  identity is its text (the Worldkeeper dedupe), so authoring `remove` can no longer name one.
  `text_slug` stays — character creation uses it.
- Behavior deliberately dropped: drowned-road's `key-discovered` no longer unlocks and reveals the
  chapel→crypt way, and whispering-vault's `vault-sighted` no longer adds the `warded` trait. Both
  are folded into the hook `note`, so the Director steers them — Opinion 3's design.
- SAVE_VERSION 74 → 75; `save/state/turn` and the prompt fixtures regenerated.

### Phase 1 step 3 — tool-calling Director

- The Director runs once per turn as a tool-calling agent: `output_type=str` (the closing line only
  traces), no output validator, `UsageLimits(request_limit=16)`. `TURN_STEPS` is
  `("director", "hooks", "narrator", "worldkeeper")`; `_run_beats`/`_ask_director` are gone.
- Every tool body is `act()`: refuse against a throwaway copy, apply to the turn's draft through
  `apply_to_draft`, return the facts' traces plus any new `pending_notes`. That return is the whole
  reason the loop works — the model reacts to its own dice without being re-prompted.
- `PlanContext`/`TurnLog` live in `engines/engine.py`, not `turn/`. `AbstractToolset`'s deps param is
  contravariant, so `Engine.director_toolsets` must name the real deps type; putting it in `turn/`
  would have made the engines import `turn/` and broken the package-boundary test.
- The ops are built *inside* the play closure, so a cross-field refusal (`_one_help_die`,
  `_moves_something`) surfaces through `check_draft` as a `ModelRetry` instead of killing the turn.
- `FunctionToolset(require_parameter_descriptions=True)` makes an undocumented tool parameter fail
  at build. It caught `expand_world` immediately.
- `apply_to_draft` ends with `draft.flush_mechanics()`. Without it a later tool's trial copy
  re-parses stale mechanics JSON. Flushing in `draft()` instead is wrong — it breaks the invariant
  that a mutation against a committed state never reaches a draft (`test_integrity_boundaries`).
- Only the notes the prompt rendered are spent (`pending_notes[shown:]`), so a hook note written
  mid-run reaches the model twice: in its tool's answer, and in the next turn's prompt.
- `transact` returns `(state, facts)`; `Transacted` is gone. `Play` is now
  `Callable[[GameState, Random], Resolution]` so a trial run cannot consume the turn's dice.
- SAVE_VERSION 75 → 76: trace bytes moved (step names, and the director's output is a string now).
- A resolver's refusal text is prompt surface: `_require_open_way` was still telling the model to
  write a `relation-change` effect, on the most common refusal path there is. Refusal strings have
  to move with the wire, and nothing type-checks them.

#### Eval evidence (`evals/turn_eval.py`, n=9 per case, 10 closed whispering-vault cases)

| | before | after |
|---|---|---|
| all expectations held | 86% | 89% |
| turns that errored | 3% | 0% |
| Director model calls / turn | 1.37 | 1.00 |
| seconds / turn | 1.9 | 3.1 |

Both runs are checked in under `evals/results/`. The tool wire is markedly better at *sequences*
(`three-things`: reaching the tower 67→89%, handing the lantern over 56→89%) and it removed the
three `Exceeded maximum output retries` failures the large beat schema produced.

Its one regression was compound single actions — "find the chart and pick it up" revealed without
taking, 100→67% — plus a trait-gain drop. Both came from prose deleted with `examples.json`, and
both were fixed by one paragraph in `director.md` (finish the player's action; a lasting state must
call `add_trait`), which is what took 77% back to 89%. Worth remembering: the worked-plan examples
were carrying instruction, not just illustration.

### Phase 1 step 4 — the beat machinery deleted

- `Engine` is now metadata, sheet + mechanics types, `begin`/`validate`/`check_mechanics`/`seed`/
  `new_sheet`, `describe`/`sheet_view`/`renderer`, `binding`/`check_overlay`, instructions +
  toolsets, advancement, creation. `beat_type`, `unpack_beat`, `check_beat`, `resolve_beat`,
  `_play`, `resolve_roll`, `apply` and `SETTLE_REFUSAL` are gone; so are both `*Beat` models, both
  effect unions, `Resolution.followup`, `Followup`, and the `BEAT_*` description constants.
- The wire vocabulary did not move: `director_tools.json` and every `save`/`state`/`turn` fixture
  regenerate byte-identical, so SAVE_VERSION stays at 76. Nothing beat-shaped was ever persisted —
  a trace holds the Director's string and the facts, and `Resolution` never reached a save.
- Three modules were renamed to what is left in them: `state/apply_effects.py` → `state/actions.py`
  (the world resolvers, unprefixed and taking plain typed parameters), `state/beat.py` →
  `state/resolution.py` (`Resolution` + `check_draft`), and `state/effects.py` is gone — its last
  survivor `AdvanceThread` now sits in `state/world.py` beside the `Hook` that persists one.
  `tests/core/test_effects.py` follows as `tests/core/test_actions.py`.
- `AdvanceThread` is the one op class that survived, and it is not wire-only: `Hook.advance_thread`,
  both `scenarios/*/world.json` and `ExpansionPatch.hooks` persist it, and `"op": "advance-thread"`
  is in the save fixtures — so its `op` discriminator field stays even though nothing discriminates
  on it any more. Its resolver still takes the model rather than plain parameters, so the
  `advance_thread` tool keeps building it inside the play closure and `_moves_something` keeps
  surfacing as a `ModelRetry` (the step 3 note) instead of as a silent no-op.
- The engines' remaining action models (`Question`, `Attempt`, `LuckTest`) are now internal
  parameter carriers, not model-facing schemas: the tool docstrings are the schema. They lost their
  `op` fields. `ChangeCredits`/`RestoreLuck`/`CompleteJob`/`EndAdventure` are gone entirely —
  `apply_change_credits(draft, actor_id, amount)` carries the zero-amount refusal itself now.
- 24xx no longer computes a followup, so `_bad_luck` returns facts alone. The test that asserted a
  trouble roll hands the turn back went with it; nothing hands a turn back any more.
- Deleted tests, all describing machinery rather than behavior: the two `beat.json` golden schemas,
  `test_a_beat_naming_a_roll_this_engine_has_not_is_refused` (the typed-union guard it covered is
  what the tool signatures now are), and 24xx's followup test. 191 → 187.

### Phase 1 step 5 — Relation deleted

- `Exit(to, known, locked)` lives on `Entity.exits` (locations only, ids unique, no self-exit) and
  `WorldState.party` is a plain list. `Relation`, `RelationId`, `CONNECTED`, `PARTY_MEMBER`,
  `world.relations/relation()/connections()/party()` and the `reveal_way` tool are gone.
- Exits are directional and authors write both ends, so every rule about a way has to say what it
  does to the way back. Walking one reveals both ends (the room the player just entered would
  otherwise show no way out at all) and `unlock_exit` clears both (a one-way unlock strands them
  behind the door they opened). A resolver that touches one exit and not its mirror is a bug.
- `_check_party` refuses `player` in the party: `require_actor_here` accepts the player, and
  `Advancement.offers` iterates `(PLAYER_ID, *party)`, so self-joining doubled their own offer.
- `ScenarioWorld._every_known_location_reachable_by_known_ways` is deleted with them: an unknown
  way is walkable now, so it described no dead end.
- `turn/scene.py` lost its own `Exit`; `BaseScene` carries the state model plus `exit_names`, so a
  name joins at render time and the Narrator's view still holds only known ways.
- `ExpansionPatch.relations` → `exits: tuple[ExitLink, ...]` (`location_id` + `Exit`); a new
  location carries its own exits back, and every materialized way starts unknown.
- SAVE_VERSION 76 → 77.

### Phase 1 step 6 — one collection shape for worlds

- `WorldState.entities/threads/hooks` are ordered lists beside `memories` and `party`. Uniqueness
  moved into `_consistent_fiction` (`duplicate entity ids`), which is what replaced the old
  "keys disagree with their ids" invariant — with no key there is nothing to disagree.
- Lookups are linear: `find`/`require`/`require_kind`, plus `thread(id)` and `hook(id)`. Worlds
  hold under ten entities, so the scan is cheaper than the dict it replaced.
- `ScenarioWorld.world` is a plain `@property` that hands its tuples straight to `WorldState`; it
  builds a fresh one per read, which is why `begin_game` still deep-copies before mutating.
- `WorldDraft` holds the same lists; `apply`/`_remove` upsert and drop by id through one
  `_upsert`/`_drop` pair over a read-only `id` protocol.
- SAVE_VERSION 77 → 78; only the JSON container shape moved.

### Phase 1 step 7 — the Director's tool surface

Folded in from PHASE-1-ADDITIONAL-APPROACH.md; the old steps 7–10 became 8–11. The Director now
sees fewer tools, each described once, and the closed sets it has to type are closed on the wire.

- 7.1 the action model is the tool parameter (`Question`, `Attempt`, `LuckTest`,
      `AdvanceThread`); `AdvanceThread.op` and `unlock_exit.location_id` deleted.
  - Pydantic AI flattens a single model-like parameter, so the wire did not move: the same
    properties, plus a `title` and the models' own `minLength`. The `Args:` line naming the model
    parameter satisfies `require_parameter_descriptions=True` and never reaches the model, but
    griffe needs a summary line before `Args:`, so a tool cannot be described by its model's
    docstring alone — `Question`/`Attempt`/`LuckTest` lost theirs to avoid sending both.
  - A model's class docstring is sent as the schema's own `description` whenever the function
    also has one, so `AdvanceThread`'s moved onto `Hook.advance_thread` as a `Field` description —
    the slot the Expander actually reads — rather than being said twice to the Director.
  - Cross-field refusals (`_one_help_die`, `_moves_something`) are tool-argument validation now,
    which Pydantic AI retries by itself — the step 3 note about building ops inside the play
    closure no longer applies to these three.
  - SAVE_VERSION 78 → 79 for the `op` deletion alone.
- 7.2 one owner per instruction: tool text stops restating `director.md`.
  - 13 sentences cut, each checked against the prompt line that already owned it; nothing had to
    move into a prompt, so every cut was pure duplication. `add_trait`'s "shows the id written
    out" moved from the description to the `trait_id` field, where it is a legal-value statement.
  - The review found more: an owned sentence hides in a tool description that still reads well
    without it, so the pass is worth making twice. `director_tools.json` ended at 9394 → 8373
    (loner3e) and 10714 → 9624 (24xx) bytes, ~11%.
- 7.3 tools filtered to what the draft makes possible.
  - `possible(name, state)` in `turn/tools.py` over a five-entry `_APPLIES` mapping; a name with
    no entry is always offered. `director_agent` applies it — `core_toolset()` stays an unfiltered
    `FunctionToolset` so `test_golden_schemas` keeps pinning the whole vocabulary.
  - The predicate takes a state rather than a `RunContext`, so its tests need no agent harness.
  - The trap this shape sets, and the review caught twice: a predicate must offer whatever the
    *resolver* accepts, not what the tool's happy path suggests. `advance_thread(status=
    "dormant")` destroyed its own precondition while the scene went on rendering the thread under
    ACTIVE THREADS, and `add_trait` can tag the player's location, which `is_here` is false of.
    Read the resolver's guard and the scene's own filter before writing a predicate.
  - `expand_world` is filtered on `capped(log)` and keeps its `ModelRetry` guard: the cap is a
    cost boundary, and a tool definition already in flight would walk through the filter.
  - A test that reaches into `Engine.director_toolsets` now has to unwrap a `WrapperToolset`
    (`test_expansion.py` did, `test_golden_schemas.py` follows in 7.4).
- 7.4 24xx `skill`/`helper_skill` narrowed to an enum of the sheets in play.
  - The engine owns its own mechanics, so the narrowing lives in `twentyfourxx/tools.py`:
    `director_toolset()` returns its `FunctionToolset` wrapped in `.prepared(...)`. Core never
    learns what a 24xx skill is, and `test_package_boundary` stays satisfied.
  - A prepare function is handed the *same* definition objects on every step, so the schema dict
    and each property dict are copied before the enum is written and the result rebuilt with
    `dataclasses.replace`. Mutating in place accumulates across steps.
  - `skills_in_play` needs no player special case: `is_here` is true of the player, who stands at
    their own location. It needs no missing-sheet guard either — `engine.validate` runs on every
    `apply_to_draft`, so an actor here without a sheet never reaches the Director.
  - The golden pins the *static* vocabulary: `_definitions` unwraps a `WrapperToolset`, so no
    `enum` appears in `director_tools.json` and the per-step narrowing has its own test.

Left out of the source proposal, with its trigger: enums for entity ids, thread ids, and exit
destinations. The ids are already bracketed beside every entity in the prompt, the legal set
differs per tool and per argument, and no eval has shown a turn lost to an invented id. Fold it in
when one does.

Still owed: one `evals/turn_eval.py` run. Every cut in 7.2 was verified duplication, but step 3's
lesson was that prose deleted from the Director's surface carries instruction, and only the eval
sees that.

### Broken tool arguments are repaired at the model boundary

Not a plan step: 9 of 90 runs in `evals/results/step-7.json` died as `Tool '<name>' exceeded max
retries`, every one of them a backend handing back tool arguments whose closing brace was missing.
The model re-emits the identical truncated JSON when asked to fix it, so the retries only burn the
turn.

- `RepairedToolArgs` (`src/aidm/llm.py`) wraps every role's model in `build_agent`, so one place
  covers every tool and every role. `repaired()` touches only arguments that do not already parse
  as an object, tries three repairs in order — unfence, unwrap a double-encoded string, close what
  is still open (dropping a dangling comma) — and returns the original bytes when none of them
  parses, so a call is never silently reshaped. A repair logs a warning.
- Deliberately not repaired: single-quoted JSON, Python literals, prose wrapped around the object,
  and dropping a truncated dangling key. The first three need a re-parse that can mangle an
  apostrophe in narration text; the last silently drops a field the resolver needs, turning a loud
  failure into a wrong action.
- `evals/results/step-7-repair.json`: errors 9/90 → 0/90, cases fully passed 80% → 87%,
  expectations held 85% → 93%, seconds/turn 8.0 → 5.8 (a dead turn was paying for two retries).

### Open: `three-things` loses its trait, worst on 24xx

Both engines drop the third clause of "climb, hand over the lantern, and I am left winded and
shaking" — the turn records the move and the handover and never calls `add_trait`. The recorded
facts say so plainly: the failing runs hold `entity_moved`/`entity_discovered`/`entity_moved` and
no `trait_added`. A rarer second mode loses the whole turn: 24xx rolls `roll_attempt` for the climb
and stops on the outcome without moving anyone.

24xx's `director.md` framed traits as damage ("There are no hit points: injuries and broken gear
are traits", HARM AND DEFENCE), while loner3e's names "a condition taking hold", so the wording was
widened to match and to say that no roll has to stand behind a trait. **Unverified**: the A/B was
abandoned half-run, and the arm that did complete says why it has to be same-hour with a control —
`loner3e/three-things`, which no edit touched, read `trait-gained` 89% at one hour and 44% two
hours later. A same-hour baseline (`evals/results/ab-baseline.json`, n=18, prompt reverted) puts
24xx at 44% and loner3e at 67%; the only candidate data is an earlier-hour n=9 run
(`evals/results/three-things-trait.json`, 24xx 56%), which the control invalidates. Next attempt: run both arms back
to back at n=18 with loner3e as the control, and only believe a move the control does not make.

## Next

- Phase 1 step 8 — separate runtime `Game` from `SavedGame`.
- Re-run `evals/turn_eval.py` once to confirm steps 5–7 moved nothing.
- Finish the `three-things` trait A/B above, or drop the 24xx prompt widening if it shows
  nothing.
