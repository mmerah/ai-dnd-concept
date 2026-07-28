# Repository guidance

## Commands

Run from the repository root:

```bash
uv run pytest
uv run ruff check
uv run basedpyright
uv run python -m aidm
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

## Architecture invariants

- The model proposes typed data; deterministic Python decides outcomes and mutates no state directly.
- State evolves only through the pure reducer in `domain/`, applied to typed events.
- `domain/` and `engine/` import nothing from `agents/` and perform no I/O.
- Each agent has one narrow role. Its proposal is resolved by `engine/`, never another prompt.
- `agents/` owns one centralized context policy for what each role sees.
- `engine/` reads compiled profiles from `engine/ruleset.py`; only `engine/pack_ruleset.py` knows pack storage shape.
- Content is derived once: `scripts/srd/` narrows upstream records and the ruleset compiler reads them.
- `bootstrap.py` is the composition root. Below it, collaborators and paths are explicit; no globals.
- `application/` owns the open game behind ports, while `store.py` performs path-based I/O.
- Only the Narrator writes player-facing prose and it never sees unrevealed canon or hidden state.
- The Narrator sees mechanics only through `reducer.render(events)`.
- `render` never exposes absolute or maximum HP for a non-player actor; wounds stay qualitative.

## Framework rules

- Use Pydantic V2 APIs only. Copy frozen models through the shared `updated` helper so validation runs.
- Pydantic AI roles return validated structured output. Per-turn validators request retries and never mutate state.
- NiceGUI reflects session state only. Keep domain logic out of `ui/` and update refreshable views.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in `config.py`.

## Verification

- Test core behavior and integrity boundaries, not exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent; never require network access.

Change this file only for rules expected to remain true across project phases.
