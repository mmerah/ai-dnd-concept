# PROGRESS

One entry per phase of `PLAN.md`. Counts are `find src -name '*.py' | xargs cat | wc -l`.

## Phase 1 — the memory (2026-09-04)

| | before | after |
|---|---|---|
| `src` lines | 8,659 | 9,070 (target 8,900 to 8,980: +90, reported per PLAN rule 6, no check trimmed) |
| `engines/scenes/` | 1,017 | 1,123 (under 1,150) |
| `engines/rooms/` | 977 | 1,070 (under 1,150) |
| tests | 469 | 508 |

Landed as PLAN 1.1 to 1.4: `ChapterRecord` and the third depth in `render_history`; `render_whole`;
every fact filed on the exchange (the chat shows cards); `Attempt`, `Job.summary`, the reopened
job; `summary` and `recap` on both return drafts; `arc` on the scene drafts, the canon and the
world, printed to the master as THE ARC; the crossing names the place left; the bar on every
player-facing return field, one leak rule (`named_unmet`: a multi-word name or a bare id) shared by
both engine families. Goldens: only the three scene engines' `master.txt`, by the one `rules.md`
sentence. Saves from before this phase are stale (no version field): say so in the commit message.

### Decisions made off-plan (the maintainer's, 2026-09-04)

- `Campaign.job_at` is not built: nothing calls it.
- `Campaign.taken(intent)` matches the page's `TAKE_JOB` line only, case-folded like `left_open`;
  a title in the player's free text never reopens a job (a short title would match by accident).
- One span validator, `Campaign.check_spans(places)`, replaces `check_walked` and the attempt checks
  PLAN 1.3.2 and 1.4.1 placed in `_consistent` and `_playable`.
- `Job.start()` (the walking attempt's index) serves `since_start`, `walked_places` and the recap
  landing, in place of three `attempts[-1].started` reads narrowed by hand.
- `reopening` is computed once in `advance` and passed down to the prompt and the install, in both
  families, rather than `taken(intent)` running twice per turn.

### Reviews

Two adversarial reviews of the staged diff: the Fable reviewer and an Opus reviewer (no `codex` on
this machine, so the Opus reviewer stood in for Codex Sol). Every finding was fixed except one:

- Refuted, Opus cut 3: `_recaps_unmet`'s `if job is None: return []` is "unreachable". Kept:
  `walked_job()` is typed `Job | None`, the guard is the narrowing, and an empty list is the honest
  answer for a world with no walked job; a `Refusal` there would swap one guard for another.

### Known and accepted

- The `src` count is 90 lines over the phase target; the overrun is the bar on three return fields,
  the shared leak rule and the two reopen paths, each named by PLAN.
- Once a job collapses into a CLOSED block, the master reads its summary twice (ledger line and
  block), as PLAN 1.2.2 allows under the whole-context rule.
- Untold fact traces are not checked against the return's player-facing fields (prose cannot be
  matched to a trace); the two-spawn fallback PROPOSALS names is the answer if it leaks in play.
- A one-shot `SceneDraft.arc` is required by shape and refused when empty by the bar; a campaign's
  `HubDraft` and `ReturnDraft` default it to empty (a return clears the world's arc).
- `uv run aidm` boots and serves the launcher; the manual campaign play PLAN's "Done when" describes
  (take a job, two scenes, go home, re-take) needs live roles and was not played in this session.
  The shutdown traceback on SIGTERM (`ui/app.py`, untouched) predates the phase.
