# AI Dungeon Master

AI Dungeon Master is a browser game for solo role-playing.

The app starts three separate AI roles:

- The game master selects rule procedures and requests world changes.
- The narrator writes the story text that the player can read.
- The worldsmith writes the opening world and makes the world grow in play, and writes the complication the game master brings down on a scene.

The narrator opens the game with who the player is and where they stand; the player acts from there.

Python code controls the rules and the game state. It rolls the dice, validates requests, applies changes, and saves the game.

The app does not give save-file access to the AI roles. The narrator receives revealed information only. Hidden information cannot enter the narration.

Four engines ship from one build, and they play nothing alike.

Loner 3e is a solo game in scenes. An oracle answers questions. The player writes the way to the next scene.

Tunnel Goons is a dungeon crawl on an authored map. The game master runs it. The player walks, fights and rests. The map grows when it runs out.

Breathless is a survival game in scenes. Every roll wears the die down. Catching breath resets the dice and brings a complication.

24XX is a science-fiction game in scenes. One skill die meets three outcome bands. Harm is a hindrance, gear breaks to soften a hit, and a finished job raises a skill.

A scenario is a premise, a scope and an opening. Scope is prose guidance on how far the adventure reaches and whether it tends toward an ending, asked for on the create page and read by the game master and the worldsmith; no mode, turn budget or ending is enforced.

The game master of a scene engine may bring a complication down on the place the player stands, asked for as an argument of `next_scene`. The ask ends the turn: every later tool call in it is answered with a wait line, and the turn narrates only what landed. The worldsmith then writes the new scene and the player reads the arrival in the same place. A failed write is filed as a failed pursuit is, and a reload never finds a pending brief.

The three roles are spawned command-line programs. The narrator and the worldsmith return typed proposals; the master plays through tools, and only Python code changes state or rolls dice. The engine seam is `Engine`, an abstract class every engine subclasses. `SceneEngine` is the base of the three scene engines. The registry is the one place that joins an engine to the app. Imports flow one way, `core <- engines <- turn <- app <- ui`, so nothing above the engines knows a world shape.

## Start the app

You need `uv` and an AI command-line program (Claude, Codex). The default settings use the `claude` command.

1. Install the project.

   ```bash
   uv sync
   ```

2. Start the app.

   ```bash
   uv run aidm
   ```

3. Open the address that the command shows.

Open Settings in the app to change the AI commands or other settings.

Characters live one file per engine, under `characters/<id>/<engine>.json`. Scenarios live under `scenarios/<id>/world.json`, the engine's starting world, with the engine's own packs as tables. Saves are strict and engine-typed, with no version field, so a stale save is invalid. A save from before a stored-shape change is stale; the launcher skips it with a warning, and nothing migrates or deletes it. Play costs the subscription the player already has; illustration and speech are the exceptions, optional, off by default, with their own provider key.

## Project information

- Read [CLAUDE.md](CLAUDE.md) for development rules and checks.
- Read [docs/LONER-3E.md](docs/LONER-3E.md) for sources, license, attribution, and implementation differences.
- Read [docs/TUNNEL-GOONS.md](docs/TUNNEL-GOONS.md) for sources, license, attribution, and implementation differences.
- Read [docs/BREATHLESS.md](docs/BREATHLESS.md) for sources, license, attribution, and implementation differences.
- Read [docs/24XX.md](docs/24XX.md) for sources, license, attribution, and implementation differences.

## License

Loner v.3.0 © 2025 Roberto Bisceglie, CC BY-SA 4.0 — attribution in the [Loner notes](docs/LONER-3E.md).

Tunnel Goons is © Nate Treme, released under a Creative Commons 4.0 International License — attribution in the [Tunnel Goons notes](docs/TUNNEL-GOONS.md).

Breathless is based on Breathless by Fari RPGs, licensed under the ORC License — full credit line in the [Breathless notes](docs/BREATHLESS.md).

24XX rules (v1.4) are CC BY Jason Tocci — attribution in the [24XX notes](docs/24XX.md).

This project does not yet specify a license for the other code.
