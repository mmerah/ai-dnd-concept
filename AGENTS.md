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

- Prefer pure transformations, immutable values, explicit inputs, and side effects isolated at boundaries.
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
- State evolves only through the pure reducer in `aidm/domain/`, applied to typed events.
- Core owns topology and commits; the selected rules package owns typed mechanics and rules-only patches.
- `aidm-core` imports neither rules package nor NiceGUI; `aidm-rules-story` imports no 5e code.
- Rules packages import no UI code. The UI composition root registers both first-party engines.
- Each agent has one narrow role. Its proposal is resolved by the selected engine, never another prompt.
- `aidm/agents/` owns one centralized context policy for what each role sees.
- The 5e engine reads compiled profiles from `aidm_5e/engine/ruleset.py`; only `pack_ruleset.py` knows pack storage shape.
- 5e content is derived once: `packages/aidm-rules-5e/scripts/srd/` narrows upstream records.
- `aidm_ui/bootstrap.py` is the composition root. Below it, collaborators and paths are explicit; no globals.
- `aidm/application/` owns the open game behind ports, while `aidm/store.py` performs path-based I/O.
- Only the Narrator writes player-facing prose and it never sees unrevealed canon.
- Every role sees engine state through engine-owned presentation; core owns which entities each role may see.
- The Narrator receives exact state for visible entities and translates mechanics into fiction instead of reciting stat blocks.

## Framework rules

- Use Pydantic V2 APIs only. Copy frozen models through the shared `updated` helper so validation runs.
- Pydantic AI roles return validated structured output. Per-turn validators request retries and never mutate state.
- NiceGUI reflects session state only. Keep domain logic out of `aidm_ui/` and update refreshable views.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in `config.py`.

## Verification

- Test core behavior and integrity boundaries, not exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent; never require network access.

Change this file only for rules expected to remain true across project phases.
