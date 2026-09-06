# NEXT-SPECS — after the hub

Tracks A through F of the 2026-09-02 brainstorm became `PLAN.md` and were cut from this file;
Track R (the seam refactor) became PLAN.md Phase 5 the same day and was cut too. Track G (the
party, then crews) became `PLAN.md` on 2026-09-06 and was cut, with two of its shapes replaced
(the sheet comes from a `hire` arm, not the worldsmith; succession keeps ids). What stays: the
maintainer's decisions and what was left in `IDEAS.md` or refused.

## Decisions made in the brainstorm (the maintainer's, 2026-09-02)

1. **One scene engine, three payloads.** `engines/scenes.py` may take pydantic type parameters
   on the cast and player types. PLAN.md settled 7 ("no type parameter") retires with PLAN.md.
   Loner's player leaves the cast and lives as `world.player`, as in 24XX and Breathless; Loner
   saves go stale, which the design allows.
2. **Memory is a recap the worldsmith writes on the crossing.** No summarizer role. The
   window is `SCENE_EXCHANGES` in `core/views.py`, 20, a constant and not a setting. The
   summary at the return and the three depths landed 2026-09-03; "no summarizer role" stands.
3. **Voices are an HTTP provider on the illustration pattern**: off by default, the OpenRouter
   key the player already has, a local server if they run one, and the narrator's voice chosen
   per scenario as its art style is. No in-process model.
4. **The tool cap stays fifteen, counted as tools plus `change_world` arms**, the two party
   arms every engine carries (Track A) not counted. An engine whose SRD plays a crew (Track G)
   may go to twenty in all; its `docs/<ENGINE>.md` says so. No fold is made for the count's
   sake. Since 2026-09-04 the cap reads: at most fifteen engine tools plus `commission`, the
   platform's, counted as tools plus `change_world` arms, the two shared party arms not counted.
   Since 2026-09-05 `commission` is gone; the cap is fifteen engine tools, counted as before.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
   Since 2026-09-05 the campaign layer is gone (PLAN.md Phase 1); moving home went with it.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects. PLAN.md Phase 6.2 (rewrite VISION's architecture)
   is skipped: Track F deletes the file.
7. **Party play (IDEAS 16) is in scope, in two layers.** A minimal party every engine gets:
   an NPC joins and follows the player, is interacted with, and every role reads it as part of
   the party the player leads; the master applies the engine's own help knob. Then engine
   layers on top: 24XX sheets, help dice, the ship and succession; Tunnel Goons goons who roll
   and level. Retires PLAN.md settled 17 (no companions gained) and 19's "no crew list"; closes
   `docs/24XX.md` deviations 1, 2, 3 and the ship half of 4, and `docs/BREATHLESS.md` 5.
8. Ponytail audit: dropped. Eval loop (IDEAS 4): stays in `IDEAS.md`.

Standing rules from `CLAUDE.md` bind every track: engines self-contained under 2,000 lines; one-way
imports; `core`/`turn`/`app`/`ui` know no world shape; only the narrator writes player-facing
text from revealed facts; only resolver code changes state or rolls; a bad answer is re-prompted
once; saves carry no version; no abstraction until two things need it; no building for later.


---

## Left in `IDEAS.md`, on purpose

- Moving home (D.5), with its sketch.
- The eval loop (IDEAS 4): a script against live CLIs, the only way to answer "does it play
  better"; the tool cap and Track G's help rule are the first two questions it would settle.
- Pack authoring (13) and the demo GIF (11).
- 24XX's priced gear table and d20 detail tables as pack data; Breathless and Loner deviations
  (none of the tracks touches a table procedure or a way-back procedure).
- Crew play for Breathless and Loner beyond what G leaves them.

## Refused in this round, with the reason

- A summarizer role: a fourth spawn per crossing for a paragraph the worldsmith already can
  write in the answer it gives.
- A "Previously…" narrator spawn on resume: the page opening at turn 1 was the bug (D.2).
- In-process Kokoro: torch or onnxruntime plus a 300 MB model in a seven-dependency project,
  untyped under strict pyright; the same model behind its HTTP port is Track C.
- Raising the cap for its own sake, or folding a tool for the count's sake: no engine is
  blocked, and flattening arms is token-neutral and unmeasured.
- A separate `crew` store, a `Regular` class, a `Ship` model, a `PARTY_MAX`, a `Scene.crew`
  stamp: each was a second way to hold what the cast, an `Item` or the party already holds.
- `Offer.follows`, a reputation counter, a second concurrent home: prose and the ledger do it.
- The master as its own worldsmith (the first seam review's fourth proposal): the maintainer's
  call. Authoring is a second profession; scenario creation needs the role anyway; the
  fifteen-tool cap is the master's attention budget.
- One flat scene draft with optional `recap`, `job`, `offers`, `debrief`: the five classes are
  the schema the worldsmith answers in, and pydantic enforces which fields a crossing, a job or
  a return owes; a flat draft moves that demand into prose and the bar, and the seven
  `isinstance` sites become seven `if draft.offers` sites.
- A `SceneRules` record and a `scene_engine` factory in place of `SceneEngine` (PLAN 5.1): the
  same surface, with a `partial` per field where the class carries `packs` and `cast` on
  `self`.
- Folding the `Kill` arm into `engines/base.py`: 24XX's succession (G.2) changes what a kill
  does, so the arm stays per engine.
