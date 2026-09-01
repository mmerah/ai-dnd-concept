# AI Dungeon Master

AI Dungeon Master is a browser game for solo role-playing.

The app starts three separate AI roles:

- The game master selects rule procedures and requests world changes.
- The narrator writes the story text that the player can read.
- The worldsmith writes the opening world and makes the world grow in play.

Python code controls the rules and the game state. It rolls the dice, validates requests, applies changes, and saves the game.

The app does not give save-file access to the AI roles. The narrator receives revealed information only. Hidden information cannot enter the narration.

Two engines ship from one build, and they play nothing alike. Loner 3e is a solo game in scenes. An oracle answers questions. The player writes the way to the next scene. Tunnel Goons is a dungeon crawl on an authored map. The game master runs it. The player walks, fights and rests. The map grows when it runs out.

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

## Project information

- Read [VISION.md](VISION.md) for product goals and main design decisions.
- Read [CLAUDE.md](CLAUDE.md) for development rules and checks.
- Read [docs/LONER-3E.md](docs/LONER-3E.md) for sources, license, attribution, and implementation differences.
- Read [docs/TUNNEL-GOONS.md](docs/TUNNEL-GOONS.md) for sources, license, attribution, and implementation differences.

## License

The Loner content uses CC BY-SA 4.0. The [Loner notes](docs/LONER-3E.md) give the full license
and attribution.

Tunnel Goons is © Nate Treme, released under a Creative Commons 4.0 International License. The
[Tunnel Goons notes](docs/TUNNEL-GOONS.md) give the attribution.

This project does not yet specify a license for the other code.
