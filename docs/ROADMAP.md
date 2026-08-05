# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose.

## Invariants worth preserving

- The model proposes, Python decides. Engines resolve against a draft; only a revalidated commit
  replaces state.
- The Narrator is the one role kept from unrevealed canon, because it alone writes to the player.
- Every turn commits whole or not at all; a role failure leaves state untouched.
- Context comes from `SceneSnapshot` and the Narrator-only `VisibleScene` in
  `src/aidm/workflow/prompts.py`, not scattered f-strings.
- One structured plan from the Director, resolved by engine code; the only role tool left is the
  read-only rules lookup.

## Known weaknesses

### Reliability

- A dropped consequence is silent. The Maintainer only grows canon; nothing checks narration against facts. The Narrator then describes something the state never recorded, and the turn commits looking healthy.
- `finish_reason: "error"` from Groq when a structured role answers in prose under `tool_choice: required`. The Director is back on tool output regardless: under `NativeOutput` gpt-oss-120b never emitted a single plan effect (Phase 8 in `baseline.md`), and the Groq crash costs ~12% of eval turns where the empty plans cost every conditions case. Maintainer and Creator stay on `NativeOutput`, which their small schemas handle. Excluding the failing provider via OpenRouter routing preferences would recover the deaths.

### Canon quality

- The Maintainer grows eagerly. Passing mentions become entities — "the Whispering Vault", "the bell tower", "cracked vellum" all got created from scenery in narration.
- Growth can only create, never deepen. An existing entity that the story develops gets no update; the Maintainer's only verb is "add".
- Locations and inventory are typed canon, but locations do not yet form a traversable graph with exits or travel constraints.

### Structure and scale

- Spell preparation is unmodelled: a caster's whole known list stays castable — an over-permission at the class boundary rather than an invented limit. Concentration is a sheet note the resolver writes; temporary HP has no state, so a spell's duration is description-guided.
- History is the last 6 exchanges, verbatim. No summarisation, no retrieval; a long game silently forgets its own middle.
- No undo. The save is a single current state, not a history of commits.
- Three sequential role calls per ordinary turn (Director, Narrator, Maintainer), plus one Creator call per accepted growth request, with no streaming.
- The trace file grows unbounded and the trace panel loads the entire history on resume.
- Per-role model, budget, reasoning, and retries are configurable. Engine-specific Director instructions remain owned by each rules package.

## Direction

### Next, and highest value

- pre-commit configuration (format, check, type safety, tests)
- Maintainer validation pass: check narration against facts, retry the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.

### Planned features

- Locations are connected, they have a state.
- Deepen 5e play where the lenient shape is still thin: prepared casting, equipment state beyond
  armour, temporary HP.
- Expand Story consequences only where narrative play demonstrates a concrete need.
- Character creator, decoupling the character from the scenario file.
- AI scenario creator — from a premise, or ingested from a PDF.
- More roles and per-role tools; the context projections and `Role` literal already scale to this.
- Token-efficient rendering. An entity render resolves every ref it holds inline, so a 5e caster
  costs more tokens than a Story character — legitimately, since the arithmetic lives in that
  detail. Two ways to spend it better: render compactly where the shape allows it, and make the
  render prompt-aware, expanding a spell or a feature in full only when the turn's prompt reaches
  for it and leaving the rest as a name. Measure it against the eval suite, not by eye.
- Image and voice generation for flavour, behind an interface, never on the turn's critical path.
- UI growth: character sheet, journal, known-world panel.
- Memory system

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
- Configurable pipeline order — the fixed sequence is the thesis.
