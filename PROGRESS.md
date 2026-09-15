# PROGRESS

Newest first. One entry per phase of `PLAN.md`.

## Phase 1 — `engines`

Findings 1–8, all inside `src/aidm/engines`. The phase's one golden regeneration ran at the end
and moved exactly the two fixtures the plan named. Three implementers: parts A (steps 1–3, rooms
and tunnelgoons) and B (steps 4–7, breathless, twentyfourxx, loner3e) in parallel on disjoint
files, then D (step 8 and the regeneration) on the finished tree.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,239 | 10,299 | +60 |
| `tests` | 11,559 | 11,831 | +272 |

`uv run pytest` 782 → 796 passing: 14 tests added, one deleted
(`a_place_walked_through_without_a_word_is_no_chapter`, which pinned nothing once `move` stopped
opening a chapter). `uv run ruff check`, `uv run ruff format --check` and `uv run basedpyright`
(0 errors) all clean. `uv run aidm` serves `/` and `/settings` (HTTP 200); no live turn — this
container runs no AI role — so the turn path rests on the suite.

`src` grew where the plan said it would shrink. Step 1 is the predicted net removal (`map_model`
gone from three places, one model added), but steps 2, 6 and 7 each add a refusal the engine did
not have, and those are the findings. The one place the phase could have been smaller is refuted
below.

### The three facts step 1 asks to record, so nobody re-derives them

- **The anchor place's title is required, not a caveat.** `attach` does not move the player
  (`rooms/world.py:405-415`), so `narrator_view()` titles the new chapter from the place the
  player still stands in. That is correct: `check_extension` forces the region's own `start` place
  to be hidden (`rooms/worldsmith.py` → `_map_unmet(start_known=False)`), so titling from the
  region would leak a hidden name into the narrator's "WHAT THE PLAYER HAS READ" header.
- **The empty-trailing-chapter pop** (`seam.py:277-278`) is right at the new call site: it is only
  reachable when MORE_MAP fires before any exchange, and the recap is then dropped with the empty
  chapter, which is what should happen.
- **Nothing persisted is invalidated.** `TunnelGoonsScenario = Scenario[MapDraft[Npc]]`
  (`tunnelgoons/world.py`) is what lands on disk; the region draft is consumed by `attach` and
  never stored, and `Game.generation` is `exclude=True` (`core/model.py:105`).

### Decisions made off-plan

- **The loner3e screen reads the whole cast, not `self.hidden()`.** PLAN step 7 spells the screen
  against "`self.hidden()`'s entities". `SceneWorld.hidden()` (`scenes/world.py:82-83`) is the
  unknown entities in the *current run's* `here`, so a cast member the player has never met who is
  not in this scene passed it — and the leak step 7 closes is the **stored sheet row**, which
  outlives the scene that wrote it. `check_unnamed` screens
  `[entry for entry in self.cast.values() if not entry.known]` instead. Both reviewers' severity
  ranking put this first; CLAUDE.md's "hidden facts have no path into" the narrator is the rule it
  serves, and the refusal text already promised "what the player has not met". One test added for
  the case `self.hidden()` missed.
- **The region model is named `RegionDraft`.** PLAN says "add a `MapDraft` subclass" without
  naming it. `RegionDraft[N](MapDraft[N])` mirrors `NextDraft(SceneDraft)` and matches the word
  PLAN itself uses throughout step 1 ("the region draft is consumed by `attach`").
- **The npc bar lives in `_map_unmet`, not in both room checks.** PLAN says "Call it from
  `scene_unmet` and from both room checks… Each caller keeps its own sentence." Written literally
  that pasted one identical clause and one identical sentence into `check_map` and
  `check_extension`, and forced both from a single expression into four lines. Both reviewers
  raised it independently. The clause moved into `_map_unmet`, which both checks already call;
  `scene_unmet` still keeps its own sentence, which is what the instruction was for. The
  extension-only item bar became `_planted_unmet` beside it, so both checks stay one expression.
- **The 24XX harmless-gear sentence is `_harmless(item)`.** Steps 5 and 6 leave the same
  player-facing string in `check_defenses` and in `_break`, in one file, where the whole point is
  that the pre-roll and post-roll refusals say the same thing. One helper beside the existing
  `_broken(item)`.
- **`CROSSING`'s format key is `{asked}`, not `{pursuit}`.** Step 8 removes the master's
  `pursuit` from that path; leaving the key named after the field that no longer feeds it made the
  name say the opposite of the value. No prompt wording changed, so no fixture moved.
- **`docs/TUNNEL-GOONS.md` lost "adventure" in two places, not one.** PLAN names only deviation 1's
  "once per adventure" → "once per game". That alone left the sentence contradicting itself ("an
  end-of-adventure step the master calls once per game… an adventure is the closest thing this app
  has to a session"), and the tool list at `:52` still read "once, at the adventure's end". The
  code has no notion of an adventure — which is why the refusal string dropped it — so the doc no
  longer asserts one.
- **One test outside both parts' scope was reworded.** `tests/turn/test_turn.py:301` set a drive
  goal of "Get the vault map out safely", which literally names the shipped scenario's hidden
  entity `the vault map`; the new screen correctly refuses it, so the drive never landed. Same
  rewording part B made in `tests/loner3e/test_world.py`. The screen catching a leak in the test
  data is the fix working.

### Refuted review findings

- **"Bind the model once in `rooms/engine.py` (`model = MapDraft[self.member]`), recovering ~6
  `src` lines."** Refused. The scenes family spells `SceneDraft[self.member]` twice inline in
  `author` (`scenes/engine.py:294`, `:297`) and `NextDraft[self.member]` inline in `render_next`
  (`:256`), and PLAN step 1 names that shape as the one the rooms family should mirror when it
  deletes `map_model`. An alias in one family and not the other re-opens the inconsistency the
  step closed. The extra lines are ruff's wrapping, not added logic.
- **"Read `draft.log[-1].exchanges` instead of `draft.exchanges()` in `depart`."** Refused. PLAN
  step 8 names `Game.exchanges()` as "the flat read" for exactly this, and the flat read is the
  correct one: when the current chapter is empty but earlier chapters are not — reachable, since
  `install` opens a fresh chapter — `log[-1].exchanges` yields `""` and silently drops the
  player's words. The saving is one tuple build per scene change, not per turn.

### Known and accepted

- A rooms player who never triggers MORE_MAP has one chapter for the whole game, capped at
  `exchanges[-20:]`. Scene engines have the same gap inside one long scene.
- The worldsmith can no longer author an already-dead or zero-HP NPC entity; a corpse belongs in
  the place's `description`. The shipped `buried-keep` map has 3 npcs, all alive, all HP > 0, none
  sheeted, so nothing migrates.
- `CROSSING` renders `They asked for this: ""` when `depart` runs on a game with no exchange at
  all. Unreachable in play — a departure always follows a player turn — and the guard exists
  because `tests/core/test_golden_turn.py:56` calls `advance` on a freshly begun game.
- Broadening the loner3e screen to the whole cast can refuse master text that happens to contain
  an unmet entity's name innocently. A refusal is a message the master reads and rewrites; the
  sheet row it would otherwise write is permanent.
