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

## Phase 2: one bar, one request table, one renderer, shared engine code

Counts: `src` 9,920 -> 9,869 (target about 9,877, at most 9,895; PLAN's 9,923 base counted
three lines phase 1 had already cut); `tests` 9,307 -> 9,304; `qa` 1,788 -> 1,788.

Decisions off-plan (each from a review finding, all a few lines):

- `engines/hiring.py`: `Hiring` registers `hire` by overriding `worldsmith_requests` on top of
  `super()`'s, the way `master_tools` layers, instead of a `Hiring.__init__` that patches
  `self.requests` after the fact. One way to fill the one table; the family's entries still come
  first, so `next(iter(engine.requests))` and the prompt goldens are unchanged.
- `engines/seam.py`: `worldsmith_requests` is abstract, not `return {}`: both families override
  it and no engine stands outside them, so the default had no user.
- `engines/seam.py`: `type Written = tuple[tuple[Fact, ...], str | None]`, which the phase would
  otherwise have spelled six times (`Request.write`, `advance`, `depart`, `complicate`, `extend`,
  `write_hire`).
- `engines/seam.py`: `render_request` and `render_opening` share a private `_render` that binds
  the role prompt; they differ only in where source, scope and family come from.
- `core/views.py`: `check_speakers` folded into `check_narration`, its one caller.
- `engines/base.py`: `ItemSheet.drop` inlined into `drop_item`, its one caller.
- `engines/breathless/world.py`: `Survivor.require_item` deleted too; its one caller in `roll`
  already held the sheet and calls `sheet.require` directly.
- `engines/hiring.py`: the missing-target refusal reads "a hire request names no target": the
  operation is always `hire` once the seam's table routes here.
- Five test names that said `_refusal` for a bar now named `check` were renamed to match, so
  the PLAN "Done when" grep prints what it says.

Refuted findings:

- Opus: `ItemSheet.drop_item` reads its owner three times, so the fact should stay on the
  member. PLAN step 9 chose the sheet because `Sheeted[S]` is not bound to `ItemSheet`, so
  `Survivor` and `Crewmate` could only host it as two copies or through a new mixin.
- Opus (named as accepted): the `isinstance` narrow in `Hiring.hireable` cannot fire because
  the world files only `M`. PLAN step 10 chose it as the price of deleting the three hook
  bodies; `Engine.world` is typed `World[Person, P]`.

Known and accepted:

- Two PLAN "Done when" greps print more than PLAN says: `def drop_item` also prints the two
  engine tool methods PLAN step 9 itself keeps, and `grep "str | None" core/views.py` prints
  `PlayerView.over`, a field, not a bar.
- The qa harness (`qa/run_all.sh loner goons breathless 24xx`): `goons`, `breathless` and `24xx`
  report 0 issues; `loner` reports the same pre-existing "no live turn after a reload mid-turn"
  phase 1 recorded.
