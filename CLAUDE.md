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
- This project is pre-stability. Choose the simplest final architecture.
- Add a port or interface when a second implementation exists. A protocol may be useful earlier when core must stay independent of a specific dependency.
- Choose names that make extra explanation unnecessary.
- Keep functions below 100 lines and files below 1000 lines.
- Write a comment or non-runtime docstring only for a non-obvious reason, constraint, tradeoff, invariant, or tooling exception, and keep it to one line. Let names and signatures explain behavior. Treat descriptions used by reflection, Pydantic, or LLM prompts as runtime behavior: preserve their meaning and verify changes.
- Keep directives such as `# pyright: ignore[...]` narrowly scoped and add a reason when needed.
- Keep package `__init__.py` files empty and import from explicit module paths.
- Use module-scope runtime imports for both values and types. Keep the dependency flow one-way so imports stay acyclic: `core <- kits <- engines <- turn <- app <- ui`. Break a cycle by moving the smallest shared type into its own module.
- Order every module top to bottom: imports, then constants and type aliases, then models and classes, then public functions, then private helpers.
- A statement evaluated at module scope keeps its dependency order; that order is the law and the section rank only breaks ties, so a table may follow the classes it names and a factory may precede the model whose default it is.

## Design rules

- Each role is a one-shot CLI the app spawns. It returns typed, validated proposals. Resolver code applies them deterministically to the turn draft, records facts, and owns all state changes, rolls, and ledger updates.
- The world is whatever its engine-selected kit says it is: the scene kit under `src/aidm/kits/scenes/` owns sentence-driven scenes, while the rooms kit under `src/aidm/kits/rooms/` owns authored maps. Each kit owns its state, `change_world` verbs, boundary, and views.
- Each engine owns all of its mechanics. It puts its own sheet union on kit entities, treats incompatible state as invalid, and gives entities created during play a default sheet.
- An engine ships one game-master tool per SRD procedure, never more than eight: the engine rolls everything the procedure needs and hands back one result. The kit owns the world tools every game master sees; a tool only one engine's rules read is added by that engine, so an unused tool never crowds the model's choice.
- Route all player-facing prose through the narrator. Its input type contains revealed canon exclusively, leaving hidden information with no path into the prompt.
- Build the app once from one composition root, where dependencies are assembled. Pass collaborators and paths explicitly below it and keep state in owned objects.
- Represent save compatibility with its recorded origin and strict validation. Treat stale saves as invalid; the save format has no version field or conversion path.

## Framework rules

- Use Pydantic V2 APIs. Validate once at the transaction boundary rather than after each field change. Remember that `model_copy(update=...)` skips validation.
- A role that returns a value is validated against its expected type. An invalid answer is re-prompted once with the error, then raises.
- Check each turn-loop tool call against a throwaway copy first, then apply valid calls to the turn draft through resolver code.
- Confine writes to drafts. The worldsmith runs against a deep copy of committed state; application code owns committed state, saves, and files.
- Use NiceGUI to display session state and submit typed decisions. Put domain logic in domain packages and update refreshable views.
- Keep each role's command and timeout in `config.py`. Only `turn`, `app` and `ui` may read it.

## Verification

- Focus tests on core behavior and integrity boundaries rather than exact creative prose, live model quality, or trivial wiring.
- Never start a process in a test. Stub every role with `ScriptedSpawner`, which answers from a per-role list and records the prompts it was given.

Keep this file for rules that remain true in every future phase. Put phase-specific or refactor-sensitive guidance elsewhere.
