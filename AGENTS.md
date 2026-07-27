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

- The model proposes, Python decides. LLMs never mutate state; agents emit typed data (intents, events, structured entities) that deterministic Python rules process.
- Single reducer. State evolves in exactly one place — the reducer in `domain/`, applied to typed events. Never mutate state in place; always produce a new value.
- Dependency direction. `domain/` and `engine/` import nothing from `agents/` and do no I/O, so mechanics stay testable without an agent and agents cannot decide outcomes. Growing the ruleset means growing `engine/`, not the role prompts.
- Strict role boundaries. Each agent has one narrow responsibility. An agent's structured proposal is resolved by deterministic code in `engine/`, never by another prompt.
- Centralized context policy. One place in `agents/` is the source of truth for what each role sees. Extend that policy rather than injecting raw state into prompt strings elsewhere.
- Narrator blindness. The Narrator alone writes what the player reads, so it is never shown unrevealed canon or hidden state. It *is* shown `reducer.render(events)` — this turn's resolved outcome, including DCs and rolls — because it must not narrate an outcome that did not happen. `render` is the boundary: everything mechanical the Narrator may see passes through it, and nothing else does. `render` never emits an absolute hp or max_hp for a non-player actor; a monster's wounds are qualitative.

## Framework specifics

- Pydantic V2 only. Use V2 APIs and native config, never V1 methods. Copy frozen models through the shared `updated` helper so validation still runs.
- Pydantic AI. Structured roles emit validated typed output; per-turn validation lives in an output validator that asks the model to retry on invalid data, and never mutates state itself.
- NiceGUI. The UI only reflects session state; keep all domain logic out of `ui/` and drive updates through refreshable views.
- Per-role LLM settings (model, endpoint, retries, token budget, reasoning level) live in the config module, one entry per role — never hardcoded in a role module.

## Testing and verification

- Keep tests minimal and focused on core behavior and integrity boundaries.
- Do not test exact creative prose, live model quality, or trivial wiring.
- Tests must not require network access (stub model calls via Pydantic AI's FunctionModel or similar)

Update this file only when a rule is expected to remain true across project phases.
