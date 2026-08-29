# Memory system

Deleted in Phase 1 of PLAN.md. This records what went, why, and the shape a re-implementation
should take.

## What was deleted

The `Memory` model in `state/world.py`, `WorldState.memories`, and the memory-owner invariant
check that went with it. The scenario model's `memories` in authored content, and the `"memories"` arrays
in the two shipped scenarios. The Worldkeeper role entire: `worldkeeper_agent`, `WorldkeeperReport`,
`MemoryProposal`, `render_worldkeeper`, `prompts/worldkeeper.md`, and its turn step. `Settings.max_memories`
and `Settings.history_window`. A turn now runs Director -> Narrator, and the conversation window is
unbounded:
`history = exchanges_to_messages(state.history)`.

Two player-facing surfaces went with it and are recorded nowhere else: `JournalView.memories` and
the journal panel's "What is remembered" block. A re-implementation has to put both back.

## Why

A memory was 0-2 sentences per turn (`max_memories` capped it at two) bought with a whole model
round-trip. The conversation window already carries the same continuity, so the round-trip paid
for something the turn had for free. Making the window unbounded gets the continuity without the
extra role; the turn got faster and lost a role.

## What a re-implementation looks like

The signal to start is now explicit rather than a hunch: `RoleConfig.max_input_tokens` caps each
role's estimated input, and `run_segment` refuses a segment that exceeds it before calling the
model. When players start hitting that ceiling, memory comes back — not as a role guessing what to keep
every turn, but as a durable fact per entity, deduped on text so the same
fact is never written twice. It is written by a role that runs *after* narration, so it records
what actually happened rather than what a plan predicted. It is shown only to roles that may see
canon — the Director and anything else that resolves mechanics — and never the Narrator:
the Narrator's input type must carry no field an unrevealed fact could travel through (in builtin
mode; code mode holds this by prompt), the same rule that already keeps hidden entities out of its
prompt. The old shape is worth copying almost
whole: `owner: EntityId | None` for the world itself or one entity, `text` as one concrete
sentence, kept behind a casefolded dedupe set. What should change is the trigger — write on
retrieval failure or window pressure, not unconditionally every turn — so the round-trip is paid
only when the window actually needs help.
