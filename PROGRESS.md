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

## Phase 2 — commission (2026-09-04)

| | before | after |
|---|---|---|
| `src` lines | 9,070 | 9,481 (target 9,150 to 9,250: +231, reported per PLAN rule 6, no check trimmed) |
| `engines/scenes/` | 1,145 | 1,282 (under 1,300) |
| `engines/rooms/` | 1,085 | 1,269 (under 1,300) |
| tests | 508 | 526 |

Landed as PLAN 2.1 to 2.4: `Commission` on the game (`wanted`, `on_order`, `withdraw`);
`commission` on every engine from the seam, outside the fifteen; the suspended turn (every tool
answers the wait line while one waits), the worldsmith spawn and the re-spawned master in
`GameService.play`, told what landed before it asked; `CastDraft`, `NpcDraft`, `ItemDraft` and
their bars; a `later` met at the next write in both families, surviving a room return; the
master's "Ask for more"; the ticker copy; the docs. Goldens: every `master_tools.json` gains
`commission` last, every `master.txt` the one section. Saves from Phase 1 still load (the field
defaults).

### Decisions made off-plan (the orchestrator's, 2026-09-04)

- `hub_sections(world, *, returning, reopening)` takes the flags `render_next` already threads,
  not an `intent` (PLAN 2.2.4 predates the Phase 1 `reopening` decision). `render_next` takes any
  `answer: type[BaseModel]`, so `render_commission` is one call to it rather than a second copy of
  the prompt.
- The rooms' `COMMISSION_ASK` is its own constant in `rooms/worldsmith.py`; no cross-family import.
  The rooms' commission prompt puts the ask under THE GAME MASTER ASKED FOR, not under WHAT THE
  PLAYER WANTS TO PURSUE, which reads a neutral line.
- `Engine.commission` refuses a second `later` while one is on order (an Opus finding): without it
  N turns file N `later` commissions and the next write owes N entries, a soft-lock at a crossing.
  A `now` while a `later` is on order is allowed. The "refused while one waits" guard PLAN named is
  `Turn.call`'s wait line; the seam carries no second copy.
- `Game.on_order()` replaces three copies of the `later` filter.
- `npc_refusal` also refuses an npc `unwritten()` may not write (a dead one), as `cast_refusal` does.
- The docs bullet reads `` `commission` (platform, not counted) — ... `` to match its list.

### Reviews

Two adversarial reviews of the staged diff: the Fable reviewer and an Opus reviewer (no `codex` on
this machine, so the Opus reviewer stood in for Codex Sol). Fixed: the re-spawn note read the facts
after the install landed, so the worldsmith's answer was listed as resolved "before you asked";
a re-filed entry was traced under the worldsmith's name, not the world's; an unknown room kind
raised a `Refusal` where a bug raises; the scenes `worldsmith.md` sentence was wrong for the
`later` case; `cast_refusal` re-checked a Field bound (branch and `model_construct` test deleted);
"next scene" in the room's `later` copy; `later`/`asked` built before the return branch that never
read them. Refuted:

- Opus cut: one `match` arm selecting `(model, bar)` then one `await`. `WorldsmithAnswer.__call__`
  is generic on the answer model, and a union of `(type[M], Callable[[M], ...])` pairs does not
  solve `M`; three arms stay.
- Opus cut: a shared base for `SceneCommission` and `RoomCommission`'s `brief` and `later`. Pydantic
  puts parent fields first, so `kind` would print last in the schema the master reads; and the two
  `later` descriptions now differ (scene, region).

### Known and accepted

- The `src` count is 231 lines over the phase target; the overrun is the second family's full
  commission path (drafts, two bars, three installs) and the extracted prompt sections, each named
  by PLAN.
- PLAN's `grep -rn "commission" src/aidm/core` finds `model.py` only: `play.py` holds the class
  `Commission`. The invariant (commissions live in those two files) holds.
- The manual play PLAN's "Done when" describes (a scene master commissions a person, the ticker
  shows Worldsmith, the re-spawn brings them in with `enter`; a `later` appears in the next scene;
  a Tunnel Goons npc stands hidden) needs live roles and was not played; `uv run aidm` boots. The
  shutdown traceback on SIGTERM (`ui/app.py`, untouched) predates the phase.
