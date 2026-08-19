# Opinion 1 — accepted simplifications

Four surgical deletions from a codebase audit, ranked by value over effort. Each is independent
and lands with `uv run pytest && ruff check && ruff format --check && basedpyright` green.
Rejected in the same audit, do not revive without new evidence: typing `beat_type` behind a
generic `BeatBase` (a future engine may want a differently shaped beat), stripping `title` from
the generated JSON schema (pydantic-ai owns generation; no clean knob), collapsing the `state/`
modules, and deleting the `views.py` projections.

## 1. Delete three dead pass-through fields — ~30 min
- `Fact.source` (`state/facts.py:14`) is `"core"` at all six construction sites and is never read.
  It is persisted on every line of every `.trace.jsonl`.
- `Resolution.outcome` (`state/beat.py:30`) flows through `Engine._play` (`engines/engine.py:143`)
  into `Transacted.outcome` (`engines/transact.py:22`), which **no production code reads** — only
  tests. The value already lives in the roll fact's `data["outcome"]`, and engines keep using it
  internally (`loner3e/actions.py` `_strike`, `twentyfourxx/actions.py` followup choice).

Persisted bytes move: bump `SAVE_VERSION` (`state/base.py:31`) and `FIXTURE_SAVE_VERSION`
(`tests/core/test_golden_state.py:10`) together, regenerate save/state/turn fixtures with
`AIDM_GOLDEN_REGEN=1`, read the diff. Point the tests asserting `resolution.outcome` at fact data.

## 2. Make the engine registry static, at the composition root — ~30 min

`engines/registry.py` resolves engines through `import_module` plus an `ENGINE` module sentinel
plus a `pyright: ignore`, purely to avoid a `core -> engine` import cycle. Every importer is
app-side (`app/session.py`, `app/launcher.py`, `app/authoring/playability.py`) or test-side, so
there is no cycle to avoid: an `app/registry.py` holding `ENGINES = (Loner3eEngine,
TwentyfourxxEngine)` imports both statically. That deletes the dynamic import, the sentinel, the
"declares no ENGINE" path and the suppression. `tests/core/test_package_boundary.py:69` then
expects `app/registry.py` as the one file naming a concrete engine, instead of the empty set.

## 3. Put outcomes on `Exchange`; drop the history/trace pairing — ~1 h

`app/views.py:43` `played_turns` zips `state.history` against trace `Turn` entries in reverse with
`strict=False`, to hang outcome strings under the chat bubbles at `ui/panels.py:90`. Two sequences
that grow independently, paired by position — it holds only because both grow one entry per turn.

Write the narrator-visible traces onto `Exchange` (`state/history.py`) when the turn commits in
`turn/pipeline.py`. `played_turns`, `PlayedTurn` and `_outcomes` go; `panels.chat` reads one
object. Persisted bytes move: bump `SAVE_VERSION` as in item 1.

## 4. Deduplicate the two engines' shared spine — do last

`loner3e` and `twentyfourxx` carry the same three things under different names: the `EndAdventure`
/ `CompleteJob` ops recording that the fiction closed a chapter; `Mechanics.completed: Counter`
with an `Advancement.earned()` returning `completed.current`; and `new_sheet`'s "a newcomer starts
level with the party" (`loner3e/rules.py:49`, `twentyfourxx/rules.py:47`). Lift `completed` onto
`SheetMechanics` (`engines/sheets.py`) and merge the two ops into one whose player-facing wording
the engine supplies. ~80 lines out, but the merged op reshapes the Director schema, so both
`director.md` files, both `examples.json`, and the golden schema and prompt fixtures move with it.
