# AI Dungeon Master

A role-separated narrative game platform. Two rules engines ship:

- **Loner 3e** — the tag-based engine: one closed question to the Oracle, Chance d6 against Risk
  d6, six outcomes, a Twist Counter, and Harm against a pool of Luck. Loner 3e rules CC BY-SA
  Roberto Bisceglie, Zotiquest Games — <https://lonersrd.zotiquestgames.com>. docs/LONER-3E.md is
  the SRD extraction, and names every deviation this implementation takes.
- **24XX** — the skill-die engine: one attempt per turn, a skill die of d6/d8/d10/d12 with an
  extra d6 for help and a d4 when hindered, take the highest, three outcomes. 24XX rules are CC
  BY Jason Tocci — <https://24xx-srd.carrd.co>. docs/24XX.md is the SRD extraction, and names
  every deviation this implementation takes.

## The engine shelf

Candidate engines are docs, not code: an exact SRD extraction per system under `docs/`, each
ending with a sketch of what its engine package would look like here. The rule for the shelf —
official, freely licensed, low mechanical overhead: a system the Directors can drive without a
rules lawyer.

`docs/LONER-3E.md` and `docs/24XX.md` are the same extraction for the two shipped engines. An
engine package appears only when it is next to be played; a skeleton package is dead code.
`docs/FATE-CONDENSED.md` is the first unimplemented shelf entry: the full CC BY 3.0 SRD, its
engine-size estimate, and the proposed Fate Condensed Core content pack.

```text
prompt → DIRECTOR → resolve → NARRATOR → commit
         tool calls  engine code  prose
```

The Director judges what the turn is about and calls a tool for every mechanic it asks for, one
at a time, reading what each call answers before the next. Engine code resolves every call
deterministically on a draft (rolls, costs, intrinsic outcomes), and core commits a fully
revalidated state. An engine is ordinary typed Python: its own strict mechanics
model, the typed overlay authored content is validated against, and action models with their
resolvers. Core owns the fiction — entities, placement, relations, threads and their clocks,
traits — and persists the engine's mechanics as one opaque payload it never reads. The Narrator
receives no unrevealed canon; for visible entities it receives the same state as the other roles,
with instructions to translate mechanics into fiction rather than recite stat blocks. This
pipeline is builtin mode's; in code mode (below) one agent plays Director and Narrator through
the same tools, and everything between them — resolution, validation, commit — is identical.

## Run

From the repository root:

```bash
uv sync
uv run aidm
```

The app opens at <http://localhost:8080>. Set `PROVIDERS__OPENROUTER__API_KEY` in `.env` — code
mode below needs no key. Content packs load from `packs/<engine>/*.json`
(`PACKS_DIR` moves that directory), and a user pack replaces a shipped one of the same name. The
home page lists saves and lets you choose a scenario — every scenario plays under every engine —
then a rules engine and a character whose overlay supports it. The game header always identifies
the active engine.

Scene illustrations are off by default. `MEDIA__ENABLED=true` in `.env` turns them on
(`MEDIA__MODEL` picks the image model). An image is generated after a turn commits, in the
background, and only when the place or its revealed cast has changed since the last one.

## Two modes

The game plays in one of two modes, over the same engines, state and saves.

**Builtin mode** (the default) — the browser is the game. The Director and Narrator run on the
provider `.env` names: the cheapest, fastest models, or fully local through the `local` provider.

```bash
uv run aidm                      # play at http://localhost:8080
```

**Code mode** — Claude Code is the game. One agent plays Director, Narrator, advisor and scenario
creator through an MCP server, so a subscription covers all four and **the provider is billed
only when media is on**. A code-mode `.env` needs no `api_key` at all.

```bash
echo "HARNESS=code" >> .env
claude                           # approve the aidm server once, then say "play"
uv run aidm                      # optional: a second, read-only window on the same save
```

`open_game` answers with the link to that window, so the player only has to click it.

Nothing is installed: `.mcp.json` and the `playing-aidm`, `growing-aidm` and `authoring-aidm`
skills are checked in. `list_games` shows the saves, and the parts a new
`<scenario>--<character>--<engine>` slug is built from. In the browser the game page follows the
save file as the server writes it, and characters are still made there; new scenarios move to the
terminal (`begin_scenario`), because that page is the only one that would need a key. Codex CLI
ignores `.mcp.json` but reads the checked-in `.codex/config.toml`: mark the project trusted and
the same server appears.

Code mode gives up two guarantees for the subscription. The Narrator's hidden-canon boundary is a
prompt rule rather than a type, and its model half has no offline test —
`tests/core/test_code_mode.py` drives the MCP handlers as plain functions.

A scenario written with `grows` keeps writing itself. Once the player is nearly out of places to
find, new unknown locations, exits and threads are added. Builtin mode does that at the end of
the turn, on the configured scenario creator. Code mode says growth is due in `end_turn` and
`scene()`, and the agent runs the `growing-aidm` loop against the server's own authoring tools —
in a subagent, so it costs the play conversation nothing.

Run repository checks with:

```bash
uv run ruff check
uv run basedpyright
uv run pytest
```

## Layout

One distribution. The import direction — `state <- content <- engines <- turn <- app <- ui`, with
`aidm/config.py` a leaf every layer may read — is enforced by
`tests/core/test_package_boundary.py`: an engine does not import another or `aidm.ui`, and
nothing below `app` imports the UI or NiceGUI.

The **Trace** tab shows the Director's plan, resolved facts, and the exact prompt received
by each role. The **State** tab shows the committed game state. Every engine subsystem gets its
own tab — both shipped engines ship **Advancement** — where an advisor drafts a proposal; the player reviews
each change and its reason, then confirms. In code mode that tab is read-only and the agent
drafts the proposal itself, against the engine's own proposal schema.

## Docs

- `AGENTS.md`: durable engineering and architecture rules.
- `docs/FATE-CONDENSED.md`: Fate Condensed SRD and candidate-engine scope.
- `docs/ROADMAP.md`: known weaknesses and direction.
- `IDEAS.md`: loose ends and the idea backlog.

## Licensing

- `docs/LONER-3E.md`, the loner3e engine's prose and instruction files, and its content packs
  (`src/aidm/engines/loner3e/packs/`) derive from the Loner 3e SRD and are CC BY-SA 4.0 —
  attribution: Roberto Bisceglie / Zotiquest Games, <https://lonersrd.zotiquestgames.com>.
- `packs/ap01-fantasy.json` derives from the SRD site's AP01 Fantasy page, whose own footer
  states only "© Roberto Bisceglie" while the site declares CC BY-SA 4.0. It is treated as
  covered by the site's license; a one-line email to the publisher would settle it if certainty
  is ever wanted.
- `docs/24XX.md`, the 24XX engine's prose, instructions and pack
  (`src/aidm/engines/twentyfourxx/`) derive from the 24XX SRD and are CC BY 4.0 — 24XX rules
  are CC BY Jason Tocci, <https://24xx-srd.carrd.co>.
- `docs/FATE-CONDENSED.md` reproduces the Fate Condensed SRD under CC BY 3.0. The complete
  required attribution is preserved at the top of that file; official source archive:
  <https://fate-srd.com/downloads/CC-BY-SRDs.zip>.
- The license of the rest of the code is an open decision the maintainer has not made yet; this
  section records that rather than inventing one.
