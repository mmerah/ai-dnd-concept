# PROPOSALS — memory, the job arc, and a game master who can ask for more

Six issues seen in the role trace of 2026-09-03 (four campaigns played through the real code
with scripted roles). Each entry: what the code does today, verified; the options; a
recommendation; the questions to settle together. High level by design: a settled entry becomes
a `PLAN.md` phase. Nothing here is decided.

Counts that bound every option: the tool cap is fifteen per engine (tools plus `change_world`
arms, party arms not counted) and 24XX sits at fifteen today, Breathless at thirteen; the master
spawn times out at 300 s, the worldsmith at 900 s; an engine stays under 2,000 lines.

## 1. Recent play is the current job only, and the hub is not a job

**Today.** `SceneWorld.scenes()` and `RoomWorld.scenes()` render `job_runs()`: in a campaign,
the runs since the open job's `started`, or only the hub's last run when no job is open
(`Campaign.since_start`, `engines/hub.py`). One-shots render every run. So the master, the
narrator and the worldsmith all read the same window:

- at the hub: the last hub visit only; the job just closed is gone, the hub visit before it is
  gone;
- on a job: the job's scenes, the last two whole, older ones as a recap or a three-exchange
  tail; the hub visit that took the job is not there (its content survives only as the
  `JobDraft.recap`, which is filed on the hub run and never shown again once the job starts).

The window was chosen so a long job keeps its start (README). It was not chosen to drop the
hub. The trace shows the master at the second hub visit with RECENT PLAY = the arrival
narration alone, and JOBS SO FAR = one debrief paragraph.

**Options.**

- A. **Hub visits are one running scene.** `job_runs()` for a hub visit returns every hub run
  plus the job runs between them as recaps (option 3 below writes those recaps). The hub reads
  like a scene the player keeps coming back to; a job reads like an excursion. Cheap: one
  method, no new shape.
- B. **A fixed window of N runs regardless of jobs.** Simplest, but a long job would push its
  own start out again, which the current rule exists to prevent.
- C. **Keep the window, add a "LAST TIME AT HOME" section** at the hub: the previous hub visit's
  recap. Least change, least memory.

**Recommendation.** A. It uses `render_history`'s existing recap path and gives every role the
same picture. Open question: does the hub's own run get a recap when the player leaves it (today
`JobDraft.recap` is that, filed on the hub run, so yes for scene engines; Tunnel Goons has no
recaps at all, see 3).

## 2. Jobs so far is a debrief for the player, not a memory for the master

**Today.** `Campaign.ledger()` prints per closed job: title, place, the `debrief` (one
paragraph the worldsmith writes in the second person for the player's card), "(left open)" and
the terms. The scene recaps written during the job (`NextDraft.recap`) exist on the runs but no
role reads them once the job closes. The last scene of a job never gets a recap: `ReturnDraft`
has no `recap` field, and Tunnel Goons writes none anywhere. So a closed job survives as one
player-facing paragraph.

**Options.**

- A. **The worldsmith writes the job's summary at the return**, as it writes the debrief: a
  `summary` field on both `ReturnDraft`s, master-facing (third person, the facts, what was left
  undone, who was met, what is owed), stored on `Job`, printed in JOBS SO FAR instead of the
  debrief. The debrief stays the card. One more field, no new spawn; the return prompt already
  holds THIS JOB / SCENES SO FAR whole.
- B. **A narrator spawn summarises every exchange of the job at the close.** Accurate to what
  the player read, but the narrator's input is the told half only and a second spawn on every
  return costs a minute. The maintainer decided "no summarizer role" on 2026-09-02
  (`NEXT-SPECS.md` decision 2); this reopens it.
- C. **Concatenate the scene recaps** into the ledger line. Free, but the last scene has no
  recap and the recaps were written for the next scene, not for the ledger.

**Recommendation.** A, with the `ReturnDraft` also carrying a `recap` for the scene being left
so option C's gap closes too. Question: how long may the ledger grow before older jobs are cut
to a line? Ten jobs of one paragraph is about 2,000 words in every master prompt.

## 3. Leaving a job open, and taking it again

**Today, scene engines.** Going home with the question open needs `next_scene` first
(`ready()` requires `run.left` or the hub), then the return closes the job with `finished =
False`: ledger shows "(left open)" and the terms; the offer normally stays on the board
(`RETURN_BRIEF`). Taking it again appends a **new** `Job` with a new `started`; the old runs
are not part of `job_runs()`, so RECENT PLAY starts fresh. `TAKE_BRIEF` tells the worldsmith an
offer taken before "opens at the place its JOBS SO FAR line names, with its cast and its terms";
THE WHOLE CAST carries "last seen in: <scene>" lines. Continuity is prose only: the debrief, the
terms, the cast's last-seen lines. Nothing marks which scenes belonged to the first attempt.

**Today, Tunnel Goons.** The dungeon stays on the map with its ways from the tavern; `JOB_BRIEF`
asks for "the part not yet walked" as a new region. The old region is still walkable but no
longer the job's. Same ledger behaviour.

**Options.**

- A. **A re-taken job is the same `Job`, reopened.** `Job` gains `attempts` (or `runs` indices);
  `job_runs()` for the reopened job returns the earlier attempt's runs as recaps then the new
  ones whole. The worldsmith writes a `JobDraft` whose recap is the hub visit, as today, and
  reads the earlier attempt in SCENES SO FAR. No new prose shape; proposal 2A's summary covers
  the gap between attempts.
- B. **Keep new-job-per-attempt, feed the earlier attempt's summary** (2A) to both roles under
  a "THIS JOB BEFORE" section. Smaller; the ledger keeps one line per attempt.
- C. **The worldsmith updates instead of rewriting:** for a reopened job, the draft model lets
  it re-file cast and place with changes. This is the "more agentic worldsmith" reading; it
  touches the bars (`scene_refusal`, the map bars) and the install.

**Recommendation.** B now, A when the summary exists and is read; C only if B's prose proves
too thin in play. Question: should the board mark an offer "left open" so the player knows it is
a return?

## 4. The crossing narrator reads nothing on a job's first scene and on the return

**Today.** `GameService._grow` narrates the crossing after `advance` installed the new run.
`told_narration(engine.scenes(draft))` now sees the new job's runs only (or the new hub run
only), both empty, so WHAT THE PLAYER HAS READ is "(nothing yet)" while CROSSING says "The
player is leaving WHAT THE PLAYER HAS READ for the place in SCENE". Confirmed in the trace at
both Take-a-job and Go-home for all three scene engines. Inside a job, Go on works because the
scene left is still in the window. The opening spawn (`OPENING`) is correct: nothing was read.

**Options.**

- A. **Narrate the crossing from the pre-install draft's history.** `_grow` takes the told
  narration before `advance` and hands it in; `render_narrator` gets a `read` argument instead
  of computing it. Smallest fix, no shape change.
- B. **`scenes()` for a run with no exchanges includes the run before it**, so the window never
  opens empty. Fixes every reader at once but changes RECENT PLAY for the master's first turn in
  a scene too (arguably right: the master then sees how the player arrived).
- C. Solved by 1A for the hub side only.

**Recommendation.** B: one rule in `job_runs()` ("a window never starts on an empty run"),
which also gives the master the last hub exchanges on a job's first turn. A as the fallback if
B widens the master's window unacceptably. Also reword CROSSING to name the place left rather
than a section.

## 5. Does the worldsmith design a job for several scenes?

**Today.** `ONE_SHOT_OPENING` says the cast is "the adventure's people and things, not the
scene's: write who is met here and who the player will meet farther in". `TAKE_BRIEF` asks for
the job's first scene and its `job` terms, nothing about what lies beyond. `worldsmith.md`
opens with "You write the next scene". No draft has a field for what is planned and not yet
shown; the only forward canon is the cast (with `known=False` entries) and the `job` terms.
`SURPRISE` asks to recombine what exists. So a job's shape lives in the worldsmith's head for one
spawn and in cast briefs after that.

**Options.**

- A. **A hidden `arc` on the job**: `JobDraft.arc` (and `SceneDraft.arc` for one-shots), two
  to four lines of what the job holds beyond this scene, master- and worldsmith-facing, never
  the player's. Stored on `Job` (or `SceneCanon`), printed under THE JOB for the master and
  under WHAT COMES NEXT for later scene writes, rewritable by each `NextDraft`. One field, one
  section, both bars unchanged.
- B. **Instruction only**: tell the worldsmith to write the first scene "as the first of
  several" and to file the later cast now. Free, and probably what the opening already does;
  nothing carries the plan between spawns.
- C. **Author the whole job up front** (several scenes), as Tunnel Goons authors the whole
  dungeon. Costs minutes per job and fights "the player's own words build the next scene".

**Recommendation.** A, with B's sentence in `TAKE_BRIEF`. The arc is also what proposal 6
needs the game master to read before it asks for anything. Question: does the master see the
arc, or only the worldsmith? Seeing it lets the master foreshadow; it also tempts it to narrate
what has not been written.

## 6. A game master who can ask the worldsmith for more

**Today.** The master changes the world only through engine tools on the draft. `enter` needs
an existing cast id; there is no way to introduce anyone. The worldsmith runs only in `author`
and `advance`. Tool calls are synchronous rules code on a candidate copy (`Turn._apply`), under
the runtime lock, inside a master spawn that times out at 300 s. A worldsmith spawn is measured
at minutes. The design rules say the worldsmith writes cast entries and the master plays
through tools that mutate the draft.

**Options.**

- A. **`commission`: a request, filled at the next scene write.** One shared tool (or a
  `change_world` arm) with a `brief` and a `kind` (person, thing, rumour, place). It lands as a
  fact and a note; the next worldsmith prompt carries "THE GAME MASTER ASKED FOR" and the bar
  requires the request met (a new cast entry whose brief answers it). Nothing spawns mid-turn;
  no lock held; the narrator says nothing until the thing exists. Costs one tool everywhere:
  24XX goes to sixteen unless the cap counts platform tools apart from engine tools.
- B. **`commission` fulfilled now, mid-turn.** The tool returns "waiting on the worldsmith",
  the turn suspends like a pending decision (`Game.pending` with a `worldsmith` kind), the
  service spawns the worldsmith with a small `CastDraft` model and the existing refusal bar,
  installs it, and re-spawns the master with the new entry under HERE / THE WHOLE CAST. The
  master's spawn never blocks; the player sees a "Worldsmith is working" step in the turn.
  Larger: a new suspension kind in `Turn`, a new draft model and bar, a re-spawn path.
- C. **The master writes the entry itself**, a `introduce` arm with name, brief and the sheet
  fields the rules allow. Fastest and cheapest, but it retires the rule that the worldsmith
  writes cast and the master's picture is not the source; small models would flood the cast.

**Recommendation.** A first: it fits the seam (a fact, a note, a prompt section, a bar line),
costs no spawn, and gives the worldsmith a reason for the new entry. B is the same tool with a
second delivery path, added only if "next scene" proves too late in play. The rewrite-a-brief
case is already the worldsmith's (an id re-filed in `cast` rewrites the brief); "save for later"
is the same request with `known=False`. Questions: is the cap raised by one for a platform tool,
or does `commission` replace something; does a request expire; may the master commission a
place, which for Tunnel Goons is a region.

## What to settle first

1. Proposals 1 and 4 change what every role reads and cost no new shape: do them together, one
   phase, golden prompts regenerated.
2. Proposal 2A (the summary at the return) and 5A (the arc) are one field each on the return and
   job drafts; one phase.
3. Proposal 3 and 6 wait on 2 and 5, and each needs a decision above before it is planned.
