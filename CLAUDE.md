# Repository guidance

## The maintainer

The maintainer has ADHD. Load the `i-have-adhd` skill at the start of each session.

## Commands

Run these from the repository root. Do not set `UV_CACHE_DIR`. It breaks the tests.

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run aidm
```

The tests run offline. They give the same result every time.

## How the game works

- Three AI roles play the game. Each role starts with no memory every turn.
- Two roles answer with typed proposals. One role plays through tools.
- Only code changes the game state. Only code rolls dice.
- An engine owns its world. The layers above the engines do not know the shape of a world.
- A tool is an engine method with a mark. Its docstring is the text the model reads.
- The narrator sees only revealed facts. Hidden facts never reach it.
- A bad model answer gets one retry with the error. Then it raises.
- Saves have no version. An old save is invalid.
- Only the app and the UI read the settings.

## Code

- A class owns its state and the methods that use it. A function with no owner stays free.
- A property reads one value. A method builds or renders.
- Side effects live at the edges: files, network, UI. Rules code changes only the draft it gets.
- State models are mutable. Value models are frozen.
- Use exact types. Use `Any` only where the type system gives no other way.
- Validate data at each boundary with strict models. Reject bad data at once.
- A message for a person or a model is a `Refusal`. Any other exception is a bug. Do not catch it.
- Use the same field names for the same things. An id field ends in `_id`.
- Do not add an abstraction before two things need it.
- Do not build for future needs.
- Names must explain themselves. Add a comment only when the code cannot show the reason.
- Keep `__init__.py` files empty. Import from full module paths.
- Imports flow one way: `core <- engines <- turn <- app <- ui`. No cycles.
- Module layout: imports, constants, classes, public functions, private functions.

## Tests

- Test behavior and boundaries. Do not test prose or wiring.
- Never start a process in a test. Use the scripted stub for roles.
- A golden detects drift. It does not test prose.
