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
- State models and engines own the methods that read or mutate them; a method that writes nothing
  outside its arguments is pure.
- State models are mutable. Value models are frozen.
- Do not use `Any`. Use exact types. The one exception: a class or function generic on the game
  state, where `Game[P]`'s invariance makes `Any` the only spelling of the bound.
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
- An engine is self-contained under `engines/<id>/`, under 2,000 lines, with at most fifteen game-master tools, counted as tools plus `change_world` arms, the two shared party arms not counted; twenty in all for an engine whose SRD plays a crew, named in its `docs/<ENGINE>.md`. Every engine subclasses `Engine` in `engines/seam.py`; the three scene engines subclass `SceneEngine` in `engines/scenes/engine.py`; all four share the hub in `engines/hub.py`.
- The narrator writes the story text; the worldsmith's scene titles, offers and debrief reach the player on cards and panels. The narrator's input holds revealed facts only. Hidden facts have no path into it.
- The worldsmith writes new cast entries and rewrites a brief; a name and a sheet are the rules'. The scene bar and the install share one refusal list, so the worldsmith's one retry sees every refusal.
- A bad model answer is re-prompted once with the error, then raises.
- Saves have no version field. A stale save is invalid.
- Only `turn`, `app`, and `ui` read the settings.

## Tests

- Test behavior and boundaries, not prose or wiring.
- Never start a process in a test. Stub roles with `ScriptedSpawner`.

Keep this file for rules that stay true in every phase.
