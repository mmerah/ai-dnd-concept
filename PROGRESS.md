# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Phases 0–6 are done and their per-phase entries were pruned; `git log --stat` holds the detail.
What is below is what a later phase still needs to know.

## Counts

| phase | `src` | `tests` |
|---|---|---|
| start | 9,452 | 6,044 |
| 0 — the probes kept | 9,452 | 6,044 |
| 1 — one engine | 7,471 | 4,411 |
| 2 — the scene kit and the port | 5,806 | 3,408 |
| 3 — the three roles and the tool surface | 5,458 | 3,275 |
| 4 — the pages | 5,625 | 3,393 |
| 5 — the sweep | 5,627 | 3,386 |
| scene transitions rebuilt (off-plan) | 5,791 | 3,519 |
| 6 — the architecture deletion | 5,600 | 3,517 |

Every phase ended with the full check green — pytest, ruff check, ruff format, basedpyright — and
with a turn actually played, not only checked. Phase 4 is the one phase that grew `src`: it added
the new-scenario page, which did not exist before. Phase 6 came in 110 lines under the bottom of
its own range because its step 3 was refuted and added nothing back. **No deletion was ever
invented to reach a number.**

**Every phase was reviewed adversarially against its staged diff, and every review found real
defects.** That is the standing method, not a phase ritual: the reviews caught a scene installed
for the wrong turn, a `kill` that lost what the dead carried, a scene installed with no player in
it, a crash that orphaned the worldsmith, and a claim in this very file that was measured wrong.

## Standing decisions — settled, do not re-propose

1. **The union payload is refuted for good.** `SceneState[S]` is invariant, so a
   `SceneState[LonerSheet] | SceneState[TfxSheet]` gives three strict errors, at `narrator_view`,
   `apply_change` and `apply_scene`. Runtime passes, which is why it would have shipped as a
   silent type hole for anyone who reached for `Any`.
2. **Sheet erasure is refuted too, on the published schema.** Dropping `[S]` from `Entity`,
   `SceneState`, `SceneCanon` and `SceneDraft` passes every runtime check and reports zero type
   errors — but `PlainValidator` has no input schema, so `Entity.model_json_schema()` renders the
   sheet as `{}` and the worldsmith is handed a schema that says nothing about what a sheet is.
   The one untried alternative is a `SceneDraft` that stops reusing `Entity`.
3. **A two-parameter `Game[S, P: EnginePayload[S]]` is rejected by the type checker**: a bound may
   not reference another type parameter. A shared payload base also cannot declare `engine` and
   let engines narrow it to a `Literal` — that is `reportIncompatibleVariableOverride`.
4. **Route 2 works and is the shortest path open**: `Game[S]` with a `SerializeAsAny` payload plus
   a per-engine `Game` subclass. Byte-identical round trip, `twist` and `twist_pack` survive
   `committed()`, one narrow `pyright: ignore`. Cost is ~46 annotation sites; the payoff lands
   with engine two, which is why Phase 6 skipped it. **It was skipped on cost, not impossibility.**
5. **`_gain` + `_rewrite` (31 lines) stay**, and **the tag glossary (24 lines) stays.** Both were
   examined as fat and both are load-bearing: the glossary is the only place a tag's meaning
   reaches the master, and a keyed tag map would trade named sheet fields for string keys and
   change the save shape.
6. **`Scene.ways_out`, a travel tool, and a menu of destinations are all refused.** Authored exits
   rebuild the map ontology the vision threw out. The player's own sentence is the whole brief for
   the next scene.
7. **Speculative scene writing is deleted.** A scene written before the player chooses is a scene
   for the wrong place.
8. **`next_scene` is not a `PendingDecision`.** A decision blocks the master's tools and forces the
   player out of a scene they may still want to play.
9. **A projection type must earn itself.** `NarratorView`'s absence of hidden fields is a real
   correctness boundary and it stays. `PlayerView` fields are read by the page, which imports
   neither the engine nor the kit — that is `VISION.md` §5, not drift.

## Open — known and accepted

1. **`_history` keys a scene's outcomes by title**, so two scenes sharing a title merge their
   history in the worldsmith prompt. Scene ids exist; the join does not use them.
2. **The tag glossary only explains pack tags.** A scenario-invented tag such as "A Guttering
   Lantern" reaches the master unexplained.
3. **`scene_spent` runs after `draft.turn += 1`**, so `SCENE_TURN_CAP = 12` fires on the eleventh
   turn in a scene. It is a safety net and the number is not load-bearing.
4. `IDEAS.md` entries I5 and I7 still say "builtin mode"; `docs/24XX.md` and
   `docs/NEXT-ENGINE-RESEARCH.md` cite the deleted `twentyfourxx/director.md` by path. The engine
   phase rewrites the latter two.
5. The local `saves/whispering-vault--kael.json` does not load and never did after phase 2. The
   home page logs it and skips it; `saves/` is untracked.
6. `tests/core/fixtures/source/drowned-road.{md,pdf}` are kept — `test_documents` reads them to
   test PDF and markdown parsing, not 24XX. `docs/24XX.md` and `docs/BREATHLESS.md` are kept for
   the engine phase.

## Measured before the engines return

No code changed for either measurement; `PLAN.md` phase 8 carries the conclusions.

**24XX: ~1,050 `src` python lines, not the 500 the plan first claimed.** Three methods agree —
scale the old 24XX (932) by Loner's measured port delta (+21.5%) -> 1,132; walk all sixty old
symbols -> 1,035; fixed cost -> 1,005. The cleanest refutation needs no estimate at all: Loner 3e,
the simplest engine here, is 823 lines, and 24XX is larger at every comparable symbol. The port
makes an engine grow: Loner went 675 -> 823, because the engine now owns its typed state, three
payload models, `new_game`, `guidance`, `scene_closed`, and ~34 lines of helpers that came back
when `engines/core.py` fell from 483 to 141.

**Loner is not fat.** By category: 74 imports (9%), ~80 lines of prompt prose (10%), ~104 of state
and pack schema (13%), ~180 of SRD mechanics (22%), ~82 advancement, ~62 creation, ~109 seam
wiring.

**About 40 lines inside `loner3e` name no Loner rule** — `owed_notes`, `party_member`,
`check_packs`, `find_entry`, `ADVANCE_SPENT`, `describe_rows`. They were `engines/core.py` code at
`c9dbf9f`. With one engine that reads as engine code; with two it is duplication. Move them when
the second engine proves each one, and keep the party/ledger cluster apart from the pack and option
lookups.

**Breathless: ~770 `src` python lines**, below Loner and 27% below 24XX. Two methods agree (767,
801); the port-delta method was rejected because it assumes helpers Breathless does not use — a
read confirms zero uses of `party`, `party_member`, `advances_owed`, `ADVANCE_SPENT`, `find_entry`,
`other_than` or `pack_meanings`. It is smaller because **it has no advancement system at all**,
and Loner spends 119 lines on that ledger and its glossary.

**Each engine also regenerates ~1,300–1,400 lines of golden JSON**, because the golden tests
parametrize over `ENGINE_IDS`. Machine-written, but a real diff to read.

## Phase 7

Drafted and split in two. **7A** restructures: it removes the envelope stack, the split tool
dispatcher, the default-engine guess and the two-graph chronology (`src` 5,600 -> about 5,540).
**7B** gives the three roles typed CLI drivers, provider/model/effort settings, resumed provider
sessions and a scrubbed child environment (`src` about 5,540 -> about 5,880). See `PLAN.md` for
the steps. Neither has started.

**7A is not a line-deletion phase, and the plan says so.** An adversarial review measured every
step: most of what 7A touches moves rather than disappears, and `SceneRun` puts the scene fields
into a wrapper instead of deleting them. The win is in the design, not the count. A first draft
claimed about −180 lines; that was wrong and the numbers in `PLAN.md` are the measured ones.
