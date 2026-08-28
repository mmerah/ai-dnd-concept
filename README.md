# AI Dungeon Master

A narrative game platform with separated roles. A model plays the game master. Engine code resolves the mechanics in typed Python, and the app owns every state change.

## How this differs from other AI game masters

Most AI game master projects let the model decide outcomes. Dice are a script the model may or may not call. State is a markdown or JSON file the model rewrites. The model sees every secret, so it cannot keep one. Almost all of them run D&D 5e on a frontier model.

This project does the opposite:

- Code rolls every die and applies every change. The model only proposes typed tool calls.
- The narrator receives only revealed facts. Hidden canon has no path into its prompt.
- A cheap or local model is the design bar. Each engine has a small tool surface a weak model can clear.
- The rules engines are light, freely licensed SRDs (Loner, 24XX, Breathless), not 5e.

Closest neighbours: `claude-dnd-skill` (Claude Code plugin, 5e, prompt-enforced rules), Familiar and Loremaster (Foundry VTT modules, VTT rolls, model narrates), Daicer and NarrativeEngine-P (open source, code-owned rolls). None of them targets light SRDs or weak models, and none keeps secrets by construction.

## Rules engines

Two engines ship.

| Engine | Core mechanic |
|---|---|
| Loner 3e | Chance d6 against Risk d6, six outcomes, a Twist Counter, Harm against Luck |
| 24XX | one skill die of d6 to d12, +d6 for help, +d4 when hindered, take the highest |
| Breathless | one skill or item die of d4 to d12 that steps down each roll until you Catch Your Breath, three outcome bands, a loot die, stress |

`docs/LONER-3E.md`, `docs/24XX.md` and `docs/BREATHLESS.md` point at each engine's official rules and name every deviation this implementation takes; the rules text itself is not copied here. A candidate engine is a pointer file, not code: the shelf takes official, freely licensed, low-overhead systems, and a package appears only when it is next to be played.

## How a turn runs

```text
prompt → DIRECTOR → resolve → NARRATOR → commit
         tool calls  engine code  prose
```

- The Director calls one tool for each mechanic, and reads tool results before the next call.
- Engine code resolves each call on a draft: the rolls, the costs and the outcome.
- Core commits a validated state, and owns the fiction: entities, placement, threads, traits.
- The Narrator writes the prose based on the mechanical facts. It receives no unrevealed canon in
  builtin mode; code mode holds this by prompt.

## Run

```bash
uv sync
uv run aidm     # http://localhost:8080
```

Set `PROVIDERS__OPENROUTER__API_KEY` in `.env`. Code mode needs no key. Every `.env` key except the four directory paths is editable at `/settings` in the app, and a change applies as soon as it is saved.

- The home page lists the saves, and starts a new game from a scenario and a character; the scenario names its engine.
- Content packs load from `packs/<engine>/*.json`. A user pack replaces a shipped pack of the same name, and `PACKS_DIR` moves the directory.
- Scene illustrations are off. `MEDIA__ENABLED=true` turns them on, `MEDIA__MODEL` picks the model. An image is generated after a turn commits, and only when the scene has changed.

## Two modes

Both modes use the same engines, state and saves. `HARNESS` in `.env` selects one.

In **builtin mode**, the default, the browser is the game. The Director and the Narrator run on the models named in `.env`, or on your own machine through the `local` provider.

In **code mode** one coding agent plays the Director, the Narrator and the scenario creator over an MCP server. With a subscription, only scene illustrations would need an API key and billing.

| `HARNESS` | Who plays the turn | The browser |
|---|---|---|
| `builtin` | the app's own roles | plays |
| `external` | a CLI you start yourself | follows the save (read-only) |
| `claude` | Claude Code, in this process | plays |
| `codex` | `codex exec`, one process per turn | plays |
| `opencode` | `opencode run`, one process per turn | plays |
| `pi` | `pi -p`, one process per turn | plays |

```bash
echo "HARNESS=external" >> .env   # you start the agent
claude                            # approve the aidm server once, then say "play"
uv run aidm                       # read-only window; open_game answers with its link

echo "HARNESS=claude" >> .env     # the app starts the agent
uv run aidm                       # type the action; the dev tab logs the tool calls
```

`claude` runs the MCP server in this process, on the app's own `Runtime`: one writer, and a turn appears as the agent commits it. The other three run their server in a second process, so the page reads each turn back off the save file. They are slower and cost more per turn.

### What each harness needs

Nothing is installed. Every config file is in the repository, and `.claude/skills` symlinks into `.agents/skills`, so both trees carry the `aidm` skills.

| Harness | Config file | Skills |
|---|---|---|
| `claude` | none | `.claude/skills` |
| `external` | `.mcp.json` | `.claude/skills` |
| `codex` | `.codex/config.toml` + trust the project | `.agents/skills` |
| `opencode` | `opencode.json` | `.agents/skills` |
| `pi` | `.mcp.json` (`pi-mcp-adapter` extension) | `.agents/skills` |

`codex` runs with `--approve-for-me`, because `codex exec` cancels every MCP call under its default `never` policy ([codex#24135](https://github.com/openai/codex/issues/24135)). `pi` ships no MCP client, so the extension proxies every tool behind one `mcp` tool.

Code mode gives up two things:

- The hidden-canon boundary for narration is only a prompt rule, not enforced.
- The model half has no offline test. `tests/core/test_code_mode.py` drives the MCP handlers as plain functions.

Characters and scenarios are still made in the browser, and the scenario page asks the agent when `HARNESS` names one. Under `external` it sends you to `begin_scenario()` in the terminal.

## Worlds that grow

A scenario written with `grows` keeps writing itself: when the player is nearly out of places to find, new locations, exits and threads are added. Builtin mode does this after the turn, on the scenario creator role. Code mode reports that growth is due, and the agent runs the `growing-aidm` skill in a subagent (ideally), so the play conversation pays nothing.

## Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

## Layout

One distribution. `tests/core/test_package_boundary.py` enforces the import direction:

```text
state ← content ← engines ← turn ← authoring ← app ← harness ← ui
```

`aidm/config.py` is a leaf that every layer may read. An engine never imports another engine, and only `ui` imports NiceGUI.

The **dev** tab holds **trace** (the plan, the resolved facts and each role's exact prompt), **state**, and the **agent** log when the app launched an agent.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `docs/ROADMAP.md`: known weaknesses and direction.
- `IDEAS.md`: loose ends and the idea backlog.

## Licensing

| Files | License | Attribution |
|---|---|---|
| `src/aidm/engines/loner3e/` prose, instructions and packs | CC BY-SA 4.0 | Roberto Bisceglie / Zotiquest Games, <https://lonersrd.zotiquestgames.com> |
| `src/aidm/engines/twentyfourxx/` prose, instructions and pack | CC BY 4.0 | Jason Tocci, <https://24xx-srd.carrd.co> |
| `src/aidm/engines/breathless/` prose, instructions and pack | ORC License | Fari RPGs, René-Pier Deshaies-Gélinas, <https://farirpgs.itch.io/breathless-srd> |

Each `docs/<game>.md` pointer file carries its game's sources, license and required attribution.

`packs/ap01-fantasy.json` comes from the Loner SRD site's AP01 Fantasy page. That page carries no CC declaration at all — only the site-wide footer "© 2021-2026 Roberto Bisceglie" — while the site index declares CC BY-SA 4.0. It is treated as covered by the site's license. One email to the publisher would settle it.

The license of the rest of the code is an open decision.
