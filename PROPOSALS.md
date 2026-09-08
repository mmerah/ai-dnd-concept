# Simplification and consistency proposals

Six independent full-codebase reviews (five subagents plus the session author), merged.
Every claim below was re-verified against the source before it was written down.

**Baseline at the time of review:** 565 tests pass in 6.3s; `ruff check`, `ruff format --check`
and `basedpyright` are all clean. 9,897 lines under `src/`, 9,236 under `tests/`, 2,292 under `qa/`.

Notation: **[n/6]** is how many independent reviewers raised the item.
Effort is S (under an hour), M (half a day), L (a day or more).

---

## 0. Start here

The five things worth doing first, in order. Each is small, each is agreed, none needs a decision.

| # | Do | Where | Effort |
|---|---|---|---|
| 1 | Delete two provably dead guards | `turn/run.py:117,131-134` | S |
| 2 | Fix the MCP argument-validation escape | `app/mcp.py:87` | S |
| 3 | Move the per-engine palettes onto `Engine` | `ui/theme.py:26-73` → `engines/seam.py` | M |
| 4 | Split `core/views.py` into models and prompt rendering | `core/views.py` | S |
| 5 | Give `Survivor`/`Crewmate` a shared sheeted base | `breathless/world.py`, `twentyfourxx/world.py` | M |

Everything after this is either larger, or needs a decision from Section D first.

---

## 1. Concept inventory

Every concept the codebase defines, by layer. The **Verdict** column is the merged judgement;
proposals referenced as `P<n>` are in Section B.

### 1.1 `core/` — the shape-free kernel (967 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Slug` / `EngineId` / `EntityId` / `CheckedEntityId` | `core/entities.py:10,13,14,16` | Four id grammars, split by who wrote the id | Keep — load-bearing |
| `Frozen` / `Mutable` / `Loose` | `core/entities.py:19,23,29` | The three Pydantic base configs | Keep; see C11 (a fourth exists in `app`) |
| `Refusal` | `core/entities.py:35` | The one exception a role or player reads | **Do not touch** |
| `parse` | `core/entities.py:56` | The single `ValidationError` → `Refusal` funnel | **Do not touch** |
| `content_id` / `slug` / `require_unique` | `core/entities.py:39,46,51` | Id narrowing, minting, duplicate bar | Keep; `require_unique` misused twice (C6) |
| `Fact` | `core/facts.py:32` | One thing that occurred | Keep; `kind` is questionable (**D5**) |
| `Fact.kind` | `core/facts.py:35` | Event category | **50 literals written, 1 read** — see **D5** |
| `DiceEvent` / `roll` / `cards` / `traced` | `core/facts.py:13,51,42,47` | The only die roller and the two fact renderings | **Do not touch** |
| `Line` / `SpokenLine` / `Narration` / `Interjection` | `core/play.py:10,20,38,44` | The narrator's typed answers | Keep |
| `DecisionOption` / `PendingOption` / `PendingDecision` | `core/play.py:62,68,75` | The suspended-decision machinery | Keep |
| `Answer` | `core/play.py:91` | Player input: option xor text | Keep |
| `Exchange` / `SceneRecord` | `core/play.py:108,127` | The unit of play; the unit of history | Keep; `SceneRecord` is rebuilt wastefully (P10) |
| `Scenario[P]` / `Character[P]` / `Game[P]` | `core/model.py:60,74,94` | The three persisted envelopes | Keep |
| `ScenarioMeta` | `core/model.py:27` | title/premise/scope/art_style/voice | Keep |
| `EngineHeader` / `CharacterHeader` | `core/model.py:42,55` | Routing headers read before the engine is known | **Do not touch** |
| `Named` | `core/model.py:48` | (name, brief) | One use (`model.py:57`) — see **D3** |
| `Generation` | `core/model.py:86` | An engine's one request to the worldsmith | Keep; string dispatch is the issue (**D4**) |
| `WorldsmithAnswer` / `Check[T]` | `core/model.py:82,24` | The ask protocol and its extra bar | Keep; `Check` name collides (C5) |
| `Game.draft()` / `.commit()` | `core/model.py:113,117` | Working copy; whole-tree revalidation | **Do not touch** |
| `Subject` | `core/views.py:25` | (id, name, brief) as roles and art see it | Keep; field names drift (**D3**) |
| `Panel` / `PanelRow` | `core/views.py:46,40` | Sidebar row and its group | Keep; `PanelRow` is a stringly-typed 3-way variant (C12) |
| `Action` | `core/views.py:59` | The page's way-on button | **Field-for-field a `DecisionOption`** — see **D3** |
| `DiceLook` | `core/views.py:51` | Per-engine dice colours | Keep — and the model for P3 |
| `NarratorView` | `core/views.py:67` | The narrator's input; structurally free of hidden canon | **Do not touch** |
| `PlayerView` | `core/views.py:135` | What the pages read | Keep; the UI bypasses it (C8) |
| `Rows` / `Sections` | `core/views.py:21,22` | Two aliases of one type, distinguished by a comment | Merge or `NewType` — see **D3** |
| `sections` / `lines_of` / `render_history` / `told_history` | `core/views.py:145,149,153,160` | Prompt text assembly | Split out of `views.py` (P4) |
| `FileStore` / `Library` | `core/io.py:25,53` | Saves; scenarios + characters on disk | Keep |
| `decode` + `_unique_keys` | `core/io.py:147,183` | Duplicate-key-rejecting JSON | **Do not touch** |
| `routed` / `write_text` | `core/io.py:155,139` | Engine routing; atomic staged write | **Do not touch** |
| `MasterTool` / `master_tool` / `Play` | `core/tools.py:28,35,14` | Tool record, factory, resolver signature | **Do not touch** |
| `Attempt` | `core/tools.py:18` | The `what` field four engines extend | Keep; it is game vocabulary in `core` (C18) |
| `schema_of` / `_normalize` | `core/tools.py:50,61` | One schema pipeline for MCP and prompts | **Do not touch** |
| `CreationStep` / `Picks` / `check_picks` | `core/creation.py:10,6,23` | Creation questions and their one legality rule | Keep |
| `other_than` / `option_of` / `chosen_option` | `core/creation.py:38,42,46` | `DecisionOption` list helpers | Move to `core/play.py` (P6) |
| `given_text` / `whole_text` | `core/source.py:14,22` | PDF/text source ingestion | Move to `app/` (P7) |

### 1.2 `config.py` (165 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `ProviderConfig` / `Providers` | `config.py:20,97` | base_url + key per provider | Keep |
| `RoleConfig` / `Roles` | `config.py:25,74` | Per-role provider/model/effort/timeout/max_rounds | Keep; `each()` duplicates `for_name()` (C13) |
| `MediaConfig` / `SpeechConfig` | `config.py:51,61` | Optional features, both off by default | Keep |
| `Settings` + `_keys_present` | `config.py:115,137` | The `.env` surface with a cross-field key check | Keep |
| `Role` / `ProviderName` / `CliProvider` / `RoleProvider` / `Effort` | `config.py:11-16` | Five string literals; `RoleProvider` is deliberately flat | Keep — the flat union is justified in a comment |
| Placement of `config.py` itself | outside every layer name | — | See **D7** |

### 1.3 `engines/` — the world layer (5,234 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Engine[P, G]` | `engines/seam.py:37` | The seam: 11 class attrs, 12 abstract, ~15 concrete | Keep; **not** an ISP problem (C4) |
| `Engine.compose` | `engines/seam.py:91` | Build-inside-the-bar so an unbuildable opening re-prompts | Keep |
| `Engine.close`/`commit`/`begin`/`restore` | `engines/seam.py:114,132,136,69` | The state lifecycle | Keep; `commit` names three things (C9) |
| `Engine.answer` | `engines/seam.py:82` | Play a `PendingOption` as a tool call | Keep |
| Hire machinery | `seam.py:180-198`, `base.py:144,147,168,215` | `hire`, `unwritten`, `check_request`, `require_hireable`, `sign_on` | 3 of 4 engines — see **D6** |
| `AnyEngine` | `engines/seam.py:28` | `Engine[Any, Any]` | Keep — the sanctioned `Any` |
| `build_engines` | `engines/registry.py:9` | The one composition root | **Do not touch** |
| `Thing` / `Person` / `World[P]` | `engines/base.py:38,96,113` | The entity hierarchy | Keep |
| `Counter` | `engines/base.py:182` | Bounded current/max with fact-emitting `change` | Keep |
| `Pack` | `engines/base.py:176` | Table-set base — **scene engines only** | Move to `scenes/` (P8) |
| `JoinParty` / `LeaveParty` / `Hire` | `engines/base.py:154,161,168` | Shared change verbs | Keep |
| Panel builders | `engines/base.py:225-262` | `character_panel`, `here_panel`, `party_panel`, `trail_panel`, `party_section` | Keep; consider own module (P8) |
| `keep_highest` | `engines/base.py:271` | Roll-and-keep-highest, 3 users | Keep; belongs near `roll` (P8) |
| `named_unmet` / `read_packs` / `SRD_PACK` | `engines/base.py:282,293,18` | **Scene-only helpers in the shared base** | Move to `scenes/` (P8) |
| `EXTEND` | `engines/base.py:20` | **Rooms-only constant in the shared base** | Move to the room engine (P8) |
| `SceneEngine` family | `engines/scenes/*` (901 lines, 3 users) | `SceneRun`, `SceneCanon`, `SceneWorld`, `SceneDraft`, `NextDraft` | **Do not touch** — earns its keep |
| `RoomEngine` family | `engines/rooms/*` (834 lines, **1 user**) | `Dungeon`, `Place`, `Way`, `Visit`, `RoomCanon`, `RoomWorld`, `MapDraft` | See **D1** |
| `MapDraft` vs `RoomCanon` | `rooms/drafts.py:7`, `rooms/world.py:114` | Both are `Dungeon + start` | Merge candidate — part of **D1** |
| `ChangeWorld` ×4 | `loner3e/tools.py:63`, `breathless:43`, `tunnelgoons:22`, `twentyfourxx:122` | One discriminated-union tool per engine | **Byte-identical** — see **D2** |
| `Reveal` / `Kill` ×2 | `scenes/tools.py:15,36`, `rooms/tools.py:9,26` | Same shape, different prose | Merge candidate (P9) |
| `scene_refusal` / `map_refusal` / `extension_refusal` | `scenes/worldsmith.py:38`, `rooms/worldsmith.py:38,43` | One bar per draft kind, all reasons at once | Keep; joiner duplicated 3× (P12) |
| Four concrete engines | `loner3e/`, `tunnelgoons/`, `breathless/`, `twentyfourxx/` | Each: engine, world, tools, worldsmith, rules.md, packs | **Keep all four** — see D1 rationale |

### 1.4 `turn/` (249 lines, 2 files, 1 consumer)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Turn` | `turn/run.py:29` | One turn's draft, rng, facts, notes | Keep |
| `Turn.call` | `turn/run.py:102` | The one gate every published tool passes | **Do not touch** |
| `Turn._apply` | `turn/run.py:128` | Trial-run against a copy; a refused call costs no dice | **Do not touch** the mechanism; delete the dead guard (P1) |
| `Turn.picture` | `turn/run.py:91` | Builds the master prompt | Rename (C10); it recomputes history (P10) |
| `render_master` | `turn/context.py:23` | Master prompt | See **D8** |
| `render_narrator` / `render_interjection` / `_picture` | `turn/context.py:47,60,81` | Narrator prompts | See **D8** |
| `turn/` as a layer | — | — | See **D8** |

### 1.5 `app/` (1,547 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `GameService` | `app/runtime.py:59` | One live game — **7 responsibilities** | Split (P13) |
| `Runtime` | `app/runtime.py:377` | Sessions, engines, library, store, tool surface, settings | Split (P14) |
| `RoleSpawner` | `app/runtime.py:365` | CLI-or-API per role | Keep; the decision is written 3× (P11) |
| `Spawner` / `Driver` protocols | `app/spawn.py:129,34` | Role execution; per-CLI argv+parse | **Do not touch** |
| `ClaudeDriver` / `CodexDriver` | `app/spawn.py:56,93` | The two CLI dialects | Keep |
| `CliSpawner` | `app/spawn.py:134` | The only thing that starts a process | **Do not touch** |
| `ask` + `RETRIES` | `app/spawn.py:188,19` | One retry carrying the error | **Do not touch**; move to its own module (P5) |
| `final_message` + scrapers | `app/spawn.py:163,247,257,266,272` | Extract JSON from four CLI output shapes | Move to `app/scrape.py` (P5) |
| `BuiltinSpawner` / `Tools` | `app/builtin.py:64,22` | Completion-API loop; the one real DIP inversion | **Do not touch** the protocol |
| `_Echoed` | `app/builtin.py:27` | A fourth Pydantic base config, declared in `app` | See C11 |
| `Illustrator` / `Reader` | `app/media.py:29`, `app/speech.py:21` | Cached art and TTS | Keep — see **D9** |
| `claim` / `post_bearer` | `app/providers.py:9,17` | Single-flight guard; the one bearer POST | Keep |
| `MountedLifespan` / `endpoint` | `app/mcp.py:21,57` | MCP over streamable HTTP | **Do not touch** |
| `LauncherCatalog` / `CatalogEntry` / `LaunchTarget` / `SaveOption` | `app/launch.py:43,14,23,33` | The launcher read model | `read()` does two jobs (P15) |

### 1.6 `ui/` (1,735 lines)

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `GamePage` | `ui/game.py:72` | One tab — **7 jobs, 18 attributes, 9 uninitialised** | Split (P16) |
| `Observed` | `ui/game.py:52` | The 1 Hz poll snapshot | Keep — genuinely the diff |
| Pure UI rules | `ui/game.py:597-637` | `can_type`, `standing_proposal`, `near_end`, `draft_spent`, `insert_at_caret`, `placeholder` | Keep; **module-layout violation** (C7) |
| `LaunchForm` / `CharacterForm` / `ScenarioForm` / `SettingsForm` | `ui/app.py:60`, `ui/create.py:22,139`, `ui/settings.py:23` | The four forms | Keep; `LaunchForm` after a public function (C7) |
| `ENGINE_PALETTES` | `ui/theme.py:26-73` | Per-engine CSS, keyed by four hardcoded ids | **Move to the seam** (P3) |
| `DiceTray` / `Dictation` | `ui/dice.py:13`, `ui/dictation.py:4` | Two JS components | Keep |
| `widgets` | `ui/widgets.py` | `page_header`, `avatar`, `entity_row`, `decision_widget`, … | Keep |

### 1.7 Test and QA concepts

| Concept | Location | Purpose | Verdict |
|---|---|---|---|
| `Table[G]` / `ScriptedSpawner` | `tests/support/table.py:144,115` | Live game + scripted roles | **Do not touch** — mandated by CLAUDE.md |
| `golden` / `AIDM_GOLDEN_REGEN` guard | `tests/support/golden.py:13`, `conftest.py:5` | Drift detector that cannot pass while regenerating | **Do not touch** — good design |
| `tests/support/golden_turn.py` | 14 lines, 3 constants | One consumer each | Delete (P18) |
| `tests/support/ui.py` | 20 lines | `ui_settings`, used by two non-UI tests | Delete (P18) |
| `tests/support/loner.py` | 87 lines | **The shared default game fixture**, used by 14 non-loner files | Rename (P18) |
| Dynamic golden lookup | `tests/core/test_golden_turn.py:19-26` | `import_module(f"tests.{id}.golden_turn")` behind two `cast`s | Replace with a table (P19) |
| `SixthEngine` et al. | `tests/core/test_rooms.py` (17 references) | A fabricated second room engine | Part of **D1** |
| `test_package_boundary.py` | 84 lines | The layer rule, enforced by AST | **Do not touch**; close the literal hole (P3) |
| `test_context_boundary.py` | 180 lines | The hidden-canon firewall | **Do not touch** |
| `test_integrity_boundaries.py` | 144 lines | Save/file corruption modes | **Do not touch** |
| `qa/` harness | 2,292 lines, 11 scenarios, 217 assertions | Real app + Playwright + scripted roles | Keep — see **D10** |

---

## 2. Simplification proposals

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

### P4 — Split `core/views.py` into models and prompt rendering **[2/6]** · S · high confidence

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

### P5 — Split `app/spawn.py` into three **[2/6]** · S · high confidence

**Current.** 299 lines doing four jobs: `Driver` + two CLI drivers (34-126), process spawning
(133-160, 208-244, 293-299), LLM-output scraping (163-185, 247-290), and the `ask` retry loop
(188-205).

**Do:**
- `app/scrape.py` — `final_message`, `_last_said`, `_object`, `_string`, `_found`, `_decodes`.
  String in, string out; zero knowledge of processes or settings; **already** imported across a
  module boundary by `builtin.py:12`. This is the strongest cut.
- `app/ask.py` — `ask()` and `RETRIES`. It takes a `Spawner` and never starts anything.
  `runtime.py:14` currently imports it from `spawn`, which reads as if asking spawns a process.
- `app/spawn.py` keeps `RunResult`, the protocols, the two drivers, `CliSpawner`, `_spawn`,
  `child_environment`, `_kill` — one job: start a role, get its text back.

While there: `CodexDriver.parse` (`spawn.py:122`) and `_last_said` (`spawn.py:249`) contain a
**byte-identical** event-list comprehension, and `parse` then calls `final_message(output)` on the
next line, which re-runs it. Extract `_events(output)`.

**Lost:** nothing.

---

### P6 — Move the `DecisionOption` helpers out of `core/creation.py` **[1/6]** · S · high confidence

`core/creation.py` is two things: character creation (`CreationStep:10`, `Picks:6`, `ANSWER_MAX:7`,
`picked:19`, `check_picks:23`) and generic `DecisionOption` list utilities (`other_than:38`,
`option_of:42`, `chosen_option:46`) — while `DecisionOption` itself lives in `core/play.py:62`.

The visible consequence: `turn/run.py:9` imports `option_of` from `core.creation` to resolve a
**pending play decision** — turn-time code importing a character-creation module.

**Do:** move the three helpers to `core/play.py` beside `DecisionOption`. `creation.py` becomes a
coherent 30-line module. (`option_of` and `chosen_option` differ only by raise-vs-`None`; keeping
both is fine, they have different callers.)

**Lost:** nothing.

---

### P7 — Move `core/source.py` to `app/` **[1/6]** · S · high confidence

`core/source.py` imports `pypdf` and reads the filesystem. It has **one** caller:
`app/runtime.py:22,454`. (`ui/create.py:14` takes `SOURCE_SUFFIXES` from `core/io.py:17`, not from
here.)

**Do:** move to `app/source.py`, and take `SOURCE_SUFFIXES`/`SOURCE_STEM` with it. `core` then
declares only `pydantic`, and PDF extraction stops being kernel vocabulary.

**Lost:** nothing.

---

### P8 — Evict the single-family symbols from `engines/base.py` **[3/6]** · S · high confidence

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

### P9 — Give the shared change verbs one home **[2/6]** · S · medium confidence

`Reveal` and `Kill` are defined twice with the same shape — `scenes/tools.py:15,36` and
`rooms/tools.py:9,26` — while their siblings `JoinParty`/`LeaveParty` live in `engines/base.py`.
So "the shared world-change vocabulary" currently has no single home.

**Do:** define `Reveal` and `Kill` once beside `JoinParty`/`LeaveParty`.

**Lost:** the per-family `description=` prose differs (`rooms`' `Reveal` says "an npc or an item";
`scenes`' says "an entity listed as hidden here"), and those descriptions reach the model through
`schema_of`. Either one wording serves both, or the union overrides the field. **Check the schema
goldens** (`tests/core/fixtures/schemas/*/master_tools.json`) before committing.

---

### P10 — Compute the view and the history once per turn **[2/6]** · M · high/medium confidence

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

### P11 — Resolve the CLI-vs-API decision once **[1/6]** · S · high confidence

The question "is this role a CLI or an API?" is written three times, each re-reading
`settings.roles.for_name(role)` independently: `RoleSpawner.run` (`runtime.py:371-373`),
`CliSpawner.run`'s guard (`spawn.py:141-142`), `BuiltinSpawner.run`'s mirror guard
(`builtin.py:71-72`).

**Do:** `RoleSpawner` resolves the `RoleConfig` once and passes it down —
`CliSpawner.run(role, config, prompt, session)`. Both guards and both re-reads disappear.

**Lost:** the two spawners stop being callable with just a role name. Nothing calls them that way.

**Note:** do **not** try to unify or drop the two mechanisms themselves. They are already unified
behind a one-method `Spawner` protocol, which is the minimum. `IDEAS.md:4` records that the builtin
mode was removed once and deliberately brought back. The duplication is the *decision*, not the
mechanisms.

---

### P12 — One unmet-reason joiner, one room-draft bar **[2/6]** · S · high confidence

Three copies of `return None if not unmet else "the X needs " + "; ".join(unmet)`:
`scenes/worldsmith.py:42-43`, `rooms/worldsmith.py:39-40`, `rooms/worldsmith.py:44-45`.
And `rooms/worldsmith.py:48-58` (`_start_unmet`) vs `:61-73` (`_extension_unmet`) are the same
eleven lines, differing only in the `known` polarity and one extra empty-places guard.

**Do:** one `unmet_refusal(what, unmet)` helper; merge the two room functions into
`_reachable_unmet(draft, *, start_known: bool)`.

**Lost:** two named functions that read as prose, traded for one boolean parameter.

---

### P13 — Split `GameService` **[4/6]** · M · high confidence

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

### P14 — Split `Runtime` **[2/6]** · M · medium confidence

`app/runtime.py:377-507` does five jobs: composition root (engines, library, store, spawner),
session cache, settings reload, MCP tool routing, scenario authoring.

**Do:**
- Extract **`SessionTools`** — `_sessions` plus `published_tools`, `playing`, `call`,
  `busy_refusal`, `play_refusal`, `session`. This is what `mcp.py` and `BuiltinSpawner` actually
  need. Today `mcp.py:10` imports the whole composition root to reach two methods, and
  `builtin.Tools` (`builtin.py:22`) is a protocol **no production type is declared against**.
  It also un-cycles the wiring: `Runtime → BuiltinSpawner → Runtime` becomes
  `Runtime → BuiltinSpawner → SessionTools`.
- Move `new_scenario` (`:444-467`) to `app/authoring.py` as a free function. It touches no
  `Runtime` state beyond `engines`, `library`, `settings`, `spawner`.

`Runtime` then ≈ 60 lines.

**Against:** CLAUDE.md's "do not add an abstraction until two things need it" — but the protocol
already exists and is simply unused, so this is making an existing abstraction real rather than
inventing one.

---

### P15 — Split `LauncherCatalog.read` **[1/6]** · S · high confidence

`app/launch.py:63-122` is a 60-line `@classmethod` doing two jobs: build the scenario and character
entries (67-87) and validate every save (88-121 — load, decode, route, restore, cross-check title,
scenario engine and filename, read the scene title, with three warn-and-continue arms).

**Do:** extract `readable_saves(store, engines, scenarios, characters)` as a free function. `read()`
drops to ~20 lines, and the majority of `tests/ui/test_launcher.py` (313 lines) can target the
function directly.

**Related waste:** `LauncherCatalog.read` is called from `ui/app.py:23` **and** `ui/create.py:273`,
but `ScenarioForm` uses only `catalog.characters_for` (`create.py:177`). Opening `/scenario`
therefore fully `restore()`s every save on disk for nothing. Also, `scenario_models` is built
identically at `launch.py:67` and `runtime.py:478-479` — one `Runtime.scenario_models()` method.

---

### P16 — Decompose `ui/game.py` **[2/6]** · M · high confidence

637 lines, seven jobs, and `GamePage.__init__` (`:75-96`) declares 18 attributes of which **nine are
bare annotations with no value** — the object is not usable until `build()` runs.

**Do, in order of confidence:**
1. **`ui/rules.py`** — move the six pure functions at `:597-637`. Fixes the module-layout violation
   (C7), ~40 lines, zero risk.
2. **`ui/composer.py`** — a `Composer` owning `box`, `send`, `action_button`, `over_label`,
   `Dictation`, plus `_set_composer`, `_clear_spent_draft`, `submit`'s widget half,
   `dictated`/`dictation_failed`. ~130 lines. This is the tightest seam: four of the eighteen
   attributes, and the three duplicated `run_method("updateValue")` pairs at `:391-394`, `:431-434`
   and `:472-473` collapse into one `set_text()`.
3. **`ui/transcript.py`** and **`ui/panels.py`** — later, and only after P10(3) settles, or you will
   thread `PlayerView` through three constructors twice.

`GamePage` then ≈ 230 lines with one job: drive the page.

---

### P17 — Move the shared scene-bar tests out of the engine directories **[1/6]** · M · high confidence

`scene_refusal` (`scenes/worldsmith.py:38`) and `SceneEngine.install` (`scenes/engine.py:303`) are
tested three times over — `tests/breathless/test_worldsmith.py:27,32,40,45,56,71,85`,
`tests/twentyfourxx/test_worldsmith.py:94,125,132,139,144,169,184,191,218,233`, and
`tests/loner3e/test_world.py:113,136,205`. Several are functionally identical. Meanwhile
`tests/core/test_scenes.py` already owns the shared scene world.

**Do:** move one copy of each shared-bar assertion into `tests/core/test_scenes.py`. Leave in each
engine directory only what is genuinely that engine's (`Survivor.unwritten()` returning `"a sheet"`,
24XX's `SheetDraft.refusal(pack)`).

**Lost:** the accidental property that the bar is proven against each engine's concrete cast type —
recoverable by parameterising the moved tests over the three cast types.

---

### P18 — Retire two test-support modules, rename a third **[1/6]** · S · high confidence

- **`tests/support/golden_turn.py`** (14 lines, 3 constants): `NARRATION`/`INTERJECTION` have one
  consumer (`test_golden_turn.py:9`), `LISTENING` has one (`tests/loner3e/golden_turn.py:1`).
  Inline them; delete the module.
- **`tests/support/ui.py`** (20 lines): `ui_settings`'s only delta over `offline_settings`
  (`table.py:106`) is a populated OpenRouter key — and it is imported by `tests/core/test_speech.py:10`
  and `tests/core/test_media.py:9`, contradicting its name. Replace with
  `offline_settings(..., keyed=True)`.
- **`tests/support/loner.py`** (87 lines): **verified** — imported by 14 test files outside
  `tests/loner3e`. It is the shared default game fixture, not a loner3e helper. Rename to
  `tests/support/game.py`.

Also: `offline_settings()` (`table.py:106-111`) defaults `saves_dir` to `Path("saves")` — the
working directory. Two call sites use the no-arg form and neither writes today, but it is a live
trap. Make `saves` required or default it to a temp dir.

---

### P19 — Replace the dynamic golden-turn lookup with a table **[1/6]** · S · high confidence

`tests/core/test_golden_turn.py:19-26` does
`cast(..., import_module(f"tests.{engine_id}.golden_turn").SCRIPT)` — two `cast`s past the type
checker, working only because `tests/` are implicit namespace packages. A new engine without that
file fails with `ModuleNotFoundError`, not a readable message.

**Do:** a `GOLDEN_TURNS: dict[EngineId, tuple[Script, Behind]]` in `tests/support/table.py`
importing the four modules directly. Removes both `cast`s; a missing entry becomes a `KeyError`
naming the engine.

**Lost:** the property that adding an engine needs no core edit — worth one line per engine, and a
new engine already has to write `tests/<id>/golden_turn.py` anyway.

---

### P20 — Bring `qa/` under the toolchain **[1/6]** · S · high confidence

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

## 3. Consistency and SOLID findings

Ranked by impact. Findings that already have a proposal are cross-referenced, not repeated.

**C1 — `ui/theme.py` holds per-engine world knowledge.** See **P3**. The highest-impact rule
violation in the codebase, and it fails silently.

**C2 — Two tool-argument validation conventions at the two transports.** See **P2**. A behavioural
bug, not just drift.

**C3 — `GameService` and `Runtime` are the app layer's God objects.** See **P13**, **P14**.
The sharpest symptom is `Runtime.playing()` (`runtime.py:410-415`): because an MCP tool call carries
no session identity, the runtime must assert that at most one turn is in flight process-wide and
raise `ValueError` otherwise. That is a global-singleton assumption forced by the transport, and it
is invisible from `Turn` or `Engine`. See **D13**.

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
See **D14**.

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
`aidm.app.runtime` — it tests `app`, not `ui`. See **D15**.

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

## 4. Decisions

Each of these is genuinely open — either the reviewers disagreed, or the trade-off is a judgement
call about where this project is going. Options are listed with the merged recommendation last.

### D1 — Does `engines/rooms/` survive as a family?

**Facts.** `rooms/` is 834 lines across five modules with generic parameters `[N]`, `[P]`, `[G]`.
**Verified:** the only importer of `aidm.engines.rooms` outside `rooms/` itself is `tunnelgoons/`.
The only second implementer is `SixthEngine`/`SixthWorld`/`SixthGame`/`SixthScenario`/`SixthCharacter`
in `tests/core/test_rooms.py` (17 references) — a fabricated engine that exists because the
abstraction demands a second user the codebase does not have.

**Verified against the roadmap:** `IDEAS.md:18` says the planned second dungeon game (Maze Rats)
"rewrites the world on its own strict actor/item/place model" — i.e. it is *not* planned to reuse
`rooms/`.

Structural asymmetries that exist either way: `scenes/` has a family `rules.md` appended at
`scenes/engine.py:96`; rooms has none. `rooms/drafts.py` is 10 lines and its one class *imports the
world*, so the stated reason for a separate `drafts.py` (`scenes/worldsmith.py:41`: "the drafts may
not import the world") does not apply to it. `EXTEND` is a rooms-only constant in the shared
`base.py:20`. Four verb pairs diverge for the same roles (`render_opening`/`render_map`,
`render_next`/`render_extension`, `write_next`/`write_extension`, `install`/`install_extension`).

- **(a) Fold `rooms/` into `tunnelgoons/`.** Removes 834 source lines plus 257 test lines including
  the synthetic engine; drops five layers of generic parametrisation and the runtime-subscript trick
  at `rooms/engine.py:67-69`. Merge `MapDraft` and `RoomCanon` (both are `Dungeon + start`).
  Mechanical, 2-3 hours. This is the codebase's own "do not add an abstraction until two things need
  it" rule violated at the largest scale present.
- **(b) Keep it and fix the asymmetries.** Add `rooms/rules.md`, move `drafts.py`'s class into
  `world.py`, align the four verb names with `scenes/`, move `EXTEND` out of `base.py`. ~2 hours.
  The code is written, tested and correct; folding it in is churn unless it buys clarity, and
  `RoomWorld` (406 lines) is its own module either way.
- **(c) Keep the models, drop the engine.** Fold `RoomEngine` into `TunnelGoonsEngine`, leave
  `rooms/world.py` as a shared map model.

**Two reviewers split here.** Recommend **(a)** — `IDEAS.md:18` refutes (c)'s premise outright, and
(b) protects one package by writing an exception into the rules. But (b) is the safe answer if a
second map ruleset is more likely than the roadmap suggests, and the asymmetry fixes in (b) are
worth doing *first* either way, since (a) subsumes them.

### D2 — How to remove the four `ChangeWorld` wrappers

**Verified byte-identical** at `loner3e/tools.py:63`, `breathless/tools.py:43`,
`tunnelgoons/tools.py:22`, `twentyfourxx/tools.py:122` (plus a fifth in `tests/core/test_rooms.py:43`),
differing only in the union they wrap.

- **(a) A generic `class ChangeWorld[C](Frozen)` in `engines/base.py`**, with each engine writing
  `ChangeWorld[WorldChange]`. Keeps the union as a written annotation and stays type-checked.
- **(b) A `create_model` factory**, `change_world_args(union)`. Saves the most lines, but the output
  is opaque to basedpyright and would likely need a `# pyright: ignore` — against the spirit of the
  no-`Any` rule.
- **(c) Just rename the four** (`BreathlessChangeWorld`, …) so the name stops resolving to four
  different types depending on the import, and accept the duplication.

Recommend **(a)**, with (c) as the fallback if pydantic's discriminated union does not accept a
type-parameter field cleanly — **verify that before committing**. Either way, check
`tests/core/fixtures/schemas/*/master_tools.json`: `schema_of` strips `title` (`core/tools.py:15`),
so the goldens should not move, but confirm.

### D3 — One labelled-value vocabulary, or leave the five shapes?

Six spellings of "a thing with a name and a line":

```
Named          (name, brief)                          core/model.py:48   1 use
Subject        (id, name, brief)                       core/views.py:25   roles + art
CatalogEntry   (id, engine, title, subtitle, rules)    app/launch.py:14   launcher
PanelRow       (label, detail, icon_id)                core/views.py:40   sidebar
DecisionOption (id, label, detail)                     core/play.py:62    choices
Action         (id, label, detail)                     core/views.py:59   the way-on button
```

**Verified:** `Action` and `DecisionOption` have the same three fields; `DecisionOption` adds
`min_length=1` on `label` and a default `detail=""`.

- **(a) Minimal.** Delete `Action` (use `DecisionOption`), delete `Named` (one use), collapse
  `Rows`/`Sections` into one alias. ~11 lines, ~10 sites. Low risk.
- **(b) Minimal plus the rename.** Also rename `Subject.name`/`brief` → `label`/`detail` and make
  `CatalogEntry` a `Labelled` plus `engine`/`rules`, establishing one naming law: `id`/`label`/`detail`,
  with `icon_id` the one extension. ~30 sites including `base.py:92,225-262`, `launch.py:70-87`,
  `media.py:176,193`, `context.py:92-96` and all four engines. Mechanical but wide.
- **(c) Leave it.** Each name carries local intent (`Action` says "this is a button, not a choice
  inside a decision").

Recommend **(a) now, (b) later**. (a) is unambiguous. (b) is a real improvement and a real diff; do
it as its own commit when nothing else is in flight, and add the naming law to CLAUDE.md so it holds.

Related, same decision shape: `Rows` and `Sections` (`core/views.py:21-22`) are PEP 695 aliases of
the identical type, so the checker treats them as one — a sheet can be passed where a prompt section
is expected with no error. Either make them `NewType`s (the distinction becomes real) or admit they
are one type and keep one name.

### D4 — Replace `Generation.operation` string dispatch?

The slug is compared by `==`/`in` at nine sites: `seam.py:191,197`, `scenes/engine.py:109,207,209,331`,
`rooms/engine.py:74,177`, plus `!= HIRE` in three engines. The `operations` tuple (`seam.py:49`) is a
parallel declaration kept in sync by hand (`(*Base.operations, HIRE)` in three engines).

- **(a) `Operation` value objects.** `class Operation(Frozen): id: Slug; unwritten: Fact`. Each
  family declares its tuple; `Engine.unwritten` becomes a lookup instead of an `if`-chain with a
  `super()` fall-through; `validate` becomes a membership test. But `Generation.operation` must stay
  a `Slug` on disk, so you gain an indirection at the boundary.
- **(b) Do D6 first, then re-measure.** Folding the hire round-trip into the seam removes three
  `!= HIRE` comparisons and lets `check_request` merge into the operations check, leaving five sites
  inside the two family bases.
- **(c) Leave it.** Three operations total (`hire`, `departure`/`complication`, `extend`); an enum
  would add ceremony without removing a branch.

Recommend **(b)**. With three operations, (a) risks tripping "do not build for future needs". If a
fourth operation appears, do (a) then.

### D5 — Delete `Fact.kind`?

**Verified:** 50 distinct `kind` literals are written across all four engines and both families.
Production reads the field in **exactly one place**: `loner3e/engine.py:205`,
`if not any(fact.kind == "conflict_lost" for fact in exchange)`. (The other `.kind` hits are
`PendingDecision.kind` and `ChangeTags.kind` — different fields.)

- **(a) Delete it.** Replace the one read by having `_strike` (`loner3e/engine.py:251`) return
  `(facts, ended: bool)` — it already knows at `:259` that `hit.luck.current == 0`. Removes a field,
  an argument from `Thing.fact()` and its ~60 call sites, 50 invented string constants, and ~80 test
  assertions that check `kind` and nothing else — which CLAUDE.md's own test rule calls "wiring".
- **(b) Keep it.** It is a human-readable annotation in the save JSON, visible in
  `tests/core/fixtures/turn/*.json`. And `IDEAS.md:9` contemplates a "state keeper" role that might
  filter facts by kind.
- **(c) Keep it, drop the tests that assert only on it.** Half the win, none of the churn.

Recommend **(a) or (c)**, not (b). The `IDEAS.md:9` argument is precisely the "build for future
needs" the rules forbid, and the field can be re-added in one commit when a second reader appears —
but `trace` already carries the same information in prose, so (b) is defensible if the save-file
readability is genuinely used. **(c) is the low-risk middle**: it removes the wiring tests
immediately and leaves the delete for later. Four turn goldens regenerate under (a).

### D6 — How is the hire feature factored?

Three engines hire (breathless, tunnelgoons, 24XX); loner3e does not. The machinery is spread over
four files: `Engine.hire` (`seam.py:180`), `Engine.unwritten`'s HIRE branch (`:189`),
`Engine.check_request` (`:195`), `World.require_hireable` (`base.py:144` — a base method that
unconditionally raises, with its parameter unused), `World.sign_on` (`base.py:147`), plus
`HIRE`/`HIRE_TOOL`/`SIGNED_ON`/`Hire`/`hire_target` in `base.py`. And the same six-step `advance`
branch is written three times: `breathless/engine.py:196-224`, `tunnelgoons/engine.py:153-172`,
`twentyfourxx/engine.py:303-326`.

- **(a) A template method on the seam.** `Engine.advance` handles the HIRE arm and delegates to a new
  `write_sheet(draft, member, terms, worldsmith) -> str` hook; the families implement a `grow` hook
  for their own operations. Each hiring engine keeps only its prompt and sheet construction.
  Loner3e needs a default that raises — the same optional-method smell, moved.
- **(b) A `Hiring` mixin** the three hiring engines opt into, removing the machinery from `Engine`
  entirely. ISP-correct: loner3e stops carrying four methods it never uses. But it adds a third
  dimension to an already-generic hierarchy (`Engine[P,G]` → `SceneEngine[C,P,G,K]` → concrete).
- **(c) Leave it.**

Recommend **(b) if the mixin composes cleanly with `SceneEngine`/`RoomEngine`; otherwise (a)**.
**Do neither until the coverage gap in Section 6 §2 is closed** — 24XX's hire-then-succession path
has no end-to-end test, and both options touch it.

### D7 — Should `config.py` move under `app/`?

It sits outside every layer name, imports only `core.entities.Frozen`, and is hand-listed in the
boundary test. Its real readers are `app` (6 imports) and `ui` (3).

- **(a) Leave it, and fix the stale rule.** Tighten CLAUDE.md and
  `tests/core/test_package_boundary.py:22` to `("app", "ui")`. Free (see C24).
- **(b) Move to `app/config.py`** and tighten the rule. `ui → app` is already legal. Removes the one
  module with no layer.
- **(c) Leave everything.**

Recommend **(a) now**, since it is free and correct, and **(b)** if the "every module has a layer"
property is worth a rename.

### D8 — Where does prompt rendering live?

`turn/context.py` holds three renderers with two different owners: `render_master` is called only
from `Turn.picture` (`run.py:92`); `render_narrator` and `render_interjection` are called only from
`GameService._narrate` (`runtime.py:284`) and `GameService.interject` (`runtime.py:185`). They share
only `_picture` and `_prompt`.

Separately: `turn/` is 249 lines with one consumer. **Verified:** it imports no settings, so the one
property it currently earns is that `Turn` cannot reach a `Spawner`, `Settings` or `GameService`.

- **(a) Leave `turn/` as is,** and just fix the stale settings claim (D7a).
- **(b) Split `context.py` by owner.** `render_master` folds into `turn/run.py` beside
  `Turn.picture`; `render_narrator`/`render_interjection`/`_picture` move to `app/` beside their only
  callers, with `narrator.md`/`interjection.md` moving to `app/prompts/`. One module deleted, each
  renderer beside its owner, and `turn/` keeps one honest job.
- **(c) Merge `turn/` into `app/` entirely.** Deletes a layer name, pushes `app/runtime.py` past 750
  lines, and mixes "the rules of a turn" with "the plumbing of a session".

Recommend **(b)**, and explicitly **not (c)** — the compile-time guarantee that turn logic cannot
reach a spawner is the property the whole design rests on.

### D9 — Null Object for `media` / `reader`?

`GameService.media: Illustrator | None` and `reader: Reader | None` (`runtime.py:66-67`), guarded at
`runtime.py:302, 307, 311, 314, 322` and `ui/game.py:171`.

- **(a) Two Null classes** (`BlankIllustrator`, `SilentReader`). Removes five guards — but
  `ui/game.py:171` decides whether to start a 3-second poll at all, so an `enabled` flag comes back
  anyway. Two new classes to delete four `if`s.
- **(b) Keep the `Optional`s, extract a `Presenter`** (part of P13). The checks stay but live in one
  45-line class instead of interleaved with turn orchestration, and `Presenter.polls` answers
  `ui/game.py:171` honestly.
- **(c) Both.**

Recommend **(b)**. The Null Object is net ceremony here, and "do not add an abstraction until two
things need it" applies. The clustering is the real problem, not the checks.

### D10 — What is `qa/` for, going forward?

2,292 lines, 11 scenarios, 217 assertions, 103 screenshots. It runs the real app with scripted
roles under Playwright. It is maintained (4 of the last 100 commits touch it, the most recent `a46e7ee`; three
commits exist purely to fold its findings back in: `823f702`, `abac557`, `afa36d3`). It is the **only** coverage of `ui/app.py`,
`ui/create.py`, `ui/widgets.py` and the real MCP JSON-RPC transport. It is also outside every gate:
unchecked by basedpyright, 14 dead `noqa`s, no CI at all.

- **(a) Leave it as is.** Zero work; the drift continues.
- **(b) Bring it under the toolchain and trim the pytest-redundant scenarios** (P20). Add `qa` to
  `basedpyright.include`, clear the dead directives, shrink `s_settings` (193 lines, largely
  restating `tests/ui/test_settings.py`) and fold `s_home`'s route checks into `s_visual`.
  Keep `s_visual`, `s_mobile`, `s_probe`, `s_mcp` and the four engine drives — nothing in `tests/`
  touches what they cover.
- **(c) Delete it and port the checkable parts to pytest.**

Recommend **(b)**, and explicitly **not (c)**. But take the trimming half only if those two scenarios
have genuinely stopped finding things — the redundancy has historically paid.

### D11 — Delete the unreachable `_apply` guard, or promote it?

`turn/run.py:131-134` (see P1).

- **(a) Delete.** It is dead; "do not build for future needs".
- **(b) Convert to `assert`.** Documents a real, non-obvious invariant — a tool that opens a
  decision while one is already open would be a genuine engine bug — and would fire loudly if a
  third `_apply` caller appears.
- **(c) Keep as is.** Costs nothing at runtime.

Recommend **(b)**. The invariant is real, but expressing it as a `Refusal` mislabels a bug as a
message, which is exactly what CLAUDE.md forbids.

### D12 — Which boundary owns tool-argument validation?

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

### D13 — Should the MCP tool surface be per-turn rather than process-global?

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

### D14 — How does the UI learn about the game?

See C8.

- **(a) Leave it.** The boundary test already prevents the real hazard (importing a concrete engine).
- **(b) Give `GameService` the six accessors the UI actually uses** — `history()`, `scenes()`,
  `narrator_view()`, `engine_title`, `engine_id`, `dice_look` — and forbid `ui` from touching
  `session.engine`. ~15 lines.
- **(c) A full DTO boundary:** the UI sees only `PlayerView` and a `ChatView`, never `Fact` or
  `Exchange`.

Recommend **(b)**. It is the smallest change that makes the stated boundary true, and it makes
P10(3)'s caching possible in one place. (c) adds a whole shape family that would itself become a
finding.

### D15 — Do the test directories get re-shaped to mirror `src/`?

See C26.

- **(a) Full re-shape.** `tests/{core,engines,turn,app,ui}` plus the four engine dirs;
  `tests/ui/test_launcher.py` → `tests/app/`; `tests/support/loner.py` → `tests/support/game.py`.
  ~30 files, zero behaviour change, expensive to review.
- **(b) Minimal.** Move the one clearly-misfiled file and do the rename from P18. Leave the rest.
- **(c) Leave it.**

Recommend **(b) now, (a) later** — and (a) only after P17 and P18 have landed, so `tests/core` is
smaller when it moves.

Related, and settled: **keep the four per-engine directories**. They hold 740-1,240 lines of
genuinely different rules each; collapsing them would produce 1,000-line files. The problem is not
the split, it is that shared-family code is tested inside engine directories (P17).

---

## 5. Load-bearing — do not touch

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

## 6. Coverage gaps that gate the risky work

Simplification without coverage is a bet. These are the gaps, in the order they constrain the
proposals above.

1. **No full-playthrough test for any scene engine.** `tests/tunnelgoons/test_play.py:45` is the only
   start-to-finish test. `breathless` and `twentyfourxx` have no multi-turn test at all.
   **Gates D6 and P17.**
2. **24XX's hire-then-succession path is untested end to end.** `tests/twentyfourxx/test_world.py:124`
   and `test_tools.py:416` cover the mechanism, but not a hired member's sheet surviving a save
   across `_succession` (`twentyfourxx/engine.py:278`). **Gates D6 specifically.**
3. **Modules with no test importing them at all:** `ui/app.py` (207 lines — `home_page`,
   `LaunchForm`'s scenario↔character re-pairing at `:86-101`, `_register_pages`, the MCP mount at
   `:166-172`); `ui/create.py` (292 lines — the refresh-on-blur dance at `:80`, `_drop_stale`, the
   preview gate at `:135`); `ui/widgets.py` (88 lines — `decision_widget`, **the only way a player
   answers a `PendingDecision`**, heavily tested server-side and untested client-side).
   Covered only by `qa/`. **Gates D10's trimming half and P16.**
4. **The real MCP transport** exists only in `qa/s_mcp.py`. `app/mcp.py` is tested for lifespan only
   (`test_mcp_lifespan.py`, 22 lines). **Gates P2, D12 and D13 — do not trim `s_mcp`.**
5. **`reload_settings` and background tasks.** `tests/ui/test_settings.py:75,83` covers the refusals;
   nothing covers what happens to a background interjection belonging to an evicted session
   (`runtime.py:440-442`). **Gates P13's `Presenter` extraction** — and see C23, which says the
   current behaviour is not what the comment claims.
6. **`app/providers.py`** (28 lines) — `claim()`'s no-await invariant (`:9-14`) is exercised only
   indirectly. **Gates any merge of `Illustrator` and `Reader`.**
7. **`Pack._twist_columns_pair_up`** (`loner3e/worldsmith.py:33-40`) — the only guard that a twist
   column is exactly six rows, and it has no direct test.
8. **No CI at all.** `.github/` does not exist. **Do P20's CI half before any L-effort move.**

---

## Appendix — how this was produced

Five subagents plus the session author each independently read the whole codebase against CLAUDE.md,
with different emphases: `core/`+`turn/`, `engines/`, `app/`+`ui/`, `tests/`+`qa/`, and a
whole-system pass (hot path, vocabulary, layering, big bets).

Every factual claim reproduced here was re-verified against the source before being written down.
Where a reviewer's number was wrong it was corrected; where two reviewers disagreed, the
disagreement is preserved as a decision in Section 4 rather than resolved silently.

Claims deliberately **not** carried forward, because verification contradicted them or the evidence
was too thin to act on, are omitted rather than listed.
