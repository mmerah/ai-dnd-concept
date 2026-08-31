# AI Dungeon Master

AI Dungeon Master is a browser game for solo role-playing.

The app starts three separate AI roles:

- The game master selects rule procedures and requests world changes.
- The narrator writes the story text that the player can read.
- The worldsmith writes new scenes.

Python code controls the rules and the game state. It rolls the dice, validates requests, applies changes, and saves the game.

The app does not give save-file access to the AI roles. The narrator receives revealed information only. Hidden information cannot enter the narration.

The world is a sequence of scenes. The player can continue the current scene or move to a new scene.

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

## License

The Loner content uses CC BY-SA 4.0. The [Loner notes](docs/LONER-3E.md) give the full license
and attribution.

This project does not yet specify a license for the other code.
