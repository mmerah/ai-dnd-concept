# AI Dungeon Master

A narrative game you play in a browser. Its three roles — game master, narrator and worldsmith — are one-shot CLI sessions the app spawns, so play costs a coding subscription you already have. Engine code resolves the mechanics in typed Python, and the app owns every state change.

The world is a sequence of scenes. When a scene is spent, the worldsmith writes the next one.

## How this differs from other AI game masters

Most AI game master projects let the model decide outcomes, keep state in a file the model rewrites, and show the model every secret, so it cannot keep one. Here, code rolls every die and applies every change; the model only proposes typed tool calls. The narrator's input type, `NarratorView`, carries revealed canon only, so hidden canon has no path into player-facing prose.

## Rules engines

One engine ships.

| Engine | Core mechanic |
|---|---|
| Loner 3e | Chance d6 against Risk d6, six outcomes, a Twist Counter, Harm against Luck |

`docs/LONER-3E.md` points at the official rules and names every deviation this implementation takes; the rules text itself is not copied here. 24XX and Breathless come back on this design; `docs/24XX.md` and `docs/BREATHLESS.md` are their pointer files.

## How a turn runs

```text
player types → GAME MASTER → NARRATOR → commit
                tool calls    prose
```

- The app spawns the game master and serves it the tools. It reads the whole picture, calls one tool per consequence, and writes no prose.
- Engine code rolls the dice and applies each call to the turn draft. There is no `end_turn` tool: the process exiting ends the turn.
- The app builds the narrator prompt from `NarratorView` and the told facts, spawns the narrator, then validates, records and commits.
- When `scene_spent` fires, the app starts the worldsmith on a snapshot of the committed state. The scene it writes arrives on a later turn.

## Run

```bash
uv sync
uv run aidm     # http://localhost:8080
```

- The home page lists the saves and starts a game from a scenario and a character. It also opens the new-character form and the new-scenario form, which takes a premise or an uploaded `.md`, `.txt` or `.pdf` and asks the worldsmith for an opening scene.
- The play page holds the transcript on the left, and **scene**, **journal** and **dev** tabs on the right. The dev tab shows the game master's raw output.
- `/settings` reflects over the `Settings` model, writes one `.env` key per box, and applies the change live.

Scenarios live in `scenarios/`, characters in `characters/`, saves in `saves/`.

### The roles

Each role is a command and a timeout in `.env`:

```text
ROLES__MASTER__COMMAND     = "claude -p --permission-mode bypassPermissions --tools \"\" --mcp-config .mcp.json --strict-mcp-config"
ROLES__MASTER__TIMEOUT     = 300
ROLES__NARRATOR__COMMAND   = "claude -p --tools \"\" --strict-mcp-config"   # empty reuses the master command
ROLES__NARRATOR__TIMEOUT   = 120
ROLES__WORLDSMITH__COMMAND = "claude -p --tools \"\" --strict-mcp-config"
ROLES__WORLDSMITH__TIMEOUT = 900
```

The command carries the model flag, because only the CLI knows how it names its own models. A spawn that fails or returns nothing usable is retried once, then fails its step loudly.

An uploaded adventure reaches every prompt, so the commands take the tools away: the game master keeps this repo's MCP server and nothing else, and the two roles that only write text get no tools at all. Give every role its own command when you swap the CLI.

### The tool surface

The app mounts an MCP endpoint at `/mcp` on the server it already runs, so the spawned game master reaches the live game instead of a save file. `.mcp.json` and `.codex/config.toml` both point at `http://localhost:8080/mcp/`; Codex needs the project marked trusted, because it does not read `.mcp.json`. `SERVER_PORT` in `.env` moves the server, and both files must then move with it.

| tool | purpose |
|---|---|
| `start_turn` | opens the turn and returns the whole picture |
| `scene` | the same picture again, after a compaction |
| `next_scene` | brief the worldsmith; returns at once and does not end the turn |
| `change_world` | one settled world change; `verb` picks the arm |
| `roll_question` | Loner: Chance against Risk for one dramatic question |
| `restore_luck` | Loner: restore an actor's luck after a conflict |
| `complete_chapter` | Loner: record that the adventure has ended |
| `advance` | Loner: spend an advance a party member earned |

A call that does not fit the moment is refused with what to do instead.

### Content and media

- Loner packs ship in `src/aidm/engines/loner3e/packs/*.json`. A user pack in `<PACKS_DIR>/loner3e/` replaces a shipped pack of the same name.
- Scene illustrations are off. `MEDIA__ENABLED=true` turns them on and needs `PROVIDERS__OPENROUTER__API_KEY`; that key is needed for nothing else. Two scenes in one `place` share one image.

## Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Tests run offline: `ScriptedSpawner` answers each role from a queue and records every prompt it was given, and `CliSpawner` is the only thing in the codebase that starts a process.

## Layout

One distribution. `tests/core/test_package_boundary.py` enforces the import direction:

```text
state ← kernel ← content ← kits ← engines ← turn ← app ← ui
```

`ui` sits above them all and stays engine-agnostic. Only `ui` imports NiceGUI, and only `turn`, `app` and `ui` read `aidm/config.py`. Two modules may name the concrete engine: `engines/registry.py`, which builds it, and `state/model.py`, whose save payload is a closed union over engine states.

## Docs

- `CLAUDE.md`: durable engineering and architecture rules. `AGENTS.md` symlinks to it.
- `VISION.md`: the target design and the reasoning behind it.
- `PLAN.md`: the order of work.
- `IDEAS.md`: loose ends and the idea backlog.

## Licensing

| Files | License | Attribution |
|---|---|---|
| `src/aidm/engines/loner3e/` prose, instructions and packs | CC BY-SA 4.0 | Roberto Bisceglie / Zotiquest Games, <https://lonersrd.zotiquestgames.com> |

Each `docs/<game>.md` pointer file carries its game's sources, license and required attribution.

`src/aidm/engines/loner3e/packs/ap01-fantasy.json` comes from the Loner SRD site's AP01 Fantasy page. That page carries no CC declaration at all — only the site-wide footer "© 2021-2026 Roberto Bisceglie" — while the site index declares CC BY-SA 4.0. It is treated as covered by the site's license. One email to the publisher would settle it.

The license of the rest of the code is an open decision.
