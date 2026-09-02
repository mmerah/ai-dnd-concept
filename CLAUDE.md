# Repository guidance

## The maintainer

The maintainer has ADHD. Load the `i-have-adhd` skill at the start of each session.

## Commands

Run from the repo root. Do not set `UV_CACHE_DIR` as it breaks the test suite.

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run aidm
```

Tests run offline. They are deterministic.

## Code

- Write pure functions. Put side effects at the edges (files, network, UI).
- State models are mutable. Value models are frozen.
- Do not use `Any`. Use exact types.
- Validate data at each boundary (file, model output, tool call) with strict Pydantic V2 models. Reject bad data at once.
- Do not add an abstraction until two things need it.
- Do not build for future needs.
- Names must explain themselves. Do not add a comment unless the reason is not visible in the code. One line max.
- Keep `__init__.py` files empty. Import from full module paths.
- Imports flow one way: `core <- engines <- turn <- app <- ui`. No cycles.
- Module layout: imports, constants, classes, public functions, private functions.

## Design decisions (not visible from the code)

- Each role is a spawned CLI. The app resumes its session each turn when the CLI allows it. A role returns typed proposals only. Resolver code applies them. Only resolver code changes state or rolls dice.
- The engine owns the world. `core`, `turn`, `app` and `ui` know no world shape. The registry is the one place that connects them.
- An engine is self-contained under `engines/<id>/`, under 2,000 lines, with at most fifteen game-master tools, world verbs included, one per SRD procedure. The scene engines share the scene lifecycle in `engines/scenes.py`; all four share the hub in `engines/hub.py`.
- The narrator writes the story text; the worldsmith's scene titles, offers and debrief reach the player on cards and panels. The narrator's input holds revealed facts only. Hidden facts have no path into it.
- A bad model answer is re-prompted once with the error, then raises.
- Saves have no version field. A stale save is invalid.
- Only `turn`, `app`, and `ui` read `config.py`.

## Tests

- Test behavior and boundaries, not prose or wiring.
- Never start a process in a test. Stub roles with `ScriptedSpawner`.

Keep this file for rules that stay true in every phase.
