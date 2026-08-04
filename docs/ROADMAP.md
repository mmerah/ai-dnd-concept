# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose.

## Invariants worth preserving

- The model proposes, Python decides. Engines resolve against a draft; only a revalidated commit
  replaces state.
- The Narrator is the one role kept from unrevealed canon, because it alone writes to the player.
- Every turn commits whole or not at all; a role failure leaves state untouched.
- Context comes from `SceneSnapshot` and the Narrator-only `VisibleScene` in
  `src/aidm/workflow/prompts.py`, not scattered f-strings.
- Small output schemas and few tools per role.

## Known weaknesses

### Reliability

- A dropped consequence is silent. The Maintainer only grows canon; nothing checks narration against facts. The Narrator then describes something the state never recorded, and the turn commits looking healthy.
- `finish_reason: "error"` from Groq when a structured role answers in prose under `tool_choice: required`. Worked around with `NativeOutput` (provider-enforced JSON schema) on Director, Maintainer and Creator. Worth re-checking if the model or routing changes.

### Canon quality

- The Maintainer grows eagerly. Passing mentions become entities — "the Whispering Vault", "the bell tower", "cracked vellum" all got created from scenery in narration.
- Growth can only create, never deepen. An existing entity that the story develops gets no update; the Maintainer's only verb is "add".
- Locations and inventory are typed canon, but locations do not yet form a traversable graph with exits or travel constraints.

### Structure and scale

- Spell preparation is unmodelled. `cast` spends a slot and resolves attack rolls, saves, damage and healing; a known caster's repertoire is chosen at level-up from the pack's cumulative `spells_known`. A prepared caster has no per-rest decision channel, so their whole class list stays castable — an over-permission at the class boundary rather than an invented limit. Concentration and temporary HP have no state either, so a spell's duration is description-guided.
- History is the last 6 exchanges, verbatim. No summarisation, no retrieval; a long game silently forgets its own middle.
- No undo. The save is a single current state, not a history of commits.
- Four sequential role calls per ordinary turn, plus one Creator call per accepted growth request, with no streaming.
- The trace file grows unbounded and the trace panel loads the entire history on resume.
- Per-role model, budget, reasoning, and retries are configurable. Engine-specific Director instructions remain owned by each rules package.

## Direction

### Next, and highest value

- pre-commit configuration (format, check, type safety, tests)
- Maintainer validation pass: check narration against facts, retry the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.
- A small eval harness over recorded turns, so reliability is measured rather than recalled.

### Planned features

- Locations are connected, they have a state.
- Continue 5e mechanics inside `aidm/plugins/dnd5e/` without widening core state.
- Expand Story consequences only where narrative play demonstrates a concrete need.
- Character creator, decoupling the character from the scenario file.
- AI scenario creator — from a premise, or ingested from a PDF.
- More roles and per-role tools; the context projections and `Role` literal already scale to this.
- Image and voice generation for flavour, behind an interface, never on the turn's critical path.
- UI growth: character sheet, journal, known-world panel.
- Memory system

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
- Configurable pipeline order — the fixed sequence is the thesis.
