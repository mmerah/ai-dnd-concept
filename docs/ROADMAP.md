# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose. PLAN.md holds the phased next work, IDEAS.md the loose ends. This file is the standing list of what is weak about the build as it stands.

## Invariants worth preserving

- The model proposes, Python decides. Resolvers run against a draft; only a revalidated commit replaces state.
- Every turn commits whole or not at all; a role failure leaves committed state untouched.
- The Narrator writes the only player-facing prose. The Director reads the whole canon side; the Narrator's input type carries no field unrevealed canon could travel through.
- One structured plan from the Director, resolved by engine code.
- Content is data; procedures are Python. Nothing parses rules prose at run time, and what the model reads is rendered from the same values the resolver reads, so the two cannot drift.

## Known weaknesses

### Reliability

- Nothing checks narration against facts. The Worldkeeper only adds canon, so a turn that narrates a consequence the state never recorded commits looking healthy.

### Canon quality

- Growth can only create, never deepen. `WorldkeeperReport` carries creations and nothing else, so an entity the story develops gets no update.
- A relation carries tags and nothing else — no note, no state of its own — so a connection can be locked but not described.
- Core interprets exactly two relation kinds and one tag (`connected`, `party-member`, `locked`). Any other kind a role writes is inert state that only a prompt reads.
- A hook is one-shot by default (`once`), and `fired_hooks` records only that it fired, never how often, so a hook cannot fire a second time with a different consequence and a repeatable one has no bound. Chaining itself works: hooks fire in bounded rounds within a turn (`MAX_HOOK_ROUNDS` in `state/hooks.py`) and react to subsystem changes as well as turns.

### Structure and scale

- History is the last 6 exchanges, verbatim. No summarisation, no retrieval, no memory beyond the window; a long game silently forgets its own middle.
- No undo. A save is a single current state, not a history of commits.
- Three sequential role calls per turn — Director, Narrator, Worldkeeper — with no streaming.
- The trace file grows unbounded and the session loads every entry on resume.
- The State tab is a raw JSON dump of the game state.

## Direction

- pre-commit configuration (format, check, type safety, tests).
- A narration-against-facts check, retrying the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.
- UI growth: character sheet, journal, known-world panel.

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
