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

- A class owns its state and the methods that read or change it. A function whose first argument
  is one of our objects is a method; a free function is for what has no owner. A function stays
  free when its object's class lives in a lower layer, when it renders or builds at an edge, or
  when it is unit-tested on its own.
- A property is a scalar, or a one-line reading of the object's own fields; anything that renders
  a block, joins other objects or builds a collection is a method.
- Side effects live at the edges (files, network, UI). Rules code changes only the draft it is
  handed and rolls only the `Random` it is handed.
- State models are mutable. Value models are frozen.
- A tool is an engine method marked `@tool`; its docstring is what the master reads. It
  resolves ids and rolls dice, and the world or entity method it calls changes fields and
  returns the facts.
- `id`, `label`, `detail` for a pick, an option or a panel row, on disk too; `name` and `brief`
  for an entity; `title` for a scene, a scenario, an engine. Tool arguments: `actor_id` for who
  acts, `target_id` for who is acted on, `to_id` for a destination, `_id` on every id.
- Do not use `Any`. The exceptions: `Game[Any]`, `Engine[Any, Any]`, `World[Any, Any]`,
  `Scenario[Any]`, `Character[Any]` where the app holds every engine at once or a class is
  generic on the game state, and the `Any` inside a world bound (`W: SceneWorld[Any]`),
  because a world's cast parameter is invariant.
- Validate data at each boundary (file, model output, tool call) with strict Pydantic V2 models. Reject bad data at once.
- A message a role or the player is meant to read is a `Refusal`; any other exception is a bug
  and is not caught.
- Inside a validator raise `ValueError` or call a check helper; `parse` turns either into the
  refusal.
- Do not add an abstraction until two things need it.
- Do not build for future needs.
- Names must explain themselves. Do not add a comment unless the reason is not visible in the code. One line max.
- Keep `__init__.py` files empty. Import from full module paths.
- Imports flow one way: `core <- engines <- turn <- app <- ui`. No cycles.
- Module layout: imports, constants, classes, public functions, private functions. A constant
  built from a class follows that class.

## How the game is built

- Three AI roles, each a spawned CLI or a loop over a completion API, starting cold every turn. The narrator and the worldsmith
  answer with typed proposals. The master plays through tools on a draft that is checked before it
  lands. Only code changes state or rolls dice.
- The engine owns the world. `core`, `turn`, `app` and `ui` know no world shape; the registry is
  the one place that joins an engine to the app.
- An engine is one class with its fields and tools written out; `SceneEngine` and
  `RoomEngine` are the two loops, one per family, and an engine adds its own tools to one of
  them.
- The narrator reads revealed facts only. Hidden facts have no path into it. The master reaches
  it only through tool calls that landed.
- A bad model answer is re-prompted once with the error, then raises.
- Saves have no version field. A stale save is invalid.
- Only `app` and `ui` read the settings.

## Tests

- Test behavior and boundaries, not prose or wiring.
- Never start a process in a test. Stub roles with `ScriptedSpawner`.
- A golden is a drift detector, not a prose test.
