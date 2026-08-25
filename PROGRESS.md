# Refactor progress

Tracking `PLAN.md`. One line per numbered step; only what is done or in flight.

## Phase 0 — Free deletions — DONE (`920d5c9`)

- Shipped before this log started. `TurnRecord.steps`, `Advancement.id` gone; `Slug` lives in `config.py`.

## Phase 0b — Delete `CharacterOverlay` — DONE (staged, uncommitted)

- [x] 1. `Character.rules` / `CreatedCharacter.rules: dict[str, JsonValue]`; `CharacterOverlay` deleted.
- [x] 2. `characters/kael/{loner3e,twentyfourxx}.json` unwrapped (one nesting level gone).
- [x] 3. Six readers updated: `content/io.py`, `app/launch.py`, `ui/create.py`, both engines' `create()`.
- [x] 4. Suite green: 259 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.
- Net: −10 lines in `src`; `io.py` gained `_read_text` so the rules dict and the models share the missing-file error. Rules read with `json.loads` and validated by `Character` itself; written with `json.dumps`.

## Phase 1 — Typed facts and resolver-built events — NOT STARTED
## Phase 2 / 2b / 3 / 4 / 5 / 6 — NOT STARTED
