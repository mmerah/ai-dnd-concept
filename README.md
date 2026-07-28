# AI Dungeon Master — role-separated pipeline

A proof of concept: split the Dungeon Master into narrow roles so a small, fast model (gpt-oss-120b) stays consistent without losing creativity.

```
prompt → DIRECTOR → resolve → NARRATOR → MAINTAINER → CREATOR → commit
         Direction   Events    prose      Growth       Entity
```

Resolution is the only non-LLM stage: pure Python, no model call.

Two rules hold the design together:

- **The model proposes, Python decides.** The Director proposes typed mechanics that reference canon by id. The resolver turns them into events deterministically. Applying events to a state is the only thing that produces a new one. No LLM ever mutates state.
- **Context is a policy.** Each role has exactly one prompt builder, and that builder's signature *is* the policy. What a role may see is decided in one place, never assembled ad hoc at a call site.

## Run

```bash
uv sync
uv run pytest              # deterministic, no network
uv run python -m aidm      # http://localhost:8080
```

Run from the repo root; paths and `.env` resolve against the working directory. `.env` needs `PROVIDERS__OPENROUTER__API_KEY` for OpenRouter.

The **trace** tab shows what every role contributed and the verbatim prompt each one received. That panel is the point of the PoC. The **state** tab is the live game state.

## How a game is put together

A game state is composed at `new_game` from a **scenario** (premise plus starting canon) and a **character**, kept in separate files so one character can be replayed across scenarios. Play only ever edits the live world, never the static scenario identity. The player is an ordinary actor entity inside that world, under a reserved id, so events and positions name them exactly as they name anyone else.

Content ships as **packs**: a manifest plus narrow record collections, addressed by a `(pack, collection, index)` triple rather than a bare slug. The shipped pack is a projection of 5e-database, converted offline by a script in the repo and committed, so the pack doubles as the edition pin. An entity that names a record snapshots the numbers the reducer touches at creation and reads everything descriptive live, which is why a save records the pack versions it was played against and refuses to load against different ones.

## Docs

- `AGENTS.md`: engineering principles and the architectural invariants, in enforceable form.
- `docs/ROADMAP.md`: what is weak today, and what comes next.
