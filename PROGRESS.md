# PROGRESS

One entry per PLAN.md phase: counts before and after, decisions made off-plan, refuted review
findings and why, and anything known and accepted.

## Phase 1: one tool per change

Counts: `src` 9,994 -> 9,920 (target about 9,920, at most 9,940); `tests` 9,321 -> 9,307;
`qa` 1,792 -> 1,788.

Decisions off-plan:

- `tests/support/table.py`: `change` and `refused` take the tool `name` positional-only.
  `GainItem` has a field called `name`, so `change(ENGINE, draft, "gain_item", name="Rope")`
  would otherwise be a `TypeError`.
- `engines/seam.py`: the `master_tools` docstring reads "family, then `hire`, then the engine"
  instead of PLAN's wording, which ran to 103 characters; CLAUDE.md keeps comments to one line.
- `engines/tunnelgoons/rules.md:39-40`: the "use the `unlock_way` arm" phrase spanned two
  lines, so line 39 changed too ("Then use the" -> "Then call"). Three prose lines came out one
  character longer where "arm" became "tool"; no wrap moved.
- `README.md:31` (review finding): "`change_world` for any settled change" -> "one tool per
  settled change". PLAN step 12 named only `rules.md` and `docs/`.
- `uv run basedpyright` is green only after `uv sync --all-groups --locked`: without the `qa`
  group installed, Playwright's types are unknown and `qa/*.py` reports 1,100 errors.

Refuted findings: none.

Known and accepted:

- A 24XX save from before this phase holding an open succession decision has options that name
  `change_world`; they are refused at `answer`. No compatibility path (PLAN "How to work" §6).
- The qa harness (`qa/run_all.sh loner goons breathless 24xx`, real app, scripted roles,
  Playwright) plays a turn in each engine and lands a change tool in each: `goons`, `breathless`
  and `24xx` report 0 issues; `loner` reports one, "no live turn after a reload mid-turn"
  which fails identically on unchanged `c08edd5`, so it is pre-existing and not this phase's.
