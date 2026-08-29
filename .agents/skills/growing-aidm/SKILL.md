---
name: growing-aidm
description: Extend the world of an open aidm game with new places to find. Use when the aidm server reports WORLD GROWTH DUE, or the player asks for more world.
---

# Growing an aidm world

The `aidm` MCP server holds the game and the draft. This loop writes canon that the player has
not found yet. Nothing you write can be narrated until `finish_growth` lands it.

If the `aidm` tools are not loaded in this conversation, load them first. A new agent sometimes
starts without them, and then the first call fails.

1. `begin_growth()` — returns the briefing: the bar this pass must meet, the premise or source,
   engine-specific rules, selected pack content, and a worked example.
2. Follow the briefing's engine guidance for which new entities need `rules`. Use selected-pack
   vocabulary where the engine requires it; some engines explicitly allow freeform tags.
3. `write(patch)` and `connect(from_id, to_id)` — add locations, actors, items and threads.
   Connect at least one new location to a place the player already knows of. Every answer ends
   with what the draft still needs.
4. `scenario_so_far()` — the whole draft as JSON. Call it whenever you lose track of the draft.
   The server holds the draft, so a compaction costs you nothing.
5. `finish_growth()` — checks the draft, then makes it canon the player can discover. A
   draft under the bar comes back with the reason, and the run stays open. Fix the draft and call
   `finish_growth` again.

Write ids of your own. The live game holds more than `scenario_so_far` shows you. `finish_growth`
refuses an id the game has already taken; rename it and call `finish_growth` again.
