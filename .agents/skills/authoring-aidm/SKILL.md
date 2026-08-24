---
name: authoring-aidm
description: Write a new aidm scenario from a premise or a source document. Use when the user asks to create, author or write an aidm scenario or adventure.
---

# Authoring an aidm scenario

Use a conversation of its own for this loop. It is long, and the user steers it between passes.
No game has to be open.

Work from the repository root. Scenarios are written to `scenarios/` under the working directory.

1. Ask the user for the premise, or for the path to a .md, .txt or .pdf adventure to author from.
   Ask which rules engines the scenario must play under. Ask whether the scenario `grows`. A
   scenario that grows needs only an opening slice, because play writes the rest of its world.
2. `begin_scenario(slug, premise, engines, grows, source)` — returns the briefing: the bar the
   draft must meet and a worked example.
3. `write(patch)` and `connect(from_id, to_id)` — build the world in passes. Every answer ends
   with what the draft still needs. Show the user each pass and follow their steering.
4. `scenario_so_far()` — the whole draft as JSON. Call it whenever you lose track of the draft.
5. `finish_scenario(summary)` — checks the draft and writes it to disk. A draft under the bar
   comes back with the reason, and the run stays open.
