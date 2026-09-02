# PLAN — campaigns with a home base

The order of work for the hub. `VISION.md` says what we build and why; read it once, first. This
file says what a campaign is and what to do, step by step, and is self-standing: it needs no other
design document, and Phase 5 deletes the one it grew from.

## What a campaign is

> A campaign is one save. Its world has a home base the player keeps coming back to. A job is
> what happens between two visits home. The player takes a job from the board and goes; when
> they come home, the job ends on a card, and the board has moved on.

Two kinds of scenario, both folders under `scenarios/`, both on the home page:

| | one-shot (today's scenarios) | campaign |
|---|---|---|
| `meta.kind` | `"one-shot"` | `"campaign"` |
| opens on | the adventure's first scene or place | the hub, with a board of offers |
| ends when | the story ends, or death | death only |
| the worldsmith writes | the next scene or region | the next job's opening, and the return home |
| the player sees | today's page | today's page plus offer buttons, a "Go home" or "Report in" button, a `Jobs` panel, chapter headings |

Two words, two levels. A **campaign** is the scenario kind. A **job** is one outing between two
hub visits. "Job" is the design and code word; an engine's text may use its SRD's word.

How it plays, in a scene engine:

1. A campaign opens at the hub. The board already holds two or three offers. The hub is a scene:
   the player talks, shops, rests; every master tool works there. The hub is always open: the
   way on is offered without the scene being settled, and the spent note never fires there.
2. The player clicks an offer. Its button plays `TAKE_JOB` with the offer's title; the worldsmith
   reads the pitch off the board and writes the job's opening scene from it, the existing bar
   applies, the arrival is narrated. Free text plus Move on still works at the hub, for a job
   with a twist or for work the player names themselves: every scene that leaves the hub opens
   a job, and the worldsmith writes its `job` from the player's words.
3. The job runs as scenes run today. The master's picture and the narrator's view do not change.
   The sidebar's `Trail` lists this job's scenes only.
4. When a job scene is settled the sidebar offers "Go home" beside the way on. Clicking it is
   Move on with a fixed intent. Whether the job was finished is the game master's word, given
   when it settled the scene (`next_scene` with `job_done`): it played the job and holds its
   history. The worldsmith writes the hub scene, a one-paragraph debrief of the job just left,
   told the verdict, and the new board: keep, drop, add.
5. On install: a "Job done" or "Job left open" card carrying the debrief, then the arrival
   narration. The board panel shows the new offers; `Jobs` gains a line. When the job was
   finished and the SRD prints a between-jobs step, a note tells the master it applies.
6. An open job stays on the board, so the player can take it again: a new opening scene, the
   same place slug and cast, so the art and the faces return.

Tunnel Goons plays it on the map's own terms: the hub is a tavern place, a job is a dungeon the
worldsmith hangs off it, the player walks out and walks back, and "Report in" at the tavern is
what closes the job. Section 4 has it.

| engine | hub | job | between-jobs step (printed) |
|---|---|---|---|
| 24XX | a station bar with a fixer | the SRD's job | `job_done`: raise a skill, gain d6 credits |
| Breathless | a camp, a safe house | a run | none |
| Loner | a guild hall, a ship | a chapter | the master's growth line |
| Tunnel Goons | a tavern | a dungeon hung off the tavern | `level_up` |

Two worldsmith waits back to back (the return, then the next job) is the always-open hub's worst
case. It is inherent; the card and a cheap turn with the fixer in between are the mitigation. Do
not fix it with pre-written openings.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Rules:

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step**, except the steps a phase marks "checked
   together": a new shipped scenario makes the golden state test look for its fixture, so the
   content file and the fixture regen are always the last two steps of a phase.
3. **Tests must be green.** Change a shape and update its tests in the same step. Test lines are
   not budgeted. One test per new behaviour; no test of prose or wiring.
4. **Golden files** live in `tests/core/fixtures/`. Rebuild them **once**, at the end of a phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. A one-shot's `narrator.txt` and `picture.txt` never change.
   `master.txt` and `master_tools.json` change only by the `rules.md` and tool-description
   lines the phase names. The Phase 1 regen adds `"kind": "one-shot"` to `state/` and `save/`
   and `"debrief": null` to every scene in them; each engine's phase adds `"hub": null,
   "board": []` to that engine's world and canon. Anything else is a bug.
5. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase (Phase 1 creates the file):
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never pad, never invent a deletion.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive.
9. **Review each phase adversarially against its staged diff before the commit.**
10. **Verify every rule against the SRD page before you build on it.** The docs under `docs/`
    hold sources and deviations, never rules text. The rules this plan builds on were read
    2026-09-01: 24XX "After a job, each character increases a skill (none→d8→d10→d12) and gains
    d6 credits", and its optional d6 job-finding setup "1–2 Nothing. Owe somebody to get in on a
    job. / 3–4 Found a job, but something seems off. / 5–6 Choose between 2 jobs."; Breathless
    prints no between-runs step; Tunnel Goons' `level_up` and Loner's growth line are already
    built and documented in `docs/`.

| phase | `src` after |
|---|---|
| start (`c9efa13`) | 9,548 |
| 1 — the seam and `engines/hub.py` | about 9,720 |
| 2 — 24XX | about 9,870 |
| 2b — the shape, refined | about 9,990 |
| 3 — Breathless and Loner | about 10,200 (landed 10,227) |
| 3b — the shared hub code, once | about 10,100 |
| 4 — Tunnel Goons | about 10,250 |
| 5 — the enduring documents | about 10,250 |

Targets are targets. The caps stand: 2,000 Python lines per engine, fifteen game-master tools
(tools plus `change_world` arms; 24XX is at fifteen). No phase adds a tool.

---

## Settled. Do not re-open these inside a phase.

1. **One save.** A campaign is a normal game: no hub file, no save per job, no second writer.
   Saves have no version field; a stale save is invalid.
2. **The platform learns two fields.** `ScenarioMeta.kind: ScenarioKind = "one-shot"` (a badge
   on the home page, a toggle on the create page, passed to the authoring) and
   `PanelRow.intent: str = ""` (a sidebar row with an intent renders as a button that plays Move
   on with it). `core`, `turn`, `app` and `ui` never say "hub", "job", "board" or "debrief".
   The one platform behaviour beyond the fields: a silent install (`arrival_brief is None`) that
   lands a told card is recorded as a lineless exchange, so the card shows.
3. **The hub is engine-owned, and a one-shot is a campaign with no hub.** `world.hub is None`
   is today's behaviour, and every existing scenario keeps playing unchanged. `validate` refuses
   `kind` and `hub` disagreeing, through `check_kind`: the engine's validate is the one place
   that sees both the envelope and the payload.
4. **The hub is a scene** (a `Place` in Tunnel Goons) with a fixed slug. The player plays turns
   there; master tools work there as anywhere; the art cache reuses its picture.
5. **The board lives on the world.** `world.hub: Slug | None` and `world.board: tuple[Offer,
   ...]`, on every engine's world and canon; Tunnel Goons has no scene to hang a board on, and
   one shape lets the shared helpers read all four engines. A return swaps the whole board;
   taking a job leaves it alone. Two or three offers, always.
6. **A debrief is a value on the hub stop.** `Debrief{text, finished}` on `Scene.debrief`
   (scene engines) and `Visit.debrief` (Tunnel Goons), `None` everywhere else. `text` is the
   worldsmith's; `finished` is the game master's verdict, set by code from `next_scene`'s
   `job_done` (scene engines) or `level_up` (Tunnel Goons), never judged by the worldsmith or
   claimed by the player. A job is derived
   by one walk over `Stop{place, title, debrief}` triples; a job's title and place are those of
   the first stop after leaving the hub, and the ledger names both, so the worldsmith can reopen
   a job at its place and the art cache hits. The worldsmith titles that first scene after the
   offer taken, so the ledger names what the player clicked. In the scene engines that scene
   also carries `job`, a short paragraph on the job as taken (who wants what done, what done
   looks like, what it pays); the master reads it as `THE JOB`, and every later scene's
   worldsmith sees it in `SCENES SO FAR`. A one-shot's `meta.premise` plays that part already,
   and Tunnel Goons' job is a visible map, so neither has it. Nothing else is stored, nothing is
   indexed.
7. **The shared hub code lives in `engines/hub.py`**, a flat module beside `core.py` and
   `scenes.py`, written in Phase 1: the models, the walk, the rows, the ledger, the card, the
   checks, the fixed intents and the prompt briefs. `hub.py` imports `core`; `scenes.py` and
   every engine import `hub.py`. The three scene worlds share a base class, `SceneWorld` in
   `scenes.py`, holding what they hold in common (`runs`, `source`, `hub`, `board` and the walk
   over them); no type parameter, protocol or callback is added beyond it. World-free code takes
   plain values — `hub`, `runs`, a draft's fields. What the engines copy from each other moves
   there: `scenes.py` exists for exactly that, and Phase 3b does it once.
8. **The drafts are structural.** A scene engine's worldsmith answers with one of four models,
   picked by the moment: `SceneDraft` (a scene: no `job`, no `offers`), `JobDraft(SceneDraft)`
   (the scene that leaves the hub: `job` required, at least `MIN_JOB` characters),
   `HubDraft(SceneDraft)` (the campaign's opening: `offers` bounded to two or three) and
   `ReturnDraft(HubDraft)` (the return: `debrief: str`, the paragraph). Nothing is overridden,
   so the bounds live on the fields and `extra="forbid"` refuses a field out of place; the bar
   checks only what a schema cannot (the place, the cast, hidden names). Tunnel Goons answers a
   return with its own `ReturnDraft` (`debrief: str`, bounded `offers`). `finished` is never in
   a draft (settled 6).
9. **Home is a fixed intent.** `GO_HOME = "Go home."` (scene engines) and `REPORT_IN = "Report
   in."` (Tunnel Goons) are the exact strings the sidebar rows send and `write` matches on, and
   only away from the hub: at the hub every intent, `GO_HOME` typed included, is a job write. A
   typed "go home" in a job is a job scene like any other; if the worldsmith places it at the
   hub, the bar refuses it ("home is reached by going home") and the player uses the button.
   An intent is played as the PLAYER ACTION of a full turn before the crossing, shown as the
   player's bubble and quoted to the narrator. An offer's button plays `TAKE_JOB = 'I take the
   job "{title}".'`, so `pitch` is the board's own words, as the fixer posts it ("Crates off
   Deck 9, no manifest, half up front."); the worldsmith finds it on `THE BOARD` by title.
   A button plays a full master turn, as typed words do: the fixer answers, then the crossing.
   The master's rules name both strings as the page's own words for leaving, so it plays the
   goodbye in one call or none. Latency is not a reason to skip that turn.
10. **The way on stays the scene's.** `Transition.ready` is `way_open = run.settled or at_hub`.
    The "Go home" row shows only when the way is open, so pressing it never raises "no
    transition from here". Leaving a job means settling its current scene first, as leaving any
    scene does. Tunnel Goons: `way_open = at_hub or map_exhausted`; "Report in" shows at the
    tavern with a job open, and there is no teleport home: the player walks.
11. **The "more beyond here" banner stays at the hub.** Hiding it would teach the platform what
    a hub is, and its text is true there. The hub's own `This scene` row says what to do.
12. **Fidelity first.** Where an SRD prints a between-jobs step, a finished job's return appends
    one note to `state.notes` and the master fires the existing tool: 24XX `job_done`, Loner the
    growth line (`change_tags`, `drive`). Tunnel Goons needs no note: `level_up` is the SRD's
    end-of-adventure step, so calling it with a job open is the master's verdict that the job is
    done, applied at once. Breathless prints none, so nothing is invented. An unfinished job
    appends no note. Reputation is prose: no counter; the
    ledger and the sheet are what the worldsmith reads to decide which offers fit.
13. **Two cards on a return.** `job_closed` ("Job done: <title>" or "Job left open: <title>",
    then the debrief on its own line) and the engine's opening card reading "Home: <the return
    scene's title>" instead of "New scene: ...". Tunnel Goons' job
    take is one told card, "A way opens: <region start>", so the player sees the map grew. A
    silent install's exchange is filed under the intent that caused it, not "(the story moves
    on)"; that heading stays the narrated crossing's.
14. **The master reads the ledger; the narrator does not.** `master_sections` gains `JOBS SO
    FAR` in a campaign and `THE BOARD` at the hub. `NarratorView` does not change: it stays the
    one type with no field for hidden canon.
15. **Prompt memory is compacted per job.** The worldsmith's `SCENES SO FAR` and the sidebar's
    `Trail` run from the last debriefed stop; `JOBS SO FAR` is one line per closed job. Older
    scenes stay in the save. The cast list still grows; accepted, as is twenty ledger lines
    after twenty jobs.
16. **Growth lives in the save.** No write-back to `characters/`; a second campaign starts the
    same character fresh. Death ends the campaign, as every engine ends today.
17. **No companions are gained.** Breathless and 24XX keep none: the worldsmith is told that
    anyone from the hub's cast the player names in their intent is present in the job's opening
    scene, and no more. Loner's companions travel as they do now, home included.
18. **Content is hand-written.** One campaign scenario per engine, beside its one-shot, with no
    worldsmith run. The test support requires exactly one shipped scenario per (engine, kind).
19. **Nothing else.** No session reset at the job boundary (`app` knows no job), no
    `PendingDecision` for the board (an offer never blocks the master's tools), no crew list, no
    new master tool, no journal chapters beyond the `where` heading every exchange already
    carries.

---

## Phase 1 — the seam and `engines/hub.py`

Everything above the engines, plus the type-free hub code, with no engine playing a campaign
yet. **Split:** A (platform and `hub.py`) then B (the pages), sequential: B needs A's fields.

### 1.1 `core/model.py`, `core/views.py`

```python
type ScenarioKind = Literal["one-shot", "campaign"]

class ScenarioMeta(Frozen):
    title: str
    premise: str
    kind: ScenarioKind = "one-shot"

class PanelRow(Frozen):
    label: str
    detail: str
    icon_id: EntityId | None = None
    # Set when the row is a way on: the sidebar draws a button that plays Move on with it.
    intent: str = ""
```

### 1.2 `engines/hub.py` (new)

Imports: `core.entities`, `core.facts`, `core.model` (`ScenarioKind`), `core.views` (`PanelRow`,
`Rows`). Layout: constants, models, public functions.

```python
BOARD_MIN, BOARD_MAX = 2, 3
GO_HOME = "Go home."
HOME_ROW = PanelRow(label="Go home", detail="Back to base; the job closes on a card.", intent=GO_HOME)
HUB_ROW = PanelRow(label="Take a job from the board, or name where you go.", detail="")
HUB_BRIEF = (
    "The hub is {title} ({place}). Anyone from its cast the player names in WHAT COMES NEXT is "
    "present in the scene you write. An offer taken again opens at the place its JOBS SO FAR "
    "line names, with its cast. Never place a scene at {place}: home is reached by going home."
)
# Shared by the scene engines and Tunnel Goons; `hub_sections` prepends the scene sentence.
RETURN_BRIEF = (
    "The player is home at {title} ({place}). `debrief.text` is one paragraph on the job they "
    "just left, written for the player; `debrief.finished` is true only when that job was "
    "completed. Return the whole board in `offers`: keep, drop or add, two or three in all. A job "
    "left open normally stays on the board, so the player can take it again."
)
WRITE_HUB_SCENE = "Write the hub scene there. "


class Offer(Frozen):
    title: str = Field(min_length=1)
    pitch: str = Field(min_length=1)   # the job in the player's own words; it is played as their action


class Debrief(Frozen):
    text: str = Field(min_length=1)
    finished: bool


class Stop(Frozen):
    """One run or visit, as the job walk reads it; the engine maps its own shape to this."""

    place: Slug
    title: str
    debrief: Debrief | None = None


class Job(Frozen):
    title: str
    place: Slug
    debrief: Debrief
```

Functions, all pure:

- `check_kind(kind: ScenarioKind, hub: Slug | None) -> None`: raises when
  `(kind == "campaign") != (hub is not None)`.
- `check_board(hub, board) -> None`: no hub → the board is empty; hub → `BOARD_MIN <= len(board)
  <= BOARD_MAX`.
- `job_titles(hub, stops) -> tuple[str, ...]`: one entry per stop; `""` at the hub, or without
  one; else the title of the first stop since the last hub stop. This is the chapter heading.
  Every other walk reads this tuple as `titles`; "a job stop" below means `titles[i]` is
  non-empty.
- `job_start(hub, stops) -> int`: the index of the last stop with a debrief, else 0.
- `open_job(hub, stops) -> str | None`: `titles[i]` of the last job stop with `i >
  job_start(...)`, else `None`.
- `closed_jobs(hub, stops) -> tuple[Job, ...]`: one `Job` per stop `i` with a debrief; its title
  and place are those of the first job stop `j < i` after the previous debriefed stop (there is
  always one: `check_hub` and `write_extension` refuse the cases without).
  Worked: stops `hub, a1, a2, hub†, b1, hub†, c1` († = debriefed) give titles `"", a1, a1, "", b1,
  "", c1`, closed jobs `(a1, b1)`, open job `c1`, start 5. Tunnel Goons' `tavern, a, b, tavern†`
  (the debrief lands on the tavern visit the player walked back to) gives closed `(a,)`, open
  `None`, start 3.
- `board_rows(board) -> tuple[PanelRow, ...]`: `PanelRow(label=offer.title, detail=offer.pitch,
  intent=offer.pitch)`.
- `board_lines(board) -> str`: `- <title>: <pitch>` per offer, for prompts.
- `jobs_rows(jobs) -> tuple[PanelRow, ...]`: `label=title` plus `" (left open)"` when not
  finished, `detail=text`.
- `ledger(jobs) -> str`: `- <title> (<place>): <text>` per job, `(left open)` appended when not
  finished; `"(none yet)"` when empty.
- `hub_sections(hub_title, hub, board, jobs, *, returning) -> Rows`: `("JOBS SO FAR",
  ledger(jobs))`, `("THE BOARD", board_lines(board))`, `("THE HUB", WRITE_HUB_SCENE +
  RETURN_BRIEF if returning else HUB_BRIEF, formatted with title and place)`.
- `job_closed(job) -> Fact`: `kind="job_closed"`, `told=True`, card `"Job done: <title>\n<text>"`
  or `"Job left open: <title>\n<text>"`, trace `"the job <title> closed (done|left open): <text>"`.

Tests in `tests/core/test_hub.py`: the walk on one stop list holding two closed jobs and one open
(titles, closed jobs, open job, job start); `check_board`; `check_kind`; the card text.

### 1.3 `engines/scenes.py`

```python
class Scene(Frozen):
    ...                                # as today, plus:
    debrief: Debrief | None = None     # the hub's word on the job just left; hub runs after the first
```

- `check_hub(hub, board, runs) -> None`: `check_board`; no hub → no run has a debrief; hub →
  `runs[0]` is at the hub with no debrief, for every later run `(scene.place == hub) ==
  (scene.debrief is not None)`, and no hub run directly follows a hub run (a return always
  closes a job).
- `stops_of(runs) -> tuple[Stop, ...]`: `Stop(place=scene.place, title=scene.title,
  debrief=scene.debrief)`.

### 1.4 The engines' seam

```python
@dataclass Authoring:
    answer: type[BaseModel]
    prompt: Callable[[str, Sequence[Slug], ScenarioKind], str]
    build: Callable[[str, str, str, tuple[Slug, ...], BaseModel, str, ScenarioKind], AnyScenario]
```

Every `build_scenario` and `render_opening`/`render_map` gains the `kind` parameter. In this
phase `render_opening`/`render_map` raise `ValueError("<engine> has no hub yet")` on
`"campaign"` — `new_scenario` calls the prompt before any spawn, so the refusal is instant —
and each engine's validate calls `check_kind(state.scenario.kind, None)`, which is the gate
`build_scenario` needs. Phases 2–4 replace both.

### 1.5 `app/runtime.py`, `app/launch.py`

- `new_scenario(..., art_style, kind)` passes `kind` to `authoring.prompt` and `build`.
- `_install(transition, written, announce, brief, intent)`: `_grow` passes its `intent`. When
  `brief is None` and `cards(facts)` is non-empty: `self.commit(close_segment(self.engine,
  self.engine.narrator_view(draft), draft, intent, (), facts))`; else the plain commit as
  today. `close_segment` takes empty lines already; the exchange is the card alone, filed under
  the intent, and the turn counter moves as it does for a narrated crossing.
- `CatalogEntry.kind: ScenarioKind` and `SaveOption.kind: ScenarioKind`, read from the meta.

### 1.6 `ui/create.py`, `ui/app.py`, `ui/panels.py`, `ui/game.py`

- Scenario page: `ui.toggle({"one-shot": "One-shot", "campaign": "Campaign"},
  value="one-shot")` above the premise; `write()` narrows it: `kind: ScenarioKind = "campaign"
  if toggle.value == "campaign" else "one-shot"`.
- Home page: `ui.badge("campaign")` after the scenario subtitle and on a saved card, when the
  entry's kind is `"campaign"`.
- `scene_sidebar(session, move_on: Callable[[str], Awaitable[None]])`: a row with an intent
  renders as `ui.button(row.label, on_click=partial(move_on, row.intent)).props("no-caps outline
  dense")` with `row.detail` as a small label beneath; every other row renders as today.
  `game_page` passes `partial(move_on, view)`, where `move_on(view, intent)` in `game.py` is
  `submit`'s tail: return when `refuse_play(view)`; return after `ui.notify("Choose an option
  above.", type="warning")` when a pending decision has `allows_text=False`; else `_send(view,
  intent if session.player_view().prompt is None else Answer(text=intent), intent,
  moving_on=True)`.

### 1.7 Tests and fixtures

- `core_test_support.py`: `scenario_for(engine_id, kind="one-shot")` and `game(engine_id,
  kind="one-shot")` filter on `meta.kind` and still require exactly one; `shipped(engine_id) ->
  tuple[ScenarioKind, ...]`; `SHIPPED = tuple((e, k) for e in ENGINE_IDS for k in shipped(e))`.
- `test_golden_state.py` parametrises over `SHIPPED`; a campaign fixture is
  `state/<engine>-campaign.json`. The turn, prompt and schema goldens stay on the one-shot.
- `test_tool_surface.py`: the `build` call gains `"one-shot"`. The existing
  `test_a_transition_without_an_arrival_brief_extends_without_a_turn` keeps Loner's
  `install_scene`, whose `New scene` card is told, so it now asserts `turn == before + 1` and
  one exchange with no lines, that card, and the intent as its prompt; no master spawn still.
  Tunnel Goons' own silent extension (`tests/tunnelgoons/test_play.py`) lands no card and
  stays unchanged.
- Regen: per rule 4.

**Split.** A: 1.1–1.5, `test_hub.py`, `core_test_support.py`, `test_golden_state.py`,
`test_tool_surface.py`, regen. B (needs A): 1.6, `ui/`.

**Done when:** green; every one-shot plays as before; the create page offers the toggle and a
campaign is refused with the engine's message; `src` about 9,720.

---

## Phase 2 — 24XX

The first engine with a hub. One implementer.

### 2.1 `world.py`

```python
class SceneCanon(Mutable):
    ...                                          # as today, plus:
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    # validator adds: check_board; hub set → opening.place == hub; opening.debrief is None

class TwentyfourxxWorld(Mutable):
    ...                                          # as today, plus:
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    # validator adds check_hub(hub, board, runs)

    @property
    def at_hub(self) -> bool: ...                # hub is not None and current.place == hub
    def stops(self) -> tuple[Stop, ...]: ...     # stops_of(runs)
    def job_runs(self) -> list[SceneRun]: ...    # runs[job_start(hub, stops()):]
    def exchanges(self): ...                     # where = title when job in ("", title) else f"{job} — {title}"
```

- `record`: returns no spent note when `world.at_hub`.
- `settled(state)` becomes `way_open(state)`: `run.settled or world.at_hub`. `engine.py`
  registers it as `ready`.
- `new_game` copies `hub` and `board` from the canon.
- `check_packs` becomes `check_game(packs, state)`: the pack checks, then
  `check_kind(state.scenario.kind, world.hub)`.

### 2.2 `worldsmith.py`, `worldsmith.md`

```python
BOARD_GUIDANCE = (
    "The SRD's job-finding setup, as guidance for the board: 1–2 nothing, owe somebody to get in "
    "on a job; 3–4 found a job, but something seems off; 5–6 a choice between two jobs. Let the "
    "offers carry that range: one that costs a favour, one where something is off, a plain choice."
)
# Read by the next turn, which is usually the next offer click: the note must stand on its own.
JOB_DONE_NOTE = (
    "The job {title} is closed and was completed. The SRD's after-a-job step applies: call "
    "`job_done` once, with the skill the player names, else the skill the job called on."
)

class SceneDraft(Frozen):
    ...                                          # as today, plus:
    offers: tuple[Offer, ...] = ()               # the board; only a hub scene fills it

class HubDraft(SceneDraft):
    debrief: Debrief
```

- `scene_refusal(draft, world=None, *, hub=False)` and `_scene_unmet(draft, world, *, hub)`:
  `hub` means this draft is the hub scene. `hub`: `BOARD_MIN <= len(offers) <= BOARD_MAX`, and
  with a world (the return) `draft.place == world.hub`. Not `hub`: `offers == ()`, and with a
  world hub `draft.place != world.hub` ("home is reached by going home"). The existing checks
  stay.
- `opening_canon(draft, source, kind)`: `hub = draft.place` and `board = draft.offers` for a
  campaign.
- `_scene(draft)`: `debrief=draft.debrief` for a `HubDraft`, else `None`.
- `write_next`: `returning = world.hub is not None and not world.at_hub and intent == GO_HOME`;
  the model is `HubDraft` when returning else `SceneDraft`; the refusal checks `isinstance`
  against that model and calls `scene_refusal(written, world, hub=returning)`.
- `install_scene`: `apply_scene` as today, then for a `HubDraft`: `world.board =
  written.offers`; `job = closed_jobs(world.hub, world.stops())[-1]`; when
  `job.debrief.finished`, append `JOB_DONE_NOTE.format(title=job.title)` to `state.notes`;
  return `(job_closed(job), opened)`.
- `render_worldsmith(world, intent, guidance, *, returning=False)`: history is
  `scene_history(world.job_runs())`; `_worldsmith(..., hub: Rows = ())` splices `hub` after
  `SCENES SO FAR`, and in a campaign it is `hub_sections(world.runs[0].scene.title, world.hub,
  world.board, closed_jobs(...), returning=returning)`; the answer schema is `HubDraft` when
  returning; `BOARD_GUIDANCE` joins the guidance when returning.
- `render_opening(packs, source, picks, kind)`: a campaign's intent is "Write the opening of this
  campaign: the hub the player keeps coming back to — one place, the fixer and the regulars —
  and a board of two or three `offers`. Nothing has happened yet." plus `BOARD_GUIDANCE`.
- `build_scenario(..., kind)`: `scene_refusal(written, hub=(kind == "campaign"))`;
  `ScenarioMeta(..., kind=kind)`; `opening_canon(written, source, kind)`.
- `worldsmith.md`, one line: "An `offers` entry is a job the hub can hand the player: a `title`,
  and a `pitch` in the player's own words as they would take it — 'I take the Deck 9 crate
  run.' — enough to walk out on."

### 2.3 `views.py`, `rules.md`

- `player_view`: `This scene` rows are the question, then `HUB_ROW` at the hub, else when settled
  the "Way on" row and, in a campaign, `HOME_ROW`. Panels, in order: `Character`, `Gear`, `This
  scene`, `Board` (campaign, at the hub only: `board_rows(world.board)`), `Here`, `Trail`
  (`job_runs()`), `Jobs` (campaign: `jobs_rows(closed_jobs(...))`).
- `master_sections`: after `THE SCENE'S SECRET`, `("JOBS SO FAR", ledger(...))` in a campaign
  and `("THE BOARD", board_lines(...))` at the hub.
- `rules.md`, a `## Campaigns` section before the scene rules: the hub is always open, so
  `next_scene` is never needed there and the spent note never fires; play the hub as any scene —
  talk, trade, rest — and never push the player out; the board is the player's to take from the
  page, so do not choose for them; when NOTES FROM THE RULES says a job closed and was completed,
  call `job_done` once with the skill the player names. `job_done`'s tool description and its
  rules line read "once per job" instead of "once per adventure".

### 2.4 Content, tests, docs

- `scenarios/<slug>/world.json`, `kind: "campaign"`, packs `["srd"]`: a station bar as the hub
  (`place` is the hub slug), a fixer and a bartender present, one regular hidden, a `secret`,
  and a board of three offers spanning `BOARD_GUIDANCE`. No debrief. Hand-written; the implementer
  names it. Kael (`characters/kael/twentyfourxx.json`) plays it.
- `twentyfourxx_test_support.py`: `hub_world()` — a hub run with a board, then one job run.
- Tests: the world refuses a debrief off the hub and a first run away from it; `check_game`
  refuses a campaign without a hub; `way_open` at an unsettled hub; `record` never nags at the
  hub; `write_next` asks for a `HubDraft` on `GO_HOME` and a `SceneDraft` otherwise (a scripted
  `answer` records the model it was given); a job scene placed at the hub is refused;
  `install_scene` on a return swaps the board, lands the two cards, and the note only when
  finished; `player_view` shows the board at the hub, "Go home" only when settled in a job, and
  `Jobs` after a return; `exchanges()` heads a job scene `<job> — <scene>`.
- Checked together: the scenario, then regen (`state/twentyfourxx-campaign.json` appears).
- `docs/24XX.md`: deviation 3 becomes "the d6 job-finding setup is prompt guidance for a
  campaign's board, not a roll; the d20 detail tables stay unmodelled"; the reading "a job is
  the whole adventure" becomes "a job is one outing from the hub in a campaign, the whole
  adventure in a one-shot"; the tool table's `job_done` line says once per job.

**Done when:** green; a 24XX campaign opens at the bar with three buttons, an offer opens a job,
"Go home" lands the card, the note and the new board; engine at about 1,580 lines (cap 2,000);
`src` about 9,870.

---

## Phase 2b — the shape, refined

What playing Phase 2 taught, fixed once in the shared code and 24XX before Phases 3 and 4 copy
it three times. One implementer. Nothing in `core`, `turn`, `app` or `ui` changes.

### 2b.1 `engines/hub.py`

```python
type Moment = Literal["taking", "away", "returning"]   # where the worldsmith writes from
TAKE_JOB = 'I take the job "{title}".'                  # what an offer's button plays
HUB_QUESTION = (
    "The hub's `question` is what keeps the player coming back, never something to settle."
)
TAKE_BRIEF = (
    "The player is leaving {title} ({place}) on a job. WHAT COMES NEXT is the job they take: an "
    "offer by its title, whose pitch THE BOARD holds, or their own words. Write the job's first "
    "scene away from {place}, titled after the offer, and its `job`: who wants what done, what "
    "done looks like, what it pays. Anyone from the hub's cast the player names is present. An "
    "offer taken before opens at the place its JOBS SO FAR line names, with its cast."
)
JOB_ASK = "who wants what done, what done looks like, what it pays"   # in TAKE_BRIEF and the bar
AWAY_BRIEF = "The hub is {title} ({place}). Never place a scene at {place}: home is reached by going home."
RETURN_BRIEF = (... as today, plus:)
    " A new offer may grow from JOBS SO FAR: a debt, a job left open, someone met."
WRITE_HUB_SCENE = "Write the hub scene there. " + HUB_QUESTION + " "

class Offer(Frozen):
    title: str = Field(min_length=1)
    pitch: str = Field(min_length=1)   # the board's words, as the fixer posts it
```

- `board_rows`: `intent=TAKE_JOB.format(title=offer.title)`; `detail` stays the pitch.
- `hub_sections(hub_title, hub, board, jobs, *, moment: Moment)`: the brief is `TAKE_BRIEF`,
  `AWAY_BRIEF` or `WRITE_HUB_SCENE + RETURN_BRIEF` by moment (a module-level `BRIEFS: dict[Moment,
  str]`); `JOBS SO FAR` and `THE BOARD` stay.
- Tests in `tests/core/test_hub.py`: `board_rows` plays `TAKE_JOB`; `hub_sections` picks the
  brief by moment.

### 2b.2 `engines/scenes.py`

```python
class Scene(Frozen):
    ...
    job: str = ""    # the job as taken; on the scene that leaves the hub only
```

`scene_history` prints `the job: <job>` after the question line when `job` is set.

### 2b.3 24XX

- `SceneDraft.job: str = ""`; `_scene` copies it. `MIN_JOB = 80`.
- `_scene_unmet`: `taking = world is not None and world.at_hub` (never with `hub`: a hub write is
  a job write). Taking: `len(draft.job) < MIN_JOB` is unmet, "a `job` of a short paragraph: who
  wants what done, what done looks like, what it pays". Otherwise `draft.job` non-empty is
  unmet, "no `job`: only the scene that leaves the hub carries it".
- `render_worldsmith(..., returning)`: `moment = "returning" if returning else "taking" if
  world.at_hub else "away"`, passed to `hub_sections`.
- `BOARD_GUIDANCE` loses its recipe sentence: "The SRD's job-finding setup is the board's range,
  not a recipe: 1–2 nothing, owe somebody to get in on a job; 3–4 found a job, but something
  seems off; 5–6 a choice between two jobs."
- `CAMPAIGN_OPENING` ends with `HUB_QUESTION`.
- `install_scene`: a `HubDraft`'s opened card reads `f"Home: {written.title}"`.
- `master_sections`: the heading is `WHAT THIS PLACE IS ABOUT` at the hub, `THE QUESTION THIS
  SCENE SETTLES` elsewhere; `("THE JOB", job)` after `THE SCENE'S SECRET` when `job = next((run.
  scene.job for run in world.job_runs() if run.scene.job), "")` is set.
- `player_view`: the `Jobs done` panel becomes `Jobs`.
- `worldsmith.md`: the `offers` line reads "a `pitch` as the board posts it — 'Crates off Deck 9,
  no manifest, half up front.' — enough to walk out on"; one new line: "`job` goes on the scene
  that leaves the hub only: a short paragraph on the job as taken — who wants what done, what
  done looks like, what it pays. Title that scene after the offer taken."
- `rules.md ## Campaigns` gains: "THE JOB is what the player walked out on. At the hub WHAT THIS
  PLACE IS ABOUT replaces the scene's question: nothing settles there."
- `scenarios/amber-tap`: the three pitches in the fixer's voice.
- Tests: a take without `job` is refused and a later scene with one is refused; `scene_history`
  prints the job; `master_sections` has `THE JOB` in a job and the hub heading at the hub; the
  return's card is `Home: ...`; the hub test's board rows play `TAKE_JOB`.
- Regen: every scene engine's `state/`, `save/` and `turn/` fixtures gain `"job": ""` per scene;
  `twentyfourxx-campaign.json` carries the new pitches; `master.txt` changes by the `rules.md`
  line. Nothing else.

**Done when:** green; the board buttons play `TAKE_JOB`; a job's first scene carries `job` and
the master reads `THE JOB`; `src` about 9,990.

---

## Phase 3 — Breathless and Loner

Copy Phase 2 into both. **Split:** parallel, A Breathless, B Loner; they share no file.

### 3.1 Breathless (A)

Exactly 2.1–2.4 as refined by 2b, with Breathless' types. Differences: no `BOARD_GUIDANCE` (the SRD prints no job
table); no note on a finished job (the SRD prints no between-runs step), so `install_scene`
appends nothing to `state.notes`; `rules.md`'s `## Campaigns` says the return is the camp and
nothing is owed. Content: a camp or safe house as the hub, the pack's `missions` as the offers'
vocabulary. `docs/BREATHLESS.md` gains one reading: a campaign's between-runs step is none.

### 3.2 Loner (B)

Exactly 2.1–2.4 as refined by 2b, with Loner's types (`cast: dict[EntityId, LonerCharacter]`, `player_id`).
Differences: companions come home as they go anywhere (`apply_scene` keeps followers already);
`close_conflicts` runs before the move as it does now; the note is `GROWTH_NOTE = "The job
{title} is closed and was completed. The adventure's end applies: ask what the character
learned if the player has not said, then write it once with `change_tags` and `drive`."`; `rules.md`'s "Twists and the
adventure's end" section says the note names when a job's end counts as one. Content: a guild
hall as the hub, packs as the one-shot's. `docs/LONER-3E.md` deviation 5's growth line says per
job in a campaign.

**Done when:** green; both campaigns play a job and a return; each engine under about 1,560
lines; `src` about 10,200.

---

## Phase 3b — the shared hub code, once

After Phase 3 the hub code is one design copied into three engines, and Phase 4 would copy the
world-free part a fourth time. Move it once, before Tunnel Goons, and fold in what the direction
check after Phase 3 found. One implementer, opus: 3b.3 and 3b.4 reshape models. Nothing the
player sees changes except the hub headlines and a caption on the create page.

### 3b.1 `engines/scenes.py`: `SceneWorld`

```python
class SceneWorld(Mutable):
    """What the three scene worlds share; each engine adds its cast, its player and its checks."""

    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    # validator: check_hub(hub, board, runs)
    # run, current, at_hub, stops(), job_runs(), jobs(), exchanges(), last_seen(): the bodies
    # twentyfourxx/world.py holds today, verbatim; exchanges() reads hub.heading()

class SceneRun(Mutable):
    ...
    job_done: bool = False   # the master's word: settling this scene finished the job


class NextScene(Frozen):
    # A campaign only: settling this scene also finishes the job the player walked out on.
    job_done: bool = False
```

Each engine's world subclasses `SceneWorld`, keeps `cast`, `player` or `player_id` and
`companions`, its `require*`, `here`, `label`, `reveal` and its own validator, which no longer
calls `check_hub` (pydantic runs the base's validator too). `SceneCanon` stays per engine: the
cast type differs. Also here, world-free but `SceneRun`-bound: `spent_note(run, *, at_hub,
someone_dead) -> tuple[str, ...]` (`record`'s tail) and `scene_rows(question, hub, *, at_hub,
settled) -> tuple[PanelRow, ...]` (the question, then `HUB_ROW`, or "Way on" and `HOME_ROW`).

### 3b.2 `engines/hub.py`: the world-free share, read by all four engines

```python
MIN_JOB = 80
ONE_SHOT_OPENING = "Write the opening scene of this adventure: ..."          # the engines' text, verbatim
CAMPAIGN_OPENING = (                                                         # one template; {hub} is the engine's
    "Write the opening of this campaign: the hub the player keeps coming back to — one place, "
    "{hub} — and a board of two or three `offers`. Nothing has happened yet. " + HUB_QUESTION
)
HUB_QUESTION = (
    "The hub's `question` is the standing pressure at home, one sentence the player reads as the "
    "scene's headline: what is owed, who is watching, what runs out. Never something a scene settles."
)
RETURN_BRIEF = (... as today, with:)
    "`debrief` is one paragraph on the job they just left, in the second person and the present "
    "tense, as the narrator writes; THE VERDICT says whether it was finished."
JOB_DONE = Fact(kind="job_done", told=True, trace="the job is done; the way home is open")


def heading(job: str, title: str) -> str: ...        # title when job in ("", title) else f"{job} — {title}"
def job_start(stops) -> int: ...                     # loses the unread `hub`
def hub_sections(hub_title, hub, board, jobs, *, at_hub, returning, finished=False) -> Rows: ...
                                                     # picks the moment; returning adds ("THE VERDICT", "finished" | "left open")
def place_unmet(place, hub, *, returning) -> str | None: ...   # the two place checks of today's bars
def question_heading(at_hub) -> str: ...
def master_tail(hub, at_hub, board, jobs, job) -> Rows: ...    # THE JOB, JOBS SO FAR, THE BOARD
def board_panel(at_hub, board) -> tuple[Panel, ...]: ...
def jobs_panel(jobs) -> tuple[Panel, ...]: ...                 # `Jobs` only when there is one
```

`job_closed`'s trace becomes `the job {title} closed ({label})` without the text: the narrator
was re-telling the card.

### 3b.3 The drafts, structural (settled 8)

In each scene engine's `worldsmith.py`:

```python
class SceneDraft(Frozen): ...      # as today, minus `job` and `offers`
class JobDraft(SceneDraft):
    job: str = Field(min_length=MIN_JOB)
class HubDraft(SceneDraft):
    offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
class ReturnDraft(HubDraft):
    debrief: str = Field(min_length=1)


def opening_draft(kind: ScenarioKind) -> type[SceneDraft]: ...   # HubDraft for a campaign
```

- `Authoring.answer: Callable[[ScenarioKind], type[BaseModel]]` (`engines/core.py`);
  `app/runtime.py` calls it with the kind; each engine registers `opening_draft`. Tunnel Goons'
  `MapDraft` serves both kinds, so its `answer` ignores the kind.
- `write_next`: `model = ReturnDraft if returning else JobDraft if world.at_hub else SceneDraft`;
  the refusal is `isinstance` against it. `scene_refusal(draft, world)` loses `hub`.
- `_scene_unmet(draft, world)`: today's cast checks, then `place_unmet(draft.place, world.hub,
  returning=isinstance(draft, ReturnDraft))`, then for a `ReturnDraft` `named_in(draft.debrief,
  <every unknown id in world.cast>, known)` refused as "a debrief that does not name what the
  player has not met": the debrief is player-facing text and the worldsmith's cast list holds
  the unmet.
- `apply_scene`: `finished = any(run.job_done for run in world.job_runs())` read before the
  append; `_scene(draft, finished)` builds `Debrief(text=draft.debrief, finished=finished)` for a
  `ReturnDraft`, `job=draft.job` for a `JobDraft`.
- `render_worldsmith`: `hub_sections(..., at_hub=world.at_hub, returning=returning,
  finished=finished)`; `answer` is the model `write_next` picked (pass it in).
- `render_opening`: `intent=CAMPAIGN_OPENING.format(hub=<the engine's example>)`; the examples
  are today's three phrases. `build_scenario`: `scene_refusal(written)`; `opening_canon` reads
  `offers` off a `HubDraft`.
- `worldsmith.md` (three engines): the `offers` and `job` paragraphs go; a one-shot's prompt
  never sees them. `TAKE_BRIEF` already says what `job` holds; `CAMPAIGN_OPENING` and
  `RETURN_BRIEF` gain the pitch sentence: "an offer is a `title` and a `pitch` as the board
  posts it — 'Crates off Deck 9, no manifest, half up front.' — enough to walk out on".
- 24XX: `_with_board` is inlined; `BOARD_GUIDANCE` stays.

### 3b.4 The master judges completion (settled 6)

- Each engine's `next_scene(draft, args: NextScene, rng)`: refuse `job_done` when `world.hub is
  None or world.at_hub` ("no job is open here"); set `run.settled` and `run.job_done`; return
  `(SCENE_SETTLED, JOB_DONE)` when `job_done` else `(SCENE_SETTLED,)`. The tool description
  gains: "In a campaign, set `job_done` when settling this scene also finishes the job the
  player walked out on."
- `rules.md ## Campaigns` (three engines) replaces "When NOTES FROM THE RULES says ..." with:
  "When the story and the player's own words close the job, call `next_scene` with `job_done`;
  settled without it, the job stays open, and the player may go home either way. The SRD's
  between-jobs step, where there is one, is yours to fire when NOTES FROM THE RULES says the job
  closed and was completed. `Go home.` and `I take the job "…".` are the page's own words for
  leaving: play the goodbye in one call or none, then exit." The clause "and the spent note never
  fires" goes: the master cannot act on it.
- `install_scene`'s note logic is unchanged: it reads `job.debrief.finished`, now the master's.

### 3b.5 The engines, lighter

- Each world: `class XWorld(SceneWorld)`, minus `stops`, `job_runs`, `jobs`, `exchanges`,
  `last_seen`, `run`, `current`, `hub`, `board`, `runs`, `source`. `record` ends with
  `spent_note(...)`. `player_view` and `master_sections` use `scene_rows`, `board_panel`,
  `jobs_panel`, `question_heading`, `master_tail`. `render_opening` reads `ONE_SHOT_OPENING` and
  `CAMPAIGN_OPENING` from `hub.py`.
- What stays in the engine, on purpose: `SceneCanon`, the four drafts (the cast type), `_scene`,
  `install_scene`'s `ReturnDraft` branch (the note differs), `check_game` (the message),
  `CAMPAIGN_OPENING`'s `{hub}` phrase, the SRD note text.
- `ui/create.py`: one caption under the kind toggle: "A campaign opens at a home base with a
  board of jobs. Say where home is and who runs it." The one `ui/` touch.

### 3b.6 Content

`scenarios/amber-tap`, `scenarios/waystation`, `scenarios/buried-bell`: the hub `question`
becomes a standing pressure (today's are rhetorical: "What keeps Kael coming back ..."), and
`buried-bell`'s `secret` is rewritten (it repeats Amber Tap's: the board-keeper skims, the hidden
regular has noticed).

### 3b.7 Tests and fixtures

- `tests/core/test_hub.py`: one test per new `hub.py` function. `tests/core/test_scenes.py`
  (new): `SceneWorld`'s walk (`job_runs`, `jobs`, `exchanges` headings), `spent_note`,
  `scene_rows`, `check_hub` on the base. The engines' hub tests keep only what the engine owns
  (`next_scene` with `job_done` sets the run and is refused at the hub; a `ReturnDraft` naming an
  unmet cast member is refused; the return's `finished` comes from the run; `install_scene`'s
  cards and note); the triplicated shared-behaviour tests are deleted. One test per behaviour,
  once.
- Regen: `state/` and `save/` fixtures gain `"job_done": false` per run; `master_tools.json` by
  `next_scene`'s new argument; `master.txt` by the `rules.md` lines; the three campaign fixtures
  by 3b.6; every one-shot `worldsmith` prompt and schema fixture loses `job` and `offers`.
  Nothing else.

**Done when:** green; a one-shot's ANSWER WITH has no `job` or `offers`; `next_scene` refuses
`job_done` at the hub; each scene engine at least 60 lines lighter; `src` about 10,100.

---

## Phase 4 — Tunnel Goons

Full parity on the map's own terms. One implementer.

### 4.1 `engines/core.py`: `told_tail` moves

`told_tail(exchanges: Sequence[Exchange]) -> str` and `TAIL_EXCHANGES` move verbatim from
`scenes.py` to `core.py`; `scene_history` calls `told_tail(run.exchanges)`. Tunnel Goons cannot
import `scenes.py`.

### 4.2 `world.py`

```python
class Visit(Mutable):
    place: CheckedEntityId
    exchanges: list[Exchange] = Field(default_factory=list)
    job: str = ""                        # the open job's title, stamped on every visit while one is open
    debrief: Debrief | None = None       # the tavern's word on the job just reported

class MapCanon(Dungeon):
    start: CheckedEntityId
    source: str = ""
    hub: CheckedEntityId | None = None   # validator adds: check_board; hub set → hub == start
    board: tuple[Offer, ...] = ()

class TunnelWorld(Dungeon):
    ...                                  # as today, plus hub, board, job_done, and in the validator:
    # check_board; hub in places; visits[0].place == hub when set, with no job and no debrief;
    # a debrief only on a hub visit that carries a job; no job, debrief or job_done without a hub.
    # at_hub, stops() (title = visit.job), exchanges() with the job heading (hub.heading).
    job_done: bool = False               # the master's word, set by `level_up` while a job is open
```

`stops()` maps `title=visit.job`, so a stroll into a finished dungeon (`job == ""`) is never a
job stop: without this, walking into an old dungeon and back would open a phantom "job" and
block the board behind "Report in". The take stamps `job` on the tavern visit; `move` copies it
onto every new visit; the report clears it. `new_game` copies `hub` and `board`.

### 4.3 `worldsmith.py`, `worldsmith.md`

```python
REPORT_IN = "Report in."
REPORT_ROW = PanelRow(label="Report in", detail="Tell the tavern how it went.", intent=REPORT_IN)

class MapDraft(Dungeon):
    start: CheckedEntityId
    board: tuple[Offer, ...] = ()        # a campaign's opening tavern only

class ReturnDraft(Frozen):
    debrief: str = Field(min_length=1)   # the paragraph; `finished` is `world.job_done`
    offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
```

`level_up` with a job open (`visits[-1].job`) sets `world.job_done = True`: it is the SRD's
end-of-adventure step, so calling it is the master's verdict (settled 6, 12). Its description
gains: "In a campaign, call it when the job's dungeon is done; the tavern then closes the job as
finished." No note is appended on a return.

- Bars. `map_refusal` (one-shot opening) adds `board == ()`. `hub_refusal(draft)` (campaign
  opening): the start is in `places` and known, every place reachable from it, `BOARD_MIN <=
  len(board) <= BOARD_MAX`; nothing about locks, shortcuts or hidden things — a tavern needs
  none. `job_refusal(draft, world)`: `_map_unmet` (the one-shot bar) plus the id-overlap check
  and `board == ()`. `extension_refusal` adds `board == ()`. The overlap check becomes
  `_overlap_unmet(draft, world)`, shared by job and extension.
- `apply_extension(world, draft)` becomes `attach(world, draft, *, known: bool)`: the two
  appended ways carry `known`; a job attaches known, an extension unknown, so the tavern's
  `Ways out` shows the job's door.
- `write_extension(state, intent, answer)`: at the hub with `intent == REPORT_IN`, refuse with
  "no job is open to report" when `visits[-1].job` is empty, else `answer(_render_return(world),
  ReturnDraft, ...)`; at the hub otherwise, `_render_job(world, intent)` with the job bar; away
  from the hub, the extension as today.
- `install_extension(state, written)`: a `ReturnDraft` sets `visits[-1].debrief =
  Debrief(text=written.debrief, finished=world.job_done)` on the current tavern visit (no visit
  is appended: the player walked home), clears `visits[-1].job` and `world.job_done`, sets
  `world.board`, takes `job = closed_jobs(...)[-1]` and returns `(job_closed(job),)`. A
  `MapDraft` at the hub attaches known, stamps `visits[-1].job` with the region start's name
  (the ledger names the job by it too) and returns `Fact(kind="job_taken", told=True, card=f"A
  way opens: {start.name}")`; away from the hub, as today.
- `_render_return(world)`: `MAP SO FAR`, `JOBS SO FAR` (`ledger`), `THIS JOB` (each visit since
  `job_start`: the place line and `told_tail(visit.exchanges)`), `THE BOARD` (`board_lines`),
  `THE VERDICT` ("finished" | "left open", from `world.job_done`), `THE PLAYER`, `WHAT COMES
  NEXT` = `RETURN_BRIEF` formatted with the tavern (bare: there is no scene to write), `ANSWER
  WITH` `ReturnDraft`. `_render_job` is `_render_extension` plus `JOBS SO FAR`, `THE BOARD` and a
  `THE HUB` line: the region joins the map at the tavern, is a whole dungeon (the opening bar),
  and old dungeons stay on the map.
- `render_map(source, picks, kind)`: a campaign's `MAP SO FAR` says "write the tavern: one
  known place, its keeper and regulars as npcs, no ways out, and a `board` of two or three
  offers". `build_scenario(..., kind)` picks the bar by kind and sets `hub=start`, `board`.
- `map_exhausted` becomes `way_open(state)`: `world.at_hub or frontier(world) == 0`.
- `worldsmith.md`: one paragraph on the tavern and the board, one on a job region.

### 4.4 `views.py`, `rules.md`

- `player_view`: `Board` panel at the hub — `(REPORT_ROW,)` when `visits[-1].job` is set, else
  `board_rows(world.board)`: a job is reported before the next is taken, so none is dropped
  from the ledger; `Trail` from `job_start`; `jobs_panel`. `master_sections`: `master_tail`
  with `job=""` (`question_heading` has no place here: there is no scene question).
- `rules.md`, `## Campaigns`: the tavern is home; the player takes work from the page; a job is
  a dungeon hung off the tavern; there is no teleport home — the player walks, and you may cover
  a known trek in one turn of `move` calls; `level_up` when the job's dungeon is done is your
  verdict that the job is finished, and a job reported without it stays open; `Report in.` and
  `I take the job "…".` are the page's own words: play the keeper's reply in one call or none,
  then exit. "The map's end" says the page also offers work at the tavern.

### 4.5 Content, tests, docs

- `scenarios/<slug>/world.json`, `kind: "campaign"`: one place, the tavern, known; the keeper
  and one regular as npcs; no ways; a board of three. Hand-written; Kael plays it.
- Tests: the world refuses a debrief off the hub and a job stamp without a hub; `way_open` at
  the tavern; `attach` known vs unknown; `write_extension` picks `ReturnDraft` on `REPORT_IN`
  and refuses it with no job open; `install_extension` on a return debriefs the current tavern
  visit with `finished` from `job_done`, swaps the board, clears the job and lands the card; a
  job take at the hub lands the told card, a known way and the job stamp; `level_up` sets
  `job_done` only with a job open; a stroll into an old dungeon and back opens no job and shows
  the board, not "Report in".
- Checked together: the scenario, then regen (`state/tunnelgoons-campaign.json`).
- `docs/TUNNEL-GOONS.md`: deviation 1 says per adventure in a one-shot, per job in a campaign.

**Done when:** green; the tavern hands out a dungeon, the player walks it and back, "Report in"
lands the card; engine at about 1,420 lines; `src` about 10,250.

---

## Phase 5 — the enduring documents

One implementer.

1. `README.md`: one paragraph on campaigns after the engine paragraphs.
2. `VISION.md`: the target architecture names the hub as an engine concern under the seam and
   the two envelope fields as the platform's whole share; the after-MVP0 list loses nothing.
3. `CLAUDE.md`: unchanged unless a rule above proved false; then fix the rule, not the code.
4. `docs/HUB-SPECS.md`: delete; VISION carries the idea, the engine docs carry the rules, git
   history (`c9efa13`) carries the spec. `IDEAS.md` 15 is done and leaves.
5. Delete `PLAN.md` and `PROGRESS.md`, and take `PLAN.md` out of `pyproject.toml`'s
   `extend-exclude`. The git log is the record.

**Done when:** every document says what the code does, and no document holds rules text.
