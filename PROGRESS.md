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

## Next

- Phase 1 step 3 — tool-calling Director (probe `NativeOutput` + tools live before fixture work).
