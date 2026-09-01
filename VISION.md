# VISION: a game you play in a browser, run by CLIs you already pay for

This file says what we build and why, at a high level. It is the authority on the target.
`PLAN.md` is the order of work and is derived from this file. Keep this file under 200 lines.

## The one-line vision

> The app is the game, and you play it in a browser.
> Its three roles — game master, narrator, worldsmith — are one-shot CLI sessions the app
> spawns, so play costs the subscription the player already has.
> Each engine is a complete tabletop game: its rules, its world, its authoring, its views.
> The app runs any engine. Two ship, and they play nothing alike.

## Why

1. **People should be able to play it.** One window. Type, read, look at the art. No terminal,
   no MCP setup. The coding CLIs are the engine room, not the interface.
2. **The player already owns a strong model.** Claude Code, Codex, OpenCode or Pi on a
   subscription. The app spawns those and pays nothing per turn. Illustration is the one
   exception: optional, off by default, its own image key.
3. **One process owns the game.** The app is the only writer. No save polling, no two servers
   racing over one file.
4. **An engine is a whole game.** A tabletop system's rules assume a world shape. Loner says
   "everything is a character" and plays in scenes; a dungeon game needs places and ways. A shared
   world layer made both engines lie about their own rules and cost a generic type nobody owned.
   So every engine owns its world, and the platform owns none.
5. **Two engines prove the multi-engine claim.** Loner 3e is oracle-driven solo play in
   sentence-driven scenes. Tunnel Goons is game-master-driven dungeon crawl on an authored map.
   They differ on resolution, on world shape, on authoring and on what the player decides. If the
   platform runs both without a branch, it runs the next one.

## Target architecture

```
                        ┌──────────── the browser ────────────┐
                        │  play page   art · transcript · dice │
                        │  home · new character · settings     │
                        └───────────────┬──────────────────────┘
                                        │
APP  (one process, the only writer)     │
  GameService     play, extend, restart, commit
  three spawns    game master · narrator · worldsmith
  MCP endpoint    the tool surface the game master calls
  media, settings, composition root

        the engine seam: one dataclass of typed callables

ENGINE  aidm/engines/<engine>/   self-contained, at most 2,000 lines
  its typed Game payload and its own world model
  its SRD procedure tools and its world verbs
  its character creation, validation, views, recording
  its worldsmith: the opening world and how the world grows
```

Imports flow one way: `core <- engines <- turn <- app <- ui`. `core`, `turn`, `app` and `ui`
import no concrete engine; the registry is the one composition point.

## What the platform is

- **`core/`** — the envelopes (`Game`, `Scenario`, `Character`), `Fact`, the tool boundary, the
  two views, decisions and exchanges, files, and source-document reading. It knows an entity only
  as the id the told-fact gate checks, and no world shape: no thread, scene, place, inventory or
  `change_world`.
- **`turn/`** — the transaction: open, picture, apply, refuse, narrate, commit. Every mutation
  runs against a throwaway copy first and lands on the draft only when the engine accepts it.
- **`app/`** — the composition root, the game service, the spawned roles, the MCP endpoint,
  media and settings.
- **`ui/`** — the pages. They read `PlayerView` and `NarratorView` and nothing else, so no page
  knows which engine is playing.

## What an engine is

One package under `engines/<id>/`, and everything the game needs is inside it:

1. **State** — a typed payload with the engine's own world model. Invariants are structural: a
   thing that cannot hold a sheet has no sheet field. Incompatible state is invalid, not repaired.
2. **Rules** — one game-master tool per SRD procedure, world verbs included, never more than
   eight. The engine rolls everything the procedure needs and hands back one result.
3. **Creation** — the SRD's own steps, as typed picks.
4. **Worldsmith** — the opening world for a new scenario, and how the world grows in play. The
   growth bar is the engine's: a scene needs a question, a map needs a route.
5. **Views and recording** — the game master's picture, the narrator's view of revealed canon
   only, the player's view, and the chronology.

Fidelity is the goal. Every deviation from the printed rules is written in `docs/<ENGINE>.md`
with its reason. A rule is verified against the rulebook before it is built on.

## The engine seam

`Engine` is a frozen dataclass; each engine's `build()` fills it with its own module functions.
The platform reads exactly these members and no other:

- identity: `id`, `title`, `instructions`, `packs`
- models: `game`, `scenario`, `character`
- creation: `creation_steps`, `create_character`, `preview_character`
- play: `tools`, `validate`, `new_game`, `over`, `known`, `record`, `history`
- views and growth: `master_sections`, `narrator_view`, `player_view`, `authoring`, `transition`

Two methods sit on the dataclass: `restored(raw)` loads a save through the engine's own types, and
`answer(draft, option, rng)` plays a chosen decision option through the tool that offered it.
`authoring` is `answer`, `prompt`, `build`: the opening world's schema, its prompt, and the build
that raises when the bar is unmet. `transition` is `ready`, `write`, `install`, `arrival_brief`,
and every engine has one. A scene engine plays the player's sentence as a turn and crosses after
it, narrating the arrival; a map engine extends the map without a turn and leaves the player
standing. A scenario that must not grow has a `ready` that never fires.

## How a turn runs

1. The player writes, or answers a decision. The app opens a draft.
2. The game master is spawned with the rules and the action. `start_turn` hands it the picture.
3. Each tool call is tried on a copy, then applied to the draft. Refusals are answers, not errors.
4. A rule may leave a `PendingDecision`; the turn stops there and the player answers next turn.
5. The narrator receives revealed canon only and writes 2–4 sentences.
6. The exchange is recorded, the draft is validated whole and committed, the save is written.
7. If the engine's `transition` is ready, the page offers the way on. A refused or failed write
   costs the write, never the turn already played.

Every role is a fresh one-shot CLI. The narrator's input type has no field that can hold hidden
canon; the app enforces that only the player or someone present speaks.

## Content

- **Characters** — one file per engine under `characters/<id>/<engine>.json`, made on a page from
  the engine's creation steps.
- **Scenarios** — `scenarios/<id>/world.json` is the engine's starting world, written by one
  worldsmith call from a premise or a source document. Packs are the engine's own tables.
- **Saves** — strict, engine-typed, no version field and no migration. A stale save is invalid.

## MVP0

Loner 3e and Tunnel Goons play from the browser, from one build, with no `if engine` anywhere
above the seam. Done when:

1. `kits/` is gone; each engine owns its world, and `core/` knows no world shape.
2. Loner plays a decision, a crossing and the journal; its remaining deviations are the ones the
   SRD leaves open, not ones the platform forced.
3. Tunnel Goons plays a dungeon: walk it, take a route back, open a locked way, fight, rest,
   run the map out, extend it.
4. `src` is about 6,900 Python lines; the platform about 4,000; no engine over 2,000.
5. Full check green, and both engines played from a live build.

## After MVP0 — engines

Each returns self-contained, on the same seam, with its own `docs/<ENGINE>.md`:

- **Maze Rats** — the audited rules live in git at `2c3e8a5`; the return rewrites the world on
  its own strict actor/item/place model and fits 2,000 lines by dropping nothing the SRD prints.
- **24XX** and **Breathless** — scene engines; notes in `docs/24XX.md` and `docs/BREATHLESS.md`.
- **A Pokémon-style engine** — battles delegated to Pokémon Showdown. The point is the boundary:
  AIDM runs the RPG, Showdown runs the fight, neither reads the other's internals.

## After MVP0 — features

- Sounds and voices; `app/media.py` is the template.
- Per-place memory: a summary written when the player leaves a place, so a long game keeps its
  start without carrying every turn.
- The eval loop: run a turn many times, find where the model is inconsistent, fix the tool or the
  prompt that caused it.
- Pack authoring through the worldsmith, then a scenario that plays with the new pack.
- A demo: one command, one GIF of a full turn.

## Non-goals

A shared world layer or world protocol, in any name. Save migration. A built-in turn loop for
weak models, and the state-keeper agent that served it. Retrieval over source documents: the
source cap already hands a whole adventure to the worldsmith.
