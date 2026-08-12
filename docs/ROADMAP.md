# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose. PLAN.md holds the
phased next work, IDEAS.md the loose ends. This file is the standing list of what is weak about
the build as it stands.

## Invariants worth preserving

- The model proposes, Python decides. Resolvers run against a draft; only a revalidated commit
  replaces state.
- Every turn commits whole or not at all; a role failure leaves committed state untouched.
- The Narrator writes the only player-facing prose, and its input type `VisibleScene` has no field
  unrevealed canon could travel through. Both non-narrating directors read the whole canon side;
  the Scene Director's directive steers the Rules Director without replacing that context.
- Context comes from `SceneSnapshot` and `VisibleScene` in `src/aidm/turn/prompts.py`, not
  scattered f-strings.
- One structured plan from the Rules Director, resolved by engine code. The single role tool is
  `read_content`, a read-only lookup.
- Content is data; procedures are Python. Nothing parses rules prose at run time, and what the
  model reads is rendered from the same values the resolver reads, so the two cannot drift.

## Known weaknesses

### Reliability

- Phase 5's settled baseline found no general prompt-wording fix for dropped state writes.
  Conditions and rests mostly recovered; movement improved after both directors received canon
  and the movement refusal named its remedy. Advantage remains a gpt-oss-120b limit after being
  taught in both instructions and schema. The open upstream fault is Scene Director goal
  substitution on deliberate acts; PLAN.md records the failed wording experiment so it is not
  repeated blind.
- Nothing checks narration against facts. The Worldkeeper only adds canon, so a turn that narrates
  a consequence the state never recorded commits looking healthy.
- Live evals are manual evidence, not a gate. Golden fixtures and offline oracle parity protect
  refactors; same-hour live runs measure model-facing changes. At 3 runs per case the noise floor
  is large: nothing below n=9 should be attributed to a change.
- Provider lottery, not architecture: Groq answers `finish_reason: "error"` under forced tool
  choice, which cost 12% of one suite's turns; excluding it through OpenRouter routing preferences
  recovered them, and it has still leaked through since. The Rules Director is on `ToolOutput` with
  a `TextOutput` fallback, because under `NativeOutput` gpt-oss-120b emitted no plan effects at
  all. The Scene Director and Worldkeeper stay native; their schemas are small enough.

### Canon quality

- Growth can only create, never deepen. `WorldkeeperReport` carries creations and nothing else, so
  an entity the story develops gets no update.
- A relation carries tags and nothing else — no note, no state of its own — so a connection can be
  locked but not described.
- Core interprets exactly two relation kinds and one tag (`connected`, `party-member`, `locked`).
  Any other kind a role writes is inert state that only a prompt reads.
- Hooks run one pass per turn and each fires at most once, so a hook cannot react to a fact another
  hook wrote in the same turn. Chaining is deliberately across turns.

### Structure and scale

- History is the last 6 exchanges, verbatim. No summarisation, no retrieval, no memory beyond the
  window; a long game silently forgets its own middle.
- No undo. A save is a single current state, not a history of commits.
- Four sequential role calls per turn — Scene Director, Rules Director, Narrator, Worldkeeper —
  with no streaming.
- The trace file grows unbounded and the session loads every entry on resume.
- The State tab is a raw JSON dump of the game state.

## Direction

Near work is PLAN.md's, in order: the dnd5e deletion, the Oracle engine, the scenario creator,
and media (see CONCEPT.md and DECISION.md for the reorientation). What no phase owns:

- pre-commit configuration (format, check, type safety, tests).
- A narration-against-facts check, retrying the Narrator once on a contradiction. Turns silent
  desync into a visible, correctable failure.
- UI growth: character sheet, journal, known-world panel.

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
- Configurable pipeline order — the fixed sequence is the thesis. The scene/rules split ships
  unconditionally now that its A/B is settled; the toggle it was measured behind is gone.
