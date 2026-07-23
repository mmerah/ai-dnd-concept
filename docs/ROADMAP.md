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

- The Actor drops consequences. It reads the Director's prose and must call a tool per outcome. Measured: item consequence 2/2, NPC reveal 1/2. Or for example I see things like "discover_entity called." but no tool was called.
- A dropped consequence is silent. The Maintainer only grows canon; nothing checks narration against events. The Narrator then describes something the state never recorded, and the turn commits looking healthy.
- The Actor occasionally emits a tool call as message text (`{"name":"discover_entity",...}`) instead of a real call, so the tool never runs. Intermittent, provider-side; 4/4 correct on default OpenRouter routing when measured.
- `finish_reason: "error"` from Groq when a structured role answers in prose under `tool_choice: required`. Worked around with `NativeOutput` (provider-enforced JSON schema) on Director, Maintainer and Creator. Worth re-checking if the model or routing changes.

### Canon quality

- The Maintainer grows eagerly. Passing mentions become entities — "the Whispering Vault", "the bell tower", "cracked vellum" all got created from scenery in narration.
- Growth can only create, never deepen. An existing entity that the story develops gets no update; the Maintainer's only verb is "add".
- The Creator can duplicate a name. `slug` dedupes the id (`elgin_2`), which hides the duplicate rather than preventing it.
- Locations and inventory are free strings. `move_to("the crypt")` invents a place that no entity backs; only items are canonicalised against the catalogue.

### Structure and scale

- Conversation history: The history should be passed/constructed as intended by agentic workflows. The "Recent Play" context section would disappear. And player becomes a user message and DM (narration) becomes an assistant message. That history can be passed straight up to director/actor/narrator/maintainer. Maybe actor does not need it, for sure creator doesn't. Maybe configurable in same way the context is
- Character is welded to the scenario file. A scenario file *is* a starting `GameState`, which is convenient now and blocks reusing a character across scenarios.
- History is the last 6 exchanges, verbatim. No summarisation, no retrieval; a long game silently forgets its own middle.
- One hardcoded save slug and scenario, one module-level session, no scenario picker.
- No undo. The save is a single current state, not a history of commits.
- Five sequential model calls per turn, no streaming. The player waits on the whole pipeline.
- The trace file grows unbounded and the trace panel only shows turns from this process.
- Hardcoding the instructions is a maintainability issue, especially for giving tool lists. Each tool should have a concise guidance of how to use it and for what with examples, right in where it is defined. Then the instructions for each agent that use each tool can be made modular or generated depending on which tools the agent use. Maybe the list of tool the agent use is also made explicit. The model, the token budget, the reasoning level, ... all are things that should be configurable, modular and thus make all of this less of a maintainability issue

## Direction

### Next, and highest value

- Typed consequences on `Direction` (e.g. explicit success/failure effects) so the Actor stops re-parsing prose. Most likely fix for the weakest link. An alternative to discuss would be making the `Actor` have multiple passes.
- Maintainer validation pass: check narration against events, retry the Narrator once on a contradiction. Turns silent desync into a visible, correctable failure.
- A small eval harness over recorded turns, so reliability is measured rather than recalled.

### Planned features

- Locations are connected, they have a state.
- NPC should be their own entities with their own location.
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
