# AI Dungeon Master — role-separated pipeline

A proof of concept: split the Dungeon Master into narrow roles so a small, fast model
(gpt-oss-120b) stays consistent without losing creativity.

```
prompt → DIRECTOR → resolve → NARRATOR → MAINTAINER → CREATOR → commit
         Direction   Events    prose      Growth       Entity
```

`resolve` (`engine/resolve.py`) is the only non-LLM stage: pure Python, no model call.

Two rules hold the design together:

- **The model proposes, Python decides.** The Director proposes typed `mechanics` referencing canon
  by id; `engine/resolve.py` turns them into events deterministically; `apply(state, events)` is the
  only thing that produces new state. No LLM ever mutates state.
- **Context is a policy, not an accident.** One table in `agents/policy.py` is the complete
  answer to what each role sees. Read it there — it is the source of truth, not this file.

## Run

```bash
uv sync
uv run pytest              # deterministic, no network
uv run python -m aidm      # http://localhost:8080
```

Run from the repo root; paths and `.env` resolve against the working directory. `.env` needs
`PROVIDERS__OPENROUTER__API_KEY` (OpenRouter); see `config.py` for the rest, including the per-role
model, endpoint, retries, token budget and reasoning level.

The **trace** tab shows what every role contributed and the verbatim prompt each one received.
That panel is the point of the PoC. The **state** tab is the live `GameState`.

## Layout

```
src/aidm/
  domain/      pure data and the reducer — no LLM, no I/O
  engine/      deterministic mechanics: resolve.py (mechanics -> events), growth.py (screen
               creations), bestiary.py (content records -> entities)
  content/     the canonical 5e content model and the pack loader — imports nothing from domain/
  agents/      the provider, the context policy, one file per role
  utils/       primitives shared by domain/ and content/: frozen models, abilities, dice, ids
  pipeline.py  run_turn: the fixed sequence
  store.py     JSON persistence, and the one place packs are read
  ui/          NiceGUI
scenarios/     scenario definitions: premise + starting entities (no character)
characters/    characters, loaded independently so one can be reused across scenarios
packs/         content packs; `srd-2014` is 5e-bits/5e-database v5.10.0, projected and vendored
               (12 collections, 1,310 records; progression is R7 — see REFACTOR.md §Step 8)
scripts/       offline tools, not part of the app: import_srd.py + srd/ rebuild packs/srd-2014
```

A `GameState` is composed from a `ScenarioDef` and a `CharacterSheet` at `new_game`; play only ever
edits `state.world`, never the static `state.scenario` identity. The player is an ordinary actor
entity inside `state.world.entities`, under the reserved id `player`.

A content **pack** is a manifest plus narrow record collections, addressed by
`ContentRef(pack, collection, index)` — never a bare slug, since `shield` is both a spell and a
piece of armour. The projection *is* the format: `scripts/import_srd.py` converts a checkout of
5e-database into it offline, and the result is committed, so the shipped pack is the edition pin. An
entity naming a record has the numbers the reducer touches snapshotted into it at creation and reads
everything descriptive live, which is why a save records the pack versions it was played against.

The boundary that matters is `engine/` ← `agents/`: mechanics stay testable without an agent, and
agents cannot decide outcomes. Growing the ruleset means growing `engine/`, not the role prompts.

## Docs

`docs/ROADMAP.md` — what is weak today, and what comes next.
