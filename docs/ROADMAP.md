# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose.

## Invariants worth preserving

- The model proposes, Python decides. Tools resolve; only `apply(state, events)` produces state.
- The Narrator is the one role kept from unrevealed canon, because it alone writes to the player.
- Every turn commits whole or not at all; a role failure leaves state untouched.
- Context is a table (`agents/context.py`), not scattered f-strings.
- Small output schemas and few tools per role.

## Known weaknesses

### Reliability

- A dropped consequence is silent. The Maintainer only grows canon; nothing checks narration against events. The Narrator then describes something the state never recorded, and the turn commits looking healthy.
- `finish_reason: "error"` from Groq when a structured role answers in prose under `tool_choice: required`. Worked around with `NativeOutput` (provider-enforced JSON schema) on Director, Maintainer and Creator. Worth re-checking if the model or routing changes.

### Canon quality

- The Maintainer grows eagerly. Passing mentions become entities — "the Whispering Vault", "the bell tower", "cracked vellum" all got created from scenery in narration.
- Growth can only create, never deepen. An existing entity that the story develops gets no update; the Maintainer's only verb is "add".
- Locations and inventory are free strings. `move_to("the crypt")` invents a place that no entity backs; only items are canonicalised against the catalogue.

### Structure and scale

- Spellcasting is the last unbuilt compound procedure. `attack`, `roll_check`, `roll_save` and `apply_condition` each emit their whole chain from one typed proposal; `cast` needs spell-slot expenditure (state plus a rest mechanic) and a known-spell rule the SRD data does not carry, so it would mean inventing both. Monster spellcasting is projected and resolves; nothing casts yet.
- History is the last 6 exchanges, verbatim. No summarisation, no retrieval; a long game silently forgets its own middle.
- No scenario picker.
- No undo. The save is a single current state, not a history of commits.
- Five sequential model calls per turn, no streaming. The player waits on the whole pipeline.
- The trace file grows unbounded and the trace panel only shows turns from this process.
- Per-consequence guidance and per-role model/budget/reasoning are now modular: each consequence carries its own `GUIDANCE` assembled into the Director prompt, and `config.py` holds a per-role table. What remains is the same for the other roles' tools (only the Director's mechanics are assembled today) and a general per-agent tool-list assembly.

## Direction

### Next, and highest value

- pre-commit configuration (format, check, type safety, tests)
- Maintainer validation pass: check narration against events, retry the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.
- A small eval harness over recorded turns, so reliability is measured rather than recalled.

### Planned features

- Locations are connected, they have a state.
- D&D 5e ruleset in `engine/`, replacing the micro-ruleset. The `engine/` ← `agents/` boundary exists for this.
- Deterministic combat engine, driven by the same event/reducer model.
- Character creator, decoupling the character from the scenario file.
- AI scenario creator — from a premise, or ingested from a PDF.
- More roles and per-role tools; the context table and `Role` literal already scale to this.
- Image and voice generation for flavour, behind an interface, never on the turn's critical path.
- UI growth: scenario picker, character sheet, journal, known-world panel.
- Memory system

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
- Configurable pipeline order — the fixed sequence is the thesis.
