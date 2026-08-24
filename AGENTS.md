# Repository guidance

## Working with the maintainer

The maintainer has ADHD. At the start of every session, load the `i-have-adhd` skill and follow it. Lead with the next action, number multi-step work, restate progress each turn, and keep openings and endings direct.

## Commands

Run these commands from the repository root with `UV_CACHE_DIR` unset; setting it breaks the verification suite.

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run aidm
```

Tests are deterministic and run offline.

## Engineering

- Prefer pure functions with explicit inputs. Keep side effects at system boundaries. State models are mutable; value models are frozen.
- Use strict, specific types in place of `Any`. Narrow types through validation and keep suppressions narrow.
- Validate data that crosses external, storage, model, or tool boundaries with strict Pydantic V2 models.
- Reject invalid data, broken invariants, and incompatible state immediately.
- Keep code simple and DRY. Add abstractions only for current needs.
- Build every agreed capability directly in its final planned form. Apply YAGNI to features that were not agreed on.
- Add a port or interface when a second implementation exists. A protocol may be useful earlier when core must stay independent of a specific dependency.
- Choose names that make extra explanation unnecessary.
- Keep functions below 100 lines and files below 1000 lines.
- Write a comment or non-runtime docstring only for a non-obvious reason, constraint, tradeoff, invariant, or tooling exception, and keep it to one line. Let names and signatures explain behavior. Treat descriptions used by reflection, Pydantic, or LLM prompts as runtime behavior: preserve their meaning and verify changes.
- Keep directives such as `# pyright: ignore[...]` narrowly scoped and add a reason when needed.
- Keep package `__init__.py` files empty and import from explicit module paths.
- Use module-scope runtime imports for both values and types. Keep dependency flow one-way so imports stay acyclic. Engine discovery may import an engine module by name to read its declared engine class. Break cycles by moving the smallest shared type into its own module.

## Design rules

- The model returns typed, validated proposals. Resolver code applies them deterministically to the turn draft, records facts, and owns all state changes, rolls, and ledger updates.
- Each engine owns all of its mechanics. It defines the overlay schema for authored content, treats incompatible state as invalid, and seeds everything needed by entities created during play.
- Route all player-facing prose through the narrator. Its input type contains revealed canon exclusively, leaving hidden information with no path into the prompt.
- Build the app once from one composition root, where dependencies are assembled. Pass collaborators and paths explicitly below it and keep state in owned objects.
- Represent save compatibility with its recorded origin and strict validation. Treat stale saves as invalid; the save format has no version field or conversion path.

## Framework rules

- Use Pydantic V2 APIs. Validate once at the transaction boundary rather than after each field change. Remember that `model_copy(update=...)` skips validation.
- Pydantic AI roles return validated structured output. Invalid tool calls and outputs request another attempt with `ModelRetry`.
- Check each turn-loop tool call against a throwaway copy first, then apply valid calls to the turn draft through resolver code.
- Confine tool writes to drafts. Authoring tools apply typed patches to their in-memory draft; application code owns committed state, saves, and files.
- Use NiceGUI to display session state and submit typed decisions. Put domain logic in domain packages and update refreshable views.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in one config module.

## Verification

- Focus tests on core behavior and integrity boundaries rather than exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent so every test runs offline.

Keep this file for rules that remain true in every future phase. Put phase-specific or refactor-sensitive guidance elsewhere.
