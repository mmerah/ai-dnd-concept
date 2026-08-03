# Repository guidance

## Working with the maintainer

The maintainer has ADHD. Load the `i-have-adhd` skill at the start of every session and shape all output according to it: lead with the next action, number multi-step work, restate progress each turn, no preamble or closing pleasantries.

## Commands

Run from the repository root:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run aidm
```

Tests must be deterministic and require no network.

## Engineering

- Prefer pure transformations, explicit inputs, and side effects isolated at boundaries. State models are mutable; values are frozen.
- Use strict types. Avoid `Any`, unchecked casts, and broad suppressions.
- Validate external, persistence, model, and tool boundaries with strict Pydantic V2 models.
- Fail fast on invalid data, broken invariants, and incompatible state.
- Keep code simple, DRY, and maintainable. Avoid speculative abstractions.
- Introduce a port only once a second implementation exists. A protocol that decouples core from a concrete choice earns its place on the first one.
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
- Keep imports at module scope, and the import graph acyclic with no deferred or `TYPE_CHECKING` imports. Resolve a cycle by extracting the leaf shape both sides need.

## Design rules

- The model proposes typed data; deterministic Python decides every outcome. The model mutates no state.
- State evolves through transactions: copy the committed state, let mechanics mutate the copy, revalidate the whole copy once at the end. A failed transaction never replaces the committed state, and committed state is never mutated again.
- A frozen model's own fields cannot be reassigned, but its contents can still be mutable. Copy into a value whatever the same transaction goes on to mutate.
- Core owns commits and topology. An engine owns typed mechanics and mutates the draft through the operations core exposes.
- One engine is chosen at launch and seen through one flat protocol. Core never names a concrete engine outside the few declaration sites the type unions require.
- An engine's state and its authored data are typed unions discriminated on a tag they persist, never JSON envelopes. A payload from the wrong engine should be unrepresentable; where the shape allows it, a validator must reject it rather than let it through.
- Engines are independent: neither imports the other, and neither imports the UI. Core imports no UI.
- A turn's facts and directions are one persisted union discriminated on the tag naming their origin, so a reloaded trace never guesses which engine wrote a line.
- Content is authored once per scenario and per character, with one overlay per engine keyed off the authored ids. An overlay's presence is the compatibility check. Authored ids are the ids; only entities the model creates get a derived one.
- A save names its own origin and its own format version. That version is the only compatibility gate: refuse a stale save rather than converting it.
- A trace entry records what occurred, never the resulting state.
- Derived content is generated once by a script, loaded once, and shared frozen. Only runtime state is mutable. Regenerating it bumps the save format version.
- One composition root, built once. Below it collaborators and paths are explicit; no globals.
- Each role has one narrow job and one prompt. A proposal is resolved by the selected engine, never by another prompt.
- One centralized policy decides what each role may see, from one projection of the state. No per-role DTOs.
- Only the narrating role writes player-facing prose, and it never sees unrevealed canon: its input type must have no field a leak could travel through.
- Every role sees engine state through engine-owned presentation. Core owns which entities a role may see.
- The narrating role receives exact state for visible entities and translates mechanics into fiction instead of reciting stat blocks.

## Framework rules

- Use Pydantic V2 APIs only. Validation runs at the transaction boundary, not per field change; `model_copy(update=...)` does not validate.
- Pydantic AI roles return validated structured output. Per-turn validators request retries and never mutate state.
- NiceGUI reflects session state only. Keep domain logic out of the UI package and update refreshable views.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in one config module.

## Verification

- Test core behavior and integrity boundaries, not exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent; never require network access.

Change this file only for a rule expected to hold across every future phase. A rule that a refactor
can falsify does not belong here.
