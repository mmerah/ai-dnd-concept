---
name: playing-aidm
description: Run a turn of the aidm tabletop game. Use when the player asks to play, open, or resume an aidm game, or types an in-game action while one is open.
---

# Playing aidm

The `aidm` MCP server holds the game and the rules. This skill tells you how to reach them.

Work from the repository root. The game reads and writes `saves/` under the working directory,
and the server wiring (`.mcp.json`, `.codex/config.toml`) is read from there.

1. `list_games()` — lists the saves you can resume. It also lists the scenario, character and
   engine names that a new `<scenario>--<character>--<engine>` slug is built from.
2. `open_game(slug)` — opens one game. Nothing else works until this call succeeds.
3. `rules()` — the rules for a turn under this engine. Read it once at the start. Read it again
   after a compaction.
4. `scene()` — the whole state of the game. Call it at the start of every turn. You may have been
   compacted, and no other call gives you back what you knew.
5. The player writes their action as a chat message. Turn that message into tool calls. Make one
   call at a time. Read each result before you make the next call.
6. `end_turn(prompt, lines)` — closes the turn. Give the player's action and the prose you wrote.
7. `propose_advance(subject_id, proposal)` — call it when `scene()` shows an advancement on offer
   and the player asks to grow their character. Write the proposal yourself. `rules()` carries the
   advancement rules of this engine. Show the player what the proposal changes. Then call
   `apply_advance()`.
8. The server answers WORLD GROWTH DUE when the player is nearly out of places to find. Grow the
   world before the player's next action. Spawn a subagent and tell it to run the `growing-aidm`
   skill; a subagent can reach the `aidm` server, and its long loop stays out of this
   conversation. Run that skill here only if you cannot spawn a subagent.
