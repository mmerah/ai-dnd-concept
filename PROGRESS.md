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

## Next

- Phase 1 step 7 — separate runtime `Game` from `SavedGame`.
- Re-run `evals/turn_eval.py` once to confirm steps 5 and 6 moved nothing.
