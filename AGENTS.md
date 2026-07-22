# Repository guidance

## Sources of truth

Read the relevant project documentation before changing behavior or architecture:

- `docs/CONCEPT.md` is the current implementation brief.
- `docs/CONCEPT_DECISIONS.md` records decisions, rejected alternatives, and rationale.

Do not duplicate changeable product or architecture details in this file. Keep those
documents current instead. If a requested change reverses a recorded decision, state
the conflict and update both documents as part of the change. Keep
`docs/CONCEPT.md` below 500 lines.

Inspect the repository before acting. Follow the code, configuration, and commands
that actually exist rather than assuming a layout or tool invocation.

## Engineering principles

- Keep the backend and frontend in Python.
- Keep the core ruleset-agnostic; isolate mechanics behind strict ruleset boundaries.
- Prefer functional programming: pure transformations, immutable values, explicit
  inputs, and side effects isolated at boundaries.
- Use strict type safety throughout. Avoid `Any`, unchecked casts, and broad type
  suppressions.
- Use strict Pydantic models at external, persistence, model, and tool boundaries.
- Fail fast on invalid data, broken invariants, and incompatible state.
- Keep code simple, readable, DRY, and KISS. Avoid speculative abstractions.
- Optimize for maintainability over cleverness or premature flexibility.
- Keep functions below 100 lines and files below 500 lines.
- Comments explain only why and are as concise as possible.
- Docstrings are as short as possible and add only non-obvious information.
- Pass dependencies explicitly. Avoid service locators and mutable module globals.
- Prefer narrow models, discriminated unions, and exhaustive matching over stringly
  typed dispatch or free-form dictionaries.
- Do not mutate authoritative shared state in place. Return validated new values.
- Do not hide failures with broad exception handling. Translate errors once at the
  relevant boundary and preserve their cause.
- A narrow type suppression requires a concise explanation of why external typing is
  wrong or incomplete.
- Prefer the standard library and existing dependencies. Add a production dependency
  only when it removes more complexity than it introduces.
- Keep third-party and provider-specific behavior behind small typed interfaces.

## State safety

- Treat persisted campaign data as user-owned.
- Validate authoritative state before use and before persistence.
- Preserve state integrity across failures; never expose or retain partial mutations.
- Never guess missing persisted values or silently coerce incompatible versions.
- Resolve exact targets before deleting, overwriting, undoing, or migrating data.
- Make recovery behavior explicit and testable.

## Testing and verification

- Keep tests minimal and focused on core behavior and integrity boundaries.
- Test pure state transitions, invariants, failure behavior, and regression-prone
  orchestration.
- Do not test exact creative prose, live model quality, or trivial wiring.
- Tests must not require network access.
- Add a regression test when fixing a core behavioral bug.
- Use the narrowest relevant check while developing, then run every applicable test,
  formatter, linter, and strict type check configured by the repository.
- If a required check is absent or cannot run, report that clearly rather than
  inventing another toolchain or claiming success.

## Review guidelines

Prioritize concrete paths to:

1. Corrupt state, partial writes, incorrect recovery, or lost user data.
2. Broken domain invariants or unvalidated external/model output.
3. Leakage of private game information into player-visible output.
4. Type-safety escapes, swallowed failures, or unbounded work.
5. Unnecessary infrastructure, abstraction, duplication, or oversized code.

Review behavior and invariants rather than prose taste. Give a specific failure
scenario for each finding and avoid speculative issues without an executable path.

## Definition of done

- Requested behavior is complete without incidental scope changes.
- External boundaries and persisted data are strictly validated.
- Relevant core tests are updated and all applicable repository checks pass.
- Documentation reflects any changed behavior or decision.
- The handoff lists changed files, checks run, and remaining limitations.

Add nested `AGENTS.md` files only for durable subtree-specific working agreements.
Update this file only when a rule is expected to remain true across project phases.
