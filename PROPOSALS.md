# Simplification and consistency proposals

Six independent full-codebase reviews (five subagents plus the session author), merged.
Every claim below was re-verified against the source before it was written down.

**Baseline at the time of review:** 565 tests pass in 6.3s; `ruff check`, `ruff format --check`
and `basedpyright` are all clean. 9,897 lines under `src/`, 9,236 under `tests/`, 2,292 under `qa/`.

Notation: **[n/6]** is how many independent reviewers raised the item.
Effort is S (under an hour), M (half a day), L (a day or more).

---

## 0. Start here

Ten proposals, ranked. The first five are small, agreed, and need no decision from you.

| # | Do | Where | Effort |
|---|---|---|---|
| P1 | Delete two provably dead guards | `turn/run.py:117,131-134` | S |
| P2 | Fix the MCP argument-validation escape (**a bug**) | `app/mcp.py:87` | S |
| P3 | Move the per-engine palettes onto `Engine` | `ui/theme.py:26-73` -> `engines/seam.py` | M |
| P4 | Give `Survivor`/`Crewmate` a shared sheeted base | `breathless/world.py`, `twentyfourxx/world.py` | M |
| P5 | One generic `ChangeWorld[C]` instead of four | `engines/*/tools.py` -> `engines/base.py` | S |
| P6 | Split `core/views.py` into models and prompt rendering | `core/views.py` | S |
| P7 | Evict the single-family symbols from `engines/base.py` | `engines/base.py` | S |
| P8 | Compute the view and the history once per turn | `runtime.py`, `seam.py`, `turn/run.py` | M |
| P9 | Split `GameService` | `app/runtime.py:59-361` | M |
| P10 | Add CI; bring `qa/` under the linters | `.github/`, `pyproject.toml` | S |

**This list was cut from twenty.** The ten dropped were the ones I was least sure of: moving
`core/creation.py`'s option helpers, moving `core/source.py` to `app/`, merging the two
`Reveal`/`Kill` pairs, merging the unmet-reason joiners, splitting `Runtime`, splitting
`LauncherCatalog.read`, splitting `app/spawn.py`, decomposing `ui/game.py`, and three test-suite
tidying moves. Where the underlying observation was worth recording it survives in Section 4 as a
finding. None of them was a defect — only taste.

---

## 1. Settled decisions

Nine are made; the rest are in Section 5.

The first three came out of the merged review and no
longer carry a number. The rest are D1-D6 from Section 5, answered in a walkthrough.

### The `engines/rooms/` family stays. **Settled: keep it.**

`rooms/` is 834 lines with one shipping user (**verified:** the only importer outside `rooms/`
itself is `tunnelgoons/`), and its only second implementer is the `SixthEngine` fixture in
`tests/core/test_rooms.py`. The family stays anyway.

What should still be fixed is its asymmetry against `scenes/`, which is a defect either way:

1. `scenes/` appends a family `rules.md` at `scenes/engine.py:96`; rooms has none. Add
   `rooms/rules.md`, or make the family suffix an explicit, possibly-empty hook on `Engine`.
2. `rooms/drafts.py` is 10 lines and its one class **imports the world** (`rooms/drafts.py:4`), so
   the stated reason for a separate `drafts.py` (`scenes/worldsmith.py:41`: "the drafts may not
   import the world") does not apply to it. Move `MapDraft` into `rooms/world.py`.
3. `EXTEND` (`base.py:20`) is a rooms-only constant in the shared base. Move it — part of P7.
4. Four verb pairs diverge for the same roles: `render_opening`/`render_map`,
   `render_next`/`render_extension`, `write_next`/`write_extension`, `install`/`install_extension`.
   Align them on the `scenes/` names.
5. `RoomEngine.advance` (`rooms/engine.py:188-193`) never checks `request.operation == EXTEND`,
   while `SceneEngine.advance:331` does branch. One line closes it (C17).

About 2 hours for all five. Also settled by this: `MapDraft` and `RoomCanon` (both `Dungeon + start`)
stay separate — the compile-time guarantee that a draft is not a canon is worth the duplicate shape.

### The four `ChangeWorld` wrappers. **Settled: one generic in `engines/base.py`.** Now **P5**.

### One labelled-value vocabulary. **Settled: the full rename.**

Six spellings of "a thing with a name and a line" collapse to one law: **`id` / `label` / `detail`**,
with `icon_id` as the single extension. The work, in one commit, when nothing else is in flight:

1. Delete `Action` (`core/views.py:59`) — **verified** field-for-field a `DecisionOption`
   (`core/play.py:62`); `DecisionOption` additionally has `min_length=1` on `label` and
   `detail: str = ""`. The constants `MORE_MAP` and `MOVE_ON` change type only.
2. Delete `Named` (`core/model.py:48`) — one use, at `core/model.py:57`.
3. Collapse `Rows` and `Sections` (`core/views.py:21-22`). They are PEP 695 aliases of the identical
   type, so the checker already treats them as one — a sheet can be passed where a prompt section is
   expected with no error. Name the survivor for what it is.
4. Rename `Subject.name`/`brief` -> `label`/`detail` (`core/views.py:25`). Touches
   `base.py:92,225-262`, `media.py:176,193`, `turn/context.py:92-96` and all four engines.
5. Make `CatalogEntry` (`app/launch.py:14`) a `Labelled` plus `engine` and `rules`. Note `subtitle`
   currently means two different things — a premise at `launch.py:73`, a brief at `:83`.
6. Add the naming law to CLAUDE.md, or it will not hold.

~30 sites, all mechanical. The golden schema fixtures churn; regenerate with `AIDM_GOLDEN_REGEN=1`
and read the diff.

**Not covered by this decision, and still open:** whether the same tidying applies to `draft` and
`prompt`, which mean three and five things respectively (C5). Left alone.

### D1 — Replace the `operation` string dispatch? **Settled: no, option A — D3 answers it.**

The hiring mixin (D3) removes 5 of the 11 hand-written comparisons: `seam.py:191`, `seam.py:197`,
and the three `!= HIRE` guards at `breathless:197`, `tunnelgoons:156`, `twentyfourxx:306`. It also
removes the three hand-synced `operations` lines.

What is left is six sites, all inside the two family bases, and only four of them are `if`s:
`scenes/engine.py:207,209,331` and `rooms/engine.py:177`. The other two (`scenes:109`, `rooms:74`)
are membership tests against the declared list. Replacing four `if`s across two files with an
`Operation` value type would be ceremony. Leave it.

**Still worth doing, 2 minutes:** `rooms/engine.py:62` says `operations = (MORE_MAP.id,)` while
`:177` says `request.operation == EXTEND`. `MORE_MAP.id` **is** `EXTEND` (`rooms/engine.py:48`) —
one value, two spellings, one file. Make line 62 say `(EXTEND,)`.

### D2 — Delete `Fact.kind`? **Settled: yes, option A.**

50 label values are written; **exactly one is read** by the running game
(`loner3e/engine.py:205`, `fact.kind == "conflict_lost"`). `core/facts.py:10` defines
`DICE = "dice_rolled"`, which looks like a filter but is never read as one — the dice tray selects
facts by *having dice* (`ui/dice.py:36`), not by kind.

The work:
1. Change `_strike` (`loner3e/engine.py:251`) to return `(facts, ended: bool)`. It already knows at
   `:259` (`if hit.luck.current != 0`). The caller at `:205` reads the flag instead of the label.
2. Remove `kind` from `Fact` (`core/facts.py:35`) and the `kind` argument from `Thing.fact()`
   (`base.py:73`) and its ~60 call sites.
3. Delete `DICE` (`core/facts.py:10`) — write-only once `kind` is gone.
4. Drop the ~80 test assertions that check `kind` and nothing else. CLAUDE.md calls those wiring.
5. Regenerate the four turn goldens.

**Lost:** a readable label in save files. `trace` already says what happened, in better English.

### D3 — How is hiring factored? **Settled: a mixin, option B.**

The three hiring engines (breathless, tunnelgoons, twentyfourxx) opt in; loner3e does not, and stops
carrying five pieces it never uses: `Engine.hire` (`seam.py:180`), the HIRE branch of
`Engine.unwritten` (`:191`), `Engine.check_request` (`:195`), `World.require_hireable`
(`base.py:144`, a method whose whole body is a refusal with its argument unused), and
`World.sign_on` (`base.py:147`).

The mixin also absorbs the six-step `advance` block written three times
(`breathless/engine.py:194`, `tunnelgoons/engine.py:153`, `twentyfourxx/engine.py:303`), leaving each
engine only its prompt text and its sheet shape — steps 3 and 5, the two that are genuinely
per-ruleset.

**Scope and naming.** Hiring is *not* the party. `World.join`/`part` (`base.py:128,137`) and the
`JoinParty`/`LeaveParty` verbs are used by **all four** engines, loner3e included
(`loner3e/tools.py:9,59`). What the three share is narrower: bringing in someone whose **sheet must
be authored by the worldsmith**. So the mixin must not be called `Party` — that word already means
something every engine has. `Hiring` is precise. A `Crew` framing works only if it stays about
authored companions and does not annex the party verbs.

The mixin should also own its own operation, so `operations = (*SceneEngine.operations, HIRE)` —
repeated by hand in three engines (`breathless:73`, `tunnelgoons:74`, `twentyfourxx:76`) — is
contributed by the mixin instead.

**Do a short spike first** to confirm a mixin composes cleanly through
`Engine[P, G]` -> `SceneEngine[C, P, G, K]` -> concrete. If it does not, fall back to option A, a
template method on the seam.

**Blocked on coverage.** Breathless and 24XX have no multi-turn test at all (Section 7 §1), and
24XX's hire-then-succession path has no end-to-end test (§2). Write the §2 test first.

### D4 — Should `config.py` move under `app/`? **Settled: no, option A — fix the rule instead.**

`config.py` imports one project symbol (`core.entities.Frozen`) and is read by `app` (6 files) and
`ui` (3 files). **Verified: `turn/` imports it nowhere.**

Two lines to change, and both a rule and a test become true:
1. CLAUDE.md: *"Only `turn`, `app` and `ui` read the settings"* -> *"Only `app` and `ui` read the
   settings"*.
2. `tests/core/test_package_boundary.py:22`: `"aidm.config": ("turn", "app", "ui")` ->
   `("app", "ui")`.

This matters beyond tidiness: the one property `turn/` earns as a separate layer is that `Turn`
cannot reach a `Spawner`, a `Settings` or a `GameService`. The rule as written weakened that on
paper while the code kept it.

`config.py` stays at the top level, in no layer. Accepted.

### D5 — Where does prompt rendering live? **Settled: option B, split by owner.**

Each of the three renderers has exactly one caller:

| Renderer | Called from |
|---|---|
| `render_master` (`turn/context.py:23`) | `turn/run.py:92` (`Turn.picture`) |
| `render_narrator` (`:47`) | `app/runtime.py:284` (`GameService._narrate`) |
| `render_interjection` (`:60`) | `app/runtime.py:185` (`GameService.interject`) |

The work:
1. Fold `render_master` into `turn/run.py`, beside `Turn.picture`.
2. Move `render_narrator`, `render_interjection` and `_picture` (`:81`) into `app/`, beside
   `GameService`. `turn/context.py` disappears.
3. `turn/prompts/master.md` stays; `narrator.md` and `interjection.md` move to `app/prompts/`.
4. `_prompt` (`:109`, the cached file reader) is then needed in both places -> move it to
   `core/io.py` as `read_prompt(path)`.

Step 4 is worth doing on its own (C4): there are currently **three** mechanisms for reading a prompt
file — at import time (`scenes/engine.py:55-56`, `rooms/engine.py:47`), at construction
(`seam.py:52`), and cached-lazy (`context.py:109`). The import-time ones mean importing a module
performs disk I/O and can raise `OSError` from an `import` statement, against "side effects live at
the edges". One shared cached reader fixes all three.

**Explicitly rejected: merging `turn/` into `app/`.** It would push `app/runtime.py` past 750 lines
and throw away the compile-time guarantee above.

### D6 — Null Object for `media` / `reader`? **Settled: no, option B — extract a `Presenter`.**

The `X | None` fields stay. What moves is where the checks live.

`GameService` gives up `media`, `reader`, `_background`, `_retain`, `_present`, `illustrate`,
`speak`, `scene_art`, `icon`, `newest_clip` and `_newest` to one ~45-line `Presenter` whose whole
job is showing things to the player. This is part of **P9**.

A Null Object was rejected because it does not finish the job: five of the six guards would go, but
`ui/game.py:171` asks *"is this feature on at all"*, not *"is it safe to call"* — so an `enabled`
flag comes back and you have two new classes for four deleted `if`s. `Presenter.polls` answers that
question honestly instead.

**Bonus, and the reason to prefer B:** it fixes C23. `reload_settings` (`runtime.py:439-442`) calls
`session.hush()`, which cancels only the interjection task — in-flight art and speech tasks keep
running and write into the evicted session's folder, though the comment at `:440` claims eviction
stops the writing. A `Presenter` that owns `_background` can actually drain it.

---

## 2. Concept inventory

Every concept the codebase defines, by layer. The **Verdict** column is the merged judgement;
proposals referenced as `P<n>` are in Section 3, findings as `C<n>` in Section 4,
open decisions as `D<n>` in Section 5.

### 2.1 `core/` — the shape-free kernel (967 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Slug` / `EngineId` / `EntityId` / `CheckedEntityId` | `core/entities.py:10,13,14,16` | Four id grammars, split by who wrote the id | Keep — load-bearing |
| `Frozen` / `Mutable` / `Loose` | `core/entities.py:19,23,29` | The three Pydantic base configs | Keep; see C11 (a fourth exists in `app`) |
| `Refusal` | `core/entities.py:35` | The one exception a role or player reads | **Do not touch** |
| `parse` | `core/entities.py:56` | The single `ValidationError` → `Refusal` funnel | **Do not touch** |
| `content_id` / `slug` / `require_unique` | `core/entities.py:39,46,51` | Id narrowing, minting, duplicate bar | Keep; `require_unique` misused twice (C6) |
| `Fact` | `core/facts.py:32` | One thing that occurred | Keep; `kind` is questionable (**D2**) |
| `Fact.kind` | `core/facts.py:35` | Event category | **50 literals written, 1 read** — see **D2** |
| `DiceEvent` / `roll` / `cards` / `traced` | `core/facts.py:13,51,42,47` | The only die roller and the two fact renderings | **Do not touch** |
| `Line` / `SpokenLine` / `Narration` / `Interjection` | `core/play.py:10,20,38,44` | The narrator's typed answers | Keep |
| `DecisionOption` / `PendingOption` / `PendingDecision` | `core/play.py:62,68,75` | The suspended-decision machinery | Keep |
| `Answer` | `core/play.py:91` | Player input: option xor text | Keep |
| `Exchange` / `SceneRecord` | `core/play.py:108,127` | The unit of play; the unit of history | Keep; `SceneRecord` is rebuilt wastefully (P8) |
| `Scenario[P]` / `Character[P]` / `Game[P]` | `core/model.py:60,74,94` | The three persisted envelopes | Keep |
| `ScenarioMeta` | `core/model.py:27` | title/premise/scope/art_style/voice | Keep |
| `EngineHeader` / `CharacterHeader` | `core/model.py:42,55` | Routing headers read before the engine is known | **Do not touch** |
| `Named` | `core/model.py:48` | (name, brief) | One use (`model.py:57`) — see Section 1 |
| `Generation` | `core/model.py:86` | An engine's one request to the worldsmith | Keep; string dispatch is the issue (**D1**) |
| `WorldsmithAnswer` / `Check[T]` | `core/model.py:82,24` | The ask protocol and its extra bar | Keep; `Check` name collides (C5) |
| `Game.draft()` / `.commit()` | `core/model.py:113,117` | Working copy; whole-tree revalidation | **Do not touch** |
| `Subject` | `core/views.py:25` | (id, name, brief) as roles and art see it | Keep; field names drift (Section 1) |
| `Panel` / `PanelRow` | `core/views.py:46,40` | Sidebar row and its group | Keep; `PanelRow` is a stringly-typed 3-way variant (C12) |
| `Action` | `core/views.py:59` | The page's way-on button | **Field-for-field a `DecisionOption`** — see Section 1 |
| `DiceLook` | `core/views.py:51` | Per-engine dice colours | Keep — and the model for P3 |
| `NarratorView` | `core/views.py:67` | The narrator's input; structurally free of hidden canon | **Do not touch** |
| `PlayerView` | `core/views.py:135` | What the pages read | Keep; the UI bypasses it (C8) |
| `Rows` / `Sections` | `core/views.py:21,22` | Two aliases of one type, distinguished by a comment | Merge or `NewType` — see Section 1 |
| `sections` / `lines_of` / `render_history` / `told_history` | `core/views.py:145,149,153,160` | Prompt text assembly | Split out of `views.py` (P6) |
| `FileStore` / `Library` | `core/io.py:25,53` | Saves; scenarios + characters on disk | Keep |
| `decode` + `_unique_keys` | `core/io.py:147,183` | Duplicate-key-rejecting JSON | **Do not touch** |
| `routed` / `write_text` | `core/io.py:155,139` | Engine routing; atomic staged write | **Do not touch** |
| `MasterTool` / `master_tool` / `Play` | `core/tools.py:28,35,14` | Tool record, factory, resolver signature | **Do not touch** |
| `Attempt` | `core/tools.py:18` | The `what` field four engines extend | Keep; it is game vocabulary in `core` (C18) |
| `schema_of` / `_normalize` | `core/tools.py:50,61` | One schema pipeline for MCP and prompts | **Do not touch** |
| `CreationStep` / `Picks` / `check_picks` | `core/creation.py:10,6,23` | Creation questions and their one legality rule | Keep |
| `other_than` / `option_of` / `chosen_option` | `core/creation.py:38,42,46` | `DecisionOption` list helpers | Sit oddly in a creation module; `turn/run.py:9` imports `option_of` from it |
| `given_text` / `whole_text` | `core/source.py:14,22` | PDF/text source ingestion | One caller, in `app` (`runtime.py:454`); arguably not kernel |

### 2.2 `config.py` (165 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `ProviderConfig` / `Providers` | `config.py:20,97` | base_url + key per provider | Keep |
| `RoleConfig` / `Roles` | `config.py:25,74` | Per-role provider/model/effort/timeout/max_rounds | Keep; `each()` duplicates `for_name()` (C13) |
| `MediaConfig` / `SpeechConfig` | `config.py:51,61` | Optional features, both off by default | Keep |
| `Settings` + `_keys_present` | `config.py:115,137` | The `.env` surface with a cross-field key check | Keep |
| `Role` / `ProviderName` / `CliProvider` / `RoleProvider` / `Effort` | `config.py:11-16` | Five string literals; `RoleProvider` is deliberately flat | Keep — the flat union is justified in a comment |
| Placement of `config.py` itself | outside every layer name | — | See **D4** |

### 2.3 `engines/` — the world layer (5,234 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Engine[P, G]` | `engines/seam.py:37` | The seam: 11 class attrs, 12 abstract, ~15 concrete | Keep; **not** an ISP problem (C4) |
| `Engine.compose` | `engines/seam.py:91` | Build-inside-the-bar so an unbuildable opening re-prompts | Keep |
| `Engine.close`/`commit`/`begin`/`restore` | `engines/seam.py:114,132,136,69` | The state lifecycle | Keep; `commit` names three things (C9) |
| `Engine.answer` | `engines/seam.py:82` | Play a `PendingOption` as a tool call | Keep |
| Hire machinery | `seam.py:180-198`, `base.py:144,147,168,215` | `hire`, `unwritten`, `check_request`, `require_hireable`, `sign_on` | 3 of 4 engines — see **D3** |
| `AnyEngine` | `engines/seam.py:28` | `Engine[Any, Any]` | Keep — the sanctioned `Any` |
| `build_engines` | `engines/registry.py:9` | The one composition root | **Do not touch** |
| `Thing` / `Person` / `World[P]` | `engines/base.py:38,96,113` | The entity hierarchy | Keep |
| `Counter` | `engines/base.py:182` | Bounded current/max with fact-emitting `change` | Keep |
| `Pack` | `engines/base.py:176` | Table-set base — **scene engines only** | Move to `scenes/` (P7) |
| `JoinParty` / `LeaveParty` / `Hire` | `engines/base.py:154,161,168` | Shared change verbs | Keep |
| Panel builders | `engines/base.py:225-262` | `character_panel`, `here_panel`, `party_panel`, `trail_panel`, `party_section` | Keep (P7 may give them their own module) |
| `keep_highest` | `engines/base.py:271` | Roll-and-keep-highest, 3 users | Keep; arguably belongs near `roll` (P7) |
| `named_unmet` / `read_packs` / `SRD_PACK` | `engines/base.py:282,293,18` | **Scene-only helpers in the shared base** | Move to `scenes/` (P7) |
| `EXTEND` | `engines/base.py:20` | **Rooms-only constant in the shared base** | Move to the room engine (P7, D1) |
| `SceneEngine` family | `engines/scenes/*` (901 lines, 3 users) | `SceneRun`, `SceneCanon`, `SceneWorld`, `SceneDraft`, `NextDraft` | **Do not touch** — earns its keep |
| `RoomEngine` family | `engines/rooms/*` (834 lines, **1 user**) | `Dungeon`, `Place`, `Way`, `Visit`, `RoomCanon`, `RoomWorld`, `MapDraft` | See Section 1 |
| `MapDraft` vs `RoomCanon` | `rooms/drafts.py:7`, `rooms/world.py:114` | Both are `Dungeon + start` | Merge candidate — part of Section 1 |
| `ChangeWorld` ×4 | `loner3e/tools.py:63`, `breathless:43`, `tunnelgoons:22`, `twentyfourxx:122` | One discriminated-union tool per engine | **Byte-identical** — see Section 1 |
| `Reveal` / `Kill` ×2 | `scenes/tools.py:15,36`, `rooms/tools.py:9,26` | Same shape, different prose | Leave — the prose reaches the model through `schema_of` |
| `scene_refusal` / `map_refusal` / `extension_refusal` | `scenes/worldsmith.py:38`, `rooms/worldsmith.py:38,43` | One bar per draft kind, all reasons at once | Keep; the unmet-reason joiner is written 3× |
| Four concrete engines | `loner3e/`, `tunnelgoons/`, `breathless/`, `twentyfourxx/` | Each: engine, world, tools, worldsmith, rules.md, packs | **Keep all four** — see D1 rationale |

### 2.4 `turn/` (249 lines, 2 files, 1 consumer)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Turn` | `turn/run.py:29` | One turn's draft, rng, facts, notes | Keep |
| `Turn.call` | `turn/run.py:102` | The one gate every published tool passes | **Do not touch** |
| `Turn._apply` | `turn/run.py:128` | Trial-run against a copy; a refused call costs no dice | **Do not touch** the mechanism; delete the dead guard (P1) |
| `Turn.picture` | `turn/run.py:91` | Builds the master prompt | Rename (C10); it recomputes history (P8) |
| `render_master` | `turn/context.py:23` | Master prompt | See **D5** |
| `render_narrator` / `render_interjection` / `_picture` | `turn/context.py:47,60,81` | Narrator prompts | See **D5** |
| `turn/` as a layer | — | — | See **D5** |

### 2.5 `app/` (1,547 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `GameService` | `app/runtime.py:59` | One live game — **7 responsibilities** | Split (P9) |
| `Runtime` | `app/runtime.py:377` | Sessions, engines, library, store, tool surface, settings | 5 jobs; see C3 |
| `RoleSpawner` | `app/runtime.py:365` | CLI-or-API per role | Keep; the CLI-vs-API decision is written 3× (C3) |
| `Spawner` / `Driver` protocols | `app/spawn.py:129,34` | Role execution; per-CLI argv+parse | **Do not touch** |
| `ClaudeDriver` / `CodexDriver` | `app/spawn.py:56,93` | The two CLI dialects | Keep |
| `CliSpawner` | `app/spawn.py:134` | The only thing that starts a process | **Do not touch** |
| `ask` + `RETRIES` | `app/spawn.py:188,19` | One retry carrying the error | **Do not touch** |
| `final_message` + scrapers | `app/spawn.py:163,247,257,266,272` | Extract JSON from four CLI output shapes | String in, string out; sits oddly beside process spawning |
| `BuiltinSpawner` / `Tools` | `app/builtin.py:64,22` | Completion-API loop; the one real DIP inversion | **Do not touch** the protocol |
| `_Echoed` | `app/builtin.py:27` | A fourth Pydantic base config, declared in `app` | See C11 |
| `Illustrator` / `Reader` | `app/media.py:29`, `app/speech.py:21` | Cached art and TTS | Keep — see **D6** |
| `claim` / `post_bearer` | `app/providers.py:9,17` | Single-flight guard; the one bearer POST | Keep |
| `MountedLifespan` / `endpoint` | `app/mcp.py:21,57` | MCP over streamable HTTP | **Do not touch** |
| `LauncherCatalog` / `CatalogEntry` / `LaunchTarget` / `SaveOption` | `app/launch.py:43,14,23,33` | The launcher read model | `read()` does two jobs in 60 lines |

### 2.6 `ui/` (1,735 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `GamePage` | `ui/game.py:72` | One tab — **7 jobs, 18 attributes, 9 uninitialised** | See C7 |
| `Observed` | `ui/game.py:52` | The 1 Hz poll snapshot | Keep — genuinely the diff |
| Pure UI rules | `ui/game.py:597-637` | `can_type`, `standing_proposal`, `near_end`, `draft_spent`, `insert_at_caret`, `placeholder` | Keep; **module-layout violation** (C7) |
| `LaunchForm` / `CharacterForm` / `ScenarioForm` / `SettingsForm` | `ui/app.py:60`, `ui/create.py:22,139`, `ui/settings.py:23` | The four forms | Keep; `LaunchForm` after a public function (C7) |
| `ENGINE_PALETTES` | `ui/theme.py:26-73` | Per-engine CSS, keyed by four hardcoded ids | **Move to the seam** (P3) |
| `DiceTray` / `Dictation` | `ui/dice.py:13`, `ui/dictation.py:4` | Two JS components | Keep |
| `widgets` | `ui/widgets.py` | `page_header`, `avatar`, `entity_row`, `decision_widget`, … | Keep |

### 2.7 Test and QA concepts

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Table[G]` / `ScriptedSpawner` | `tests/support/table.py:144,115` | Live game + scripted roles | **Do not touch** — mandated by CLAUDE.md |
| `golden` / `AIDM_GOLDEN_REGEN` guard | `tests/support/golden.py:13`, `conftest.py:5` | Drift detector that cannot pass while regenerating | **Do not touch** — good design |
| `tests/support/golden_turn.py` | 14 lines, 3 constants | One consumer each | Small; dropped from the list |
| `tests/support/ui.py` | 20 lines | `ui_settings`, used by two non-UI tests | Misnamed; dropped from the list |
| `tests/support/loner.py` | 87 lines | **The shared default game fixture**, used by 14 non-loner files | Misnamed (D12) |
| Dynamic golden lookup | `tests/core/test_golden_turn.py:19-26` | `import_module(f"tests.{id}.golden_turn")` behind two `cast`s | Two `cast`s past the checker |
| `SixthEngine` et al. | `tests/core/test_rooms.py` (17 references) | A fabricated second room engine | Part of Section 1 |
| `test_package_boundary.py` | 84 lines | The layer rule, enforced by AST | **Do not touch**; close the literal hole (P3) |
| `test_context_boundary.py` | 180 lines | The hidden-canon firewall | **Do not touch** |
| `test_integrity_boundaries.py` | 144 lines | Save/file corruption modes | **Do not touch** |
| `qa/` harness | 2,292 lines, 11 scenarios, 217 assertions | Real app + Playwright + scripted roles | Keep — see **D7** |

---

## 3. Proposals

### P1 — Delete two provably dead guards in `Turn` **[3/6]** · S · high confidence

**Verified.** `turn/run.py:117` reads `decided_before = self.draft.pending` at a point where
`pending` is always `None`: `call` early-returns at `:108-113` whenever `pending is not None`.
So the left half of `:121`'s condition is a tautology.

Worse, `_apply`'s guard at `:131-134` — `raise Refusal("the rules already wait on a decision;
they take one at a time")` — is **unreachable from both call sites**: `:70` runs after
`draft.pending = None` at `:52`, and `:118` runs after the early return. Confirmed: no test
anywhere references that string.

**Do:** delete `:117`, simplify `:121` to `if self.draft.pending is not None:`. For `:131-134`
see **D11**. Also rename `already_pending` (`:116`) — it counts notes, not decisions.

**Lost:** nothing.

---

### P2 — Fix the MCP argument-validation escape **[1/6]** · S · high confidence — *this is a bug*

**Verified.** `app/mcp.py:87` calls `_ARGUMENTS.validate_python(params.arguments or {})` **inside**
the `try`, but it raises `ValidationError`, which is not a `Refusal`. The `except Refusal` at `:89`
does not catch it, so a CLI sending non-object tool arguments escapes the handler entirely instead
of coming back as a tool error.

The other transport gets this right: `app/builtin.py:156-160` decodes and raises an explicit
`Refusal("tool arguments are a JSON object")`.

**Do:** see **D12** for where the fix belongs. The minimal version is to catch `ValidationError`
at `:89` too.

**Lost:** nothing.

---

### P3 — Move the per-engine palettes onto `Engine` **[4/6]** · M · high confidence

**Verified.** `ui/theme.py:27,38,49,61` hardcodes `EngineId("loner3e")`, `EngineId("tunnelgoons")`,
`EngineId("breathless")`, `EngineId("twentyfourxx")` with a full palette each. CLAUDE.md says
*"the registry is the one place that joins an engine to the app"* and *"`core`, `turn`, `app` and
`ui` know no world shape"*.

`tests/core/test_package_boundary.py:76-84` misses it because it inspects `ast.Import` /
`ast.ImportFrom` only — these are string literals. And `_palette` (`theme.py:270`) falls back to
neutral silently, so a fifth engine ships themeless with **no test failing**;
`tests/ui/test_theme.py:69` iterates `ENGINE_PALETTES` itself, so it can never catch a gap.

The correct pattern already exists two lines away: `Engine.dice_look` (`seam.py:41`) and
`Engine.art_style` (`seam.py:40`) are the same class of data, declared by the engine.

**Do:** add `palette: Tokens` (or fold `dice_look`/`art_style`/`palette` into one `Look` value) as an
`Engine` class attribute. Seed the app-wide CSS once from `_register_pages` (`ui/app.py:167-172`)
with `runtime.engines`; `page_header` then sets only the class. Extend the boundary test to scan
string literals for engine ids.

**Lost:** `_inject_css` is `@cache`d and app-wide, and `page_header` (`widgets.py:25`) reaches it
without a `Runtime` — that is the plumbing cost.

---

### P4 — A shared sheeted-person base for `Survivor` and `Crewmate` **[4/6]** · M · high confidence

**Verified byte-identical.** `Survivor` (`breathless/world.py:105`) and `Crewmate`
(`twentyfourxx/world.py:96`) share four methods character for character:

| Method | Breathless | 24XX |
|---|---|---|
| `dice()` | `:110-113` | `:101-104` |
| `require_item()` | `:115-119` | `:106-110` |
| `drop_item()` | `:121-125` | `:148-152` |
| `unwritten()` | `:178-184` | `:176-182` |

Both also declare `sheet: X | None = Field(default=None, description="Leave empty.")` identically.
Their worlds' `require_actor` (`breathless:194`, `twentyfourxx:203`) and `require_hireable`
(`:202`, `:211`) differ only in the noun inside the refusal string, and the
`_player_carries_a_sheet` validator (`:188`, `:194`) is byte-identical.

**Do:** `class Sheeted[S: BaseModel](Person)` carrying `sheet`, `dice()`, `require_item()`,
`drop_item()`, `unwritten()`; and a `require_sheeted(entity_id, *, noun: str)` on the world side for
the two `require_actor`/`require_hireable` pairs. Removes ~45 lines.

Two things need it, so CLAUDE.md's bar is met, and the duplication is verbatim — this is one idea
written twice, not two similar ideas that will diverge.

**Watch:** `Item` means different things in the two engines (`breathless/world.py:30` is name+die;
`twentyfourxx/world.py:39` is name+bulky+breaks), so `require_item`/`drop_item` need the item type as
a second parameter. The codebase already relies on runtime-parametrised generic models
(`scenes/engine.py:264`, `rooms/engine.py:69`), so this should hold — confirm before committing.

**Blocked on coverage.** `breathless` and `twentyfourxx` have no multi-turn test at all (Section 7
§1), and 24XX's hire-then-succession path has no end-to-end test (§2). Close §2 first.

**Lost:** each engine stops reading as a fully self-contained implementation of one SRD.

---

### P5 — One generic `ChangeWorld[C]` instead of four **[4/6]** · S · high confidence

*Settled by D2.*

**Verified byte-identical**, differing only in the union each wraps: `loner3e/tools.py:63`,
`breathless/tools.py:43`, `tunnelgoons/tools.py:22`, `twentyfourxx/tools.py:122` — plus a fifth copy
in `tests/core/test_rooms.py:43`.

```python
class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The change to apply. `verb` picks which one.",
    )
```

**Do:** `class ChangeWorld[C](Frozen)` in `engines/base.py`; each engine keeps its own
`type WorldChange = ...` and writes `ChangeWorld[WorldChange]`. The union stays a written
annotation, so basedpyright keeps checking it.

Beyond the 25 lines, the win is that the name `ChangeWorld` stops resolving to four different types
depending on which module you imported from.

**Verify two things before committing:**
1. That Pydantic accepts `Field(discriminator=...)` on a type-parameter field at parametrisation
   time. If not, fall back to renaming the four (`BreathlessChangeWorld`, ...) — that removes the
   collision without losing types.
2. That `tests/core/fixtures/schemas/*/master_tools.json` do not move. `schema_of` strips `title`
   (`core/tools.py:15`), so they should not.

**Lost:** nothing.

---

### P6 — Split `core/views.py` into models and prompt rendering **[2/6]** · S · high confidence

**Current.** `core/views.py` holds nine frozen models (`Subject`, `PanelRow`, `Panel`, `DiceLook`,
`Action`, `NarratorView`, `PlayerView`) **and** five prompt-string functions (`sections:145`,
`lines_of:149`, `render_history:153`, `told_history:160`, plus `_block`/`_header`/`_told`) **and**
three history-window constants (`:17-19`). The two halves share nothing — the renderers take
`SceneRecord` from `play.py`, never a `Panel` or a `NarratorView`.

**Do:** keep the models in `core/views.py`; move the renderers and constants to `core/prompt.py`.
Six importers change: `turn/context.py:9-18`, `scenes/worldsmith.py:7`, `scenes/engine.py:22`,
`scenes/world.py:17`, `rooms/engine.py:20-29`, `rooms/worldsmith.py:4`.

It must be `core/prompt.py`, not `turn/`: `engines/` sits below `turn/` and calls `render_history`
(`scenes/engine.py:240`, `rooms/engine.py:240`), so the import rule forbids anything else.

**Lost:** nothing. One more module.

---

### P7 — Evict the single-family symbols from `engines/base.py` **[3/6]** · S · high confidence

`engines/base.py` is 297 lines mixing domain classes (`Thing:38`, `Person:96`, `World:113`,
`Counter:182`), tool-arg models (`JoinParty:154`, `LeaveParty:161`, `Hire:168`), `Pack:176`,
prompt/tool text constants, and eight free functions.

The genuine defect is not the length — it is that a *shared* module holds *unshared* things:

| Symbol | Location | Used by |
|---|---|---|
| `SRD_PACK` | `base.py:18` | scenes only |
| `Pack` | `base.py:176` | scenes only — and imported as `Pack as ScenePack` in all three (C14) |
| `read_packs` | `base.py:293` | scenes only |
| `named_unmet` | `base.py:282` | scenes only |
| `EXTEND` | `base.py:20` | rooms only |

**Do (minimum):** move the four scene symbols into `scenes/`, `EXTEND` into the room engine.
About an hour, drops `base.py` to ~250 lines and makes it honestly shared.

**Do (optional, later):** the three-way split — `engines/entities.py` (`Thing`, `Person`, `World`,
`Counter`, `check_filing`), `engines/panels.py` (the five panel builders, `sentence`),
`engines/hiring.py` (`Hire`, `JoinParty`, `LeaveParty`, `HIRE`, `HIRE_TOOL`, `hire_target`).
Also consider moving `keep_highest` (`base.py:271`) to `core/facts.py` beside `roll`, which is
where a reader will look for it.

**Lost:** one import line becomes two or three in most engine modules.

---

### P8 — Compute the view and the history once per turn **[2/6]** · M · high/medium confidence

Three pieces of measured waste on the hot path:

1. **`NarratorView` is built twice from the same unchanged draft.** `runtime.py:274` builds one to
   narrate; `seam.py:124` (inside `Engine.close`) builds an identical one purely to turn `Line`
   into `SpokenLine`. Each build runs `_everyone_is_a_subject` (`views.py:82`) and a full entity
   walk. **Fix:** have `_narrate` return the view it already holds, or have `Turn.finish` take
   resolved `SpokenLine`s. *(high confidence)*
2. **`Turn.picture` materialises the whole history to call `len()`.** `run.py:98` →
   `seam.py:174` → `base.py:125` `exchanges()` → builds every `SceneRecord` from scratch, flattens
   it, and discards all of it for one integer. `run.py:96` builds them a second time on the line
   above. **Fix:** carry `played: int` on `Turn`, or add `World.turn_count()`. *(high confidence)*
3. **`PlayerView` is rebuilt 7+ times per UI refresh and once a second while idle.**
   `ui/game.py:62, 209, 250, 265, 282, 304, 422, 480`, plus 5 history walks at
   `:66, 204, 324, 389, 497`. **Fix:** build one per `poll_turn` tick and pass it down.
   *(medium confidence — NiceGUI refreshables re-run independently)*

**Lost:** for (3), a little independence between refreshables. Since `poll_turn` already diffs
`Observed` and calls `refresh()` as one unit (`ui/game.py:374-381`), this is theoretical.

---

### P9 — Split `GameService` **[4/6]** · M · high confidence

`app/runtime.py:59-361` — 300 lines, one class, seven jobs:

| Lines | Job |
|---|---|
| 79, 335, 341, 348 | Save load/store/restart/resumability |
| 97-159 | Turn orchestration (`open`, `play`, `act`, `_turn`) |
| 248-269 | The master retry policy |
| 271-296 | Narrator ask + evidence assembly |
| 214-241 | Worldsmith generation |
| 160-212 | Interjections, including a d10 table at `:39` |
| 243-246, 298-333 | Media, speech, view delegation, background-task retention |

Symptom: outside code reaches in. `tests/core/test_golden_turn.py:37` awaits `service._background`
behind a `# pyright: ignore[reportPrivateUsage]`; `qa/server.py:87` reaches `runtime._sessions`.

**Do:** extract two collaborators.
- **`Presenter`** — `media`, `reader`, `_background`, `_retain`, `_present`, `illustrate`, `speak`,
  `scene_art`, `icon`, `newest_clip`, `_newest`. ~45 lines. A public `drain()` removes the
  `reportPrivateUsage` suppression.
- **`Roles`** — the three `ask`-based interactions (`_narrate`, `_master`, and `interject`'s
  prompt-and-ask half) plus `RoleSpawner` and `_worldsmith`. ~90 lines. This is what makes the
  master's retry rule, the narrator's evidence assembly, and the interjection prompt read as three
  peer role interactions instead of three methods buried between `commit` and `scene_art`.

`GameService` then ≈ 200 lines: state, turn flow, interjection policy.

**Lost:** one indirection between the page and its art — `ui/game.py` calls `session.scene_art()`
and `session.icon()` in five places, so either delegate or update the call sites.

---

### P10 — Add CI, and bring `qa/` under the linters **[1/6]** · S · high confidence

**Verified:** `.github/` does not exist — **nothing runs on push, pytest included**.
`pyproject.toml` sets `[tool.basedpyright] include = ["src", "tests"]`, so `qa/`'s 2,292 lines are
unchecked, and `ruff check --extend-select RUF100` reports **14 dead `noqa` directives**, all in
`qa/` (ten for `ANN001`/`ANN202`, rule families this repo never enabled; four `E402` in
`qa/server.py:20,22,23,24` that suppress nothing).

**Do:** add `qa` to `basedpyright`'s `include`; run `ruff check --extend-select RUF100 --fix qa/`.
Separately, `run_all.sh` defaults to nine scenarios and silently omits `visual` and `probe`, which
`qa/README.md` lists — align them.

**Do first, before any L-effort move:** add a minimal CI workflow running the four CLAUDE.md
commands. Every guarantee in this document currently depends on the maintainer running them by hand.

---

## 4. Consistency and SOLID findings

Ranked by impact. Findings that already have a proposal are cross-referenced, not repeated.

**C1 — `ui/theme.py` holds per-engine world knowledge.** See **P3**. The highest-impact rule
violation in the codebase, and it fails silently.

**C2 — Two tool-argument validation conventions at the two transports.** See **P2**. A behavioural
bug, not just drift.

**C3 — `GameService` and `Runtime` are the app layer's God objects.** See **P9**, a split of `Runtime`.
The sharpest symptom is `Runtime.playing()` (`runtime.py:410-415`): because an MCP tool call carries
no session identity, the runtime must assert that at most one turn is in flight process-wide and
raise `ValueError` otherwise. That is a global-singleton assumption forced by the transport, and it
is invisible from `Turn` or `Engine`. See **D10**.

**C4 — The `Engine` seam is *not* an ISP problem.** Worth recording, since it looks like one.
`seam.py` declares 11 class attributes, 12 abstract methods and ~15 concrete. But: the two families
answer 9 of the 12 abstract methods, so a concrete engine implements only `master_tools`,
`creation_steps`, `create_character` and one family hook. No engine writes `raise NotImplementedError`
or an empty body to satisfy the seam — `FifthEngine` in `tests/core/test_seam.py:41-71` is 30 lines,
which is the honest measure. And every public member has a caller. **Do not split the interface.**
What *is* wrong: the class mixes rules, presentation metadata (`title`, `art_style`, `dice_look`,
`directory`) and I/O wiring, and it reads `rules.md` at construction (`seam.py:52`) — while
`scenes/engine.py:55-56` and `rooms/engine.py:47` read files at **import time**, so importing a
module performs disk I/O and can raise `OSError` from an import statement. `turn/context.py:109-111`
shows the better pattern (`@cache`d, lazy). Three mechanisms for one job.

**C5 — Name collisions that make navigation guesswork.**

| Name | Collides at | Note |
|---|---|---|
| `Check` | `core/model.py:24` (a `Callable` alias) / `breathless/tools.py:50` (a tool-arg model) | `app/spawn.py:17` imports one, `breathless/engine.py:27` the other |
| `Item` | `rooms/world.py:17` / `breathless/world.py:30` / `twentyfourxx/world.py:39` | Three unrelated shapes; two engine files import "Item" from different modules |
| `commit` | `core/model.py:117` / `seam.py:132` / `runtime.py:341` | `runtime.py:126` reads `self.commit(self.engine.commit(draft))` — two meanings, one expression |
| `unwritten` | `base.py:108` (`-> str`, forbidden fields) / `seam.py:189` (`-> Fact`, a failure card) | Two unrelated meanings, both overridden independently |
| `require_actor` | `tunnelgoons/world.py:83` returns a tuple; `breathless:194` / `twentyfourxx:203` return one value | One name, two contracts |
| `starting_items` | `rooms/engine.py:85` (hook) / `tunnelgoons/world.py:63` (method) / `twentyfourxx/engine.py:507` (free function) | Same name, two designs |
| `_Choice` | `app/builtin.py:50` / `app/media.py:139` | Both parse an OpenAI-shaped reply, same package |
| `Pack` | `base.py:176` + three subclasses all named `Pack` | See C14 |
| `Loner3eSheet` | `loner3e/world.py:20` is a **`Person`** | while `SurvivorSheet`/`Sheet` are the dice block **inside** a person |
| `Driver.parse` | `spawn.py:43` | shadows the project-wide `parse` imported in the same file (`spawn.py:15`) |
| `prompt` | `Exchange.prompt`, `PendingDecision.prompt`, `Turn.prompt`, `CreationStep.prompt`, `render_*` output | Five meanings |
| `draft` | `Game.draft()`, `SceneDraft`, `MapDraft`, `NextDraft`, `SheetDraft`, `draft_spent` (UI) | Three meanings |

**C6 — `Refusal` used for programmer errors, against the stated policy.** CLAUDE.md: *"A message a
role or the player is meant to read is a `Refusal`; any other exception is a bug and is not caught."*
Two sites raise `Refusal` for what can only be a code bug: `engines/registry.py:11`
(`require_unique("engine ids", …)`) and `engines/seam.py:54` (duplicate tool names). Compare
`runtime.py:414`, which correctly raises a bare `ValueError`.

**C7 — Module-layout drift, three sites.** CLAUDE.md orders a module: imports, constants, classes,
public functions, private functions.
- `ui/game.py:597-637` — six public functions after the private `_card:539`, `_dice_group:551`,
  `_bubble:569`, `_inline_status:582`, `_clock:592`. **Verified.**
- `ui/app.py:60` — `class LaunchForm` after the public `start:47`.
- `loner3e/tools.py:102` — `TOLD` is a plain dict, not "a constant built from a class", so by the
  letter it belongs at the top.

These are the only three in `src/aidm`. Everything else follows the rule.

**C8 — The UI reaches through `GameService` into the engine, nine times.**
`session.engine.history(session.state)` at `ui/game.py:66, 204, 324, 389, 444, 497`;
`session.engine.narrator_view(...)` at `:186`; `session.engine.title`/`.id`/`.dice_look` at
`:105, 162`. `PlayerView`'s docstring (`core/views.py:136`) claims to be "what the pages read", but
the facade is nominal — the page reads raw `Fact`s and `Exchange`s and reimplements fact-to-pixel
rules (`ui/game.py:539` splits `Fact.card` on `\n`; `ui/dice.py:36` filters `cards(facts[seen:])`).
The `aidm.engines` import ban is satisfied by *name* while the UI calls engine methods on ten lines.
See **D11**.

**C9 — Validators split between `ValueError` and `Refusal`.** CLAUDE.md: *"Inside a validator raise
`ValueError`; `parse` turns it into the refusal."* Every inline `raise` obeys. But helpers called
*only* from validators do not: `check_filing` (`base.py:265`) and `check_named`
(`scenes/world.py:286`) raise `Refusal`, while the equivalent `check_spread`
(`breathless/world.py:220`) raises `ValueError`. Three helpers, one job, two exception types. It
works only because `Refusal` subclasses `ValueError` and Pydantic swallows it — which means the
`Refusal` type is *lost* and the rule is satisfied by accident. (`require_unique` is genuinely
dual-use — it is also called at tool boundaries — so it should keep `Refusal`.)

**C10 — `except Exception` in two places.** `app/media.py:122` and `app/speech.py:63`, both with a
stated reason ("media/speech is outside the game") and both `LOGGER.exception`. Defensible, but as
written a `TypeError` in `illustration_request` is swallowed forever. Narrow to
`(OSError, HTTPError, ValueError)` — the discipline the rest of `app/` already uses
(`except (OSError, Refusal)` at `runtime.py:195,232,259,290`, `ui/game.py:516`).

**C11 — A fourth Pydantic base config, declared in `app`.** `core/entities.py` establishes
`Frozen`/`Mutable`/`Loose` as *the* three configs. `app/builtin.py:27-30` declares
`_Echoed(BaseModel)` with `extra="allow", frozen=True` — a legitimate fourth quadrant of the same
2×2, living in a different layer, so the "three configs" story is quietly false. Move it to
`core/entities.py` as `Echoed`, or add one line saying why it is local.

**C12 — `PanelRow` is a stringly-typed three-way variant.** `core/views.py:39-44` documents "Three
row shapes… entity (`icon_id`), labelled value (`detail`), or bare label", and `ui/game.py:312-318`
reconstructs the discrimination with `if row.icon_id is not None / elif row.detail / else`.
Everywhere else in the codebase a variant is a discriminated union. One producer family, one
consumer, so it is below the "two things need it" bar — but it is the one place the codebase types
by convention instead of by model.

**C13 — `Roles.each()` duplicates `Roles.for_name()`.** `config.py:80-87` and `:89-94` both
enumerate the three roles by hand; `Providers.for_name` (`:107-112`) enumerates the two providers.
The exhaustive `match` in `for_name` is deliberate (it type-checks), but `each()` could be
`tuple((name, self.for_name(name)) for name in get_args(Role))`.

**C14 — `from aidm.engines.base import Pack as ScenePack`, then `class Pack(ScenePack)`.**
`loner3e/worldsmith.py:6,25`, `breathless/worldsmith.py:7,25`, `twentyfourxx/worldsmith.py:7,47`.
The base is renamed on import purely so the subclass can take the good name — three copies of the
same shadowing trick. Renaming the base to `PackBase` (or `ScenePack`, per P8) removes it.

**C15 — Three mechanisms for the same job: the hire-sheet bar.**
`tunnelgoons/engine.py:167` and `breathless/engine.py:214` pass `lambda _draft: None` as the
`Check[T]` and enforce the bar in a `model_validator`; `twentyfourxx/engine.py:317` passes a real
`lambda sheet: sheet.refusal(pack)`. `Check[T]` exists precisely for "beyond its own schema" checks,
so two of the three pass a no-op. Pick one idiom, or name the no-op so the intent reads.

**C16 — A fragile, undeclared `__init__` ordering contract.** `Engine.__init__`
(`seam.py:51-55`) reads `self.directory / "rules.md"` and calls `self.master_tools()`, which for
scene engines depends on `self.packs`. So `SceneEngine.__init__` (`scenes/engine.py:93-96`) must
call `read_packs` **before** `super().__init__()`, guarded only by an inline comment
(`# last: master_tools reads the packs`). A subclass author who calls `super().__init__()` first
gets an `AttributeError` at import. Make it explicit with a `prepare()` hook called at the top of
`Engine.__init__`.

**C17 — `RoomEngine.advance` ignores the operation it is handed.** `rooms/engine.py:188-193` never
checks `request.operation == EXTEND`. Safe today because `validate:74` constrains operations and
`TunnelGoonsEngine.advance:156` intercepts `HIRE` first, but a second room operation would be
silently treated as an extension. `SceneEngine.advance:331` does branch. One line closes it.

**C18 — `Attempt` is game vocabulary living in `core`.** `core/tools.py:18-25` — "An attempt at
something uncertain", with `what` described as "The attempt, in a few words the player reads."
CLAUDE.md says `core` knows no world shape. Four engines subclass it, so the abstraction is earned;
its home should probably be `engines/base.py`.

**C19 — Ruff's rule set leaves naming and unused arguments unchecked.** `pyproject.toml:55`:
`select = ["E", "F", "I", "UP", "B", "TID252"]`. Missing `N` (pep8-naming), `ARG` (unused
arguments), `RUF`, `SIM`. `basedpyright` covers types but not naming or unused parameters. Adding
`N` and `ARG` would surface `World.require_hireable`'s unused `entity_id` (`base.py:144`) and much
of C5. One-line change plus whatever it turns up.

**C20 — Two overlapping notions of "in flight".** `GameService.busy` is `phase is not None`
(`runtime.py:91`); `Runtime.playing()` filters on `turn is not None` (`:412`). `busy_refusal` uses
the first, the tool surface the second. They diverge during `open()` and `_generate`, which set
`phase` without a `turn` — intentional, but never stated.

**C21 — The interjection die is rolled outside the dice machinery.** `runtime.py:171`:
`self.rng.randint(1, 10) <= INTERJECTION_ODDS[candidate.chattiness]`. Every other die goes through
`core.facts.roll` and produces a `Fact`. This one is a rule living in `app`, consuming the turn's
`Random`, with no fact and no trace. Defensible as a presentation coin-flip, but it is the one
exception to "only code rolls dice" having one roller.

**C22 — `MARKS` are prose sentinels the models read as player input.** `runtime.py:34-37` defines
`OPENING_MARK`/`STORY_MARK`/`INTERJECTION_MARK`, stored in `Exchange.prompt`, matched by identity at
`ui/game.py:212`, **and fed verbatim into master and narrator prompts** by `views.py:187`
(`f"> {exchange.prompt}"`). The master literally reads `> (the story begins)` as a player action.
A field on `Exchange` would say the same thing without putting it in a prompt.

**C23 — `reload_settings` does not stop background media/speech tasks.** `runtime.py:439-442` calls
`session.hush()`, which cancels only `_speaking`, then clears `_sessions`. In-flight
`illustrate`/`read` tasks in `_background` keep running and write to the old `store.media_dir(slug)`.
The comment at `:440` claims eviction stops writing; that is true only of the interjection.

**C24 — The settings-reader allowance is stale in two places.** **Verified:** `turn/` imports
`aidm.config` **nowhere** — the only importers are `app/{builtin,media,providers,runtime,spawn,speech}.py`
and `ui/{app,game,settings}.py`. But CLAUDE.md says *"Only `turn`, `app` and `ui` read the settings"*
and `tests/core/test_package_boundary.py:22` encodes `("turn", "app", "ui")`. Both grant a
permission nobody uses. Tighten to `("app", "ui")` — free, and it makes the test describe the code.

**C25 — Two prose assertions in tests, which CLAUDE.md forbids.**
`tests/core/test_seam.py:139` asserts `"Call \`next_scene\` with \`pursuit\`" in engine.instructions`
— an assertion on `scenes/rules.md` wording. `tests/ui/test_theme.py:67` asserts the generated CSS
carries each palette's hex values — a wiring test over a data table (and the one P3 would delete).

**C26 — `tests/` does not mirror `src/`, and one file is filed under the wrong layer.**
`tests/core/` holds 11 files that test `app` or `turn` (`test_builtin`, `test_spawn`, `test_media`,
`test_speech`, `test_mcp_lifespan`, `test_game_service`, `test_turn`, `test_context_boundary`, plus
`test_rooms`, `test_scenes`, `test_seam`, `test_engines_base` which test `engines`).
**Verified:** `tests/ui/test_launcher.py` (313 lines) imports `aidm.app.launch` and
`aidm.app.runtime` — it tests `app`, not `ui`. See **D12**.

**C27 — Two idioms for constructing an engine in tests.** 13 module-level `ENGINE = XEngine()`
versus 19 uses of the already-built `ENGINES_BUILT[...]` (`tests/support/table.py:43`). Each
construction re-reads `rules.md` and every `packs/*.json` at import. Two files in the *same
directory* differ: `tests/breathless/test_views.py:7` uses `ENGINES_BUILT`,
`tests/breathless/test_engine.py:27` constructs.

**C28 — Three layered constructors for one fixture.** `open_table` (`table.py:210`) ←
`open_game_for` (`table.py:193`) ← `open_game` (`loner.py:58`). `open_game_for` adds only
`state_type=…`; `open_game` adds only `engine_id=LONER3E, state_type=Loner3eGame`. Two of the three
could be default arguments.

**C29 — Free functions whose first argument is one of our objects.** CLAUDE.md: *"A function whose
first argument is one of our objects is a method."* `hire_target(request: Generation)`
(`base.py:215`), `map_refusal(draft: MapDraft)` (`rooms/worldsmith.py:38`),
`requests_of(exchange: Exchange, …)` (`speech.py:90`, called only from `Reader`),
`illustration_request(scene: NarratorView, …)` (`media.py:171`, called once from `Illustrator._draw`).
The three `PlayerView` functions in `ui/game.py:597,602,628` have a real reason (they are unit-tested
free functions), which the rule as written does not carve out.

**C30 — `PendingOption.name` means two things, LSP-safely.** `core/play.py:68-69` documents it
("not every name is a tool"), and `BreathlessEngine.answer` (`breathless/engine.py:318-322`)
intercepts `TAKE_LOOT` before the base's tool lookup (`seam.py:82`). The override *widens* the
accepted input, so it is Liskov-safe. Recorded, not a change request — the alternative (a
`pseudo_tools` registry on the seam) is more machinery than one override.

---

## 5. Open decisions

Twelve remain. Numbering restarts — D1-D3 are settled in Section 1. Options are listed with the merged recommendation last.

### D1 — Replace `Generation.operation` string dispatch?

**Settled: no, leave it (option A).** See Section 1.

### D2 — Delete `Fact.kind`?

**Settled: yes, delete it (option A).** See Section 1.

### D3 — How is the hire feature factored?

**Settled: a `Hiring` mixin (option B).** See Section 1.

### D4 — Should `config.py` move under `app/`?

**Settled: no, fix the rule (option A).** See Section 1.

### D5 — Where does prompt rendering live?

**Settled: split by owner (option B).** See Section 1.

### D6 — Null Object for `media` / `reader`?

**Settled: no, extract a `Presenter` (option B).** See Section 1.

### D7 — What is `qa/` for, going forward?

2,292 lines, 11 scenarios, 217 assertions, 103 screenshots. It runs the real app with scripted
roles under Playwright. It is maintained (4 of the last 100 commits touch it, the most recent `a46e7ee`; three
commits exist purely to fold its findings back in: `823f702`, `abac557`, `afa36d3`). It is the **only** coverage of `ui/app.py`,
`ui/create.py`, `ui/widgets.py` and the real MCP JSON-RPC transport. It is also outside every gate:
unchecked by basedpyright, 14 dead `noqa`s, no CI at all.

- **(a) Leave it as is.** Zero work; the drift continues.
- **(b) Bring it under the toolchain and trim the pytest-redundant scenarios** . Add `qa` to
  `basedpyright.include`, clear the dead directives, shrink `s_settings` (193 lines, largely
  restating `tests/ui/test_settings.py`) and fold `s_home`'s route checks into `s_visual`.
  Keep `s_visual`, `s_mobile`, `s_probe`, `s_mcp` and the four engine drives — nothing in `tests/`
  touches what they cover.
- **(c) Delete it and port the checkable parts to pytest.**

Recommend **(b)**, and explicitly **not (c)**. But take the trimming half only if those two scenarios
have genuinely stopped finding things — the redundancy has historically paid.

### D8 — Delete the unreachable `_apply` guard, or promote it?

`turn/run.py:131-134` (see P1).

- **(a) Delete.** It is dead; "do not build for future needs".
- **(b) Convert to `assert`.** Documents a real, non-obvious invariant — a tool that opens a
  decision while one is already open would be a genuine engine bug — and would fire loudly if a
  third `_apply` caller appears.
- **(c) Keep as is.** Costs nothing at runtime.

Recommend **(b)**. The invariant is real, but expressing it as a `Refusal` mislabels a bug as a
message, which is exactly what CLAUDE.md forbids.

### D9 — Which boundary owns tool-argument validation?

See P2.

- **(a) Fix `mcp.py:87`** to catch `ValidationError` too. Smallest change.
- **(b) Move `builtin._arguments` (`builtin.py:156-160`) into `core/tools.py`** as
  `tool_arguments(value) -> dict[str, JsonValue]` raising `Refusal`, called from both transports.
  One implementation, two call sites.
- **(c) Push validation into `Turn.call`** (`turn/run.py:102`), which is already documented as "the
  one gate every published tool passes". Neither transport validates; one site owns it.

Recommend **(c), falling back to (b)**. (c) is the smallest number of validation sites and matches
"reject bad data at once" at the place that acts on it — but it changes `Turn.call`'s signature,
which ripples into `tests/support/table.py`. (b) is the safe version.

### D10 — Should the MCP tool surface be per-turn rather than process-global?

`Runtime.playing()` (`runtime.py:410`) scans every session and raises `ValueError` if two turns are
in flight; `Runtime.lock` (`:383`) serialises every tool call across every save; `mcp.py:63` runs
`stateless=True`.

- **(a) Leave it, and fix the comment.** The app is single-player; `busy_refusal` already blocks a
  second turn from the UI, so `playing()`'s `ValueError` is a "cannot happen" guard — but the comment
  at `:411` ("A second turn in flight has no owner") describes a state the code prevents elsewhere,
  and a reader cannot tell it is unreachable.
- **(b) Key the MCP session to the turn** (drop `stateless`), so a master's calls route to its own
  turn by construction. Deletes `playing()`, the lock and `NO_TURN`.
- **(c) Hand the server a turn handle** when `_turn` starts, revoked in the `finally` at `:148`.

Recommend **(a) for now**, and record why. (b) is structurally right but trades a documented
single-player constraint for MCP session plumbing; it earns its keep only if concurrent multi-save
play becomes real.

### D11 — How does the UI learn about the game?

See C8.

- **(a) Leave it.** The boundary test already prevents the real hazard (importing a concrete engine).
- **(b) Give `GameService` the six accessors the UI actually uses** — `history()`, `scenes()`,
  `narrator_view()`, `engine_title`, `engine_id`, `dice_look` — and forbid `ui` from touching
  `session.engine`. ~15 lines.
- **(c) A full DTO boundary:** the UI sees only `PlayerView` and a `ChatView`, never `Fact` or
  `Exchange`.

Recommend **(b)**. It is the smallest change that makes the stated boundary true, and it makes
P8(3)'s caching possible in one place. (c) adds a whole shape family that would itself become a
finding.

### D12 — Do the test directories get re-shaped to mirror `src/`?

See C26.

- **(a) Full re-shape.** `tests/{core,engines,turn,app,ui}` plus the four engine dirs;
  `tests/ui/test_launcher.py` → `tests/app/`; `tests/support/loner.py` → `tests/support/game.py`.
  ~30 files, zero behaviour change, expensive to review.
- **(b) Minimal.** Move the one clearly-misfiled file and rename `tests/support/loner.py` to `game.py` (it is imported by 14 files outside `tests/loner3e`). Leave the rest.
- **(c) Leave it.**

Recommend **(b) now, (a) later** — and (a) only after the dropped test-suite tidying has landed, so `tests/core` is
smaller when it moves.

Related, and settled: **keep the four per-engine directories**. They hold 740-1,240 lines of
genuinely different rules each; collapsing them would produce 1,000-line files. The problem is not
the split, it is that shared-family code is tested inside engine directories .

---


## 6. Load-bearing — do not touch

Consolidated from all six reviews. Each of these is doing real work that is not obvious from the
code, and every one has a failure mode that is silent.

| Concept | Why |
|---|---|
| `Refusal` as a `ValueError` subclass (`entities.py:35`) | It is what lets a validator's failure survive Pydantic and re-emerge through `parse`. Change the base class and every model validator silently stops refusing. |
| `parse` (`entities.py:56`) | The single `ValidationError` → `Refusal` funnel. Bypassing it anywhere loses the first-error location string the retry prompt depends on. |
| `Game.draft()` / `commit()` + `Mutable`'s `revalidate_instances="always"` (`entities.py:26`, `model.py:113-121`) | The entire safety story: rules code mutates freely, the whole tree is re-checked on landing. Remove the deep copy and a refused tool call corrupts state; remove the revalidation and every world invariant becomes advisory. |
| `Turn._apply`'s candidate copy **and rng deep copy** (`run.py:130,136`) | Guarantees a refused tool call consumes no dice. Without the rng copy, a model retrying a refused roll gets different dice — the most exploitable failure mode in the design. |
| `NarratorView` having no field that can hold hidden canon (`views.py:67`) | The hidden-information guarantee is enforced by the **shape of the type**, not a filter. One convenience field breaks the project's central promise silently. `tests/core/test_context_boundary.py` is its only enforcement. |
| `Fact.told` computed from `known` in `Thing.fact` (`facts.py:37`, `base.py:73-83`) | An unrevealed name cannot leak into `traced(..., told_only=True)`. |
| `decode`'s duplicate-key rejection (`io.py:147-152,183`) | Without it a doubled id in a world file silently keeps the last value. Three tests in `test_integrity_boundaries.py` pin it. |
| `write_text`'s staged rename (`io.py:139-144`) | Two processes may read one save; a reader must never see a half-written file. |
| `master_tool`'s description check (`tools.py:41-42`) | A tool parameter with no description reaches the model unlabelled. Failing at app start is the right edge. |
| `schema_of` (`tools.py:50`) | The one function so MCP's published schema and every prompt's `ANSWER WITH` block cannot diverge. Pinned by `test_golden_schemas.py`. |
| `routed` + `EngineHeader` (`io.py:155`, `model.py:42`) | The only way a document's engine is discovered before its model is known. |
| `Turn.call`'s pending/generation gates (`run.py:104-117`) | They **answer** rather than refuse when the rules are waiting, precisely so no retry prompt tells the model to try again. Subtle and correct. |
| `Tools` protocol (`builtin.py:22`) | The one genuine DIP inversion: `BuiltinSpawner` needs `Runtime`, `Runtime` constructs `BuiltinSpawner`. The protocol breaks the cycle. |
| `Spawner` / `Driver` protocols (`spawn.py:129,34`) | `Spawner` is how every test avoids starting a process; `Driver` keeps `CliSpawner` "the only thing that starts a process". |
| `MountedLifespan` (`mcp.py:21`) | Documented workaround for a mounted ASGI app whose lifespan never runs. Removing it hangs startup. |
| `build_engines` (`registry.py:9`) | The one composition root, enforced by `test_package_boundary.py:76-84`. |
| `ScriptedSpawner` (`tests/support/table.py:115`) | Mandated by CLAUDE.md. It is why 565 tests run in 6 seconds with no processes. |
| The `AIDM_GOLDEN_REGEN` guard (`tests/conftest.py:5-9`) | A regeneration run cannot be mistaken for a passing run. Genuinely good design. |
| The three boundary tests | `test_package_boundary` is the layer rule made executable; `test_context_boundary` is the hidden-canon firewall's only enforcement; `test_integrity_boundaries` maps one-to-one onto real corruption modes. None is ceremony. |

**Also settled, and worth recording:** keep all four shipping engines. They are what keeps the seam
honest — four different resolution systems, four different `PendingDecision` kinds (`loot`,
`conflict`, `level-up`, `succession`), two world topologies, one engine that does not hire and one
that survives its player's death. Each is a counterexample that stops a base-class assumption from
calcifying. The duplication they expose is the price; D2 and D6 collect most of it back.

---

## 7. Coverage gaps that gate the risky work

Simplification without coverage is a bet. These are the gaps, in the order they constrain the
proposals above.

1. **No full-playthrough test for any scene engine.** `tests/tunnelgoons/test_play.py:45` is the only
   start-to-finish test. `breathless` and `twentyfourxx` have no multi-turn test at all.
   **Gates D3.**
2. **24XX's hire-then-succession path is untested end to end.** `tests/twentyfourxx/test_world.py:124`
   and `test_tools.py:416` cover the mechanism, but not a hired member's sheet surviving a save
   across `_succession` (`twentyfourxx/engine.py:278`). **Gates D6 specifically.**
3. **Modules with no test importing them at all:** `ui/app.py` (207 lines — `home_page`,
   `LaunchForm`'s scenario↔character re-pairing at `:86-101`, `_register_pages`, the MCP mount at
   `:166-172`); `ui/create.py` (292 lines — the refresh-on-blur dance at `:80`, `_drop_stale`, the
   preview gate at `:135`); `ui/widgets.py` (88 lines — `decision_widget`, **the only way a player
   answers a `PendingDecision`**, heavily tested server-side and untested client-side).
   Covered only by `qa/`. **Gates D7's trimming half.**
4. **The real MCP transport** exists only in `qa/s_mcp.py`. `app/mcp.py` is tested for lifespan only
   (`test_mcp_lifespan.py`, 22 lines). **Gates P2, D9 and D10 — do not trim `s_mcp`.**
5. **`reload_settings` and background tasks.** `tests/ui/test_settings.py:75,83` covers the refusals;
   nothing covers what happens to a background interjection belonging to an evicted session
   (`runtime.py:440-442`). **Gates P9's `Presenter` extraction** — and see C23, which says the
   current behaviour is not what the comment claims.
6. **`app/providers.py`** (28 lines) — `claim()`'s no-await invariant (`:9-14`) is exercised only
   indirectly. **Gates any merge of `Illustrator` and `Reader`.**
7. **`Pack._twist_columns_pair_up`** (`loner3e/worldsmith.py:33-40`) — the only guard that a twist
   column is exactly six rows, and it has no direct test.
8. **No CI at all.** `.github/` does not exist. **This is P10, and it should come before any large move.**

---

## Appendix — how this was produced

Five subagents plus the session author each independently read the whole codebase against CLAUDE.md,
with different emphases: `core/`+`turn/`, `engines/`, `app/`+`ui/`, `tests/`+`qa/`, and a
whole-system pass (hot path, vocabulary, layering, big bets).

Every factual claim reproduced here was re-verified against the source before being written down.
Where a reviewer's number was wrong it was corrected; where two reviewers disagreed, the
disagreement was preserved as a decision rather than resolved silently.

The first draft carried twenty proposals. Ten were dropped on a second pass — the ones whose payoff
was taste rather than a defect, or whose downside was real. Where the observation behind a dropped
proposal was still worth knowing it survives in Section 4 or in the inventory's Verdict column.

Claims deliberately **not** carried forward, because verification contradicted them or the evidence
was too thin to act on, are omitted rather than listed.
