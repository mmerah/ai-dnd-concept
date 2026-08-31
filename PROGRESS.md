# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Phases 0–7 are done and their per-phase entries were pruned; `git log --stat` holds the detail.
What is below is what a later phase still needs to know.

**Every phase was reviewed adversarially against its staged diff, and every review found real
defects.** That is the standing method, not a phase ritual.

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
| 7A — the restructuring pass | 5,578 | 3,661 |
| 7B — the roles get drivers | 5,892 | 3,901 |

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
6. **`Scene.ways_out`, a travel tool, and a menu of destinations are all refused — in the scene
   kit.** Authored exits rebuild the map ontology the vision threw out from under Loner. The
   player's own sentence is the whole brief for the next scene. **This does not bind the rooms
   kit**, which is an authored map on purpose, for an engine whose printed rules need one.
7. **Speculative scene writing is deleted.** A scene written before the player chooses is a scene
   for the wrong place.
8. **`next_scene` is not a `PendingDecision`.** A decision blocks the master's tools and forces the
   player out of a scene they may still want to play.
9. **A projection type must earn itself.** `NarratorView`'s absence of hidden fields is a real
   correctness boundary and it stays. `PlayerView` fields are read by the page, which imports
   neither the engine nor the kit — that is `VISION.md` §5, not drift.

## Open — known and accepted

1. **The tag glossary only explains pack tags.** A scenario-invented tag such as "A Guttering
   Lantern" reaches the master unexplained.
2. **`scene_spent` runs after the exchange is recorded**, so `SCENE_TURN_CAP = 12` fires on the
   twelfth exchange in a scene. It is a safety net and the number is not load-bearing.
3. **`last_seen` stops counting an entity as seen in a run they left.** An entity removed by
   `leave` is gone from `run.present`, so a later scan does not find them in that run. Fixing it
   would need a field.
4. `IDEAS.md` entries I5 and I7 still say "builtin mode"; `docs/24XX.md` and
   `docs/NEXT-ENGINE-RESEARCH.md` cite the deleted `twentyfourxx/director.md` by path. The engine
   phases rewrite the latter two. `docs/NEXT-ENGINE-RESEARCH.md`'s "OPINION" section is stale in a
   second way: it cites `Entity.exits`, `Engine.seed()`, `authoring/draft.py` and `player_action`,
   all deleted by the scene pivot.
5. The local `saves/whispering-vault--kael.json` does not load and never did after phase 2. The
   home page logs it and skips it; `saves/` is untracked.
6. `tests/core/fixtures/source/drowned-road.{md,pdf}` are kept — `test_documents` reads them to
   test PDF and markdown parsing. `docs/24XX.md` and `docs/BREATHLESS.md` are kept for phase 9.

### The spawned CLIs — measured in phase 7B, still true

7. **The codex master can never resume.** `codex exec resume` accepts neither `--sandbox` nor
   `--approve-for-me`, and a resumed thread answers every MCP call with "approval policy is never".
   Only `--approve-for-me` on a cold start lets a call through. The narrator and the worldsmith
   resume; the codex master starts cold every turn.
8. **Codex keeps a shell.** `--disable shell` and `--disable mcp` are rejected as unknown feature
   flags, so the codex acceptance is least privilege: read-only sandbox (workspace-write for the
   master, which cannot take `--sandbox` beside `--approve-for-me`), empty working directory,
   `--ignore-user-config`, `--disable apps`, `web_search=disabled`, scrubbed environment. Under all
   of that the role still ran `/bin/bash -lc 'echo REACHED'`. **`--ignore-user-config` alone left
   the account's own MCP servers standing** — about a hundred tools — which is what
   `--disable apps` removes. Measured on codex-cli 0.151.0.
9. **Claude keeps `Read`.** Naming no built-in tool re-enables all of them, so one harmless tool is
   the floor. `--tools ""` disables nothing, although `--help` says it does. `--restricted` drops
   the command-running tools and `WebFetch` and confines the file tools to the working directory.
   Measured on Claude Code 2.1.251, where `--model` and `--effort` both exist.
10. **`HOME` is on the allowlist**, so a Claude role can still see `~/.claude`. `--restricted`
    ignores the settings files there; that is the flag's claim, not something the probe showed.
11. **The default models are Claude aliases.** Moving a role to codex means changing `model` in the
    same edit; `opus` is not a codex model.
12. **A cold retry can open on a refusal.** `start_turn` sets `started` but lands no fact, so a
    master that dies straight after it is retried cold, and that retry's first call answers
    `ALREADY_OPEN`. It is an answer, not a crash.

## Measured before the engines return

No code changed for either measurement; `PLAN.md` phase 9 carries the conclusions.

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
