# NEXT-SPECS — after the hub

Tracks A through F of the 2026-09-02 brainstorm became `PLAN.md` and were cut from this file.
What stays: the maintainer's decisions, Track R (the seam refactor), Track G
(the party, then crews), and what was left in `IDEAS.md` or refused. Track R becomes its own
`PLAN.md` when PLAN.md's six phases have landed; Track G follows it, written when the campaign
has been played through once with the recap. Counts and names below are as written on
2026-09-02; the code after Phase 2 is the reference for the party helpers Track G quotes
(`check_party`, `join_party`, `leave_party`, `Person`); Track R names files as PLAN.md Phase 5
lays them (`engines/seam.py`, `engines/scenes/`).

## Decisions made in the brainstorm (the maintainer's, 2026-09-02)

1. **One scene engine, three payloads.** `engines/scenes.py` may take pydantic type parameters
   on the cast and player types. PLAN.md settled 7 ("no type parameter") retires with PLAN.md.
   Loner's player leaves the cast and lives as `world.player`, as in 24XX and Breathless; Loner
   saves go stale, which the design allows.
2. **Memory is a recap the worldsmith writes on the crossing.** No summarizer role. The
   platform's `recent_exchanges` stays at 20.
3. **Voices are an HTTP provider on the illustration pattern**: off by default, the OpenRouter
   key the player already has, a local server if they run one, and the narrator's voice chosen
   per scenario as its art style is. No in-process model.
4. **The tool cap stays fifteen, counted as tools plus `change_world` arms**, the two party
   arms every engine carries (Track A) not counted. An engine whose SRD plays a crew (Track G)
   may go to twenty in all; its `docs/<ENGINE>.md` says so. No fold is made for the count's
   sake.
5. **Campaign refinements are all built**, except moving home, which stays in `IDEAS.md`.
6. **`VISION.md` is deleted** after its non-goals and turn steps move. `COMPETITOR-RESEARCH.md`
   stays as a reference to other projects. PLAN.md Phase 5.2 (rewrite VISION's architecture)
   is skipped: Track F deletes the file.
7. **Party play (IDEAS 16) is in scope, in two layers.** A minimal party every engine gets:
   an NPC joins and follows the player, is interacted with, and every role reads it as part of
   the party the player leads; the master applies the engine's own help knob. Then engine
   layers on top: 24XX sheets, help dice, the ship and succession; Tunnel Goons goons who roll
   and level. Retires PLAN.md settled 17 (no companions gained) and 19's "no crew list"; closes
   `docs/24XX.md` deviations 1, 2, 4 and the ship half of 5, and `docs/BREATHLESS.md` 5.
8. Ponytail audit: dropped. Eval loop (IDEAS 4): stays in `IDEAS.md`.

Standing rules from `CLAUDE.md` bind every track: engines self-contained under 2,000 lines; one-way
imports; `core`/`turn`/`app`/`ui` know no world shape; only the narrator writes player-facing
text from revealed facts; only resolver code changes state or rolls; a bad answer is re-prompted
once; saves carry no version; no abstraction until two things need it; no building for later.


---

## Track R — the seam, made smaller

Two outside readings of the code on 2026-09-02. The first made four proposals: an engine object
with a `SceneEngine` base in place of the `Engine` callback record; one flat scene draft in
place of the five draft classes; one `advance()` transaction in place of `ready → write →
install → arrival_brief`; and the master as its own worldsmith. The second counted what the
first was reacting to, against the code after Phase 4: 19 callables wired into `Engine`,
`Authoring` and `Transition`; 45 `partial(...)` binding packs, cast types and ids at wiring
time, because there is no `self` to carry them; three scene `worldsmith.py` of 42–50 lines that
only forward a cast type and four strings; `GameService` running `ready → write → install →
arrival_brief` as a second state machine after the turn (`_grow`, `_write`, `_install`, about
55 lines); and in `engines/scenes.py` one object split across two styles, `world.require()`,
`world.here()`, `world.jobs()` methods beside `enter(world, id)`, `kill(world, id)`,
`settle(world, done)`, `apply_scene(world, draft)` free functions on the same object, about
twelve of them, the line between the two drawn nowhere.

This track keeps the first proposal as a class and the third as written, adds the twelve moves,
and refuses the other two with the reason below. It is not a rewrite: the value models, `Fact`,
`apply_to_draft`, `Game.draft/committed`, `NarratorView`, `Turn`, the resolvers as
`(draft, args, rng) -> facts` and the Protocols in `app/spawn.py` are already the right shape
and none of them moves.

No behaviour change, no prompt change, no golden moves: `prompts/`, `schemas/`, `turn/`,
`state/` and `save/` are the track's invariant, and a phase that moves one has a bug. Three
phases, R.1 then R.2 then R.3; about three hours of agent time for R.1, one and a half each for
R.2 and R.3. `src` from Phase 6's 9,735 to about 9,535. Files are named as PLAN.md Phase 5 lays
them: `engines/seam.py`, `engines/scenes/world.py`, `engines/scenes/worldsmith.py`,
`engines/scenes/views.py`; R.1 adds `engines/scenes/engine.py`.

### Decisions (the maintainer's, 2026-09-02, revised after the second reading)

1. **`Engine` is an abstract class, `SceneEngine` its one concrete base, each engine a
   subclass.** This replaces the earlier decision for a `SceneRules` record and a
   `scene_engine` factory. The three scene `build()` are a vtable assembled by hand, and
   `partial` is what a language does when it has no `self`; a class is the shape the seam was
   already imitating. "Write pure functions" stands and reads as it always did: the resolvers
   stay functions of `(draft, args, rng)`, the values stay frozen, the side effects stay in
   `app`; a method that reads `self.packs` and its `state` argument and writes nothing is as
   pure as the function that took both as parameters. The overridable surface is the set of
   things the three engines differ on today, counted in R.1, not a set built for later. The
   platform keeps reading the engine by attribute; a test that rewired with
   `dataclasses.replace` builds its own instance and sets the attribute.
2. **One flat draft is refused** (reason below). The `isinstance` matches on the five drafts
   stay: a `match` on a frozen model is a match on a domain distinction, and the ugly piece,
   `_is_draft`, goes with R.2's typed answer.
3. **R.3 moves the scene functions that take `world` first onto `SceneWorld`.** No new
   abstraction: the object exists, half its verbs are already on it.

### R.1 The object

`Engine` becomes a class whose methods are today's callables, one to one, under today's names;
`Authoring` and `Transition` fold into it as seven methods that R.2 makes four. Every `partial`
in `engines/` goes, because `self` carries what it bound. **One implementer, opus**: the base
changes shape, so all four engines move in the same step.

- **`engines/seam.py`.**
  ```python
  class Engine[G: Game[Any]](ABC):
      """The seam joining an engine's rules to the platform; a subclass answers for one engine."""

      # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
      id: EngineId
      title: str
      art_style: str
      directory: Path                  # rules.md; a scene engine's worldsmith.md and packs/
      game: type[G]
      scenario: type[AnyScenario]
      character: type[AnyCharacter]
      # The narrator's brief for the arrival, `{pursuit}` the player's words; None when the world
      # is extended without a turn, as Tunnel Goons grows its map.
      crossing: str | None = None

      def __init__(self) -> None:
          self.instructions = (self.directory / "rules.md").read_text(encoding=ENCODING)
          self.tools = self.master_tools()
          require_unique(f"tool names of the {self.id!r} engine", (one.name for one in self.tools))

      def pack_options(self) -> tuple[DecisionOption, ...]:
          return ()

      @abstractmethod
      def master_tools(self) -> tuple[MasterTool[G], ...]: ...
      # creation_steps, create_character, preview_character, validate, new_game, over, known,
      # record, history, master_sections, narrator_view, player_view: abstract, today's signatures.
      # opening_draft, opening_prompt, build_scenario, ready, write, install: abstract, the
      # `Authoring` and `Transition` signatures, until R.2.
      # restored, answer: as today.
  ```
  `AnyEngine = Engine[Any]` stays: `Game[P]` is invariant, and the platform holds any engine.
  `Engine.packs` (the option tuple the create page reads) is renamed `pack_options()`, so an
  engine's loaded table sets can be `self.packs` as every module calls them; `ui/create.py`
  changes two lines.
- **`engines/scenes/engine.py`**, the new file.
  ```python
  class Pack(Frozen):
      """What every table set carries; an engine's own `Pack` extends it."""
      name: str

  class SceneEngine[C: Person, P: Person, G: Game[Any], K: Pack](Engine[G]):
      """The scene lifecycle, once; a subclass says what its rules add."""

      cast: type[C]
      pack: type[K]
      hub_phrase: str                  # what CAMPAIGN_OPENING asks this engine's hub to be
      finished_note: str = ""          # the note a finished job leaves for the next turn
      crossing = CROSSING

      def __init__(self, user_packs: Path) -> None:
          self.packs = load_packs((self.directory / "packs", user_packs), self.pack)
          self.role = (self.directory / "worldsmith.md").read_text(encoding=ENCODING)
          super().__init__()           # last: `master_tools` reads the packs

      def world(self, state: G) -> SceneWorld[C, P]:
          return state.payload.world   # the one place `G: Game[Any]` is narrowed to the scene world

      # Abstract, what the three differ on: guidance(picks, *, campaign), new_state(canon,
      # character), master_sections(state).
      # Hooks with a default: panels(state) -> () (24XX Gear, Breathless Backpack);
      # leaving(state) -> () (Loner: close_conflicts, before the install as the wrapper does today).
      # Implemented once: pack_options from K.name; validate = check_game(self.packs, state);
      # known, record, history, over, ready, narrator_view: today's functions; player_view =
      # scenes.player_view(state, self.panels(state)); new_game: the two "received an
      # incompatible ..." checks against self.scenario and self.character with self.title in the
      # message, then self.new_state(scenario.payload.world, character); opening_draft,
      # opening_prompt, build_scenario, write, install: today's three worldsmith.py wrappers,
      # with self.cast, self.role, self.hub_phrase, self.finished_note and
      # self.guidance(..., campaign=...) where the wrappers bound them.
  ```
  `G: Game[Any]` is `Engine`'s own bound and adds no `Any`; a bound may not name another type
  parameter, which is why `G` is not `Game[SceneState[C, P]]` and `world()` narrows in one
  place. `MasterTool[G]` is invariant, which is why the class is generic on the game and not on
  the state. `guidance` takes `campaign` because 24XX joins its board guidance on every campaign
  write and opening, and nothing else differs between the three `write_next`. The three
  `player_*` builders widen their parameter to `Character[<Engine>Character]`, one line each,
  so `new_state` takes the `AnyCharacter` the base has checked. The three engine `Pack`s extend
  this one; their `pack_options` go.
- **Each scene engine.** `engine.py` is the subclass, about 55 lines:
  ```python
  class Loner3eEngine(SceneEngine[LonerCharacter, LonerCharacter, Loner3eGame, Pack]):
      id = EngineId("loner3e")
      title = "LONER 3E"
      art_style = "Painterly illustration, muted colours, no text or lettering."
      directory = Path(__file__).parent
      game = Loner3eGame
      scenario = Loner3eScenarioFile
      character = Loner3eCharacterFile
      cast = LonerCharacter
      pack = Pack
      hub_phrase = "a guild hall or a ship, whoever keeps it and the regulars"
      finished_note = GROWTH_NOTE

      def master_tools(self) -> tuple[MasterTool[Loner3eGame], ...]:
          return tools(self.packs)

      def guidance(self, picks: Sequence[Slug], *, campaign: bool) -> str:
          return guidance(self.packs, picks)

      def new_state(
          self, canon: SceneCanon[LonerCharacter], character: AnyCharacter
      ) -> Loner3eState:
          return Loner3eState(world=new_world(canon, player_character(character)))

      def master_sections(self, state: Loner3eGame) -> Rows:
          return master_sections(self.packs, state)

      def leaving(self, state: Loner3eGame) -> tuple[Fact, ...]:
          return close_conflicts(state)

      # creation_steps, create_character, preview_character: one line each into creation.py
  ```
  `worldsmith.py` is deleted in all three: `WORLDSMITH` is read by the base, `HUB_PHRASE`,
  `GROWTH_NOTE`/`JOB_DONE_NOTE` and `BOARD_GUIDANCE` move into `engine.py`'s constants block.
  `creation.py`, `tools.py`, `world.py` do not change; `views.py` keeps `master_sections` and
  the gear lines and loses `player_view` where it only passed a panel.
- **Tunnel Goons.** `class TunnelGoonsEngine(Engine[TunnelGoonsGame])` in its `engine.py`:
  `new_game` and `check_game` move in as methods, the other fifteen delegate one line each to
  `world.py`, `tools.py`, `views.py`, `worldsmith.py` and `creation.py`, which do not change.
  About today's 100 lines, none of them wiring.
- **`engines/registry.py`.** `build_engines` is `(Loner3eEngine(packs_dir / "loner3e"),
  TunnelGoonsEngine(), ...)`. Nothing else in the registry changes.
- **`app/runtime.py`.** `engine.transition.x` reads `engine.x`; `engine.authoring.x` reads
  `engine.x`; `arrival_brief is None` reads `self.engine.crossing is None` and
  `arrival_brief(turn.prompt)` reads `self.engine.crossing.format(pursuit=turn.prompt)`. No line
  of `_grow`, `_write`, `_install` or `new_scenario` changes otherwise.
- **`CLAUDE.md`.** The code rules gain one line after "Write pure functions": "State models and
  engines own the methods that read or mutate them; a method that writes nothing outside its
  arguments is pure." The `Any` line reads "a class or function generic on the game state".
  The engine line names `SceneEngine` where Phase 5.2 named `engines/scenes/`. `README.md`'s
  architecture paragraph (PLAN 5.4) reads "one abstract class, `SceneEngine` the base of the
  three scene engines, the registry the one composition point" where it read "one dataclass of
  typed callables".
- **Tests.** The four `dataclasses.replace(...)` calls (`test_launcher.py` and
  `test_tool_surface.py` for `id`, `test_decisions.py` and `test_tool_surface.py` for `tools`)
  build a `Loner3eEngine(PACKS)` of their own and set the attribute; the transition test
  subclasses `Loner3eEngine` with `ready` returning True, `crossing = None` and a scripted
  `write`; `test_engine.py` in each engine reads `new_game` off the engine, not the module. A
  test that a fifth `SceneEngine` subclass with a bare `Person` cast, the base `Pack` and no
  tools builds a playable engine is the one new behaviour test: the review's litmus, "a fifth
  scene engine is its state model, its creation, its tools and its sections", is what this
  phase buys. No test of prose or wiring is added.
- **Done when.** Green; every golden unchanged; `grep -rn "partial(" src/aidm/engines` finds
  nothing; no scene `worldsmith.py` exists; the three scene `engine.py` under 60 lines;
  `docs/<ENGINE>.md` name the engine class where they named "the wiring file". About -120
  lines.

### R.2 The transaction

The platform asks the engine two things of the worldsmith and stops knowing their stages.

- **`core/model.py`.** `WorldsmithAnswer` becomes a `Protocol` in the classes block with a
  generic call, `async def __call__[M: BaseModel](self, prompt: str, model: type[M], refusal:
  Callable[[M], str | None]) -> M`; `CheckAnswer` goes. `app/spawn.py`'s `answered` is already
  generic, so the engine's answer is typed end to end: `_is_draft`, its
  `__pydantic_generic_metadata__` read and `install_scene`'s `SceneDraft[Any]` go.
- **`engines/seam.py`.** The seven seam methods become three, beside `crossing`:
  ```python
  @abstractmethod
  async def author(
      self,
      title: str,
      premise: str,
      source: str,
      packs: Sequence[Slug],
      kind: ScenarioKind,
      worldsmith: WorldsmithAnswer,
      playable: Callable[[AnyScenario], str | None],
  ) -> AnyScenario: ...
  @abstractmethod
  def ready(self, state: G) -> bool: ...
  @abstractmethod
  async def advance(
      self, draft: G, intent: str, worldsmith: WorldsmithAnswer
  ) -> tuple[Fact, ...]: ...
  ```
  `advance` writes, then installs on the draft it is given, and raises `ValueError` both when
  nothing usable was written and when the written world no longer fits; the platform never
  holds the written model. `author`'s refusal is the engine's bar on the draft, else the built
  file's `playable(...)`, with the build and the check inside today's `except ValueError ->
  str`, so a file that will not build is re-prompted once as it is today; `title` and `premise`
  are its parameters because each engine's premise fallback is its own (`situation`; Tunnel
  Goons the start's description).
- **`engines/scenes/engine.py`.** `SceneEngine` implements both once and no subclass overrides
  them: `advance` is `write_next` then `self.leaving(draft)` then `install_scene(draft, written,
  finished_note=self.finished_note)`, in that order as the Loner wrapper runs it today; `author`
  is `render_opening`, the draft type from `opening_draft(self.cast, kind)`, the refusal
  composing `scene_refusal` and `playable`, then `build_scenario`. `opening_draft`,
  `opening_prompt`, `build_scenario`, `write` and `install` leave the class.
  `engines/scenes/worldsmith.py`'s `install_scene(state, draft: SceneDraft[C], *,
  finished_note)` stays a typed module function: ten tests install a hand-built draft with no
  worldsmith. Tunnel Goons: `write_extension` + `install_extension` become its `advance`;
  `render_map` + `opening_draft` + `build_scenario` become its `author`; the `MapDraft |
  ReturnDraft` union is typed, no `BaseModel` left.
- **`app/runtime.py`.** `_write` and `_install` fold into `_grow`: `draft = self.state.draft()`;
  `try: facts = await self.engine.advance(draft, intent, self._ask); self.engine.validate(draft)`
  `except (OSError, ValueError)` sets `write_failure`, logs once, returns; then today's tail
  (silent commit, or the narrated crossing through `close_segment`). `_ask` is one method over
  `answered("worldsmith", ...)`. `new_scenario` becomes `written = await engine.author(title,
  premise, source, packs, kind, self._ask, playable)` then `write_scenario(...,
  written.model_copy(update={...}))` with the same `update` dict (art style; Phase 6's voice),
  where `playable` runs `begin_game`. The UI's `transition_available` reads `engine.ready`.
- **Tests.** The transition test's subclass overrides `advance` in place of `write`;
  `test_authoring_build_raises_on_an_unmet_bar` becomes a scripted worldsmith that
  `engine.author` refuses on the bar; the four `test_worldsmith.py` call `engine.advance` and
  `engine.author` where they called the pairs, and `tests/loner3e/test_world.py` and
  `test_hub_play.py` keep calling `install_scene`. No test of prose or wiring is added.
- **Done when.** Green; every golden unchanged; `grep -n BaseModel src/aidm/engines/seam.py`
  hits `new_game`'s return and the import only, and `src/aidm/app/runtime.py` not at all; a
  failed write and an install that no longer fits both leave the state untouched and set
  `write_failure`; the CLAUDE.md `Any` line loses nothing more, since `G: Game[Any]` is the
  class case it names. About -70 lines.

### R.3 The world's verbs

A pure move, so the last phase and the first to cut if R.1 runs past its target.

- **`engines/scenes/world.py`.** The functions whose first parameter is `world: SceneWorld[C,
  P]` become methods of `SceneWorld`: `reveal_hidden`, `enter`, `leave`, `kill`, `settle`,
  `record_exchange`, `apply_scene`, `merged_cast`, `hub_rows`, `recap_rows`, `scene_rows`,
  `here_lines`, `hidden_lines`, `render_worldsmith`. Each loses its `[C: Person, P: Person]`
  header and reads `self` where it read `world`; nothing else in a body changes. `SceneWorld`
  goes from eighteen methods and properties to about thirty-two; `engines/scenes/views.py`
  keeps `entity_line`, `trail_panel`, `narrator_view` and `player_view`, which take a `Person`,
  runs or a state.
- **Callers.** `enter(world, change.entity_id)` reads `world.enter(change.entity_id)` in the
  three `tools.py`; `here_lines(world)` reads `world.here_lines()` in the three `views.py`;
  about thirty-five test call sites the same way. The drafts are left alone (decision 2), and
  Tunnel Goons is left alone: `TunnelWorld` already owns its verbs.
- **Done when.** Green; every golden unchanged; `grep -n "world: SceneWorld"
  src/aidm/engines/scenes/world.py` finds only `new_world`'s return; no
  `def .*\[C: Person, P: Person\]` remains outside the models. About -15 lines.

### Refused, with the reason

- **The master as worldsmith**: the maintainer's call. The worldsmith is useful for authoring,
  and removing it would make the master do too much. Authoring is a second profession;
  scenario creation needs the role anyway; the fifteen-tool cap is the master's attention
  budget.
- **One flat draft with optional `recap`, `job`, `offers`, `debrief`**: the five classes are
  the schema the worldsmith answers in, and pydantic enforces which fields a crossing, a job or
  a return owes; a flat draft moves that demand into prose descriptions and the bar, the schema
  the model reads grows fields it must leave empty, and the seven `isinstance` sites become
  seven `if draft.offers` sites. A return closing a job is a domain distinction, not a leaked
  output shape.
- **A record and a factory for R.2**: decision 1. A record of callables and a class expose the
  same surface; the class carries `packs`, `cast` and `role` on `self` where the record needed
  a `partial` per field, and a fifth engine reads as a table of what it adds.
- **Abstract methods for what one engine does**: `panels` and `leaving` have defaults; a hook
  exists only where a second engine already differs.
- **A generic "role" abstraction over master, narrator and worldsmith**: both readings refused
  it, and so does this track. Nothing in R touches `Turn`, `Fact`, `Game.draft/committed` or
  `NarratorView`.

---

## Track G — the party, then crews (IDEAS 16)

Two layers. **The party** is the platform's minimum and every engine has it after G.1: an NPC
joins the player, follows them everywhere, can be talked to, hurt and lost, and every role reads
them as part of the party the player leads, not as someone who happens to be present; the
master turns a member's help into the engine's own knob. **A crew** is what an engine builds on
top when its SRD prints it: 24XX (sheets, help dice, the ship, succession) and Tunnel Goons
(goons who roll and level). Loner's companions are the party already; Breathless gets the party
and no crew (its "the cast carries no dice" stands until 24XX has played). G is its own
`PLAN.md`; this section is the design the briefs quote.

### G.0 The SRD, read 2026-09-02 at `24xx-srd.carrd.co` (verify again at phase start)

> Roll a skill die — d6 by default, higher with a relevant skill, or d4 if hindered by injury or
> circumstances. If helped by circumstances, roll an extra d6; if helped by an ally, they roll
> their skill die and share the risk. Take the highest die.

> Starships have basic versions of these functions; upgrades cost ₡10 each. In an emergency,
> players pick a function to do or help with. — Comms, Crafts (includes escape pod), Drive (FTL
> jump), Equipment (crew vac suits), Hull armor (breaks for defense), Sensors, Weapons.

> If killed, make a new character to introduce ASAP. Favor inclusion over realism.

> After a job, each character increases a skill (none→d8→d10→d12) and gains d6 credits.

### G.1 The party (all four engines)

- **Platform share, one thing, as the hub had two.** `NarratorView.party: tuple[Subject,
  ...]`, the player first then who travels with them, with a validator `party ⊆ subjects` (who
  the player is, not a world shape); `render_narrator` prints `YOUR PARTY: you are <name>; with
  you: <names or nobody>`. The `Illustrator` takes the player from it. Nothing else in `core`,
  `turn`, `app` or `ui` changes: the panel is a `Panel`, the arms are `change_world` arms.
- **Registration.** 24XX and Breathless register `JoinParty`/`LeaveParty` (15 → 17, 12 → 14,
  the pair not counted per decision 4); Tunnel Goons gets `TunnelWorld.party: list[EntityId]`
  through Track A's `check_party`/`join_party`/`leave_party`, `move` carries the party with
  the player (`with_ids` stays for an NPC who follows once), and registers the pair (9 → 11).
  Loner has them. The player's death ends the game as today until an engine adds succession.
- **What the master reads**, one shared paragraph in each `rules.md`: a party member is the
  player's to command in the fiction and yours to voice; when one plainly helps, that is the
  engine's help — 24XX `helped`, Loner `position`/`edge`, Tunnel Goons a lower `difficulty` or
  a named item, Breathless nothing (the SRD prints no help rule; the fiction carries it); a
  member cannot act on their own dice unless the engine gives them some (G.2, G.3); never
  volunteer a member's action to soften a scene.
- **Docs that go false**: `tunnelgoons/rules.md` "nobody follows on their own" (the party
  does); `docs/BREATHLESS.md` deviation 5 closes; `docs/TUNNEL-GOONS.md`'s "only the player
  has abilities" paragraph under "what the app adds" says the party has none until G.3.

### G.2 24XX crew

- **One cast type, an optional sheet.** `Operator(Person)` gains `sheet: Sheet | None = None`
  where `Sheet(Mutable)` is specialty, origin, traits, skills, credits, items, hindrances (what
  `Operator` carries today); the player's sheet is required by the world's validator; the
  worldsmith may give a regular one (the character file's own payload shape; the SRD's
  specialties are the vocabulary). 24XX is then `SceneWorld[Operator, Operator]`, Loner's shape,
  and Track A's party invariant holds untouched: a sheeted member rolls, an unsheeted one
  follows and helps as G.1. In a campaign, joining a sheeted regular is refused away from the
  hub: hiring is the fixer's business.
- **Rolls.** `Attempt.actor_id: CheckedEntityId` defaulting to the player (any living sheeted
  party member); `Attempt.helped_by: CheckedEntityId | None` names one sheeted member: they
  roll their own die for the named skill (d6 when they lack it) beside the actor's, and the
  highest counts; `helped` (circumstance) stays the extra d6; both may apply. A hindered helper
  is the master's call, as the actor's `hindered` is: `rules.md` says a member who is hurt does
  not help. "Share the risk" is the master's too: the consequence lands on the actor by code
  (`risking_death`, `Maimed`), and the helper takes a hindrance through `change_hindrances`
  when the fiction puts it on them. `Defend`, `ChangeHindrances`, `GainItem`, `DropItem`,
  `RepairItem`, `Spend` gain `actor_id` defaulting to the player: gear and credits are per
  operator, as the SRD keeps them.
- **After a job.** `JobDone.raises: tuple[Raise(actor_id, skill), ...]` covers the player and
  every living sheeted party member, refused when one is missing or a stranger is named; each
  raises the named skill and rolls their own d6 credits. One call per job.
- **The ship is gear.** `world.ship: dict[EntityId, Item] | None` over the seven printed
  functions (an `Item` breaks and is repaired already), plus `world.upgraded: set[str]`; the
  worldsmith answers `ship: bool` on the opening draft and code builds the seven; after Track R
  the factory picks the opening draft type, so `ship` either leaves the draft or `SceneRules`
  gains an opening-draft field, and this phase decides. `Defend` and
  `RepairItem` resolve an id in the actor's items or the ship; one arm `ship_upgrade(function)`
  costs the player ₡10. A `Ship` panel shows when there is one.
- **The android body** (deviation 4): `srd.json`'s android `case` option carries a `Kit`;
  `create_character` adds it to the items, and `defend` then breaks it as the SRD prints.
  About 6 lines; verify the case text at phase start.
- **Succession.** When the player dies with a living sheeted member, the death site sets
  `PendingDecision(kind="succession", prompt="Who leads now?", options=one PendingOption per
  such member with name="change_world", args={"change": {"verb": "take_lead", "actor_id":
  ...}}, allows_text=False)` instead of ending the game; `take_lead` swaps the objects: the
  chosen member becomes `world.player` and the dead one goes into `cast`, both keeping their
  ids, and is refused while the player lives. `player_over` fires only when the player and every
  sheeted member are dead. `NarratorView.party` carries the new "you" with no further change.
- **Counts.** Arms: `join_party`, `leave_party` (G.1), `take_lead`, `ship_upgrade`. 24XX goes
  15 → 19.
- **Views and prompts.** The `Party` panel shows a sheeted member's `rows()`; the master's `THE
  PARTY` prints sheets; `creation.py _AUTHORING` ("the cast carries no dice") and the `attempt`
  description are rewritten; `worldsmith.md` says a sheet is for someone who could plausibly be
  hired, at most one per scene. `docs/24XX.md`: deviations 1, 2, 4 close; 5 splits into "the
  priced gear table is not transcribed" (stays) and the ship (closes).

### G.3 Tunnel Goons crew

`Goon` folds into `Npc` with `sheet: Abilities | None` (brute, skulker, erudite, inventory,
level); the player is an `Npc` whose sheet the validator requires. A sheeted member is a goon:
`ActionRoll.actor_id`, `rest` heals the party, `level_up` opens one decision per living goon in
turn (the option args carry `actor_id`; answering one opens the next), `take_lead` swaps
objects as 24XX. `Dungeon._consistent`'s item-holder check reads the party. 11 → 12.
`docs/TUNNEL-GOONS.md`: the "one goon" paragraph under "what the app adds" is rewritten;
deviation 1 (the level-up cadence) stays.

### G.4 Phases, in order

1. The party: `NarratorView.party`, `render_narrator`, the arms in 24XX, Breathless and Tunnel
   Goons, `TunnelWorld.party` and `move`, the shared `rules.md` paragraph; goldens:
   `narrator.txt` gains the YOUR PARTY line, `master.txt` the paragraph, `master_tools.json`
   the two arms, nothing else.
2. 24XX: `Sheet`, `actor_id` on the tools, `helped_by`, `JobDone.raises`, the android case, the
   panel rows, `rules.md`, `_AUTHORING`, `worldsmith.md`, `docs/24XX.md`.
3. 24XX: the ship and succession; `scenarios/amber-tap` gains a sheeted regular and a ship.
4. Tunnel Goons: G.3.
5. Docs; `IDEAS.md` 16 leaves.

**Done when.** In every engine a named NPC joins, walks into the next scene and is read as the
party by all three roles; a hired regular rolls beside Kael and the highest die counts; Kael dies
on a `risking_death` disaster and the page asks who leads; the new lead plays the return home
and `job_done` raises both survivors; the hull breaks to defend; 24XX at most 1,600 lines after
Track A, nineteen verbs. About +600 lines across `core/views.py`, `turn/context.py`, 24XX and
Tunnel Goons.

**Risks.** Prompt size grows by one entity line per member per role; no cap until a prompt shows
it needs one. The narrator must keep "you" on the player: the golden and one speakers test
guard it. The crew must not soak every risk: `helped_by` is one ally, and the shared paragraph
forbids volunteered member actions.

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
