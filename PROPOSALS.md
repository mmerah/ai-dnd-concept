# PROPOSALS — memory, the job arc, and a game master who can ask for more

Six issues seen in the role trace of 2026-09-03 (four campaigns played through the real code
with scripted roles). Each entry: what the code does today, verified; the options; a
recommendation; the questions to settle together. High level by design: a settled entry becomes
a plan phase. Nothing here is decided except where marked.

## The rule the recommendations follow

**A role decides only from what it reads, so what it reads must be whole and true.** A prompt
that leaves something out to be shorter or faster makes the role guess, and a guess is a
wrong decision made politely. Prompt size and spawn time are costs to note, never a reason to
pick an option. Where two options differ only in how much a role knows, the one that knows more
wins.

Facts that bound every option: the tool cap is fifteen per engine (tools plus `change_world`
arms, party arms not counted), 24XX sits at fifteen today and Breathless at thirteen; the master
spawn times out at 300 s and the worldsmith at 900 s; an engine stays under 2,000 lines.

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

- A. **The whole campaign is the history, told at three depths.** `scenes()` returns every run
  since the campaign began: the current scene and the one before it whole (the existing
  `SCENE_EXCHANGES` window), every other scene of the current job as its recap, every closed
  job as one block (its summary from proposal 2, then its scenes' titles) and every hub visit as
  its recap. Nothing that happened is absent; only the depth changes with distance. One
  renderer, `render_history`, gains a third depth.
- B. **Hub visits are one running scene.** `job_runs()` for a hub visit returns every hub run
  plus the jobs between them as their summaries. Whole at the hub, but on a job the hub visits
  and the earlier jobs still drop out.
- C. **A fixed window of N runs regardless of jobs.** Simplest, and the one that loses the most:
  a long job pushes its own start out again.

**Recommendation.** A. The hub and the earlier jobs are the campaign's memory, and the master
deciding a hub turn without the job it just closed is the case the trace caught. Open question:
whether the worldsmith reads the same depths or the whole thing unwindowed when it writes the
next scene (it has 900 s and the most to gain from the earlier jobs' cast and debts).

## 2. Jobs so far is a debrief for the player, not a memory for the master

**Today.** `Campaign.ledger()` prints per closed job: title, place, the `debrief` (one
paragraph the worldsmith writes in the second person for the player's card), "(left open)" and
the terms. The scene recaps written during the job (`NextDraft.recap`) exist on the runs but no
role reads them once the job closes. The last scene of a job never gets a recap: `ReturnDraft`
has no `recap` field, and Tunnel Goons writes none anywhere. So a closed job survives as one
player-facing paragraph, written by a role that reads the job through the same two-scene
window.

**Options.**

- A. **The worldsmith writes the job's summary at the return, from the whole job.** A
  `summary` field on both `ReturnDraft`s, master-facing (third person; what was done, what was
  left undone, who was met and how it stands with them, what is owed, what was learned and what
  is still hidden), stored on `Job`, read by the master and the worldsmith. The return prompt
  carries the whole job unwindowed under THIS JOB: every scene's exchanges and every fact trace,
  hidden ones included, since the worldsmith writes hidden canon anyway. The debrief stays the
  player's card. Each `ReturnDraft` also carries a `recap` for the scene being left, so no scene
  is ever without one. Tunnel Goons gets recaps per place the same way.
- B. **A narrator spawn summarises the job at the close.** The narrator reads told facts only,
  so its summary cannot hold what the player has not found; the master would read a memory with
  the secrets cut out. The maintainer decided "no summarizer role" on 2026-09-02 (`NEXT-SPECS.md`
  decision 2); this reopens it for a weaker result.
- C. **Concatenate the scene recaps** into the ledger line. Free, but the last scene has no
  recap, Tunnel Goons has none, and the recaps were written for the next scene, not for the
  ledger.

**Recommendation.** A. The summary is written by the role that reads everything, from
everything. Question: whether the summary is one paragraph or a fixed shape (done, undone,
people, debts, hidden), which the ledger and proposal 3 could then read field by field.

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

- A. **A re-taken job is the same `Job`, reopened.** `Job` records its attempts (the run index
  each one started at). `job_runs()` for a reopened job returns the earlier attempt's runs at
  their depth (proposal 1) and the new ones whole; the earlier attempt's summary (proposal 2)
  sits under THE JOB. The worldsmith's `JobDraft` reads the earlier attempt whole in SCENES SO
  FAR and writes the scene where it picks up. For Tunnel Goons the same region is the job again
  and the new region joins it, not the tavern.
- B. **Keep new-job-per-attempt, feed the earlier attempt's summary** under a "THIS JOB BEFORE"
  section. The ledger keeps one line per attempt and the two attempts stay two jobs to every
  role, which they are not to the player.
- C. **The worldsmith updates instead of rewriting:** for a reopened job, the draft lets it
  re-file cast and places with changes. This is the "more agentic worldsmith" reading; it touches
  the bars (`scene_refusal`, the map bars) and the install, and it is the natural next step once
  A holds.

**Recommendation.** A, and C as the follow-up once A is played. B keeps a split the player does
not see. Question: should the board mark an offer "left open" so the player knows it is a
return, and should the offer's pitch be rewritten by the return draft to say where it stands.

## 4. The crossing narrator reads nothing on a job's first scene and on the return

**Today.** `GameService._grow` narrates the crossing after `advance` installed the new run.
`told_narration(engine.scenes(draft))` now sees the new job's runs only (or the new hub run
only), both empty, so WHAT THE PLAYER HAS READ is "(nothing yet)" while CROSSING says "The
player is leaving WHAT THE PLAYER HAS READ for the place in SCENE". Confirmed in the trace at
both Take-a-job and Go-home for all three scene engines. Inside a job, Go on works because the
scene left is still in the window. The opening spawn (`OPENING`) is correct: nothing was read.

**Options.**

- A. **`scenes()` never opens on an empty run**: a window that would start on a run with no
  exchanges includes the run before it. Fixes every reader at once and gives the master the
  last hub exchanges on a job's first turn, which it should have. Subsumed by 1A, where the
  earlier runs are always present.
- B. **Narrate the crossing from the pre-install draft's history.** `_grow` takes the told
  narration before `advance` and hands it in. Fixes the narrator alone; the master's first turn
  in the new scene still opens blind.

**Recommendation.** A, and it falls out of 1A. Also reword CROSSING to name the place left
rather than a section. Do this with proposal 1 in the same phase.

## 5. Does the worldsmith design a job for several scenes? — settled: A

**Today.** `ONE_SHOT_OPENING` says the cast is "the adventure's people and things, not the
scene's: write who is met here and who the player will meet farther in". `TAKE_BRIEF` asks for
the job's first scene and its `job` terms, nothing about what lies beyond. `worldsmith.md`
opens with "You write the next scene". No draft has a field for what is planned and not yet
shown; the only forward canon is the cast (with `known=False` entries) and the `job` terms.
`SURPRISE` asks to recombine what exists. So a job's shape lives in the worldsmith's head for one
spawn and in cast briefs after that.

**Decision (maintainer, 2026-09-03): option A.** A hidden `arc` on the job: `JobDraft.arc` (and
`SceneDraft.arc` for one-shots), a few lines of what the job holds beyond this scene, master-
and worldsmith-facing, never the player's. Stored on `Job` (or `SceneCanon`), read by the master
under THE JOB and by the worldsmith under WHAT COMES NEXT, rewritable by each `NextDraft` so it
follows play. `TAKE_BRIEF` says the scene is the first of several. The master reads it: it
decides with the whole picture, and the rule that it narrates nothing already keeps the arc off
the player's screen.

Options kept for the record: B, instruction only, carries nothing between spawns; C, author the
whole job up front, fights "the player's own words build the next scene".

## 6. A game master who can ask the worldsmith for more

**Today.** The master changes the world only through engine tools on the draft. `enter` needs
an existing cast id; there is no way to introduce anyone. The worldsmith runs only in `author`
and `advance`. Tool calls are synchronous rules code on a candidate copy (`Turn._apply`), under
the runtime lock, inside a master spawn that times out at 300 s. A worldsmith spawn is measured
at minutes. The design rules say the worldsmith writes cast entries and the master plays
through tools that mutate the draft.

**Options.**

- A. **`commission`, fulfilled now.** The master calls one shared tool with a `brief` and a
  `kind` (person, thing, rumour, place; for Tunnel Goons a place is a region). The tool answers
  "waiting on the worldsmith" and the turn suspends the way a pending decision does
  (`Game.pending` with a `worldsmith` kind, no player input). The service spawns the worldsmith
  with a small draft model (a cast entry, a rewritten brief, a region) and the existing refusal
  bar, installs the answer, then re-spawns the master with the new entry under HERE / THE WHOLE
  CAST and the commission's answer under NOTES FROM THE RULES. The master that continues the
  turn knows exactly what it asked for and got. The player sees a "Worldsmith is working" step.
  New: a second suspension kind in `Turn`, a draft model per kind, a re-spawn path in
  `GameService.play`.
- B. **`commission`, filled at the next scene write.** The same tool; the request lands as a
  fact and a note, the next worldsmith prompt carries "THE GAME MASTER ASKED FOR" and the bar
  requires it met. This is the "save for later" form: the thing exists from the next scene on.
  It cannot bring anyone into the current scene.
- C. **The master writes the entry itself**, an `introduce` arm with name, brief and the sheet
  fields the rules allow. Retires the rule that the worldsmith writes cast; the master's picture
  becomes a source of canon; small models flood the cast.

**Recommendation.** A, with B as the `later: true` flag on the same tool rather than a second
tool. A master that needs someone now should get them now, written by the role that writes
people, with the whole cast and history in front of it. Questions: the cap is raised by one
for a platform tool, or `commission` is counted apart from engine tools; what the master may
commission besides people (a rumour is a cast entry with no body; a place is a scene write); how
a commission is refused when it contradicts the arc.

## What to settle first

1. Proposals 1 and 4 change what every role reads and share one renderer: one phase, golden
   prompts regenerated.
2. Proposals 2A (the summary and the recap on the return) and 5A (the arc, decided) are fields
   on the return and job drafts and sections in the prompts: one phase, after 1.
3. Proposal 3A reads 1 and 2; proposal 6A is its own phase (`Turn`, `GameService`, a draft
   model, the UI step). Both wait on the decisions above.
