# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Phases 0–7 are done and their per-phase entries were pruned; `git log --stat` holds the detail.
Phase 8 is complete below; the record preserves the decisions the next engine phase needs.

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
| 8 — the second kit and its engine | 8,870 | 5,017 |

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

## Phase 8 — the second kit and its engine

### What shipped

- Steps 1–2 completed the generic engine envelopes and kit callback seam. Every save boundary loads
  through the engine's concrete models; `core`, `turn`, `app` and `ui` consume kit callbacks and
  import no kit.
- `AnyEngine` lives in `engines/core.py`, beside `Engine`, not in `core/model.py`: putting it with
  the erased envelopes would reverse the required `core <- engines` dependency.
- Steps 3–4 added the authored rooms kit: directed ways, holder invariants, `carried_by` cycle
  refusal, movement, unlocking, views, map authoring, and reachability/frontier validation.
- Step 6 added the rooms-only extension flow. Exhausting `frontier` offers the player a brief; the
  worldsmith writes a new authored region and the install joins it without moving or narrating the
  player. It is deliberately not the scene kit's crossing callback.
- The rooms worldsmith prompt is a kit asset at `src/aidm/kits/rooms/worldsmith.md`, paired with the
  scene kit's, so map vocabulary stays with the map ontology.

### The Maze Rats engine was wrong, and was rebuilt against the SRD

The first pass implemented rules Maze Rats does not have and got printed numbers wrong. An
adversarial audit checked every procedure against the verbatim rulebook
(`rules.moddable.games/maze-rats/`, CC BY 4.0). What it found, and what was done:

- **`PLAN.md`'s stated reason for this phase was false.** It justified the rooms kit with "Maze
  Rats' printed procedures — a 3-in-6 wandering check every ten dungeon minutes, travel rates by
  terrain, districts at 1-in-6". **Maze Rats has none of these.** It has three rules pages: Core
  Rules, Character Creation, Character Sheet. Those procedures came from
  `docs/NEXT-ENGINE-RESEARCH.md`, which `PLAN.md` itself flagged as stale. The rooms kit is still
  the right home for an authored dungeon; the justification was not.
- **Eight printed numbers were wrong** and are now the SRD's: XP thresholds `2, 6, 12, 20, 30, 42`
  (were `3, 6, 12, 24, 48, 96`); +2 maximum health per level and no change to current health (was
  +1 to both); rest and medicine heal a flat 1 (were 1d6); initiative rerolled after every round
  (was rolled once); one action per character per side-turn (was one action per side); unarmed −1
  damage (was missing); ambush grants initiative and round-1 advantage (was an unwritten field);
  heavy armour blocks advantage on DEX rolls (was unenforced).
- **Level 7 never received its advancement pick.** The loop skipped past the decision.
- **The shield decision went to the wrong player.** The SRD gives the choice to the defender; the
  code asked the human player even when a monster was the defender, and a test asserted it.
- **`pass_time` was deleted.** The dungeon clock, the 3-in-6 wandering check and monster creation
  from a table are not Maze Rats. The `morale` tool was deleted too: the SRD says morale *is* a WIL
  danger roll, not a separate procedure. `reaction` was promoted from an unused private helper.
  The roster is now six tools mapping one-to-one onto the SRD's own core-rules sections:
  `danger_roll`, `reaction`, `attack`, `cast_spell`, `rest`, `level_up`.
- **The table pack was not the SRD.** Of 42 tables only ~16 were genuine; ~10 had no counterpart in
  Maze Rats and ~8 more carried SRD names over rewritten contents, all attributed to Ben Milton
  under CC BY. The pack is now generated by `tools/import_mazerats_pack.py` from the seven official
  machine-readable table files, verbatim, keeping each table's real entry count. The 36-entry
  constraint that forced the padding is gone: real tables are 34, 35, 36 and 37 long.
- **Character creation followed a misread of step 5.** Light armour and a shield are automatic in
  the SRD, not chosen, and two identical weapons are legal.
- **The shipped character could not play.** `characters/kael/mazerats.json` had no inventory at
  all, so it could make no weapon attack, and carried a `paths` value outside the SRD's four.

### Standing decisions

- `ActorSheet.armour` is the innate bonus **above** the base 6, so the SRD's Armor categories 6–10
  are expressed as 0–4 and PCs derive the rest from worn items.
- `ActorSheet.inventory` was duplicate state: `new_game` materialised those items as cast entities
  while the sheet kept a stale copy that the panel printed forever. The field lives on
  `MazeRatsCharacter` now, where character creation needs it and play does not.
- `CombatState.engaged` was deleted. The SRD's ranged rule is a property of the attacker being in
  melee, not of a frozen pair recorded once at combat start.
- **The `WorldKit` escape hatch was taken, in the small.** `Crossing` and `Extension` shipped as
  two byte-identical dataclasses, and the wiring around them duplicated: `Engine` carried four
  fields for two optional transitions, `GameService._write` and `_write_extension` differed only in
  a log noun, and the scene kit's crossing prompt sat in `app/runtime.py`. One
  `Transition{ready, write, install, narration}` replaces both records; the empty `narration` is
  what makes the rooms extension skip the arrival, so no kit is named above the engine seam.

### Counts, and the target that was missed

`src` is **8,870**, against `PLAN.md`'s "about 7,900". **The target was missed by about 970 lines,
and the number was not chased.** Where it went, measured:

- The Maze Rats rules are simply larger than the plan assumed. `rules.py` is 870 lines *after*
  deleting the invented `pass_time`, because opposed rolls, per-round initiative, per-character
  turn tracking and ambush are all real printed procedures the first pass had skipped.
- The rooms kit and the scene kit were deduplicated rather than left as copies. The six
  `verbs.py`/`render.py` files across both kits and the new shared pair total **910 lines**, against
  **1,000** when rooms was a copy of scenes. The kit tree is **2,065** lines against **874** at the
  end of phase 7, because it now holds a second kit and the shared substrate, not because anything
  grew.
- About 90 lines of confirmed-dead rooms code were deleted, and `app/runtime.py` fell 528 -> 499
  when the two transitions merged.

`SceneState` and `RoomWorld` were **not** given a shared Pydantic base class. It would save roughly
50 more lines and would reorder the fields in every save file, and `PLAN.md` names the save golden
fixtures a contract. The shared surface is a `World` protocol in `kits/entities.py` instead, which
costs no field order. The identical free functions (`check_filing`, `entity_known`) are shared
outright.

### Verification

Full check green: **249 tests passed, `ruff check` clean, `ruff format --check` clean,
`basedpyright` 0 errors**. Golden fixtures regenerated and read: only the `mazerats` fixtures moved,
and every changed line traces to a rule fix (`minutes` deleted, `dosed` added, `inventory` off the
sheet, real starting equipment, the six-tool roster). **The `loner3e` save, state and prompt goldens
did not change**, which is the evidence that the kit deduplication did not move scene-kit behaviour.

Both engines were played from a live build: Maze Rats opens combat, rerolls initiative between
rounds, passes the turn per character, refuses a second swing out of turn, and refuses a rest during
combat.

### The second adversarial review, and what it caught

The review was run against the staged diff with the rulebook on disk. It found **two bugs that broke
play** and nine smaller defects. All are fixed.

- **Carry positions were write-once.** Nothing in `src` ever assigned `ItemSheet.position`, so the
  shipped `pry-bar` — which Kael's own brief names — could never be picked up, and every generated
  character's second weapon was unusable for the whole campaign. **Encumbrance is a printed SRD
  section that had no operation.** It now has one: `stow`, the seventh tool.
- **Opening combat conscripted the whole room.** Every living actor present who was not the party
  became an enemy, and the round could not end until each of them acted, so a friendly NPC — which
  `reaction` exists to create — deadlocked the fight. Combat now enlists the attacker and the target
  only, and latecomers join the side opposite their opponent, which also fixes rosters being frozen
  at the first swing.
- **The "map has a loop" bar was vacuous.** Ways are stored directed, so an ordinary two-way passage
  is already a directed cycle and a dead-straight corridor passed. `_has_loop` was **deleted** rather
  than fixed: `_has_shortcut` is the check that actually enforces an alternate route, which is what
  "loop" was meant to mean. The worldsmith guidance now asks for exactly what the bar enforces.
- Smaller: an opposed roll forced one ability on both sides; `_level_options` offered an ability
  already at +4 and then silently clamped it; a mid-combat `ambush` was silently discarded; medicine
  was detected by a name prefix; the `health` creation step had one option and its pick was never
  read; `PATHS`/`WEAPON_CLASSES` were hand-written beside a `get_args` idiom for the same literals.
- `Transition.narration` was renamed `arrival_brief` — it held a prompt template, not narration — and
  the narrate-or-not decision moved to the two call sites, so no code now decides "is this a
  crossing?" by testing a string for emptiness.
- Five `World` methods duplicated across both kits became free functions in `kits/entities.py`.

The review also verified the good parts independently: the pack importer reproduces `srd.json`
byte-identically, all eight printed-number fixes match the rulebook, and every documented deviation
is real. `docs/MAZE-RATS.md` now lists **16**.

### Final state

`src` is **8,913**. Full check green: **254 tests passed, `ruff check`, `ruff format --check`, and
`basedpyright` (0 errors)**. The `loner3e` save, state, schema and prompt goldens never moved through
any of this work, which is the standing evidence that the kit deduplication changed no scene-kit
behaviour.

