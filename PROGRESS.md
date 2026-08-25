# PROGRESS

Tracks [PLAN.md](PLAN.md). One bullet per step; a step is ticked only once `uv run pytest`,
`ruff check`, `ruff format --check` and `basedpyright` are green.

## Phase 0 — L1: make a pending decision unmistakable

- [x] 1. `ui/theme.py` — `.game-decision` accent rule
- [x] 2. `ui/game.py` `decision_panel` — header row (icon + kind + waiting line), readable prompt, composer pointer
- [x] 3. `ui/game.py` `_composer_placeholder` — takes the `GameView`, prompts for an answer while a decision is open
- [x] 4. `ui/game.py` `chat` — drop the `Paused:` echo for the still-open decision
- [x] 5. `engines/loner3e/rules.py` `conflict_prompt` — name the moves
- [x] 6. `harness/codemode.py` `_waiting` — prefix the kind

## Phase 1 — L2: death is a reserved trait plus one `kill` command

- [x] 1. `state/entities.py` — `DEAD` slug constant
- [x] 2. `state/actions.py` — `kill` resolver
- [x] 3. `state/actions.py` `require_actor_here` — refuse a dead actor before the player early return
- [x] 4. `state/model.py` `_check_party` — reject a dead member
- [x] 5. `turn/run.py` `consume_answer` — refuse a segment once the player is dead
- [x] 6. `engines/world.py` — `Kill` args + `kill` core command
- [x] 7. `turn/prompts/director.md` — name death in the post-roll consequence list
- [~] 8. `turn/context.py` `_headline` — reverted: `entity_state` already prints
  `traits: Dead[id=dead]` in the same block, so the headline marker was a second copy
- [x] 9. `ui/game.py` — dead marker in the scene header, composer lockout
- [x] 10. `evals/turn_eval.py` — `loner3e/finish-the-rat` case
- [x] Goldens regenerated (`AIDM_GOLDEN_REGEN=1`), `test_actions.py` covers `kill`

**Phase 0 and Phase 1 are done.** `uv run pytest` 245 passed, `ruff check`, `ruff format --check`
and `basedpyright` all clean. Not run: the two live exit checks in PLAN.md, which need `uv run aidm`
and a model — a loner fight taken to a surviving exchange, and a `kill` on the rat.

## Not started

Phases 2–4 (L5, L9+L10, I4).
