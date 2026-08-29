---
name: authoring-aidm
description: Write a new aidm scenario from a premise or a source document. Use when the user asks to create, author or write an aidm scenario or adventure.
---

# Authoring an aidm scenario

Use a conversation of its own for this loop. It is long, and the user steers it between passes.
No game has to be open.

Work from the repository root. Scenarios are written to `scenarios/` under the working directory.

1. Ask the user for the premise, or for the path to a .md, .txt or .pdf adventure to author from.
   Ask which rules engine the scenario plays under. Ask whether the scenario `grows`. A
   scenario that grows needs only an opening slice, because play writes the rest of its world.
2. `begin_scenario(slug, premise, engine, grows, packs, source)` — returns the briefing: the bar
   the draft must meet, engine-specific rules, selected pack content, and a worked example.
   `packs` defaults to `srd`; always include it and add only installed pack ids the scenario uses.
3. Follow the briefing's engine guidance for which entities need `rules`. Use selected-pack
   vocabulary where the engine requires it; some engines explicitly allow freeform tags.
4. `write(patch)` and `connect(from_id, to_id)` — build the world in passes. Every answer ends
   with what the draft still needs. Show the user each pass and follow their steering.
5. `scenario_so_far()` — the whole draft as JSON. Call it whenever you lose track of the draft.
6. `finish_scenario()` — checks the draft and writes it to disk. A draft under the bar
   comes back with the reason, and the run stays open.
