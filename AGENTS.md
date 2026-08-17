# Repository guidance

## Working with the maintainer

The maintainer has ADHD. Load the `i-have-adhd` skill at the start of every session and shape all output according to it: lead with the next action, number multi-step work, restate progress each turn, no preamble or closing pleasantries.

## Commands

Run from the repository root:

Never set `UV_CACHE_DIR` when running the verification suite; it causes the suite to break.

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
- A capability the plan commits to is built in its real form; never ship an interim stand-in
  whose replacement is already scheduled. YAGNI applies to features nobody decided on, not to
  decided ones.
- Introduce a port only once a second implementation exists. A protocol that decouples core from a concrete choice earns its place on the first one.
- Use descriptive names before adding prose to explain code.
- Keep functions below 100 lines and files below 1000 lines.
- Comments explain only a non-obvious why: a constraint, tradeoff, invariant, or tooling exception.
- Delete comments that narrate control flow, restate a name or type, give historical counts, or serve as architectural essays.
- Keep directives such as `# pyright: ignore[...]` narrowly scoped and include rationale only when the directive is not self-explanatory.
- Omit package and module docstrings by default. Never use them as file tours.
- Omit docstrings when the signature and name are the complete contract.
- Keep necessary docstrings to one concise sentence. Use multiple lines only when losing the detail would hide an important rationale or contract.
- Treat docstrings consumed by reflection, Pydantic schemas, or LLM prompts as runtime behavior: preserve their meaning and verify changes.
- Keep package `__init__.py` files empty. Import from explicit module paths.
- Keep imports at module scope, and the import graph acyclic with no deferred or `TYPE_CHECKING` imports. Engine discovery is the one exception: core imports an engine module by name to read the engine class it declares. Resolve a cycle by extracting the leaf shape both sides need.

## Design rules

- The model proposes typed, validated output; engine code resolves it deterministically against
  the turn's draft and records facts. The model never writes state; every roll and every ledger
  change happens in resolver code, never in model output.
- State evolves through transactions: copy the committed state, mutate the copy, revalidate the whole copy once at the end. A failed transaction never replaces the committed state, and committed state is never mutated again.
- An engine owns its mechanics end to end: it declares the typed overlay authored content is validated against, refuses a state it cannot play rather than repairing one, and seeds whatever an entity created during play needs.
- Content a user may extend loads from files: user copies merge over shipped ones by name, and an unreadable one is skipped with a log line instead of taking the app down.
- Only the narrating role writes player-facing prose, and it never sees unrevealed canon: its input type must have no field a leak could travel through.
- One composition root, built once. Below it collaborators and paths are explicit; no globals.
- A save names its own origin and its own format version. That version is the only compatibility gate: refuse a stale save rather than converting it.

## Framework rules

- Use Pydantic V2 APIs only. Validation runs at the transaction boundary, not per field change; `model_copy(update=...)` does not validate.
- Pydantic AI roles return validated structured output. Tools and output validators request retries with `ModelRetry`; in the turn loop tools are read-only lookups, with one exception: an expansion tool may apply a typed, validated canon patch to the turn's disposable draft through resolver code. No tool ever writes committed state, a save, or a file; an authoring tool may apply a typed patch to its in-memory draft.
- NiceGUI reflects session state only. Keep domain logic out of the UI package and update refreshable views. A panel only renders state and submits typed decisions.
- Keep each role's model, endpoint, retries, token budget, and reasoning level in one config module.

## Verification

- Test core behavior and integrity boundaries, not exact creative prose, live model quality, or trivial wiring.
- Stub model calls with `FunctionModel` or an equivalent; never require network access.

Change this file only for a rule expected to hold across every future phase. A rule that a refactor
can falsify does not belong here.
