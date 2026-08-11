# Weaknesses and direction

Status of the proof of concept, and where it should go. Kept short on purpose. PLAN.md holds the
phased next work, IDEAS.md the loose ends. This file is the standing list of what is weak about
the build as it stands.

## Invariants worth preserving

- The model proposes, Python decides. Resolvers run against a draft; only a revalidated commit
  replaces state.
- Every turn commits whole or not at all; a role failure leaves committed state untouched.
- The Narrator writes the only player-facing prose, and its input type `VisibleScene` has no field
  unrevealed canon could travel through. Hidden canon reaches the Scene Director alone; the Rules
  Director sees only what the directive passed on.
- Context comes from `SceneSnapshot` and `VisibleScene` in `src/aidm/turn/prompts.py`, not
  scattered f-strings.
- One structured plan from the Rules Director, resolved by engine code. The single role tool is
  `read_content`, a read-only lookup.
- Content is data; procedures are Python. A pack ships `Record`s whose `facts` map carries every
  normalized mechanical value, and the engine spec declares which facts a collection must hold;
  nothing parses rules prose at run time. What the model reads is rendered from the same facts the
  resolver reads, so the two cannot drift.

## Known weaknesses

### Reliability

- The Director drops the state write the fiction implies: the narration lands, the tag or counter
  change that had to accompany it does not. The measured shape, across the 2026-08-07 suites:
  `advantage-attack` never once fired (0/15 — nothing anywhere teaches when 5e grants advantage, so
  decide whether `dnd5e/director.md` teaches it or the case measures an untaught rule);
  `condition-rider` and `condition-lifted` regress and recover without anything touching them (a
  success branch that narrates the rat going down without the `prone` tag; `poisoned` surviving the
  turn that should end it); `long-rest-recharge` swings between 0% and 67%. The one prompt lever
  proven to work: `CORE_DIRECTOR`'s reveal-then-move clause took `movement-follows-exits` to 100%,
  and it has only ever been pulled for movement. The prompt pass over these is a PLAN.md phase,
  scheduled right after its simplification phases land.
- Nothing checks narration against facts. The Worldkeeper only adds canon, so a turn that narrates
  a consequence the state never recorded commits looking healthy.
- Those measurements predate the last three phases. Live eval gates are suspended by maintainer
  decision (2026-08-11) until the codebase settles; golden fixtures and offline oracle parity are
  the whole safety net meanwhile. At 3 runs per case the noise floor is large: nothing below n=9
  should be attributed to a change.
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

- Spell preparation is unmodelled: a caster's whole known list stays castable — an over-permission
  at the class boundary rather than an invented limit. Concentration is a sheet note the resolver
  writes; temporary HP has no state, so a spell's duration is description-guided.
- History is the last 6 exchanges, verbatim. No summarisation, no retrieval, no memory beyond the
  window; a long game silently forgets its own middle.
- No undo. A save is a single current state, not a history of commits.
- Four sequential role calls per turn — Scene Director, Rules Director, Narrator, Worldkeeper —
  with no streaming.
- The trace file grows unbounded and the session loads every entry on resume.
- The State tab is a raw JSON dump of the game state.

## Direction

Near work is PLAN.md's, in its order: the simplification phases (engine-owned plan lifecycle,
one explicit `run_turn`, the merged effect vocabulary, collapsed initialization), then the prompt
pass on the dropped state write and the keepers. What no phase owns:

- pre-commit configuration (format, check, type safety, tests).
- A narration-against-facts check, retrying the Narrator once on a contradiction. Turns silent
  desync into a visible, correctable failure.
- Token-efficient rendering. An entity render resolves every ref it holds inline, so a 5e caster
  costs more tokens than a Story character — legitimately, since the arithmetic lives in that
  detail. Two ways to spend it better: render compactly where the shape allows it, and make the
  render prompt-aware, expanding a spell or a feature in full only when the turn's prompt reaches
  for it. Measure it against the eval suite, not by eye.
- UI growth: character sheet, journal, known-world panel.

### Deliberately not doing

- Multiplayer.
- Save migrations (version and fail loudly instead).
- A database, workflow graph or message bus.
- Configurable pipeline order — the fixed sequence is the thesis. The scene/rules split ships
  unconditionally now that its A/B is settled; the toggle it was measured behind is gone.
