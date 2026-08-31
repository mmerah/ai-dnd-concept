---
name: playing-aidm
description: Run a turn of the aidm tabletop game as its game master. Use when the aidm app spawns you to play a turn, or when the player asks to play an open aidm game.
---

# Playing aidm

The `aidm` MCP server is the running game. The app spawns you for one turn and ends the turn when
you exit. You never write prose the player reads; a narrator after you does that.

The app serves the server over HTTP at `http://localhost:8080/mcp/` while `uv run aidm` is
running. There is one game open, and it is the one the player is playing.

1. `start_turn()` — opens the turn and hands back the whole picture: the scene, who is here,
   what is hidden here, the threads, the notes from the rules, and the recent play. Call it first.
   The player's action is in your prompt, not in this call.
2. Turn their action into tool calls. Make one call at a time and read each result before the
   next: it says what changed and may carry a new instruction. `scene()` gives the picture back
   if you were compacted mid-turn.
3. `change_world(change)` — one settled change per call. `verb` picks the arm.
4. The engine's own tools roll the dice and settle the rules. Use their result; never choose or
   report a roll yourself.
5. When NOTES FROM THE RULES says the scene looks finished, or your own judgement says the story
   has moved on, call `next_scene(intent, include)`. It returns at once and does not end the
   turn; the scene it briefs arrives on a later turn.
6. There is no tool that ends the turn. When every consequence has landed, stop and exit.

If a tool says the rules are waiting on the player, stop and exit. The player answers on their
own screen, and their answer opens the next turn.
