---
name: playing-aidm
description: Run a turn of the aidm tabletop game. Use when the player asks to play, open, or resume an aidm game, or types an in-game action while one is open.
---

# Playing aidm

The `aidm` MCP server holds the game and the rules. This skill tells you how to reach them.

Work from the repository root. The game reads and writes `saves/` under the working directory,
and the server wiring (`.mcp.json`, `.codex/config.toml`) is read from there.

1. `list_games()` — lists the saves you can resume. It also lists the scenario and character names
   that a new `<scenario>--<character>` slug is built from.
2. `open_game(slug)` — opens one game. Nothing else works until this call succeeds.
3. `rules()` — the rules for a turn under this engine. Read it once at the start. Read it again
   after a compaction.
4. The player writes their action as a chat message. `start_turn(text)` — pass their message,
   and `option_id` too when their words chose one of the options the rules are waiting on. It
   opens the turn and returns the whole state of the game.
5. Turn their message into tool calls. Make one call at a time. Read each result before you make
   the next call. `scene()` gives the picture back if you were compacted mid-turn.
6. `end_turn(lines)` — closes the turn with the prose you wrote.
7. When `NOTES FROM THE RULES` in `scene()` says an advance is owed and the player asks to grow
   their character, call `advance(subject_id, ...)` — the tool's own schema carries the engine's
   fields for the change. It refuses when none is owed.
8. The server answers WORLD GROWTH DUE when the player is nearly out of places to find. Grow the
   world before the player's next action. Spawn a subagent and tell it to run the `growing-aidm`
   skill; a subagent can reach the `aidm` server, and its long loop stays out of this
   conversation. Run that skill here only if you cannot spawn a subagent.
