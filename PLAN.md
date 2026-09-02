# PLAN — after the hub

Five phases, in order: one scene engine written once (two phases), the scene recap with the
campaign refinements, the audit with the docs, then voices. Self-standing: an implementer needs
this file, `CLAUDE.md` and the code. `NEXT-SPECS.md` stays for Track G's own plan later.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step.** Tests must be green. Change a shape and
   update its tests in the same step. One test per new behaviour; no test of prose or wiring.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them once, at the end of a phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. Each phase below names exactly which fixtures may change and
   how. Anything else is a bug.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase (Phase 1 recreates the file):
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs far past its target, stop and say so.** Never pad, never invent a deletion.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** Never leave two versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **Verify a rule against the SRD page before you build on it.** No phase here changes a rule.
   Phase 5 verified its endpoint on 2026-09-02: OpenRouter `POST /api/v1/audio/speech` takes
   `{model, input, voice, response_format}`, `response_format` is `mp3` or `pcm`, and the reply
   is raw audio bytes; Gemini TTS emits 24 kHz 16-bit mono PCM.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`46ee703`) | | 10,341 |
| 1 — one scene world | `Person`, `SceneWorld[C, P]`, the party, the world arms | 9,950 |
| 2 — one worldsmith, one view | the drafts, the bar, the crossing, the panels, once | 9,550 |
| 3 — the recap and the refinements | `NextDraft.recap`, `Job.job`, resume at the end, the save card | 9,625 |
| 4 — the audit and the docs | dead code, layout, `VISION.md` gone | 9,600 |
| 5 — voices | `SpeechConfig`, `app/speech.py`, `ui.audio` | 9,780 |

The caps stand: 2,000 Python lines per engine; fifteen game-master tools counted as tools plus
`change_world` arms, the two party arms not counted. No phase adds a tool or an arm.

---

## Phase 1 — one scene world

The three scene worlds become one generic model in `engines/scenes.py`; the party Loner has
becomes every scene engine's. Each engine keeps its `Person` subclasses, its `State`, its files,
its `player_*` builder, its tools. **One implementer, opus**: the base changes shape, so the
three engines move in the same step as the base.

### 1.1 `engines/core.py`

Add, in the layout order (constants, classes, functions):

```python
PLAYER_DEAD = "the player is dead; they take no further part."      # was _PLAYER_DEAD, twice
CHANGE_WORLD = "Apply one settled world change ..."                  # verbatim; was in four tools.py


class Person(Mutable):
    """Every cast entry and every player sheet."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    alive: bool = True

    def rows(self) -> Rows:            # the sheet, as the master's entity line prints it
        return ()

    def unwritten(self) -> str:        # what the worldsmith may not write; "" when nothing
        return "" if self.alive else "alive"


class JoinParty(Frozen): ...           # Loner's, verbatim, docstrings included
class LeaveParty(Frozen): ...


def sentence(text: str) -> str: ...    # was _sentence, three times

def join_party(party: list[EntityId], one: Person) -> Fact:
    # refuse when already in; append; entity_fact(one, "party_joined", f"{one.name}[{one.id}] travels with the player", card=f"{one.name} joins your party")

def leave_party(party: list[EntityId], one: Person) -> Fact:
    # refuse when not in; remove; entity_fact(one, "party_left", "... no longer travels with the player", card=f"{one.name} leaves your party")

def check_party(party: Sequence[EntityId], cast: Mapping[EntityId, Person]) -> None:
    # require_unique("party", party); each in cast; each alive ("{id!r} is dead and cannot travel with the player")

def party_rows(members: Sequence[Person]) -> Rows:
    # () when empty; else (("THE PARTY (led by the player)", "\n".join(f"- {m.name}[{m.id}]")),)

def party_panel(members: Sequence[Person]) -> tuple[Panel, ...]:
    # () when empty; else one Panel(title="Party", rows=PanelRow(label=name, detail=brief, icon_id=id) each)
```

`Person` lives here, not in `scenes.py`, so the party functions take it instead of a second
protocol. Inline `Counter.clamped` into `adjust` (its one user). Delete `TAIL_EXCHANGES` and
`told_tail` only in Phase 3.

### 1.2 `engines/scenes.py`: the world

Replace today's `SceneWorld` with the generic family. `SceneRun`, `Scene`, `NextScene`,
`settle`, `record_exchange`, `check_hub`, `check_named`, `scene_rows`, `trail_panel`,
`scene_history`, `last_seen` and the id helpers stay as they are.

```python
class SceneCanon[C: Person](Mutable):
    """A scenario as authored: its opening scene and cast, with no player in it yet."""
    cast: dict[EntityId, C] = Field(default_factory=dict)
    opening: Scene
    present: list[CheckedEntityId] = Field(default_factory=list)
    hidden: list[CheckedEntityId] = Field(default_factory=list)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    # validator: check_filing(cast); check_named(present, hidden, cast); check_hub(hub, board, (SceneRun(scene=opening),))


class SceneScenario[C: Person](Mutable):
    world: SceneCanon[C]


class SceneWorld[C: Person, P: Person](Mutable):
    cast: dict[EntityId, C] = Field(default_factory=dict)
    player: P                                  # known, never in the cast, never listed in a run
    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    party: list[EntityId] = Field(default_factory=list)   # in the cast, alive, unique, present in every scene

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        check_hub(self.hub, self.board, self.runs)
        check_filing(self.cast)
        check_named(self.run.present, self.run.hidden, self.cast)
        if not self.player.known: raise ValueError("the player is unknown to themselves")
        if self.player.id in self.cast: raise ValueError("the player is in the cast")
        if self.player.id in (*self.run.present, *self.run.hidden):
            raise ValueError("the player is in every scene and is never listed in it")
        check_party(self.party, self.cast)
        if left := sorted(set(self.party) - set(self.run.present)):
            raise ValueError(f"the party is in every scene; {left} are not in this one")
        return self

    # run, current, at_hub, job_done, job, stops, job_runs, jobs, exchanges, last_seen: as today
    def members(self) -> list[C]: return [self.cast[one] for one in self.party]
    def require(self, entity_id) -> C | P          # player when it is their id, else the cast, else "unknown id ..."
    def require_here(self, entity_id) -> C | P     # 24XX's body, `self.player.id` for PLAYER_ID
    def require_alive_here(self, entity_id) -> C | P
    def here(self) -> Iterator[C | P]              # the player, then present in order
    def label(self, entity: Person) -> str         # labeled(entity, self.player.id)
    def reveal(self, entity: Person) -> list[Fact] # reveal(entity, self.player.id)


class SceneState[C: Person, P: Person](Mutable):
    world: SceneWorld[C, P]
```

Nothing in `scenes.py` spells `PLAYER_ID` except `new_game`. The world arms, one model and one
function each, with the tools' docstrings and field descriptions verbatim so `master_tools.json`
does not move:

```python
class Reveal(Frozen): ...    # verb: Literal["reveal"], entity_id
class Enter(Frozen): ...
class Leave(Frozen): ...
class Kill(Frozen): ...

def reveal_hidden(world: SceneWorld[Any, Any], entity_id: EntityId) -> list[Fact]
    # today's Reveal arm + `_reveal` (card sentence(f"{name} discovered"))
def enter(world, entity_id) -> list[Fact]       # refuses the player, someone here, someone hidden here
def leave(world, entity_id) -> list[Fact]       # refuses the player; refuses a party member:
                                                # f"{one.name} travels with the player and leaves through `leave_party`"
def kill(world, entity_id) -> list[Fact]        # require_here; refuse the dead; reveal; drop from party; alive=False;
                                                # card "You are dead" for the player, else f"{one.name} is dead"
```

The seam functions, generic on the state because `Game[P]` is invariant:

```python
def new_game[C: Person, P: Person](canon: SceneCanon[C], player: P) -> SceneWorld[C, P]:
    """deepcopy the canon; refuse PLAYER_ID in its cast; build the world with runs=[SceneRun(opening, present, hidden)]."""
    # returns an unparametrized instance; the state's field validates it into SceneWorld[C, P]

def check_game[S: SceneState[Any, Any]](packs: Mapping[str, BaseModel], state: Game[S], title: str) -> None
    # "a {title} game needs at least one table set"; missing packs; check_kind
def known[S: SceneState[Any, Any]](state: Game[S], entity_id: EntityId) -> bool | None
def record[S: ...](state: Game[S], prompt, lines, facts) -> tuple[str, ...]
def history[S: ...](state: Game[S]) -> tuple[Exchange, ...]
def way_open[S: ...](state: Game[S]) -> bool
def player_over[S: ...](state: Game[S]) -> str | None
```

`Any` here is a generic bound only. Add to `CLAUDE.md`'s "Do not use `Any`" line: ", except as
the bound of a generic seam function".

### 1.3 The three engines

`world.py` keeps the constants, the `Person` subclasses, the payload models, the files and the
`player_*` builder; everything else comes from `scenes.py`:

```python
# twentyfourxx/world.py
class Operator(Person):                         # Npc is gone: the cast type is Person
    specialty: str; origin: str; traits; skills; credits; items; hindrances
    def die(...); def rows(...)                 # as today
TwentyfourxxWorld = SceneWorld[Person, Operator]
TwentyfourxxState = SceneState[Person, Operator]
class TwentyfourxxGame(Game[TwentyfourxxState]): ...
class TwentyfourxxScenarioFile(Scenario[SceneScenario[Person]]): ...
class TwentyfourxxCharacterFile(Character[TwentyfourxxCharacter]): ...
def player_operator(character) -> Operator      # as today, known=True

# breathless/world.py: Survivor(Person), BreathlessWorld = SceneWorld[Person, Survivor], same pattern

# loner3e/world.py
class LonerCharacter(Person):
    concept, skills, frailties, gear, conditions, goal, motive, nemesis, luck
    def rows(...)
    def unwritten(self) -> str:
        missing = [why for why, held in (("alive", self.alive), ("full luck", self.luck.current == LUCK_MAX)) if not held]
        return ", ".join(missing)
LonerWorld = SceneWorld[LonerCharacter, LonerCharacter]
class Loner3eState(SceneState[LonerCharacter, LonerCharacter]):
    twist: Counter = ...                        # as today
```

Loner's player leaves the cast and lives at `world.player`; `companions` becomes `party`;
`player_id` goes; `new_game` no longer lists the player in `present`. Loner saves go stale.

`engine.py`: `new_game` keeps its two isinstance checks, then
`Loner3eState(world=new_game(scenario.payload.world, player_character(character)))`. `build()`
wires `validate=partial(check_game, packs, title="Loner 3E")`, `known=known`, `record=record`,
`history=history`, `over=player_over`, `ready=way_open`, all from `scenes.py`.

`tools.py`: `apply_change`'s `Reveal`/`Enter`/`Leave`/`Kill` cases call `reveal_hidden`,
`enter`, `leave`, `kill`; delete the private copies, `_sentence` (import `sentence`),
`_PLAYER_DEAD`, `CHANGE_WORLD`. Loner's `JoinParty`/`LeaveParty` cases become
`[*world.reveal(one), join_party(world.party, one)]` after `require_alive_here`, and
`[leave_party(world.party, world.require(id))]`; delete `_join_party`, `_leave_party`.
Every `world.player_id` reads `world.player.id`; `conflict_prompt`, `_refill`, `_strike` too.
Only Loner registers the party arms in this phase.

`worldsmith.py` and `views.py` are folded in Phase 2; touch them only where the shape forces
it: `Npc` → `Person` in the drafts and `apply_scene`, `world.companions` → `world.party`,
`world.player_id` → `world.player.id`, `SceneCanon` → `SceneCanon[...]`.

Test support follows the shape: `core_test_support.with_entity`, `loner3e_test_support.hub_world`
(the player at `player=`, not in `cast`, `party=[]`), every test reading `companions`,
`player_id` or `cast[PLAYER_ID]`.

### 1.4 Docs

`docs/LONER-3E.md` deviation 5 says `party` where it says companions. `CLAUDE.md`: the `Any`
line (1.2). Recreate `PROGRESS.md` with this phase's entry.

### Done when

Green. Goldens: `state/` and `save/` for 24XX and Breathless gain `"party": []` on the world;
Loner's carry `"player": {...}` beside the cast, the player out of `cast` and `present`,
`"party": []` in place of `"companions"`, no `"player_id"`; `master.txt`, `master_tools.json`,
`narrator.txt` and `picture.txt` unchanged for all four engines. A Loner turn joins Mara to
the party, and the next scene's `present` holds her without the worldsmith naming her; `leave`
on her is refused; `kill` drops her. `src` about 9,950; each `world.py` under 110 lines.

---

## Phase 2 — one worldsmith, one view

The three `worldsmith.py` and `views.py` are one design. Move it into `scenes.py`; each engine
keeps a wiring file. **Split**: A (opus: `scenes.py` and 24XX) then B and C in parallel
(sonnet: Breathless; Loner). After A, Breathless and Loner still run their own code, so the
check stays green between parts.

### 2.1 `engines/scenes.py`: the drafts and the bar

```python
class SceneDraft[C: Person](Frozen):
    """What the worldsmith returns. Ids arrive as free text so a wrong one can be matched against
    a cast name before it is refused; code owns the scene id and never asks for the player."""
    place: Slug; title: str
    question: str = Field(min_length=10)
    situation: str = Field(min_length=MIN_SITUATION)
    present: tuple[str, ...] = (); hidden: tuple[str, ...] = (); secret: str = ""
    cast: dict[EntityId, C] = Field(default_factory=dict)

class JobDraft[C: Person](SceneDraft[C]):     job: str = Field(min_length=MIN_JOB)
class HubDraft[C: Person](SceneDraft[C]):     offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)
class ReturnDraft[C: Person](HubDraft[C]):    debrief: str = Field(min_length=1)

def opening_draft[C: Person](cast_type: type[C], kind: ScenarioKind) -> type[SceneDraft[C]]:
    return HubDraft[cast_type] if kind == "campaign" else SceneDraft[cast_type]

def scene_unmet(draft: SceneDraft[Any], world: SceneWorld[Any, Any] | None) -> list[str]
    # held = {} or world.cast; everyone = draft.cast alone, or {player.id: player, **held, **draft.cast}
    # followers = () or (player.id, *party): any of them resolved in present/hidden is unmet:
    #   f"a scene that does not list the player or the party; they are put there by code: {named}"
    # cast_unmet(others, ...) with others = present + hidden; then per cast entry with unwritten():
    #   f"cast members as the worldsmith may write them: {[f'{eid}: {why}', ...]}"; then hub_unmet
def scene_refusal(draft, world=None) -> str | None      # "the scene needs " + "; ".join(unmet)
def opening_canon(draft, source) -> SceneCanon[C]       # today's body
def apply_scene(world: SceneWorld[C, P], draft: SceneDraft[C]) -> None
    # refuse: a cast entry under the player's id ("the scene rewrites the player"), an existing id, misfiled;
    # resolve present/hidden against {player.id: player, **cast}; refuse the player or a party member named;
    # overlap; hidden-but-met; then world.cast = merged, mark present known,
    # runs.append(SceneRun(scene=_scene(draft, world.job_done), present=[*world.party, *present], hidden=hidden))
```

`_scene(draft, finished) -> Scene` moves as is. `Any` on the draft and world parameters is the
same generic-bound exception as Phase 1.

### 2.2 `engines/scenes.py`: the crossing

```python
async def write_next[C: Person, P: Person](
    world: SceneWorld[C, P], intent: str, answer: WorldsmithAnswer, *,
    cast_type: type[C], role: str, guidance: str,
) -> BaseModel
    # returning = hub is not None and not at_hub and intent == GO_HOME
    # model = ReturnDraft[cast_type] | JobDraft[cast_type] | SceneDraft[cast_type]; refusal as today

def install_scene[S: SceneState[Any, Any]](state: Game[S], written: BaseModel, *, finished_note: str) -> tuple[Fact, ...]
    # apply_scene(world, written.model_copy(deep=True)); trace "the story moves to {title}" +
    # (f", and {names} travel there with the player" when world.members()); card "Home: " | "New scene: ";
    # on ReturnDraft: world.board = offers; job = world.jobs()[-1]; if finished and finished_note:
    # state.notes += (finished_note.format(title=job.title),); return (job_closed(job), opened)

def render_worldsmith(world, intent, guidance, answer, *, role) -> str
    # cast = entity_line(player, detail=last_seen) then each cast member; scene_history(world.job_runs()); hub_rows
def render_opening[C: Person](cast_type, role, source, guidance, kind, hub_phrase) -> str
def build_scenario[C: Person](
    file_type: type[Scenario[SceneScenario[C]]], engine_id: EngineId,
    title, premise, art_style, packs, written: BaseModel, source, kind,
) -> AnyScenario
    # isinstance(written, SceneDraft) else f"{engine_id} received an incompatible scene"; scene_refusal;
    # file_type(meta=ScenarioMeta(title, premise or written.situation, kind), engine=engine_id, packs, art_style,
    #           payload=SceneScenario(world=opening_canon(written, source)))
```

Pydantic validates an unparametrized `SceneScenario(...)` into the file's parametrized field;
no type argument is needed.

### 2.3 `engines/scenes.py`: the views

```python
def subject_of(one: Person) -> Subject
def entity_line(one: Person, *, detail: str = "") -> str
    # "- {name}[{id}] — {brief}" + " (dead)"; "  {sheet}" from rows(); "  {detail}"
def here_lines(world) -> str          # entity_line of here() minus the player, or "- (none)"
def hidden_lines(world) -> str        # entity_line of require(one) for run.hidden
def narrator_view[S](state: Game[S]) -> NarratorView            # today's body
def player_view[S](state: Game[S], extra: tuple[Panel, ...] = ()) -> PlayerView
    # panels: Character (player.rows()), *extra, This scene, *board_panel, *party_panel(members()),
    # Here (the player "(you)" row, then known present who are not the player), trail_panel(job_runs()), *jobs_panel
```

Loner's "Travelling with" row and "travels with the player" line go: the `Party` panel and the
`THE PARTY` section replace them.

### 2.4 Each engine

`worldsmith.py` shrinks to: `WORLDSMITH`, `HUB_PHRASE`, its note (`JOB_DONE_NOTE`,
`GROWTH_NOTE`, `""` for Breathless), 24XX's `BOARD_GUIDANCE`, and thin wrappers:

```python
async def write_next(packs, state: TwentyfourxxGame, intent, answer) -> BaseModel:
    world = state.payload.world
    told = guidance(packs, state.packs)
    if world.hub is not None:                       # 24XX only: the board's range on every campaign write
        told = "\n\n".join((told, BOARD_GUIDANCE))
    return await scenes.write_next(world, intent, answer, cast_type=Person, role=WORLDSMITH, guidance=told)

def install_scene(state, written):                 # Loner: closed = close_conflicts(state) first, returned first
    return scenes.install_scene(state, written, finished_note=JOB_DONE_NOTE)
```

`build()` wires `Authoring(answer=partial(opening_draft, Person), prompt=partial(render_opening,
Person, WORLDSMITH, ...), build=partial(build_scenario, TwentyfourxxScenarioFile,
EngineId("twentyfourxx")))`; `render_opening`'s guidance is a per-engine function of
`(packs, picks)` since 24XX joins `BOARD_GUIDANCE` for a campaign: keep a four-line
`render_opening(packs, source, picks, kind)` wrapper per engine.

`views.py` shrinks to `master_sections` (its own ten-line tuple, since 24XX's `GEAR` and Loner's
glossary sit in different slots) plus the engine's extra panel and gear lines:

```python
def master_sections(state) -> Rows:
    world = state.payload.world; scene = world.current
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", entity_line(world.player)),
        ("GEAR", ...),                                       # 24XX; Breathless BACKPACK; Loner none
        ("HERE WITH THE PLAYER", here_lines(world)),
        *party_rows(world.members()),
        ("HIDDEN HERE (the player has not found these)", hidden_lines(world)),
        *spelled,                                            # Loner's glossary
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )

def player_view(state): return scenes.player_view(state, (Panel(title="Gear", rows=...),))
```

Delete each engine's `SceneDraft` family, `scene_refusal`, `opening_canon`, `apply_scene`,
`render_worldsmith`, `build_scenario`, `_scene`, `_scene_unmet`, `subject_of`, `entity_line`,
`entity_lines`, `narrator_view`, `_entity_row`.

### 2.5 Dead code, same phase

`ui/settings.py _without_none` (no `Optional` field exists; use `field.annotation` directly);
the `way.to in places` guard in Tunnel Goons `walk` (the validator guarantees it); 24XX
`SRD_PACK`; `core/tools.py`'s `Known` alias re-spelled at `Engine.known` (import `Known`);
`other_than` from Breathless and Loner `creation.py` into `core/creation.py`.

### 2.6 Docs

The three `worldsmith.md`: "the cast does not follow the player from scene to scene" becomes
"the party follows the player from scene to scene; nobody else does". Nothing else changes.

### Done when

Green. Goldens: `narrator.txt` and `picture.txt` unchanged; `master.txt` and
`master_tools.json` unchanged; `state/` and `save/` unchanged from Phase 1. A scene draft that
names a party member is refused by the bar before the write lands. `scenes.py` about 700; each
scene engine about 1,050; `src` about 9,550.

---

## Phase 3 — the recap and the refinements

When the worldsmith writes the next scene it writes one paragraph on the scene left; that
paragraph replaces the scene's exchanges in every later prompt. Four cheap campaign fixes ride
along. **Split**: A (sonnet: 3.1–3.3) and B (sonnet: 3.4–3.6) in parallel; disjoint files.

### 3.1 The recap, `engines/scenes.py`

```python
MIN_RECAP = 60

class NextDraft[C: Person](SceneDraft[C]):
    """A scene written in play, away from a return."""
    recap: str = Field(
        min_length=MIN_RECAP,
        description="One paragraph on the scene the player is leaving: what they did, what it "
        "cost, what they learned, what they missed. Read by the game master and by you, never "
        "by the player, so it may name the secret.",
    )

class JobDraft[C: Person](NextDraft[C]): ...          # a job's first scene recaps the hub visit

class SceneRun(Mutable): ...; recap: str = ""          # written when the player left
```

- `write_next` picks `ReturnDraft`, `JobDraft` or `NextDraft`; `opening_draft` and `HubDraft`
  are unchanged (no recap on an opening or a return).
- `apply_scene`: `if isinstance(draft, NextDraft): world.run.recap = draft.recap` before the
  append.
- `scene_history(runs)`: a run with a recap prints its title line, its question, its job line
  and `what happened: <recap>`; a run without prints its situation and every exchange as
  `> {prompt}\n{narration}` (`(nothing yet)` when none). Move `TAIL_EXCHANGES` and `told_tail`
  from `engines/core.py` into `tunnelgoons/worldsmith.py`, their one user.
- `recap_rows(world) -> Rows`: `()` when no run of `job_runs()` has a recap; else one section,
  `"EARLIER IN THIS JOB"` when `world.hub is not None` else `"EARLIER IN THIS ADVENTURE"`,
  body `- {title}: {recap}` per recapped run. Each engine's `master_sections` splices
  `*recap_rows(world)` right before `*master_tail(...)`.
- The narrator never sees a recap: `NarratorView`, `render_narrator`, `told_passages` untouched.
- Tunnel Goons: nothing.

### 3.2 A retaken job keeps its terms, `engines/hub.py`

`Stop.job: str = ""` and `Job.job: str = ""`. `SceneWorld.stops()` passes `job=run.scene.job`;
Tunnel Goons passes nothing. `closed_jobs` sets `job=stops[job_stop].job`. `ledger` prints,
under a job's line and only when `not job.debrief.finished` and `job.job`, a second line
`  the job: {job.job}`. `TAKE_BRIEF`'s last sentence ends "with its cast and its terms".

### 3.3 `master_sections` and docs

Splice `recap_rows` in the three engines (3.1). No `rules.md` changes. `README.md`'s campaign
paragraph gains one sentence: "The worldsmith writes a recap of each scene the player leaves,
so a long job keeps its start."

### 3.4 A resumed game opens at its end, `ui/game.py`

In `game_page`, after `view.transcript = transcript`:
`ui.timer(0.5, lambda: transcript.scroll_to(percent=1.0), once=True)`.

### 3.5 The save card says where you are, `app/launch.py`, `ui/app.py`

`SaveOption.where: str`. In `load_catalog`, inside the existing `try`, after the header:
`state = engines[game.engine].restored(raw)` (the `ValueError` of a stale save is already
skipped with a warning), then `history = engines[game.engine].history(state)` and
`where = history[-1].where if history else ""`. Do the engine lookup after the
`played_by`/`title` check so an unknown engine is still the warning it is today. `_saved_card`
reads `f"{saved.character_title} · turn {saved.turn}"` plus `f" · {saved.where}"` when set.

### 3.6 `IDEAS.md`

Item 2 (memory) is done: delete it. Item 12's second half (session recap on resume) is 3.4:
delete item 12 (its first half targets a skill that no longer exists).

### Done when

Green. Goldens: `state/` and `save/` gain `"recap": ""` per run for the three scene engines;
everything else unchanged (`recap_rows` is empty on a first scene). A crossing stamps the recap
on the run left; a job's third scene's master picture names the first scene's outcome under
`EARLIER IN THIS JOB`; a reopened job's ledger line carries `the job:`; the home page lists a
save with its last scene title. `src` about 9,625.

---

## Phase 4 — the audit and the docs

No behaviour change. **One implementer, sonnet.**

### 4.1 Cuts and layout

- Delete the `hint` on Tunnel Goons' three ability steps (a step with options never shows it).
- `core/views.py`: `sections()` after the classes. `ui/game.py`: `on_fact` above the private
  functions. `core/model.py`: `CheckAnswer`, `WorldsmithAnswer`, `AnyScenario`, `AnyCharacter`,
  `AnyGame` into the constants block under `ScenarioKind` (`type` aliases are lazy).
  `engines/core.py`: `AnyEngine` likewise. The `WorldChange` unions, `DRIVERS`, `TURN_TOOLS`
  and Tunnel Goons' `Entity` alias must follow their classes: one comment each says so.
- Tunnel Goons `validate` → `check_game`. The local `known` mapping in `scenes.py`'s
  `apply_scene` and `scene_unmet` → `everyone`. `twentyfourxx.creation.guidance`: one comment,
  "kept for `partial` parity with the other engines".
- Trim every docstring past one line where the code says the what.

### 4.2 `CLAUDE.md`

The engine line reads: "An engine is self-contained under `engines/<id>/`, under 2,000 lines,
with at most fifteen game-master tools, counted as tools plus `change_world` arms, the two
shared party arms not counted; twenty in all for an engine whose SRD plays a crew, named in its
`docs/<ENGINE>.md`. The scene engines share the scene lifecycle in `engines/scenes.py`; all
four share the hub in `engines/hub.py`." Design decisions gain two lines: "Non-goals: a shared
world layer, save migration, a built-in turn loop and its state keeper, retrieval over source
documents." and "A turn: the master is spawned with the rules and the action and changes the
world through tools only; a rule may leave a decision the player answers next turn; the
narrator receives revealed canon only; the exchange is recorded and the whole draft is
validated and committed; then the engine's transition may offer the way on."

### 4.3 `VISION.md` is deleted

Move first, then delete: content paths (characters, scenarios, saves) and "play costs the
subscription; illustration is the exception" into `README.md` (one short paragraph under "Start
the app"); Maze Rats (`2c3e8a5`, `62f95c6`) and the Pokémon–Showdown boundary into `IDEAS.md`
as two items. Then delete `VISION.md`, its line in `README.md`'s "Project information", and its
`extend-exclude` entry in `pyproject.toml`. `grep -r VISION` finds nothing.

### 4.4 `README.md`, `IDEAS.md`, `COMPETITOR-RESEARCH.md`

- `README.md` gains one architecture paragraph beside the campaign paragraph: the three roles
  as spawned CLIs returning typed proposals, the engine seam (one dataclass of typed callables,
  the registry the one composition point), imports one way `core <- engines <- turn <- app <-
  ui`.
- `IDEAS.md`: delete 3 and 9 (refused non-goals) and the built-in half of 4; fold 5, 6, 7, 8,
  14 into one line "audit: consistency, dead code, docstrings, one doc shape per engine", marked
  done by this phase; keep 4's eval loop, 11, 13, 16; add moving home with its sketch
  (`SceneWorld.hubs` tuple, `at_hub = place == hubs[-1]`, a `MOVE_HOME` row, `HubDraft`
  reused, a "New home: <title>" card, about 70 lines, no SRD prints it) and the two items from
  4.3.
- `docs/COMPETITOR-RESEARCH.md`: one dated note at the top: the "ours" columns, `ROADMAP.md`,
  "code mode" and `.agents/skills` are stale.

### 4.5 Engine docs, one shape

Every `docs/<ENGINE>.md` in the order `docs/24XX.md` has: official sources, licence and
attribution, pack sources, the tools, deviations, readings the SRD leaves open, what the app
adds, where the rules live. Reorder Breathless, Loner and Tunnel Goons; do not rewrite their
text. Tunnel Goons gains the two missing headings with "None." where it has nothing to say.

### Done when

Green; every golden unchanged. No document holds rules text; `grep -r VISION` finds nothing;
`src` about 9,600.

---

## Phase 5 — voices

Narration and dialogue read aloud, generated after the turn commits, cached beside the art,
played under the newest exchange. Off by default. The narrator's voice is the scenario's, as its
art style is. **Split**: A (sonnet: 5.1–5.3, config and the reader) then B (sonnet: 5.4–5.5,
the service and the page).

### 5.1 `config.py`

```python
ProviderName = Literal["openrouter", "local", "kokoro"]

class SpeechConfig(BaseModel):
    """Speech is optional presentation, so failures only log and the default is off."""
    model_config = ConfigDict(frozen=True)
    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-tts-preview"
    voice: str = "Kore"                                   # the narrator's, when the scenario names none
    voices: tuple[str, ...] = ("Kore", "Puck", "Charon", "Zephyr", "Fenrir")   # the pool dialogue draws from
    sample_rate: int = Field(default=24_000, gt=0)
    timeout: float = Field(default=60.0, gt=0.0)

class Providers(BaseModel):
    ...
    kokoro: ProviderConfig = ProviderConfig(base_url="http://localhost:8880/v1", api_key=SecretStr("none"))
    # for_name gains the arm

class Settings(BaseSettings):
    ...
    speech: SpeechConfig = SpeechConfig()
    # _keys_present also refuses speech.enabled with a provider that has no api_key
```

`local` is Ollama's port and serves no speech, hence `kokoro`. The settings page renders all of
it unchanged.

### 5.2 The scenario's voice

`Scenario.voice: str = ""` in `core/model.py` beside `art_style`. `Authoring.build` and
`Runtime.new_scenario` take `voice: str` beside `art_style`; `scenes.build_scenario` and
Tunnel Goons' `build_scenario` pass it through. `ui/create.py`: an input "Narrator voice"
with placeholder "Leave empty for the default voice" under the art style input, passed as
`voice=`.

### 5.3 `app/media.py` shares, `app/speech.py` reads

In `media.py`, make module functions of what both files use: `existing(directory, stem,
suffixes)`, `write_bytes(path, data)`, `claim(generating: set[str], key) -> bool` (synchronous,
as today's comment says), and `post_bearer(provider, path, body, timeout) -> bytes` (the bearer
POST with `raise_for_status`, returning `reply.content`; `_generate` parses the JSON from it).

`app/speech.py`, about 100 lines:

```python
SPEECH_DIR = "speech"

@dataclass(frozen=True, slots=True)
class Reader:
    """Spoken exchanges, cached on disk and never regenerated once written."""
    config: SpeechConfig
    provider: ProviderConfig
    saves: Path                       # store.media_dir(slug) / SPEECH_DIR
    voice: str                        # the narrator's
    generating: set[str] = field(default_factory=set)

    def clip(self, exchange: Exchange) -> Path | None          # existing wav for clip_key(...)
    def pending(self, exchange: Exchange) -> bool
    async def read(self, exchange: Exchange) -> None
        # key; skip when cached or not claimed; one POST per line; on any failure LOGGER.exception once and return;
        # join the pcm chunks; write a wav at saves / f"{key}.wav" through `wave`: 1 channel, 2 bytes, config.sample_rate

def open_reader(settings: Settings, store: FileStore, slug: str, scenario: AnyScenario) -> Reader | None
    # None unless settings.speech.enabled; voice = scenario.voice or settings.speech.voice

def voice_of(speaker: Speaker | None, narrator: str, pool: Sequence[str]) -> str
    # narrator when speaker is None; else pool[int(sha1(speaker.id.encode(), usedforsecurity=False).hexdigest(), 16) % len(pool)]
def requests_of(exchange, narrator, pool) -> tuple[tuple[str, str], ...]     # (voice, text) per line
def clip_key(model: str, lines: Sequence[tuple[str, str]]) -> str
    # sha1(model + "\n".join(f"{voice}|{text}"))[:12]
def speech_body(model: str, voice: str, text: str) -> dict[str, str]
    # {"model": model, "input": text, "voice": voice, "response_format": "pcm"}
```

The request body, `voice_of`, `clip_key` and the wav wrap are the tested functions; no test
spawns or posts anything.

### 5.4 `app/runtime.py`

`GameService.voice: Reader | None = None`, set by `_open` through `open_reader`. Add
`speak()`: like `illustrate`, a retained `create_task(self.voice.read(history[-1]))` over
`self.engine.history(self.state)`, no-op when `voice` is None or the history is empty. Call it
right after `self.illustrate(...)` in `play` (both places) and after the narrated crossing's
commit in `_install`. `newest_clip() -> Path | None` and `clip_pending() -> bool` read the last
exchange. Cards, situations and debriefs are not spoken; a resumed game generates nothing for
old exchanges.

### 5.5 `ui/game.py`

In `chat`, after an exchange's lines: when `session.voice is not None` and
`session.voice.clip(exchange)` exists, `ui.audio(path, autoplay=newest, controls=not newest)`
where `newest` is `exchange is history[-1]`. `GameView.shown_clip: tuple[Path | None, bool]`
beside `shown_art`; `poll_art` also compares `(session.newest_clip(), session.clip_pending())`
and refreshes `chat` when it moved; the 3-second timer runs when `media` or `voice` is set.
About 20 lines.

### Done when

Green; every golden unchanged. With `SPEECH__ENABLED=true` and a key, a turn's narration plays
within seconds of the text in the scenario's voice, or the settings' when it names none; the
wav is reused on reload; with the provider down, the turn is unaffected and one warning logs.
`src` about 9,780.
