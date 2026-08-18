# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 — Scenario creator

Done-when met: `scripts/create_scenario.py rats-of-thornhill "..."` produced
`scenarios/rats-of-thornhill/`, which appears on the home page and plays under both engines.

- `scripts/create_scenario.py <slug> "<premise>"` is a three-line shim over
  `aidm.app.scenario_creator`, which lives in `app` because it composes engines, `Stage`, and
  `begin_game`. Role key `scenario_creator` drives every call.
- **The world is authored agentically, not in one answer.** A one-shot
  `NativeOutput(ScenarioWorld)` was built first and failed live: weak models answered the huge
  schema with a `"..."` template, and one bad field threw away the whole document. It was
  replaced by an agent that builds a `WorldDraft` (its `deps`) through four tools —
  `worked_example`, `scenario_so_far`, `write(ScenarioPatch)`, `validate_scenario` — where a
  patch upserts by id, so "modify" needs no second tool. Editing a scenario conversationally in a
  later phase is the same agent with a draft loaded from disk.
- **The run ends on a `finish` tool** (`ToolOutput(str, name="finish")`, argument `response`), not
  on bare text: an author that only ever calls tools never ends its own turn, which hung the first
  real run until the request limit. Its output validator refuses `finish` while the draft does not
  play, so the agent is asked again with the reason. `UsageLimits(request_limit=40)` bounds a
  spinning run.
- The overlay stayed one-shot `NativeOutput(TypedOverlay[engine.sheet_type])` (parametrised at
  runtime from the dynamically imported engine, one narrow pyright ignore) with
  `ask_until_playable`: its output is small and it never failed. Overlays are written with
  `exclude_defaults=True`, so a generated file is as terse as a hand-written one.
- `Playtest` (engine + the shipped `kael`) is what refuses a world; `playability()` adds the
  authoring bar and reports **every** unmet item at once, because an author fixing one per round
  burns the request limit. `authored_world` revalidates after the run — the agent saying "ok" is
  never trusted — and `main()` folds any failure into one readable line.
- **Validation gained four canon invariants**, all on `ScenarioWorld` and never on `WorldState`:
  the Worldkeeper creates locations mid-game, so a commit-time reachability rule would fail the
  turn. They are: every location reachable by any `connected` way; every *known* location
  reachable by *known* ways (a place the player knows of but cannot walk to is a dead end); hook
  `match.data` ids exist; hook *effect* ids exist. The last two share one pooled-id helper with
  `check_hooks`. Ids an effect **creates** (`trait_id`, `stage`) are deliberately not policed.
- `HookMatch.kind` is `HookFactKind`, a `Literal` of the fact kinds core emits from world ops.
  Engine kinds (`conflict_lost`, `job_completed`, advancement growth) are excluded for the same
  reason hook effects are: one `world.json` is loaded by every ruleset. `hook_fired`/`hook_failed`
  are excluded too — `fire_hooks` feeds each round's facts back in, so matching them self-feeds to
  the round cap. A test greps the emit sites both ways so the `Literal` cannot rot. **A
  consequence worth knowing: an authored hook can no longer react to any engine fact.** Wanting
  that means a per-engine hook surface, not a wider `HookMatch.kind`.
- No new `Engine` API was needed for PLAN step 3's "engine-provided authoring guidance": the
  strict sheet schema carries the fields and defaults, and the shipped
  `whispering-vault/<engine>.json` is the worked example.
- `scenario_creator` carries its own defaults in `config.ROLE_DEFAULTS` (strong model, 32k tokens,
  high reasoning — the turn-loop 2048 cannot emit a world). `Settings.role` merges a partial
  `ROLES__SCENARIO_CREATOR__...` override over them through a real validation call, so setting one
  field does not silently reset the rest.
- `write_scenario` takes `Mapping[EngineId, ScenarioOverlay]`: nothing lands on disk until every
  shipped engine validates. Tests build `Settings` with `env_file=None` — the suite was reading
  the checkout's `.env`. No persisted-byte change: `SAVE_VERSION` unmoved, no fixture moved.
- Quality of a generated scenario is judged by playing it, not by the validator. What the first
  one got wrong and no rule can catch: the thread's destination was an empty room, and the
  creature the title turns on had no hook. Both are now questions in the prompt's review pass.

### Phase 2 — Progressive world expansion

Done-when met: a game whose `world.json` says `"expansion": "generative"` plays turns in which the
Director materializes canon mid-plan through `expand_world` and walks the player into it; a
`closed` scenario plays with a byte-identical Director agent. No save byte moved — `SAVE_VERSION`
stayed 70, and only the worldkeeper instructions and the `worldkeeper_report` schema fixture drifted.

- **Movement now follows explicit topology, always.** The `_require_open_way` wildcard (an
  exit-less location could reach anywhere) is gone, and `connected` is refused when `directed`.
  The consequence that made step 1 mandatory rather than cosmetic: a Worldkeeper-created location
  would otherwise be unreachable forever, so `apply_report` writes an undirected `connected`
  relation from it to the location its `location` field names — which is why that field's
  description and the worldkeeper prompt now say "the place it connects to". The relation is
  `known` only when the anchor is: a known relation may not name an entity the player has not met,
  and the Worldkeeper is shown unrevealed canon it may anchor to.
- **The adventure triple is `GameState` + `ScenarioWorld.expansion` + a `CanonSource`.**
  `content/sources.py` holds the policy literal, the protocol, and `PremiseSource`;
  `store.read_source` reads the scenario dir's `source.md` and falls back to `meta.premise`.
  Nothing lands on `GameState`, so a save resumes under its scenario's policy and a restart replays
  the same opening. `Runtime._open` is the only place a source is built, through `open_source`,
  which returns None for `closed` — that check is the only reader of the policy, so **no
  `Adventure` record carrying it exists**: an `Adventure(policy, source)` pair was written and
  deleted in review because nothing ever read `policy` back. Phase 3's `grounded` branch adds the
  parameter it actually needs at `build_stages` when it exists.
- **The Expander is a role behind a Director tool, not a pipeline stage.** `turn/expansion.py` is
  the leaf — `ExpansionPatch`, `Expansions`, and `apply_patch`, the one
  resolver that reaches the world. The stage and toolset live in `turn/roles.py` with the other
  role builders: `roles` already owns `Stage` and `PlanContext`, so putting the stage in
  `expansion.py` would have needed both extracted to break a cycle, for nothing.
- **What keeps the leak rule holding by construction:** every entity in a patch is forced
  `known=False`, so `draft.add` emits an `entity_created` fact whose `narrator` is already None;
  relations, threads, and hooks emit `canon_materialized`, a kind `HookFactKind` deliberately
  excludes and which never narrates. The Director's own `reveal`/`relation-change`/`move` effects
  are the only way the player learns anything. The one place this had to be added by hand is
  `_connect`: its trace names the *anchor*, so it narrates only when the anchor is known — gating
  on the created location alone (always `known=True`) put an unmet name in `Fact.narrator`, which
  is persisted and which Phase 5's journal export will read.
- **The tool applies through `transact`**, so created actors are seeded and hooks fire on the one
  mutation sequence. `PlanContext` grew the turn's `rng` and an `Expansions` record; the first
  Director call now receives the turn draft rather than the committed state (byte-identical at that
  point) so the tool has something disposable to write into. A patch is refused twice: by the
  Expander's own output validator (so the *Expander* retries, not the Director), then really by
  `transact` — which is outside the tool's `try`, because a half-applied draft is not a state to
  plan another beat against. **That only holds because the trial runs the whole sequence**: the
  validator wraps `transact` too, not just `apply_patch`, or hook-firing and seeding would be
  unexercised until the real pass, where a failure kills the turn instead of asking again.
  `expand_world` is registered `sequential=True` — two calls in one model answer would otherwise
  interleave on the same draft, each validating against a state without the other's canon, and both
  slipping the cap. Cap is 2 per turn; a bad `anchor_id`, the cap, and an Expander that exhausts
  its retries each get their own retry message, because "plan with what exists" is wrong advice for
  a typo'd id.
- **`--opening` authors a slice, not a scenario.** A `Brief` (instructions + bar + policy) is what
  `playability`, `authoring_toolset`, `world_stage` and `authored_world` now take, defaulting to
  `FULL`. The bar text moved out of `scenario_world.md` into `scenario_bar.md` /
  `scenario_opening.md`. `write_scenario` grew an optional source argument.
- **Live probe passed first try (working rule 2), 2026-08-17.** `ExpansionPatch` is ~5.5 KB of
  JSON schema — 2.5x the DirectorBeat envelope — and gpt-oss-120b answered it cleanly under
  `NativeOutput` at 8192 tokens / medium reasoning. A premise-start scenario, one turn of "I follow
  the road north": the Director called `expand_world`, the Expander returned one location and its
  undirected `connected` relation, and the Director's own `reveal` + `move` walked the player in.
  **The standing "keep the schema tiny" rule was over-fitted to the old 15-17 KB failure** —
  reusing the real `Entity`/`Relation`/`Thread`/`Hook` models is fine, so a later role should probe
  at the size its domain wants rather than hand-shrinking a parallel wire shape first.
- Observed in that probe, not fixed: the Expander wrote `detail.description` in second person
  ("A faint glint catches your eye"). Cosmetic — `detail` reaches the Director and Worldkeeper, not
  the Narrator — but `expander.md` says "you write records, never prose the player reads" and the
  model still drifted. Worth a sharper line there if it recurs.

### Phase 3 — Sources: PDF ingestion, grounded expansion, fused authoring

Done-when met: the shipped fixture document ingests to records, `create_scenario.py <slug> <file>`
authors from a document alone, and a `grounded` game plays turns whose expansions are written from
that document. No persisted-byte change: `SAVE_VERSION` unmoved, no fixture moved.

- **One ingestion system, two consumers, and neither of them holds a tool.** `content/sources.py`
  holds `SourceRecord`, `RecordSource`, and `ingest(path)`. The author is given the whole document
  in its prompt; the Expander is given the passages a resolver-side `source.search(...)` retrieved
  for the need the Director named. A `search_source` tool served both at first and was deleted from
  both — see the entry below on what it cost.
- **A scenario ships its source document, not the records ingested from it.** `sources.json` was
  written beside `world.json` for one round and removed: once `source_ids` was gone, nothing
  outside a single turn referenced a record id, so freezing the ingested form bought no stability
  and cost a second artifact plus an unreadable diff. `scenarios/<slug>/source.{md,txt,pdf}` is the
  original; `open_source` ingests it for `grounded`, reads it whole for `generative`, and refuses a
  `grounded` scenario that ships none. The policy's only reader is still `open_source`.
- **Extraction is `pypdf` in its default mode, and that was settled by probing real books, not by
  reasoning.** Layout mode was chosen first, because it is the only mode that preserves the blank
  lines between paragraphs. A probe against Mörk Borg's free adventure (a two-column dungeon key in
  a letter-spaced display face) showed what that costs: layout mode reads a page as one grid, so it
  weaves side-by-side columns together *word by word* and turns tracked type into
  `"Ga s se s lea k f rom hole s"`. The default mode gives clean words and keeps columns in
  readable order — its only loss is paragraph blank lines, and `_capped` already handles that.
  **The rule this leaves: judge an extractor on a real book, never on a fixture you built.**
- **A word broken across a line keeps its hyphen** (`_LINE_BREAK_HYPHEN`). Normalising whitespace
  turned `slaughter-\nhouse` into `slaughter- house`, which matched neither "slaughterhouse" nor
  "house" — 12 terms unsearchable across the two probe documents, now none. Rejoining on the hyphen
  rather than closing it up is deliberate: nothing here can tell a wrapped word from a real
  compound, and `pink-violet` must survive.
- Records are blank-line blocks, capped at `RECORD_CHARS` on a **word**
  boundary, and blocks under `MIN_RECORD` (page numbers, running headers) are dropped, which leaves
  deliberate gaps in the `p<page>-<n>` ids. The cap was written on line boundaries first and that
  was a bug: an unwrapped Markdown paragraph is one line, so it passed through whole, and
  `context()` — which stops before the first record that overflows `CONTEXT_BUDGET` — then returned
  the empty string, silently emptying every prompt's THE SOURCE section.
- **Search ranks by how many distinct query words a record holds**, ties in document order. It
  counted *occurrences* first, and two pages of real prose showed why that fails: `"the"` appears
  thirteen times in a long passage, so one paragraph won three unrelated queries on stopwords
  alone. Matching stays substring-based on purpose — with no stemmer it is what makes "chapel"
  find "chapels". A vector index is still a separate decision; nothing has needed one.
- **`SourceRecord` is `id` and `text`, and PLAN's other two fields were both cut.** `page` went
  because the id is already `p<page>-<n>` — the same fact twice. `visibility` was kept for one
  round on the argument that ingestion is the only moment a read-aloud marker can be recognised,
  then cut when the probe disproved that argument: a PDF's boxed read-aloud text is a *visual* box
  carrying no marker, so 0 of 194 probe records could ever be `player`, and what shipped was a
  Markdown-blockquote rule any later read-aloud phase would replace outright. **The rule worth
  keeping: a field is earned by a reader, and "a later phase will want it" counts only when this
  phase can actually produce the value.** Whoever wants read-aloud text must first decide how a PDF
  marks it. The quote marker is still stripped from ingested text; it just classifies nothing.
- **The anchor name is folded into the query, so a miss is rarer than it looks** — any record
  merely naming the anchor becomes THE SOURCE. It stays because a `need` written as an identifier
  retrieves nothing without it. The Expander's own out is what covers the gap: told that passages
  never touching the need should be answered with an empty patch, it returns "nothing was added"
  and the Director replans. Untested live; worth watching in a trace.
- **The leak rule now covers source text**, pinned by a test: a record's distinctive word reaches
  the Expander's prompt and never the Narrator's.
- The fixture PDF is hand-built (a minimal five-object PDF committed under
  `tests/core/fixtures/source/`), so the suite reads PDFs without a writer dependency.
- **Everything below was found by the first live run, not by the suite.** A scenario authored from
  a real document, played for one turn, exposed four defects at once — three of which predate
  Phase 3 and none of which any offline test could have caught.
- **A failed expansion used to leave no trace at all.** `Expansions.record` ran only after
  `expander.run()` returned, so an Expander that exhausted its retries discarded the one artifact
  needed to debug it. It now records `no canon written: <reason>` as the step. This was the
  expensive defect: not for its size, but because it destroyed the evidence for the other three.
- **A hook's own `reveal` re-enters matching, so authored hooks can form a domino line.** One
  Director `reveal` fired three hooks in sequence and advanced a thread three stages, ending the
  adventure on turn one and stopped only by `MAX_HOOK_ROUNDS`. Chaining is deliberate
  (`apply.py:284`) and the shipped `whispering-vault` chains one hop — which is also why the
  authored scenario chained, since that file is the `worked_example` it is told to match. So the
  rule is chain *length*, not chain existence: `check_hooks` now refuses a hook that is both fired
  by a hook and fires another. It lives there rather than in the authoring bar because
  `playability` reaches it through `Playtest.check` for both briefs with no duplication, and it
  catches hand-authored worlds the bar never sees.
- **`Relation.directed` defaults to `True`, and `connected` must be undirected.** An Expander patch
  that merely omitted the field was refused by `check_draft` — and that is the patch shape its
  prompt asks for. `_added_relation` now resolves `directed` from the kind, exactly as
  `_relation_change` always has for Director-written ties.
- **The Expander's `search_source` tool and `source_ids` field are deleted; resolver code searches
  the source instead.** The shipped grounded run failed every attempt: the model never called the
  tool (it answered from the `context()` head already in its prompt), so `RecordSource.cite`'s
  empty-`source_ids` refusal fired first, and the retry that followed asked only about provenance —
  gpt-oss-120b answered `{"source_ids": ["search_source", "p1-5"]}` with the patch emptied, echoing
  a token out of the field description, until the three retries were spent. Not a
  `NativeOutput`-versus-tools problem: the Director calls `expand_world` under
  `NativeOutput(DirectorBeat)` on the same model in the same trace. **The rule: never spend a
  role's retry budget on a field the resolver already knows the answer to.** `cite` never verified
  grounding either — it checked that an id string existed, which any id in the prompt satisfies.
- **The authoring agent lost its `search_source` tool too, and is handed the whole document.** It
  had never been observed calling it either: the world it authored held exactly the four records of
  the `context()` head and nothing past `p1-5`, so a two-page source produced a bare-minimum world.
  Full text is ~3.3k tokens for a two-page document and ~19k for a 76-page book, re-sent across up
  to `REQUEST_LIMIT` requests — affordable for what is authored today, and the ceiling is loud
  (a context-length failure) where the tool's was silent (a world written from the first 1.7 KB).
  **When a book-scale document breaks it, the answer is the Expander's shape — resolver-side
  retrieval and a size guard — not the tool back.**
- **The authoring agent must be told to use the source, not merely given access to it.** Its first
  grounded world held exactly the four records of the `context()` head and nothing past `p1-5`:
  `scenario_world.md` never mentioned the tool at all. Naming a tool only in a schema description
  or a prompt heading is not an instruction.
- **The retrieval-miss fallback was a fourth silent degradation, the same shape as the three
  above.** `expand_world` read `source.search(...) or source.context()`, which is right for a
  premise — its `search` returns nothing and the whole premise *is* the source — and wrong for a
  document: a miss handed the Expander the document's first four records, bearing on nothing that
  was asked, under the heading `THE SOURCE`. The model then invented canon and the trace showed a
  grounded expansion grounded in nothing. **The rule these four share: a degradation that reads as
  success in the trace is worse than a refusal, and a fallback chosen by the *caller* cannot know
  which source it is falling back for.**
- **`passages(need)` replaced `context()` and `search()` on `CanonSource`, so a source answers for
  itself and `""` carries the meaning.** `PremiseSource.passages` is its whole text always;
  `RecordSource.passages` is `render(search(...))`, empty on a miss. `search` stays a public method
  because its ranking is tested directly, but is off the protocol; `context()` and
  `CONTEXT_BUDGET` are deleted with their only caller, which also retired the "document order is
  orientation" ceiling the earlier design carried. An empty answer is now a `ModelRetry` to the Director in the
  same class as the bad-anchor and cap refusals — the Expander is never called, and nothing is
  recorded in `Expansions`, because there was nothing to write from.
- **`extended` is the fourth `ExpansionPolicy`: the document where it speaks, the premise where it
  is silent.** It is a composite source (`ExtendedSource` holding a `RecordSource` and a
  `PremiseSource`) rather than a branch in `expand_world`, because both behaviours already existed
  and a composite is the only thing that knows *why* it is returning the premise — so it prefixes
  `SILENT`, telling the Expander plainly that the text is silent and to write canon consistent with
  the adventure. Its premise half is `scenario.meta.premise`, never the document: a fallback earns
  its keep by being short and general. Strict `grounded` still refuses on a miss, deliberately —
  it is the loud counterpart to `extended`'s quiet one. The scenario creator still authors
  `grounded`; the new policy is reached by editing one field in `world.json`.

### Phase 4 — Media: scene illustrations

Done-when met: with `MEDIA__ENABLED=true` a turn grows an illustration seconds after the narration,
and with it off (the default) nothing in state, saves, prompts, or tests differs. No persisted-byte
change: `SAVE_VERSION` unmoved, no fixture moved.

- **An image is of a scene, not of a turn.** PLAN said `turn-<n>.png` every turn; what shipped is
  content-addressed — `saves/<slug>.media/<sha1(location|sorted revealed ids)[:12]>.<ext>`. A turn
  that changes nothing visible reuses the file, and walking back into a room redisplays the picture
  it already paid for. That also means an unrevealed arrival never burns a generation, which the
  key test pins.
- **Icons split by origin, because authored canon outlives one save.** An entity id in the
  scenario's `world.json` writes to `scenarios/<slug>/icons/<id>.<ext>` — shared by every save and
  character, committable, and pre-bakeable by dropping files there; anything the Worldkeeper or
  Expander invented writes under the save's media dir. `restart()` clears only the save side
  (`FileStore.discard` now rmtree's `<slug>.media`), so a scenario's cast is paid for once.
  `whispering-vault`'s five non-location entities ship pre-baked (~700 KB each, 3.4 MB — big enough
  that a downscale step will be wanted before many scenarios ship art).
- **Naming the attachments is what makes an icon a likeness.** The first live run passed the icons
  as bare reference images and the scene redrew Mara as a different person (and a different
  gender). Adding "the attached images are reference likenesses of, in order: <names>" made the
  scene reproduce the icon's face and clothes exactly. An icon prompt also has to refuse scenery
  outright — "one centred subject on a plain flat background" still produced a full desk scene
  until it said "no scenery, no other figures".
- **The image call is raw `httpx`, not a `Stage`.** pydantic-ai's `OpenAIChatModel` never surfaces
  OpenRouter's `message.images`, so a role would have bought nothing. One POST with
  `modalities: ["image", "text"]`, validated by a strict four-model reply shape.
- **Aspect ratio is a request field, and it had to be probed to be believed.** OpenRouter passes
  `image_config: {"aspect_ratio": ...}` through to Gemini image models: `1:1` returns
  1024×1024, `3:4` returns 896×1200, and the default (1408×768) merely *looked* like 16:9. So
  `MediaConfig.scene_ratio`/`icon_ratio` ship as "16:9"/"1:1", and the prompts name the form
  outright — "draw one wide establishing view … not a portrait" against "draw a portrait token,
  not a scene" — because the earlier wording produced a full desk scene for an icon. **Deleting
  a file is the regeneration mechanism**: cached-forever means `rm scenarios/<slug>/icons/*` and
  replay, which is how the vault's five were reshot square.
- **The reply names its own format.** `google/gemini-3.1-flash-lite-image` returns
  `data:image/jpeg`, not png, so files are written with the suffix the media type gives and looked
  up by stem across the three supported suffixes. Assuming `.png` would have written jpegs under a
  png name.
- Live probe (working rule 2), 2026-08-18: the model exists, answers in one call, and costs
  ~$0.034 per image — which is what makes the caching decision structural rather than tidy. An
  icon plus a scene is two calls, and only the first visit to a scene pays.
- Two guards an adversarial review found missing, both cheap and both about honesty rather than
  crashes: a scene already generating is not generated twice (the file check alone let a second
  turn in an unchanged room pay for the same image, and the first finisher cleared the shared
  key so the placeholder vanished early), and `MEDIA__ENABLED=true` with no api key is refused
  at settings validation rather than 401-ing into a log line every turn.
- No model decides whether to illustrate: `illustration_request` is a pure builder over
  `VisibleScene`, so the leak rule holds for media by construction (the test asserts an unrevealed
  entity's name never reaches the prompt), and a failed generation is one `LOGGER.exception` and no
  file — never a notification, never a failed turn.
- The page shows the current scene's file above the chat when it exists, and a 3 s `ui.timer`
  watches for it to land, because generation starts *after* the turn commits: without the poll the
  player would always see the previous scene's art. While a generation is in flight the slot holds
  a skeleton — `Illustrator.generating` is a live key set, not a guess from the missing file, so a
  scene whose generation *failed* stops showing a placeholder instead of waiting forever.

### Phase 5 — Player-facing UI

Done-when met: `uv run aidm` plays narration-first with the rails built from view models, NPC
dialogue arrives attributed and iconed, trace and state still work under `dev`, and the leak test
pins that no unrevealed name reaches a player panel. `SAVE_VERSION` 70 -> 71; the `save`/`state`/
`turn` families and the two narrator fixtures moved, and nothing else did.

- **`PlayerScene` was not built, because `VisibleScene` already is it.** PLAN described it as a
  wrapper over `VisibleScene` "plus the location's `brief` and exit lock markers" — and both were
  already there (`location.brief`, `Exit.locked`). A type with no field of its own is the
  `Adventure(policy, source)` record again, so what shipped is `views.player_scene(state)`, one
  builder. `JournalView` did earn its place: it is the only thing that drops `Thread.note` (Director
  steering text) and filters memories by whether their owner has been met.
- **The Narrator is now shown ids, and that is not a leak.** `speaker_id` is an `EntityId`, so
  `render_narrator` flips to `ids=True` — a role cannot name an id it was never shown, and every id
  in that prompt belongs to a revealed entity by construction. The old boundary assertion
  (`"[id=" not in prompt`) is replaced by one that every id shown is a met entity's. The rule now
  holds twice: by construction in `VisibleScene`, and by an output validator that `ModelRetry`s a
  `speaker_id` outside `{player} | here`.
- **`Exchange.narration` became a property joining `lines`.** Prompts, the history replay and the
  journal read exactly the string they read before. `Turn.narration` stayed a plain `str`: the trace
  records what was said, and the chat is the only reader that cares who said it.
- **Live probe passed first try (working rule 2), 2026-08-18.** `Narration` is 686 bytes of JSON
  schema and gpt-oss-120b answered it under `NativeOutput` with correct attribution — Mara's reply
  carried her id, the surrounding prose carried null. The Phase 2 lesson holds: probe at the size
  the domain wants.
- **Icons became a directory lookup**, `icon_dirs: Mapping[EntityId, Path]` replacing `authored`
  plus `authored_ids`, with `characters/<slug>/icons/` as the third directory for the player and
  what the character brought. The player's icon is generated *before* the scene-key guard in
  `illustrate`, so it lands on a turn whose room picture is already cached — otherwise the chat
  avatar would never appear in a scene visited twice.
- **The splitter's `h-screen` had always put the input row below the fold**, since the header takes
  4rem the splitter does not subtract. Harmless on a debug surface, wrong on a play surface:
  `calc(100vh - 6rem)`.
- Three bubble looks so who is talking reads at a glance: the player's own (sent), an NPC's (the
  Quasar default), and the DM's (`grey-3`, and one shipped material icon rather than a generated
  file). A speaker with no icon file gets a letter avatar, never a blank.
- The journal export names its speakers (`**Mara:** ...`). `Exchange.narration` alone was right for
  a prompt and wrong for a reader: without the bubbles, a quoted line reads as narration.
- `trace` and `state` became two expansions inside one `dev` tab, so the four tabs are `scene`,
  `journal`, the engine's advancement, and `dev`.
- Verified in the running app against a hand-seeded save (attributed lines, `MEDIA__ENABLED` off):
  attribution, avatars, rails, all four tabs and the markdown export. **A live turn has not been
  played through the new Narrator schema inside the app, and no chat avatar has been exercised
  against a real generated icon file.**
- Out of scope exactly as PLAN said: suggestion chips, mid-game engine switching, the map view, and
  the home-page re-skin.

## Next

- PLAN.md Phase 6: the scenario creator becomes a page, and authoring ends when the user says so.
- No scenario has been authored from a real PDF end to end. The suite proves ingestion on a
  hand-built fixture; only a real book proves the pipeline.

## Standing limitations

Measured, deliberate, and unfixed. Each names what would make it worth fixing.

- **Icons are full-size jpegs (~700 KB) with no downscale**, and nothing pre-bakes a newly authored
  scenario's art but a hand-run script. Worth fixing when more than a couple of scenarios ship art.
- **Carried items are drawn by nothing**: only the player and whoever stands in the scene get an
  icon, so inventory rows fall back to letter avatars.
- **Extraction ceilings, measured on real books**: in `pypdf`'s default mode a PDF page arrives as
  one block, so a record's edges come from `RECORD_CHARS` rather than the author's paragraphs, and
  a page footer glued to its page's last block rides into a record. `MIN_RECORD` only drops a
  footer that stands alone.
- **Whole-document authoring is ~19k tokens for a 76-page book**, re-sent across up to
  `REQUEST_LIMIT` requests. When that bites, the answer is the Expander's shape — resolver-side
  retrieval and a size guard that refuses a too-large document — not the deleted `search_source`
  tool back.
