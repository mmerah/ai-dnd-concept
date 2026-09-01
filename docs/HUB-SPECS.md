# HUB-SPECS — campaigns with a home base

What a hub is, what it changes, and what it does not. High level. A `PLAN.md` is written from
this file. Assumes Breathless and 24XX are shipped on Loner's scene lifecycle.

## The one-line idea

> A campaign is one save. Its world has a home base the player keeps coming back to.
> A job is what happens between two visits home. The player takes a job from the board and
> goes; when they come home, the job ends on a card, and the board has moved on.

## Why

1. **Some games are built this way.** 24XX prints "after a job". Breathless is a scavenge loop.
   A crew with a fixer, a party with a tavern, a ship with a captain: the base is the story's
   spine, and the jobs hang off it.
2. **Growth needs a place to matter.** `job_done`, new gear, a new face at the bar: today they
   die with the scenario. In a campaign they carry into the next job.
3. **A job needs a visible start and a visible end.** Clicking an offer starts it. A "job
   closed" card with the debrief ends it. Between those two, play is exactly a scene game today.

## Two kinds of scenario

Both are folders under `scenarios/`, and the home page lists both.

| | one-shot (today's scenarios) | campaign |
|---|---|---|
| `meta.kind` | `"one-shot"` | `"campaign"` |
| opens on | the adventure's first scene or place | the hub, with a board of offers |
| ends when | the story ends, or death | death only |
| the worldsmith writes | the next scene or region | the next job's opening, and the return home |
| the player sees | today's page | today's page plus offer buttons, "Go home" / "Report in", a "Jobs done" panel, chapter headings |

Two words, two levels. A **campaign** is the scenario kind. A **job** is one outing between two
hub visits. "Job" is the design and code word; an engine's panel text may use its SRD's word
(run, delve, chapter).

## Settled

1. **One save.** A campaign is a normal game. No hub file, no save per job, no second writer.
2. **The hub is engine-owned.** The platform learns two envelope things and nothing else:
   `ScenarioMeta.kind: "one-shot" | "campaign"` (badge on the home page, toggle on the create
   page) and `PanelRow.intent: str = ""` (a sidebar row with an intent renders as a button that
   presses Move on with that intent). Neither is a world shape.
3. **A one-shot is a campaign with no hub.** `world.hub is None` means today's behaviour. Every
   engine keeps playing its existing scenarios. `validate` refuses `kind` and `hub` disagreeing.
4. **The hub is a scene** with a fixed place slug. The player plays turns there: talks, shops,
   rests, recruits. Master tools work there as anywhere.
5. **The hub scene carries the board.** `Scene.offers: tuple[Offer, ...]`, `Offer{title, pitch}`,
   non-empty only at the hub. The sidebar shows each offer as a button. Clicking one is Move on
   with the pitch as intent, so the worldsmith writes the job's opening scene from the pitch.
   Free text + Move on still works at the hub, for a job with a twist or for going somewhere
   else.
6. **Going home is a button.** During a job the sidebar shows a "Go home" row. Clicking it is
   Move on with a fixed return intent; the worldsmith is told to write the hub scene. A free-text
   Move on that lands on the hub's place is refused: home is reached by going home.
7. **The return closes the job on a card.** The hub scene carries `Scene.debrief: str`, the
   worldsmith's one paragraph on the job just left, and `Scene.finished: bool`. On install the engine emits a told
   `job_closed` fact whose card is the debrief, so the transcript shows a chapter-end card
   before the arrival narration. The same paragraph is the note to the master: "a job closed;
   if it was completed, the between-jobs step applies."
8. **An unfinished job is marked.** The return draft carries `finished: bool`. The card reads
   "Job done: <title>" or "Job left open: <title>". The between-jobs step is noted to the master
   only when `finished`. The worldsmith is told an open job normally stays on the board, so the
   player can take it again. Going back is taking it again: scene engines get a new opening
   scene, written with the ledger, the same place slug and the same cast, so the art and the
   faces return; in Tunnel Goons the region is still on the map, and going back is walking in.
9. **A job is derived, not stored.** A job is the runs between two hub-placed runs. Its title is
   its opening scene's title. The ledger is the `debrief` of each hub run. Nothing is filed on
   install; nothing is indexed on `SceneRun`.
10. **Memory is the ledger.** The worldsmith prompt holds full scenes for the current job and one
   line per closed job: the job title and its debrief. Older scenes stay in the save and leave
   the prompt.
11. **The board persists.** The worldsmith sees the current board when it writes a return, and
    returns the new board: keep, drop, add. Two or three offers total, refused otherwise. An offer
    still there next visit makes the world feel like a world.
12. **Reputation is prose.** No SRD prints a reputation counter, so none is built. The ledger and
    the sheet are what the worldsmith reads to decide which offers fit. A "Jobs done" panel
    (title, one-line debrief) shows the player how far they have come.
13. **No new master tools.** 24XX is at fifteen. The board, the debrief and the return are the
    worldsmith's and the transition's, not a tool's.
14. **No write-back to `characters/`.** Growth lives in the save. A second campaign starts the
    same character fresh.
15. **Death ends the campaign.** As every engine does today.
16. **`PLAN.md` Settled 6 stands.** Breathless and 24XX gain no companions. The worldsmith prompt
    says: anyone from the hub's cast the player names in their intent is `present` in the job's
    opening scene. Loner's companions travel as they do now. A guaranteed crew list would be
    companions by another name; it is not built.
17. **Fidelity first.** Where an SRD prints a between-jobs step, the hub is where it fires. Where
    it does not, nothing is invented. 24XX: `job_done`. Loner: the master's growth line.
    Breathless: none (the SRD prints no between-runs step).

## How it plays

```
home page ── campaign badge ──▶ play page
                                  │
                       ┌──────────▼──────────┐
                       │  THE HUB (a scene)  │◀──────────────────────────┐
                       │  sidebar: 2–3 offer │                           │
                       │  buttons; turns:    │                           │
                       │  talk, shop, rest   │                           │
                       └──────────┬──────────┘                           │
             click an offer (or free text + Move on)                     │
             worldsmith writes the job's opening scene from the pitch    │
                       ┌──────────▼──────────┐                           │
                       │  THE JOB            │  scenes, as today         │
                       │  scene → scene → …  │  sidebar: "Go home" row   │
                       └──────────┬──────────┘                           │
             click "Go home"      │                                      │
             worldsmith writes the hub scene + debrief + the new board   │
             card: "Job closed: <title>" + debrief; then the arrival ────┘
```

1. A campaign scenario opens at the hub. The board already holds offers. The authored opening
   has no debrief; every later hub scene must.
2. The hub scene is always open: `ready = settled or at_hub`. The core "more beyond here" banner
   is not shown there; the hub's own `This scene` row says "Take a job from the board, or name
   where you go". `rules.md` tells the master the hub is always open, and `scene_spent` never
   nags at the hub.
3. The player clicks an offer. The worldsmith gets the pitch as WHAT COMES NEXT and writes the
   job's opening scene. Existing bar, existing arrival narration.
4. The job runs as scenes run today. The master's picture and the narrator's view do not change.
   The sidebar's "Trail" panel lists this job's scenes only.
5. The player clicks "Go home". The worldsmith writes the hub scene. The return bar refuses a hub
   scene without a `debrief` or without two or three `offers`, and refuses either anywhere else.
6. On install: the `job_closed` card, the note to the master, the arrival narration. The board
   panel shows the new offers; the "Jobs done" panel gains a line.
7. The chronicle heads each exchange `<job> — <scene>`, so the transcript reads as chapters.
   Nothing more is built for chapters.

Two worldsmith waits back to back (return, then the next job) is the always-open hub's worst
case. It is inherent. The card and a cheap fixer turn in between are the mitigation; do not
"fix" it with pre-written openings.

## What each engine adds

Under the seam. Build it in one engine first; the second engine's phase is the verbatim move
to `engines/core.py`, as `PLAN.md` Settled 1 says. About 100 lines per scene engine.

| engine | hub | job | between-jobs step |
|---|---|---|---|
| 24XX | the fixer, the ship, the station bar | the SRD's job | `job_done` (printed) |
| Breathless | the camp, the safe house | a run | none |
| Loner | the guild hall, the ship | a chapter | the master's growth line |
| Tunnel Goons | the tavern, a `Place` | a region attached to the tavern | `level_up` (printed) |

Shared shape: `world.hub: Slug | None`; `Scene.offers` and `Scene.debrief`; the return
refusals; the compacted history; the board rows, the "Go home" row and the "Jobs done" panel;
`ready = settled or at_hub`.

**24XX** gets a fidelity win: the SRD's optional d6 job-finding setup, which the engine does not
model today, is exactly what the board is. The worldsmith is handed the table rows as prompt
guidance when it writes offers. Prompt bytes, not code.

**Tunnel Goons — full parity, on the map's own terms.** The hub is a tavern `Place`
(`world.hub`). The board hangs on it. A job is a region the existing `extend` attaches to the
tavern, written from the pitch, and held to the one-shot map bar (four or more places, a locked
way, a shortcut), not the two-place extension bar. The player walks out and crawls it as today;
the seam stays invisible. There is no "Go home" teleport: the player walks back, and the master
may cover the trek in one turn. At the tavern with a job open (derived: the previous visit was
not the tavern), the sidebar shows a **"Report in"** row. Clicking it is Move on; `write`
returns a `ReturnDraft{debrief, finished, offers}` instead of a `MapDraft`, and install emits the
`job_closed` card, swaps the board and notes `level_up` to the master. `ready = at_hub or
map_exhausted`. Old dungeons stay on the map and can be walked again. About 120 lines; Tunnel
Goons is at about 1,300.

Platform line this needs: a silent install (`arrival_brief is None`) today commits its facts
without recording them, so the card would vanish. `_install` records them as a lineless segment.

## Platform touches

1. `ScenarioMeta.kind`. The create page asks; `Authoring.prompt` and `Authoring.build` receive
   it so the worldsmith writes an opening hub with a board instead of an opening scene.
2. `PanelRow.intent`. The sidebar renders a row with an intent as a button that plays Move on
   with it. The play page learns nothing about jobs.
3. Home page: the badge. Nothing else; the home page reads no engine payload.
4. `_install`: a silent install records its facts as a lineless segment, so a map engine's
   `job_closed` card shows.

Not done, on purpose: no session reset at the job boundary (`app` knows no job), no
`PendingDecision` for the board (`PLAN.md` Settled 15: an offer does not block the master's tools),
no reputation counter, no crew list.

## Content

- `scenarios/<id>/world.json` with `meta.kind = "campaign"`: the opening hub scene, its cast
  (the fixer, the regulars), and a starting board. One per scene engine, plus a tavern map
  (one known place, no ways out, a board) for Tunnel Goons; its authoring bar is that, not the
  one-shot map bar.
- Existing scenarios are untouched and stay `"one-shot"`.

## Risks

1. **Prompt growth.** The ledger is one line per job played. Twenty jobs is twenty lines.
   Acceptable; if a campaign outgrows it, the worldsmith compacts the ledger itself in a later
   phase.
2. **Engine size.** 24XX targets 1,600 lines before the hub. Count after the design above, not
   before; if it does not fit, build less, not elsewhere.
