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

## Phase 2 — L5: cut the ceremony an engine pays before it writes a rule

Steps 1 (signed `DiceEvent`) and 6 (optional `Engine.advancement`) ship with L7/L8; step 2 landed
before the phase.

- [x] 7. `engines/registry.py` — `ENGINES` discovered over `engines/*/engine.py`, in 16 lines
- [x] 8b. `authoring/draft.py` — `AuthoringBrief.label` + `BRIEFS`; `ui/create.py` `_BRIEF_LABELS` gone
- [x] 8a. loner3e `rules.py` — `outcome_for` returns a frozen `Outcome`; `HARM` gone. 24XX kept a
  `Slug` and tests `!= "success"`: an `Outcome` for one bool cost more than `HURT` it replaced
- [x] 3. `engines/core.py` — `Decision` base, `Engine.decisions`; both engines' `check_pending`/`resume` gone
- [x] 5. `engines/packs.py` — `PackCreation` base; both `Creation` classes lose the pack preamble
- [x] 4. `SheetBase.rows()` — `describe`/`sheet_view`/`overlay_rows` concrete on `SheetEngine`
- [x] Goldens regenerated, tests corrected, four checks green
- [x] Over-engineering pass, then an adversarial review: net -46 lines, four checks green

**Phase 2 is done.** `uv run pytest` 245 passed, `ruff check`, `ruff format --check` and
`basedpyright` all clean.

## Not started

Phases 3–4 (L9+L10, I4).
