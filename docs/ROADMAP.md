# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose. IDEAS.md holds the loose ends. This file is the standing list of what is weak about the build as it stands.

## Invariants worth preserving

- The model proposes, Python decides. Resolvers run against a draft; only a revalidated commit replaces state.
- Every turn commits whole or not at all; a role failure leaves committed state untouched.
- The Narrator writes the only player-facing prose. The Director reads the whole canon side; the Narrator's input type carries no field unrevealed canon could travel through.
- One structured plan from the Director, resolved by engine code.
- Content is data; procedures are Python. Nothing parses rules prose at run time, and what the model reads is rendered from the same values the resolver reads, so the two cannot drift.

## Known weaknesses

### Reliability

- Nothing checks narration against facts. A turn that narrates a consequence the state never recorded commits looking healthy.
- A hidden entity's `when reached` text is visible to the Director every turn, so it may advance a thread before the player reaches it, guarded only by prose in `director.md`.

### Canon quality

- Growth can only create, never deepen. Nothing in a turn updates an entity the story develops.
- An exit carries `known` and `locked` and nothing else — no note, no state of its own — so a way can be locked but not described.

### Structure and scale

- History is the whole game, sent verbatim. No summarisation, no retrieval; a long game sends its entire history every turn.
- No undo. A save is a single current state, not a history of commits.
- Three sequential role calls per turn — Interpreter, Director, Narrator — with no streaming.
- The turn trace lives only in memory: a resume shows an empty Trace tab.
- The State tab is a raw JSON dump of the game state.

## Direction

- The memory system is deliberately gone. It returns per `docs/MEMORY-SYSTEM.md` once the conversation window stops carrying continuity on its own.
- pre-commit configuration (format, check, type safety, tests).
- A narration-against-facts check, retrying the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.
- UI growth: character sheet, journal, known-world panel.

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
