# PROGRESS

One entry per phase of `PLAN.md`: the counts, the decisions taken off-plan, the review findings
refuted and why, and what is known and accepted.

## Phase 1: one pack, and the saved shape

Counts, `find <dir> -name '*.py' | xargs cat | wc -l`:

| dir   | before | after | change |
| ----- | -----: | ----: | -----: |
| src   |  10506 | 10376 |   −130 |
| tests |  12065 | 11913 |   −152 |
| qa    |   2020 |  2020 |      0 |

Both parts landed as planned. The three worldsmith goldens were regenerated and showed no text
change. Reviewed by two independent Opus reviewers (no `codex` on the machine).

Decisions taken off-plan:

- `Engine.author_pack` loses its `pack_id` positional. Its one reader was `check_addable`, which
  the phase deletes; `Runtime.new_pack` still derives the id against `engine.packs.installed`
  and writes with it. `check_head` builds the pack alone, as `check_body` does; a label that
  makes no id still re-prompts, and a test pins that.
- `ui/create.py` does not import `SRD_PACK` or `AnyEngine`: `tests/core/test_package_boundary.py`
  forbids `ui` from naming `aidm.engines`. The default pack is `Runtime.default_pack`, beside
  `Runtime.default_engine`; `_pack_select(offered, chosen, on_change)` takes the engine's
  `packs.options()` and builds no select when one pack alone is offered.
- `_pack_select` returns nothing: no caller read the select it returned.
- Tests of deleted behaviours went beyond the seven the plan names: the 24XX skill-less
  supplement `select`, the doubled and missing `packs` validators, the "no packs" scene check,
  the two "records the packs it was made with" character tests, `new_scenario`'s `admit`
  refusal, and the two SRD-collision pack tests (`defined_ids` is gone). One new test pins the
  invariant the first of those carried: a written 24XX pack adds no skills to the increase step.

Review findings refuted:

- "`test_choosing_a_pack_refreshes_the_steps…` awaits nothing; make it `def`": a refreshable's
  `refresh()` schedules a NiceGUI background task on the running loop, so the test needs one;
  the reason is now a comment above it.

Known and accepted:

- A game on an Adventure Pack renders that pack's `PACK:` block and special rules alone; the
  SRD's setting block no longer precedes it. One setting per adventure is what the phase asks.
  The shipped scenarios all play `srd`, which is why the goldens did not move.
- `qa/agents.py` has one `basedpyright` error when `qa` is checked explicitly; `pyproject.toml`
  includes `src` and `tests` only, and the error predates this phase.
