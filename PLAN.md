# PLAN — the memory, the job arc, and a game master who can ask for more

Two phases, in order: the memory, then `commission`. The six decisions of PROPOSALS.md
(2026-09-03) land here: 1A and 4A (the whole campaign at three depths, the crossing named),
2A (the summary and the recap at the return), 5A (the arc), 3A (a re-taken job is the same job)
in Phase 1, one stored-shape change; 6A (`commission`, now or `later`) in Phase 2. Self-standing:
an implementer needs this file, `CLAUDE.md` and the code. `NEXT-SPECS.md` stays for Track G.

The rule every step follows: a role decides only from what it reads, so what it reads must be
whole and true. Prompt size and spawn time are costs to note, never a reason to drop a section.
Not in this plan: 3C, the worldsmith updating cast and places instead of rewriting them, is the
follow-up once 3A has been played.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step.** Tests must be green. Change a shape and
   update its tests in the same step. One test per new behaviour; no test of prose or wiring.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of every step that
   changes a stored shape or a prompt:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. Each phase below names exactly which fixtures may change and
   how. Anything else is a bug. The shipped `scenarios/*/world.json` and `characters/kael/*.json`
   have no regen: a step that changes their stored shape rewrites them with a throwaway script
   in the scratchpad, never committed. Neither phase below changes them: every new field on a
   canon or a sheet has a default.
4. **Saves have no version field.** Phase 1 changes `Job`, `SceneRun`, `Visit`, `SceneCanon`
   and `SceneWorld`; a save from before it is stale and is skipped with the launcher's warning.
   Phase 2 adds `Game.commissions` with a default, so its saves stay readable. Say this once,
   in the Phase 1 commit message.
5. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never pad.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive at a commit.
9. **Review each phase adversarially against its staged diff before the commit.**
10. **The standing limits hold.** Fifteen engine tools per engine, counted as tools plus
    `change_world` arms, the two party arms not counted; Phase 2 adds `commission`, a platform
    tool outside that count. Every `engines/<id>/` stays under 2,000 lines (`engines/scenes/`
    and `engines/rooms/` too); imports flow `core <- engines <- turn <- app <- ui`; no `Any`
    beyond the `Game[P]` bound; every `__init__.py` empty; tests never start a process
    (`ScriptedSpawner`).
11. **A rename is a rename.** A step that deletes, moves or re-signs a name lists in its brief
    every file `grep -rln <name> src tests` returns; the orchestrator runs the grep, the
    implementer does not explore.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`93b4cf7`) | | 8,659 |
| 1 — the memory | `ChapterRecord` and the third depth in `render_history`; `render_whole`; every fact filed on the exchange; `Attempt`, `Job.summary`, the reopened job; `summary` and `recap` on both return drafts; `arc` on the scene drafts and the world; the crossing named; the bar on every player-facing return field | 8,900 to 8,980 |
| 2 — commission | `Commission` on the game; `commission` on every engine from the seam; the suspended turn, the worldsmith spawn and the re-spawned master in `GameService.play`; `CastDraft`, `NpcDraft`, `ItemDraft`; `later` met at the next write | 9,150 to 9,250 |

---

## Phase 1 — the memory

One commit: every step below changes a stored shape or what a role reads; a save from before it
is stale.

### 1.1 The history at three depths

1. `core/play.py`: after `SceneRecord`, add
   ```python
   class ChapterRecord(Frozen):
       """A closed stretch of scenes read back as one block: its summary, then its scenes' titles."""

       title: str
       verdict: str  # "done" or "left open", as the ledger says it
       summary: str
       scenes: tuple[str, ...]


   type HistoryRecord = SceneRecord | ChapterRecord
   ```
   `SceneRecord` keeps its four fields.
2. `core/views.py`: `render_history(records: Sequence[HistoryRecord])`. `_block` gains the
   chapter case, printed as
   `CLOSED: {title} ({verdict})\nwhat happened: {summary}\nscenes: {'; '.join(scenes)}`; the
   scene case is unchanged (the last two records whole, older ones recap or tail). The "not
   started yet" check reads the `SceneRecord`s only. `told_narration(records)` reads the
   exchanges of the `SceneRecord`s among the last two records. Add
   ```python
   def render_whole(scenes: Sequence[SceneRecord]) -> str:
       """Every exchange and every fact, told or not: what the worldsmith reads to sum a job up."""
   ```
   printing, per scene, the `SCENE:` header, then per exchange `> {prompt}`, one `- {trace}`
   line per fact, then the narration. `tests/core/test_views.py`: one test that a chapter prints
   its summary and titles and none of its exchanges; one that `render_whole` prints a fact the
   narrator never told.
3. `engines/seam.py::Engine.close` files `facts=tuple(facts)`: every fact rides on the exchange,
   because `render_whole` needs the hidden ones. `core/play.py::Exchange.facts` gets the one-line
   comment "every fact, told or not; `cards` picks the player's". `ui/game.py::GamePage.chat`
   iterates `cards(exchange.facts)`. `grep -rn "\.facts\b" src` finds no other reader.
   `Engine.scenes` returns `tuple[HistoryRecord, ...]`; `turn/context.py::render_master` and
   `render_narrator` take `Sequence[HistoryRecord]`; `SceneEngine.scenes` and `RoomEngine.scenes`
   follow (their bodies change in 1.3 and 1.4).
4. The crossing names the place left (4A). `engines/seam.py::Engine.crossing(self, state: G,
   pursuit: str) -> str | None`; `SceneEngine.crossing` returns
   `CROSSING.format(left=self.world(state).run.title, pursuit=pursuit)`;
   `scenes/worldsmith.py::CROSSING` opens with "The player is leaving {left} for the place in
   SCENE." and keeps the rest. `app/runtime.py::GameService.play` computes
   `brief = self.engine.crossing(self.state, answer.text) if moving_on else None` (the state
   before the turn is the scene being left). `tests/core/test_master_tools.py::_SilentEngine.crossing`
   takes the state.

### 1.2 The job

1. `engines/hub.py`: add, before `Job`,
   ```python
   class Attempt(Mutable):
       """One walk out on a job; a job left open and taken again has several."""

       started: int | None = None  # index of the first run or visit away from the hub
       returned: int | None = None  # index of the hub run or visit that closed it
   ```
   with a validator refusing `returned` at or before `started`. `Job` replaces `started` with
   `attempts: list[Attempt] = Field(default_factory=list)`; `debrief: str = ""` (the last
   return's card, kept on a reopen); gains `summary: str = ""` (the worldsmith's, for the master
   and itself); properties `open` (the last attempt exists and is unreturned) and `walking`
   (`open` and that attempt has `started`); `begin(started: int | None) -> None` appends an
   `Attempt`; `close(returned: int, debrief: str, summary: str) -> None` sets the last attempt's
   `returned` and the two texts. `Job.closed()` is unchanged. `grep -rn "started\b" src tests`
   lists every site the next steps rewrite: `scenes/world.py`, `rooms/world.py`,
   `rooms/engine.py`, and the tests named in 1.2.3, 1.3.6, 1.4.5.
2. `Campaign`: `_jobs_in_order` refuses an open job that is not the last, a `finished` job or a
   job with a `debrief` that has no attempt with `started`, and an attempt other than the last
   without `returned`. `check_walked(walked)` checks every `started` and `returned` below
   `walked`. `open_job()` is the last job when `open`; `closed_jobs()` the ones not open;
   `finished` and `terms()` as today. Add `returns() -> int` (attempts with `returned`),
   `job_at(index: int) -> Job | None` (the job with an attempt where `started <= index` and
   `returned` is `None` or above `index`), `job_records(records: Sequence[SceneRecord]) ->
   tuple[SceneRecord, ...]` (the open job's, over every attempt),
   `history(records: Sequence[SceneRecord]) -> tuple[HistoryRecord, ...]` (a closed job whose
   records all lie before the last two becomes one `ChapterRecord`: title, `"done"` or
   `"left open"`, summary, its records' titles; every other record stands, hub visits included),
   `records_of(job: Job, records: Sequence[SceneRecord]) -> tuple[SceneRecord, ...]` (that
   job's, over every attempt; `job_records` is `records_of` on the open job),
   `taken(intent: str) -> Job | None` (the left-open job the intent names: the page's
   `TAKE_JOB` line, or its title in the player's own words, case-folded),
   `left_open(title: str) -> Job | None` (a closed, unfinished job whose title matches case-folded),
   `reopen(job: Job, started: int | None) -> None` (move it to the end of `jobs`, `finished =
   False`, `begin(started)`), `swap_out() -> None` (drop the open job's unwalked attempt; a job
   with no attempt left goes with it). `since_start` reads the walking attempt's `started`, else
   the last run. `ledger()` prints `- {title} ({place}): {summary}{open_suffix}` and the terms
   line as today; `job_row()` prints the terms, then `so far: {summary}` when the open job has
   one (the reopened job's earlier attempt, 3A). `board_lines()` and `board_rows()` append
   `OPEN_SUFFIX` to an offer `left_open` names; the pitch is not rewritten. `MIN_RECAP = 60`
   moves here from `scenes/drafts.py`; add `MIN_SUMMARY = 120`. Add
   `named_unmet(text: str, names: Iterable[str]) -> list[str]`, the multi-word rule of
   `scenes/worldsmith.py::named_in` (case-folded, a name with a space in it), so both bars use
   one rule.
3. `engines/hub.py` prose. `TAKE_BRIEF` says the scene is the first of several and that an offer
   marked "(left open)" is a job taken before: title the scene exactly as the offer, open it
   where the job stands (its summary is in JOBS SO FAR), restate its `job`, write its `arc` from
   what is still undone. `RETURN_BRIEF` adds: THIS JOB is the whole job, hidden facts included;
   `summary` and `recap` are written from it for the game master, `debrief` for the player.
   `tests/core/test_hub.py`: every `started=` becomes `attempts=[Attempt(started=..., returned=...)]`;
   `test_since_start_reads_the_open_jobs_walk_or_the_hubs_last` and the ledger test follow;
   new tests: `history` collapses a closed job before the last two and not one whose last scene
   is among them; `left_open` and `reopen` move the job last and keep its summary; `job_at`
   answers `None` for a hub index; the board marks a left-open offer.

### 1.3 The scene world and its drafts

1. `engines/scenes/drafts.py`: `RECAP = Field(min_length=MIN_RECAP, description=...)` (today's
   `NextDraft.recap` field, named once); `NextDraft.recap` and `ReturnDraft.recap` both use it.
   `SceneDraft.arc: str = Field(default="", description="A few lines on what lies beyond this
   scene, for the game master and for you, never the player: who waits farther in, what the job
   hides, how it can end. A one-shot's opening writes it; a campaign's hub leaves it empty.")`;
   `NextDraft.arc: str = Field(min_length=MIN_ARC, description=...)` overrides it (rewritten every
   scene so it follows play), `MIN_ARC = 60`. `ReturnDraft` gains `summary: str =
   Field(min_length=MIN_SUMMARY, description="One paragraph on the job, in the third person,
   for the game master and for you, never the player: what was done, what was left undone, who
   was met and how it stands with them, what is owed, what was learned and what is still
   hidden.")`. Every field of `SceneDraft`, `HubDraft` and `ReturnDraft` gets a description
   naming its reader (`title`, `question`, `situation`, `offers`, `debrief`: the player;
   `present`, `hidden`, `cast`, `recap`, `summary`, `arc`: the game master and the worldsmith).
   Above `class ReturnDraft`, one comment line: `# One answer, two readers: debrief, situation and
   question are the player's; summary, recap and arc are not. Leaks in play make this two spawns.`
   The two spawns PROPOSALS names, should it come to that: the summary first, then the debrief
   and the scene from the summary and the told history.
2. `engines/scenes/world.py`: `SceneCanon.arc: str = ""`; `SceneWorld.arc: str = ""`;
   `begin` copies it. PROPOSALS stores the arc on `Job` or `SceneCanon`; one live field on the
   world serves a one-shot and a campaign alike, the canon seeds it, and a closed job needs none
   (its summary says what is still hidden). Add `records() -> tuple[SceneRecord, ...]`, today's `scenes()` body over
   `self.runs`; `scenes()` returns `records()` when `campaign is None`, else
   `campaign.history(records())`. `job_runs()` stays (the Trail panel). `apply_scene`: the recap
   lands on the run left for `NextDraft | ReturnDraft`; `self.arc = draft.arc` always (an empty
   return clears it); a `JobDraft` whose `left_open(draft.title)` matches reopens that job with
   `started=len(self.runs)` and re-files `terms = draft.job`, else appends
   `Job(title, place, terms=draft.job, attempts=[Attempt(started=len(self.runs))])`; a
   `ReturnDraft` calls `job.close(returned=len(self.runs), debrief, summary)` before the board
   swap. `_consistent`: hub runs after the first equal `campaign.returns()`; every attempt's
   `started` names a run away from the hub and every `returned` a hub run.
3. `engines/scenes/worldsmith.py`: `scene_unmet` refuses a one-shot opening (`world is None`
   and not a `HubDraft`) with an empty `arc`. `_hub_unmet` checks `debrief`, `situation` and
   `question` of a `ReturnDraft` against every unmet cast entry (`known=False`, anywhere in the
   world), one refusal line per field; `named_in` calls `named_unmet`. Names are what a check
   can hold; a leak in prose is what the two-spawn fallback is for.
4. `engines/scenes/engine.py`: `master_sections` adds `("THE ARC (the player has not found
   this)", world.arc)` after HIDDEN HERE when `arc` is non-empty; its own section rather than
   a line under THE JOB, because a one-shot has no THE JOB. `render_next`: `history` stays
   `render_history(world.scenes())`, so the worldsmith reads the same three depths as every
   other role; the intent gains `\n\nThe arc as last written: {arc}. Rewrite `arc` so it
   follows what happened.` when the world has one; `hub` gains `("THIS JOB",
   render_whole(campaign.job_records(world.records())))` before `campaign.sections(...)` when
   the answer is a `ReturnDraft`, and `("THE JOB BEFORE", render_whole(campaign.records_of(job,
   world.records())))` when the answer is a `JobDraft` and `campaign.taken(intent)` finds a job
   (the earlier attempt whole, 3A). `opening_canon` copies `draft.arc`. `render_opening`'s
   intent for a one-shot says the opening writes `arc` (`ONE_SHOT_OPENING` in `hub.py` gains one
   sentence).
5. `engines/scenes/worldsmith.md`: the first line says a job is several scenes and `arc` is the
   plan for the ones not yet written; one sentence that `summary` and `recap` are the game
   master's memory and hold what the player has not found, and that `debrief` and `situation`
   never do. The three scene engines' `rules.md`, in "Campaigns": one sentence, "THE ARC is what
   the worldsmith planned beyond this scene: play toward it, and narrate none of it."
6. Tests: `tests/support/loner.py`, `tests/support/twentyfourxx.py`, `tests/support/breathless.py`
   `hub_world()` build `attempts=[Attempt(started=1)]`. Every `NextDraft` or `JobDraft` a test
   builds adds an `arc` and every one-shot opening built through `build_scenario` or
   `opening_canon` adds one too: `grep -rln '"recap"\|recap=\|build_scenario\|opening_canon' tests`
   lists the files. `tests/core/test_scenes.py` follows and
   gains: `scenes()` on a campaign with two closed jobs returns a `ChapterRecord` for the first
   and scene records for the second's last run; a reopened job's runs from both attempts are in
   `job_records`; `_consistent` refuses an attempt whose `returned` is not a hub run.
   `tests/loner3e/test_hub_play.py`, `tests/breathless/test_worldsmith.py`,
   `tests/twentyfourxx/test_worldsmith.py`: `_return_draft()` carries `recap`, `summary`; one
   test per engine that a `summary` naming an unmet cast member passes and a `situation` naming
   one is refused; `tests/twentyfourxx/test_worldsmith.py::test_write_next_picks_the_draft_the_moment_calls_for`
   asserts THIS JOB is in the return prompt and absent from the others.
   `tests/core/test_master_tools.py::test_the_worldsmith_is_shown_the_source_the_cast_and_what_actually_happened`
   asserts the arc line in WHAT COMES NEXT.

### 1.4 The room world and its drafts

1. `engines/rooms/world.py`: `Visit.recap: str = ""`. `records()` builds one `SceneRecord` per
   visit (title the place's name, question its brief, `recap=visit.recap`); `scenes()` returns
   `records()` or `campaign.history(records())`. `walked_job()` is the open job when `walking`.
   `move` off the hub calls `job.begin(len(self.visits) - 1)` when the open job is not walking.
   `attach(region, start, *, known, anchor: EntityId | None = None)`: the anchor is `current.id`
   when `None`. `_playable`: every attempt's `started` names a visit away from the hub and every
   `returned` a hub visit.
2. `engines/rooms/drafts.py`: `ReturnDraft` gains `summary` (the `MIN_SUMMARY` field of 1.3.1,
   the same description) and `recaps: dict[CheckedEntityId, Annotated[str,
   Field(min_length=MIN_RECAP)]]` described "one paragraph per place walked on this job, keyed
   by place id, for the game master and for you"; `debrief` and `offers` get descriptions
   naming the player. The same one comment line as 1.3.1 above `class ReturnDraft`.
3. `engines/rooms/worldsmith.py`: add `return_refusal(draft: ReturnDraft, world: RoomWorld[N,
   Any]) -> str | None`: the `recaps` keys are exactly the places of the walking attempt's
   visits; `debrief` names no unmet npc or item (`named_unmet` over their names). `JOB_BRIEF`
   adds: an offer marked "(left open)" is a job taken before; name the new region's start
   exactly as the offer; it joins the map at that job's own start, not the tavern, and holds
   only the part not yet walked.
4. `engines/rooms/engine.py`: `render_return`'s THIS JOB is
   `render_whole(campaign.job_records(world.records()))`; `render_job` adds `("THE JOB BEFORE",
   render_whole(campaign.records_of(job, world.records())))` when `campaign.taken(intent)` finds
   a job; `write_extension` asks the return with
   `lambda answer: return_refusal(answer, world)`. `install_extension` on a `ReturnDraft`:
   `job.close(returned=len(world.visits) - 1, debrief, summary)`, then `visit.recap =
   recaps[visit.place]` for every visit of the walking attempt, then the board. At the hub:
   `campaign.swap_out()` replaces the `jobs.pop()` line; when `campaign.left_open(start.name)`
   matches, `campaign.reopen(job, started=None)` and `world.attach(..., known=True,
   anchor=EntityId(job.place))`, else `Job(title=start.name, place=extension.start,
   attempts=[Attempt()])`.
5. Tests: `tests/tunnelgoons/test_tools.py`, `test_worldsmith.py`, `test_views.py` build
   `attempts=[Attempt(started=1)]` where they set `started=1` and assert
   `attempts[-1].started`; `test_worldsmith.py::RETURN` carries `summary` and `recaps`; new
   tests: a return whose `recaps` miss a walked place is refused; the recaps land on the
   attempt's visits; a left-open job taken again attaches the region at the job's start and
   reopens the same `Job`; swapping out a reopened, unwalked job leaves it closed.

### 1.5 The record

1. `README.md` line 27: the worldsmith writes a recap of each scene left and a summary of each
   job at the return; every role reads the whole campaign, the far parts as recaps and summaries.
   `NEXT-SPECS.md` decision 2 gains one sentence: the summary at the return and the three depths
   landed 2026-09-03; "no summarizer role" stands.
2. `AIDM_GOLDEN_REGEN=1 uv run pytest`, then `uv run pytest`, then read the diff: only the three
   scene engines' `prompts/<id>/master.txt` change, by the one `rules.md` sentence of 1.3.5
   (the golden turn is a one-shot with no arc, so no THE ARC section appears). `narrator.txt`,
   `schemas/*`, `turn/*` and `prompts/tunnelgoons/master.txt` are byte-identical.
3. `PROGRESS.md` entry.

### Done when

Green. Goldens as 1.5.2. `scenarios/` and `characters/` untouched and every one loads.
`grep -rn "started=\|\.started\b" src tests` finds only `Attempt`'s field and `attempts=[Attempt(`
sites; `grep -rn "debrief is None\|debrief is not None\|job_visits\b" src` finds nothing;
`grep -rn "since_start" src` finds `hub.py` and the two Trail panels only. `uv run aidm`, a
campaign in a scene engine: take a job, play two scenes, go home; the master's next hub turn
shows the job as recaps then whole, then after the next job opens as one CLOSED block, and JOBS
SO FAR prints the summary; the crossing narration after Take-a-job and after Go-home carries the
scene left under WHAT THE PLAYER HAS READ; leave a job open, come home, take it again: the board
says "(left open)", the Jobs panel keeps it while open, THE JOB carries "so far:". Tunnel Goons:
report in, the ledger prints the summary, every visited place has a recap. `src` 8,900 to 8,980;
`engines/scenes/` and `engines/rooms/` under 1,150 each.

---

## Phase 2 — commission

The master asks the worldsmith for something the picture lacks, written now or at the next
scene write. A tool call runs synchronously on a candidate under the runtime lock inside a
master spawn with a 300 s timeout, and a worldsmith spawn takes minutes, so the tool cannot
spawn: it suspends the turn, `GameService.play` spawns the worldsmith, installs, and spawns the
master again with what it asked for and what it got under NOTES FROM THE RULES.

The wait lives on `Game.commissions: list[Commission]`, a sibling of `Game.pending`, not a
`pending` kind: `pending` means the composer is the only way on (`ui/game.py::_can_type`,
`turn/context.py::_waiting`, `Exchange.decision` all read it as the player's), and a `later`
commission must survive to the next write, which a `pending` cannot. Every commission in the
list is shape-free (a kind name and a brief), so `core` stays world-blind.

The open question, how a commission that contradicts the arc is refused and who decides: nobody
refuses. No check can be written for a contradiction in prose, so the bar checks shape only; the
master reads THE ARC and commissions with it in view, and the worldsmith rewrites `arc` in the
same answer so the two agree. A refusal path would be a judgement call in a role, which the bar
rule forbids where the bar cannot hold it.

### 2.1 The platform tool

1. `core/play.py`: add
   ```python
   class Commission(Frozen):
       """What the game master asked the worldsmith for; `later` files it for the next scene write."""

       kind: str
       brief: str
       later: bool = False
   ```
   `core/model.py::Game.commissions: list[Commission] = Field(default_factory=list)` and
   `wanted() -> Commission | None`, the first with `later=False`. A save from Phase 1 still loads.
2. `engines/seam.py`: constants `COMMISSION = "commission"`, `COMMISSION_BRIEF` (the tool
   description: ask the worldsmith for what the scene needs and the cast lacks; written now, the
   turn pauses and you are spawned again with the answer under NOTES FROM THE RULES; `later`
   has it written into the next scene; read THE ARC first, what you ask for becomes canon),
   `WORLDSMITH_WAIT = "the worldsmith is writing what you asked for. Stop here and exit; you
   will be spawned again with the answer."`. `Engine.__init__` builds
   `tools = (*self.master_tools(), self.commission_tool())`. Concrete
   ```python
   def commission(self, draft: G, kind: str, brief: str, *, later: bool) -> list[Fact]:
       """Refused while one waits; a `later` one is a note until the next write meets it."""
   ```
   appending `Commission(kind=kind, brief=brief, later=later)` and returning one untold fact,
   kind `commission_asked`, trace "waiting on the worldsmith for a {kind}: {brief}" or "the
   worldsmith will write a {kind} into the next scene: {brief}"; a `later` one also
   `draft.note`s that trace, so the next turn's master knows what is on order. Abstract
   `commission_tool(self) -> MasterTool[G]` and
   ```python
   async def fulfil(self, draft: G, asked: Commission, worldsmith: WorldsmithAnswer) -> Play[G]:
       """Ask the worldsmith from the draft as it stands; the install comes back to run under the turn's gate."""
   ```
   (`Play` from `core/tools.py`). `tests/core/test_seam.py::FifthEngine` and
   `tests/core/test_rooms.py::SixthEngine` inherit both from their bases (2.2, 2.3) and their
   tests assert `"commission" in engine.tools`.
3. `turn/run.py`: `COMMISSIONS_PER_TURN = 1` (a bound on the re-spawn loop, not a design
   choice); `Turn.commissioned: int = 0`. `Turn.call` answers `WORLDSMITH_WAIT` to every tool
   while `self.draft.wanted()` is set (a plain answer, as the pending case is), and refuses
   `COMMISSION` once `commissioned` reaches the bound with "one commission per turn: play on
   with what you have". `Turn.apply` appends `- {WORLDSMITH_WAIT}` when the call left
   `wanted()` set where it was `None`. `tests/core/test_turn.py`: a commission answers the wait
   line and the next call answers it too; a second commission in one turn is refused.
4. `app/runtime.py::GameService.play`: after `_act(turn)`,
   ```python
   while (asked := turn.draft.wanted()) is not None:
       await self._fulfil(turn, asked)
       self.phase = "master"
       await self._act(turn)
   ```
   before the narrator. `_fulfil(turn, asked)`: `phase = "worldsmith"`; `play = await
   self.engine.fulfil(turn.draft, asked, _worldsmith(self.spawner))` then `landed =
   turn.apply(play)`; on `(OSError, Refusal)` log a warning, `turn.draft.commissions.remove(asked)`
   and `landed = "it could not be written; play on without it"`; then
   `turn.draft.note(f'You asked the worldsmith for a {asked.kind}: "{asked.brief}". Answered:\n{landed}')`
   and `turn.commissioned += 1`. The re-spawned master reads the note under NOTES FROM THE
   RULES and the new entry under HERE or HIDDEN HERE once it brings it in. The `_STEP_COPY`
   ticker shows "Worldsmith" during the wait (2.4.2).
   `tests/core/test_game_service.py`: a scripted master that commissions, a scripted worldsmith
   answer, and a second master spawn whose prompt carries the note and the new id; a worldsmith
   that fails leaves the turn playable and the note says so.

### 2.2 The scene engines

1. `engines/scenes/tools.py`: `SceneCommission(Frozen)`: `kind: Literal["person", "thing",
   "rumour"]` (each a cast entry), `brief: str = Field(min_length=20, description=...)`,
   `later: bool = Field(default=False, description=...)`; every field described.
2. `engines/scenes/drafts.py`: `CastDraft[C: Person](Frozen)`: `cast: dict[EntityId, C] =
   Field(min_length=1, max_length=1, description="One entry under its own id. A new id is a
   new person, thing or rumour, unmet; an id already in THE WHOLE CAST re-files that entry's
   brief and nothing else.")` and `arc: str = Field(default="", description="Rewritten only
   where it must bend to hold the new entry; empty keeps it.")`.
3. `engines/scenes/worldsmith.py`: `COMMISSION_ASK` (the intent: the game master asked for a
   {kind}: {brief}; write that one entry, or rewrite one brief, and nothing else).
   `cast_refusal(draft: CastDraft[C], world: SceneWorld[C, P]) -> str | None`: exactly one
   entry, not the player's id, filed under its own id; a new id is `known` False with
   `unwritten()` empty. `scene_unmet(draft, world, asked: Sequence[Commission] = ())` adds:
   new cast entries at least as many as `asked` ("N asked for, M written"). `worldsmith_prompt`
   gains `asked: str = ""`, printed as `("THE GAME MASTER ASKED FOR", asked)` before WHAT COMES
   NEXT when non-empty.
4. `engines/scenes/engine.py`: `commission_tool()` returns `master_tool(COMMISSION,
   COMMISSION_BRIEF, SceneCommission, self.ask_worldsmith)`; `ask_worldsmith(draft, args,
   _rng)` calls `self.commission(draft, args.kind, args.brief, later=args.later)`.
   `render_commission(draft, asked) -> str`: `worldsmith_prompt` with the same source, history,
   cast, guidance and hub sections as `render_next`, `intent=COMMISSION_ASK` plus the arc line,
   `answer=CastDraft[self.cast]`. `fulfil` asks with `cast_refusal` and returns a `Play`
   installing `install_cast(draft, asked, written)`: `world.cast = world.merged_cast(written)`
   (a new entry lands, a known id keeps its name and sheet and takes the brief), `world.arc =
   written.arc or world.arc`, `draft.commissions.remove(asked)`, one untold fact, kind
   `commissioned`, trace "the worldsmith wrote {label}: {brief}; bring them in with `enter`"
   or "rewrote {label}: {brief}". `merged_cast` takes a `Mapping[EntityId, C]` so both drafts
   feed it.
   `write_next` hands the `later` commissions to `scene_refusal` and to the prompt;
   `install` clears `draft.commissions`.
   `engines/scenes/worldsmith.md`: one sentence on a commission (one entry, unmet, nothing
   else, and `arc` bent only where it must).
5. Tests: `tests/twentyfourxx/test_worldsmith.py` (the fullest bar suite): `cast_refusal`
   refuses a second entry, an existing id, a known entry; `install_cast` files the entry unmet
   and drops the commission; a `later` commission is refused by `scene_refusal` until the draft
   writes a new entry and is cleared by `install`; `render_commission` carries THE ARC's line
   and THE GAME MASTER ASKED FOR is absent.

### 2.3 The room engine

1. `engines/rooms/tools.py`: `RoomCommission(Frozen)`: `kind: Literal["npc", "item",
   "region"]`, `brief`, `later`, described as 2.2.1.
2. `engines/rooms/drafts.py`: `NpcDraft[N: Dweller](Frozen)` with `npc: N`; `ItemDraft(Frozen)`
   with `item: Item`; a region answers with `MapDraft[N]`.
3. `engines/rooms/worldsmith.py`: `npc_refusal(draft, world)`: a new id, `place` the current
   place, `known` False; `item_refusal(draft, world)`: a new id, `on` the current place or a
   living npc here, `known` False; a region uses `extension_refusal`. `_asked_unmet(draft:
   MapDraft[N], asked: Sequence[Commission]) -> list[str]`: new npcs at least the npc
   commissions, new items at least the item commissions; `job_refusal` and `extension_refusal`
   take `asked` and include it.
4. `engines/rooms/engine.py`: `commission_tool()` and `ask_worldsmith` as 2.2.4 with
   `RoomCommission`; `render_extension(world, intent, hub=(), *, answer: type[BaseModel] | None
   = None, asked: str = "")` prints `answer or self.map_draft()` under ANSWER WITH and
   `("THE GAME MASTER ASKED FOR", asked)` before WHAT THE PLAYER WANTS TO PURSUE when
   non-empty; `render_commission(world, asked, answer) -> str` is `render_extension` with the
   intent `COMMISSION_ASK` and that answer; `fulfil` picks the
   draft and the bar by `asked.kind` and returns a `Play` installing the npc at the current place
   (`world.npcs[id] = npc`), the item (`world.items[id] = item`), or the region
   (`world.attach(region, region.start, known=False)`), then `draft.commissions.remove(asked)`
   and one untold `commissioned` fact naming the id and "reveal it when the player finds it".
   `write_extension` hands the `later` commissions to the two bars and prints THE GAME MASTER
   ASKED FOR; `install_extension` clears `draft.commissions`.
   `engines/rooms/worldsmith.md`: one sentence on a commission.
5. Tests: `tests/tunnelgoons/test_worldsmith.py`: each kind installs where the bar says and a
   wrong place, an existing id or a known entry is refused; a `later` npc commission is refused
   by `job_refusal` until the region writes a new npc.

### 2.4 The prompts, the page, the record

1. `turn/prompts/master.md`: a section "## Ask for more": `commission` asks the worldsmith for
   a person, a thing or a rumour (an npc, an item or a region in a room crawl) the picture
   lacks; when its result says the worldsmith is at work, stop and exit, you are spawned again
   with the answer under NOTES FROM THE RULES; `later` files it for the next scene; one per turn;
   read THE ARC first.
2. `ui/game.py::_STEP_COPY["worldsmith"]`: "Writes the next scene or region, or what the game
   master asked for: where the story goes and who is waiting there. This one is slow; a few
   minutes is normal."
3. `CLAUDE.md`, the engine bullet: "with at most fifteen engine tools plus `commission`, the
   platform's, counted as tools plus `change_world` arms, the two shared party arms not
   counted". `NEXT-SPECS.md` decision 4: the same sentence, dated. Each
   `docs/<ENGINE>.md` "The tools" list gains `- commission (platform, not counted): ask the
   worldsmith for <the engine's kinds>, now or for the next scene.` `README.md` line 9: the
   worldsmith also answers the game master's commissions.
4. `AIDM_GOLDEN_REGEN=1 uv run pytest`, then `uv run pytest`, then read the diff: every
   `schemas/<id>/master_tools.json` gains `commission` last; every `prompts/<id>/master.txt`
   changes by the `master.md` section of 2.4.1; `narrator.txt` and `turn/*` are byte-identical.
5. `PROGRESS.md` entry.

### Done when

Green. Goldens as 2.4.4. `grep -rn "commission" src/aidm/core` finds `play.py` and `model.py`
only; `grep -rn "Any" src/aidm/engines/rooms src/aidm/engines/scenes` finds only the `Game[Any]`
bounds and the bars' `RoomWorld[N, Any]`. Every engine lists sixteen or fewer tools plus arms
with `commission` among them. `uv run aidm`: in a scene engine the master commissions a person,
the page shows the Worldsmith ticker, the master is spawned again, brings them in with `enter`,
and the narrator names them; a `later` commission appears in the next scene; in Tunnel Goons an
npc commissioned now stands hidden at the current place. `src` 9,150 to 9,250;
`engines/scenes/` and `engines/rooms/` under 1,300 each.

---

## What the tests cover

Behaviour and boundaries, never prose or wiring. Stub every role with `ScriptedSpawner`.

**Phase 1.**
- `render_history`: a `ChapterRecord` prints summary and titles and none of its exchanges; the
  last two records stay whole; `told_narration` skips a chapter. `render_whole` prints an untold
  fact's trace.
- `Campaign.history`: a closed job before the last two collapses; one whose last run is among
  the last two does not; hub runs stand as recaps; `job_records` spans two attempts.
- `Job`/`Attempt`: an attempt other than the last without `returned` is refused; an open job not
  last is refused; `reopen` keeps `summary` and `debrief`; `swap_out` on a fresh job drops it and
  on a reopened one drops the attempt.
- The worlds: `_consistent`/`_playable` refuse a `returned` that is not a hub run or visit;
  `apply_scene` on a return closes the attempt and stores summary and recap; a `JobDraft` titled
  as a left-open offer reopens rather than appends; `move` off the tavern begins an attempt on a
  reopened job; `install_extension` attaches a re-taken region at the job's start.
- The bars: a return `situation` or `question` naming an unmet cast member is refused and a
  `summary` naming one passes; a one-shot opening without an `arc` is refused; a room return
  whose `recaps` miss or add a place is refused.
- The crossing: after Take-a-job and after Go-home, `render_narrator`'s WHAT THE PLAYER HAS
  READ carries the scene left (`tests/core/test_master_tools.py`, the crossing tests), and the
  brief names it.
- Every fact rides on the exchange and the chat shows only cards (`tests/core/test_turn.py`).

**Phase 2.**
- `Engine.__init__` registers `commission` on the fifth and sixth test engines; a second `now`
  commission is refused while one waits; every other tool answers the wait line.
- `GameService.play`: the master is spawned twice, the second prompt carries the note and the new
  id; a failed worldsmith leaves the turn playable with the note; the narrator runs once, after.
- The bars: `cast_refusal`, `npc_refusal`, `item_refusal` as 2.2.5 and 2.3.5; a `later`
  commission blocks the next write until met and is cleared by the install.
- `Game.commissions` round-trips through a save; a save without the key loads.
