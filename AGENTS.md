# Repository guidance

## Commands

```bash
uv run pytest              # deterministic, no network
uv run ruff check
uv run basedpyright        # strict mode; the enforcement behind "avoid Any"
uv run python -m aidm      # http://localhost:8080
```

Run from the repo root; paths and `.env` resolve against the working directory.

## Engineering principles

- Prefer functional programming: pure transformations, immutable values, explicit inputs, and side effects isolated at boundaries.
- Use strict type safety throughout. Avoid `Any`, unchecked casts, and broad type suppressions.
- Use strict Pydantic models at external, persistence, model, and tool boundaries.
- Fail fast on invalid data, broken invariants, and incompatible state.
- Keep code simple, readable, DRY, and KISS. Avoid speculative abstractions.
- Use descriptive names that clearly tell the purpose of the object (names of file, classes, variables, methods, ...)
- Optimize for maintainability over cleverness or premature flexibility.
- Keep functions below 100 lines and files below 500 lines.
- Comments explain only why and are as concise as possible.
- Docstrings are as short as possible and add only non-obvious information.

## Domain & Architecture Invariants

- The model proposes, Python decides. LLMs never mutate state. Agents output typed data (intents, events, or structured entity data) which is processed by deterministic Python rules.
- The Reducer Pattern: State evolution is strictly centralized. `domain/events.py:apply(state, events)` is the only allowed mechanism for producing new state. Never mutate objects in place.
- Dependency Direction: `domain/` and `engine/` import nothing from `agents/` and perform no I/O. Mechanics stay testable without an agent, and agents cannot decide outcomes. Growing the ruleset means growing `engine/`, not the role prompts.
- Strict Role Boundaries: Each agent has a narrow, singular responsibility (Director plans and proposes the turn's typed mechanics, Narrator writes, Maintainer tracks, Creator invents). The Director's `plan` is resolved deterministically by `engine/resolve.py`.
- Centralized Context Policy: `agents/context.py` is the absolute source of truth for what each role sees. If an agent needs new data, update the policy table there. Never inject raw state directly into prompt strings outside of this policy.
- Narrator Blindness: The Narrator is uniquely kept blind to unrevealed canon. Never expose hidden world state, DCs, or dice rolls to the Narrator, as it writes what the player reads.

## Framework specifics

- Pydantic V2: Use `model_validate`, `model_dump`, and native V2 config. Do not use V1 methods (`dict()`, `parse_obj`). Use the custom `updated(obj, **kwargs)` helper for copying frozen models.
- Pydantic AI: Structured roles use `NativeOutput`; the Director validates its output against per-turn canon via `RunContext[DirectorDeps]` in an `output_validator` (raising `ModelRetry` on an off-menu id). Agents emit typed data only. `engine/resolve.py` maps the Director's `plan` to `Event`s, and `apply` alone mutates state.
- NiceGUI: The UI is purely a reflection of `Session.state`. Use `@ui.refreshable` to handle state-driven reactivity. Keep domain logic completely out of the `ui/` directory.

## Testing and verification

- Keep tests minimal and focused on core behavior and integrity boundaries.
- Do not test exact creative prose, live model quality, or trivial wiring.
- Tests must not require network access (stub model calls via Pydantic AI's FunctionModel or similar)

Update this file only when a rule is expected to remain true across project phases.
