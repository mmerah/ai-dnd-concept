# Repository guidance

## Working with the maintainer

The maintainer has ADHD. Load the `i-have-adhd` skill at the start of every session and shape all output according to it: lead with the next action, number multi-step work, restate progress each turn, no preamble or closing pleasantries.

## Commands

Run from the repository root:

```bash
uv run pytest
uv run ruff check
uv run basedpyright
uv run aidm
```

Tests must be deterministic and require no network.

## Engineering

- Prefer pure transformations, explicit inputs, and side effects isolated at boundaries. State models are mutable; values are frozen.
- Use strict types. Avoid `Any`, unchecked casts, and broad suppressions.
- Validate external, persistence, model, and tool boundaries with strict Pydantic V2 models.
- Fail fast on invalid data, broken invariants, and incompatible state.
- Keep code simple, DRY, and maintainable. Avoid speculative abstractions.
- Use descriptive names before adding prose to explain code.
- Keep functions below 100 lines and files below 500 lines.
- Comments explain only a non-obvious why: a constraint, tradeoff, invariant, or tooling exception.
- Delete comments that narrate control flow, restate a name or type, give historical counts, or serve as architectural essays.
- Keep directives such as `# pyright: ignore[...]` narrowly scoped and include rationale only when the directive is not self-explanatory.
- Omit package and module docstrings by default. Never use them as file tours.
- Omit docstrings when the signature and name are the complete contract.
- Keep necessary docstrings to one concise sentence. Use multiple lines only when losing the detail would hide an important rationale or contract.
- Treat docstrings consumed by reflection, Pydantic schemas, or LLM prompts as runtime behavior: preserve their meaning and verify changes.
- Keep package `__init__.py` files empty. Import from explicit module paths.
- Keep imports at module scope. Resolve cycles by extracting leaf models or protocols, never with function-local imports.

## Architecture invariants

- The model proposes typed data; deterministic Python decides outcomes and mutates no state directly.
- State evolves through transactions: `state.draft()` copies, mechanics mutate that draft, `draft.committed()` revalidates it once. A turn runs two — the engine's resolution and the pipeline's growth-and-exchange — and an advancement runs its own. A failed transaction never replaces the committed state, and a committed `GameState` is never mutated again; enforced by the resolve-purity tests, not by the type system.
- `Frozen` means the model's own fields cannot be reassigned, not that its contents are immutable: a `Frozen` fact may hold a `Mutable` model. Copy into a fact whatever the same transaction goes on to mutate.
- Core owns commits. Engines own typed mechanics and mutate the draft directly, including topology, through `GameState`'s `add`/`reveal`/`move_actor`/`move_item`.
- A turn's facts are one persisted union — core topology facts plus each engine's own — discriminated on `source` then `fact`. Core renders its own and delegates the engine's in `engines.py`; directions carry the same `engine` tag so a reloaded trace never guesses.
- `GameState.engine` is one `EngineAggregate` per engine, discriminated on the engine tag. Entities carry no rules field, and the state validator asserts those keys track the world's actor and item ids.
- Engine state and authored engine data are typed unions, never JSON envelopes: a wrong-engine payload is unrepresentable rather than validated. Engines narrow authored data with `definitions.py::for_engine`.
- Core assigns entity ids and hands each one's authored data back on `AuthoredWorld`. An engine never re-derives which definition became which entity.
- One distribution. `aidm_story/` imports no 5e code and vice versa; neither imports `aidm_ui/` or NiceGUI, and `aidm/` imports no UI. Enforced by `tests/core/test_package_boundary.py`.
- `EngineId` is a closed literal. An engine is a concrete value built by `aidm/engines.py::engine_for`, and core pairs each engine with its own direction type there.
- Each agent has one narrow role. Its proposal is resolved by the selected engine, never another prompt.
- `aidm/agents/` owns one centralized context policy for what each role sees. `SceneSnapshot` is the one projection of a `GameState`; each renderer takes it plus the bound entity renderer, never a per-role DTO.
- The 5e engine reads compiled profiles from `aidm_5e/engine/ruleset.py`; only `pack_ruleset.py` knows pack storage shape.
- 5e content is derived once: `scripts/srd/` narrows upstream records. A pack loads once and every turn shares its records, so pack and compiled-profile maps stay frozen; runtime state maps are plain dicts.
- `aidm_ui/bootstrap.py` is the composition root. Below it, collaborators and paths are explicit; no globals.
- `aidm/application/` owns the open game behind ports, while `aidm/store.py` performs path-based I/O.
- `save_version` is the only compatibility gate. `store.py` refuses a stale save or trace at load; regenerating the SRD content pack bumps `SAVE_VERSION`.
- Only the Narrator writes player-facing prose and it never sees unrevealed canon. `render_narrator` takes `VisibleScene`, which has no field a leak could travel through; never widen it to `SceneSnapshot`.
- Every role sees engine state through engine-owned presentation, bound to the state it reads by `engines.py::entity_renderer`; core owns which entities each role may see.
- The Narrator receives exact state for visible entities and translates mechanics into fiction instead of reciting stat blocks.

## Framework rules

- Use Pydantic V2 APIs only. Validation runs at the transaction boundary, not per field change; `model_copy(update=...)` does not validate.
- Pydantic AI roles return validated structured output. Per-turn validators request retries and never mutate state.
- NiceGUI reflects session state only. Keep domain logic out of `aidm_ui/` and update refreshable views.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in `config.py`.

## Verification

- Test core behavior and integrity boundaries, not exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent; never require network access.

Change this file only for rules expected to remain true across project phases.
