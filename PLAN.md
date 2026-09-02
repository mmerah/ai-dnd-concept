# PLAN — after the hub

Seven phases, in order: one scene engine written once (two phases), the scene recap with the
campaign refinements, the play issues, the seam as classes, the audit with the docs, then
voices. Self-standing: an implementer needs this file, `CLAUDE.md` and the code.
`NEXT-SPECS.md` stays for Track G's own plan later.

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
   Phase 7 verified its endpoint on 2026-09-02: OpenRouter `POST /api/v1/audio/speech` takes
   `{model, input, voice, response_format}`, `response_format` is `mp3` or `pcm`, and the reply
   is raw audio bytes; Gemini TTS emits 24 kHz 16-bit mono PCM.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`46ee703`) | | 10,341 |
| 1 — one scene world | `Person`, `SceneWorld[C, P]`, the party, the world arms | 9,950 |
| 2 — one worldsmith, one view | the drafts, the bar, the crossing, the panels, once | 9,550 |
| 3 — the recap and the refinements | `NextDraft.recap`, `Job.job`, resume at the end, the save card | 9,625 |
| 4 — the play issues | the brief rewrite, one bar, the opening told, the rules named, engine art, the dice | 9,580 |
| 5 — the seam as classes | `Engine` abstract, `SceneEngine`, `advance`/`author`, the world's verbs, the opening told plainly | 9,415 |
| 6 — the audit and the docs | dead code, layout, `VISION.md` gone | 9,390 |
| 7 — voices | `SpeechConfig`, `app/speech.py`, `ui.audio` | 9,570 |

Phase 3 landed at 9,480, under its row; Phase 4 at 9,613, 29 over its row; the rows after it
count from there.

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
protocol. `TAIL_EXCHANGES` and `told_tail` move only in Phase 3; `Counter.clamped` goes in
Phase 6.

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
    # Field order is today's dump order, so the fixtures move only where a field is new.
    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    hub: Slug | None = None
    board: tuple[Offer, ...] = ()
    cast: dict[EntityId, C] = Field(default_factory=dict)
    player: P                                  # known, never in the cast, never listed in a run
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

Nothing in `scenes.py` spells `PLAYER_ID` except `new_game`. Once `SceneWorld` is generic a
bare `SceneWorld` annotation is a strict-pyright error, so every function that takes a world is
generic: `def settle[C: Person, P: Person](world: SceneWorld[C, P], job_done: bool)`, and the
same on `record_exchange`, `hub_rows`, `scene_rows` and the arms below. The world arms, one
model and one function each, with the tools' docstrings and field descriptions verbatim so
`master_tools.json` does not move:

```python
class Reveal(Frozen): ...    # verb: Literal["reveal"], entity_id
class Enter(Frozen): ...
class Leave(Frozen): ...
class Kill(Frozen): ...

def reveal_hidden[C: Person, P: Person](world: SceneWorld[C, P], entity_id: EntityId) -> list[Fact]
    # today's Reveal arm + `_reveal` (card sentence(f"{name} discovered"))
def enter[C, P](world, entity_id) -> list[Fact]     # refuses the player, someone here, someone hidden here
def leave[C, P](world, entity_id) -> list[Fact]     # refuses the player; refuses a party member:
                                                    # f"{one.name} travels with the player and leaves through `leave_party`"
def kill[C, P](world, entity_id) -> list[Fact]      # require_here; refuse the dead; reveal; drop from party; alive=False;
                                                    # card "You are dead" for the player, else f"{one.name} is dead"
```

The seam functions take the game, and `Game[P]` is invariant, so they are generic on the state
with a bound of `Any`:

```python
def new_game[C: Person, P: Person](canon: SceneCanon[C], player: P) -> SceneWorld[C, P]:
    """deepcopy the canon; refuse PLAYER_ID in its cast; return SceneWorld(cast=canon.cast, player=player,
    runs=[SceneRun(scene=canon.opening, present=list(canon.present), hidden=list(canon.hidden))], source, hub, board)."""
    # written unparametrized; pyright infers SceneWorld[C, P] from the arguments, and the state's field
    # validates the instance into the parametrized class

def check_game[S: SceneState[Any, Any]](packs: Mapping[str, BaseModel], state: Game[S]) -> None
    # f"a {state.engine!r} game needs at least one table set"; missing packs; check_kind
def known[S: SceneState[Any, Any]](state: Game[S], entity_id: EntityId) -> bool | None
def record[S: ...](state: Game[S], prompt, lines, facts) -> tuple[str, ...]
def history[S: ...](state: Game[S]) -> tuple[Exchange, ...]
def way_open[S: ...](state: Game[S]) -> bool
def player_over[S: ...](state: Game[S]) -> str | None
```

Add to `CLAUDE.md`'s "Do not use `Any`" line: ", except in `engines/scenes.py`'s seam
functions, where `Game[P]`'s invariance makes `SceneState[Any, Any]` the only spelling of the
bound". No other `Any` is added.

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
wires `validate=partial(check_game, packs)`, `known=known`, `record=record`,
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
`world.player_id` → `world.player.id`, `SceneCanon` → `SceneCanon[...]`. Loner's
`worldsmith.py` needs three more edits, each making it read as 24XX's does today, because its
player is no longer in the cast: `apply_scene`'s `followers` is `world.party` alone (the player
is never listed, so `kept` holds party members only and `present=[*kept, *present]`);
`render_worldsmith` prints `entity_line(world, world.player, ...)` first, then the cast;
`_scene_unmet`'s `known` mapping is `{world.player.id: world.player, **held, **draft.cast}` and
`others` drops what resolves to `world.player.id`.

Test support follows the shape: `core_test_support.with_entity`, `loner3e_test_support.hub_world`
(the player at `player=`, not in `cast`, `party=[]`), every test reading `companions`,
`player_id` or `cast[PLAYER_ID]`.

### 1.4 Docs

`docs/LONER-3E.md` deviation 5 says `party` where it says companions. `CLAUDE.md`: the `Any`
line (1.2). Recreate `PROGRESS.md` with this phase's entry.

### Done when

Green. Goldens: `state/` and `save/` for 24XX and Breathless gain `"party": []` after
`"player"`; Loner's carry `"player": {...}` after the cast, the player out of `cast` and
`present`, `"party": []` in place of `"companions"`, no `"player_id"`; in every engine's sheet
dump (`Operator`, `Survivor`, `LonerCharacter`) `"alive"` moves up to follow `"known"`, since
`Person` declares it; `master.txt`, `master_tools.json`, `narrator.txt` and `picture.txt`
unchanged for all four engines. A Loner turn joins Mara to the party, and the next scene's
`present` holds her without the worldsmith naming her; `leave` on her is refused; `kill` drops
her; Loner's player death now cards "You are dead" as the other engines do. `src` about
9,950; each `world.py` under 110 lines.

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
    # a class subscripted by a `type[C]` variable type-checks under basedpyright strict; pydantic
    # parametrizes it at runtime, and `isinstance(x, HubDraft)` on the result is True

def scene_unmet[C: Person, P: Person](draft: SceneDraft[C], world: SceneWorld[C, P] | None) -> list[str]
    # held = {} or world.cast; everyone = draft.cast alone, or {player.id: player, **held, **draft.cast}
    # followers = () or (player.id, *party): any of them resolved in present/hidden is unmet:
    #   f"a scene that does not list the player or the party; they are put there by code: {named}"
    # cast_unmet(others, ...) with others = present + hidden; then per cast entry with unwritten():
    #   f"cast members as the worldsmith may write them: {[f'{eid}: {why}', ...]}"; then hub_unmet
def scene_refusal[C, P](draft, world=None) -> str | None      # "the scene needs " + "; ".join(unmet)
def opening_canon[C](draft, source) -> SceneCanon[C]          # today's body
def apply_scene[C: Person, P: Person](world: SceneWorld[C, P], draft: SceneDraft[C]) -> None
    # refuse: a cast entry under the player's id ("the scene rewrites the player"), an existing id, misfiled;
    # everyone = {player.id: player, **merged cast}; resolve present/hidden against it;
    # refuse the player or a party member named; overlap; hidden-but-met; then world.cast = merged,
    # mark present known, runs.append(SceneRun(scene=_scene(draft, world.job_done),
    #                                          present=[*world.party, *present], hidden=hidden))
```

`_scene(draft, finished) -> Scene` moves as is. The local mapping is `everyone` in both
functions; `known` would shadow the seam function of that name in the same module.

### 2.2 `engines/scenes.py`: the crossing

```python
async def write_next[C: Person, P: Person](
    world: SceneWorld[C, P], intent: str, answer: WorldsmithAnswer, *,
    cast_type: type[C], role: str, guidance: str,
) -> BaseModel
    # returning = hub is not None and not at_hub and intent == GO_HOME
    # model = ReturnDraft[cast_type] | JobDraft[cast_type] | SceneDraft[cast_type]; refusal as today

def install_scene[S: SceneState[Any, Any]](state: Game[S], written: BaseModel, *, finished_note: str) -> tuple[Fact, ...]
    # if not isinstance(written, SceneDraft): raise ValueError(f"{state.engine!r} received an incompatible scene")
    # draft: SceneDraft[Any] = written     # isinstance narrows to SceneDraft[Unknown]; a parametrized class is no isinstance target
    # apply_scene(world, draft.model_copy(deep=True)); trace "the story moves to {title}" +
    # (f", and {names} travel there with the player" when world.members()); card "Home: " | "New scene: ";
    # on ReturnDraft: world.board = offers; job = world.jobs()[-1]; if finished and finished_note:
    # state.notes += (finished_note.format(title=job.title),); return (job_closed(job), opened)

def render_worldsmith[C, P](world, intent, guidance, answer, *, role) -> str
    # cast = entity_line(player, detail=last_seen) then each cast member with
    # detail="travels with the player" for a party member, else last_seen: the worldsmith must know who follows;
    # scene_history(world.job_runs()); hub_rows
def render_opening[C: Person](cast_type, role, source, guidance, kind, hub_phrase) -> str
def build_scenario[C: Person](
    file_type: type[Scenario[SceneScenario[C]]], engine_id: EngineId,
    title, premise, packs, written: BaseModel, source, kind,
) -> AnyScenario
    # isinstance(written, SceneDraft) else f"{engine_id} received an incompatible scene"; scene_refusal;
    # file_type(meta=ScenarioMeta(title, premise or written.situation, kind), engine=engine_id, packs,
    #           payload=SceneScenario(world=opening_canon(written, source)))
```

Pydantic validates an unparametrized `SceneScenario(...)` into the file's parametrized field;
no type argument is needed. The `SceneDraft[Any]` in `install_scene` is the one local `Any`
the `CLAUDE.md` exception covers beside the bounds.

`art_style` leaves `Authoring.build`: its type becomes `Callable[[str, str, tuple[Slug, ...],
BaseModel, str, ScenarioKind], AnyScenario]` (title, premise, packs, written, source, kind),
Tunnel Goons' `build_scenario` drops the parameter too, and `Runtime.new_scenario` applies it
once on the built file: `write_scenario(..., as_scenario(written).model_copy(update={"art_style":
art_style}), document)`. Phase 7 adds `voice` to that same update.

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

def install_scene(state, written):
    return scenes.install_scene(state, written, finished_note=JOB_DONE_NOTE)

# Loner: the conflicts close before the crossing, since close_conflicts reads the scene being left
def install_scene(state, written):
    closed = close_conflicts(state)
    return (*closed, *scenes.install_scene(state, written, finished_note=GROWTH_NOTE))

def render_opening(packs, source, picks, kind) -> str:       # guidance is the engine's; 24XX joins BOARD_GUIDANCE for a campaign
    return scenes.render_opening(Person, WORLDSMITH, source, guidance(packs, picks), kind, HUB_PHRASE)
```

`build()` wires `Authoring(answer=partial(opening_draft, Person), prompt=partial(render_opening,
packs), build=partial(build_scenario, TwentyfourxxScenarioFile, EngineId("twentyfourxx")))`,
the first and last from `scenes.py`, `render_opening` the wrapper above.

`views.py` shrinks to `master_sections` (its own ten-line tuple, since 24XX's `GEAR` and Loner's
glossary sit in different slots) plus the engine's extra panel and gear lines. `views.py` no
longer imports `worldsmith.py` or the reverse: both import `scenes`:

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

### 2.5 Dead code, same phase, part A

`ui/settings.py _without_none` (no `Optional` field exists; use `field.annotation` directly);
the `way.to in places` guard in Tunnel Goons `walk`, with its `places` parameter, the same
parameter on `has_shortcut`, and the argument at their four call sites (the validator
guarantees every way leads to a place); 24XX `SRD_PACK`; `core/tools.py`'s `Known` alias
re-spelled at `Engine.known` (import `Known`); `other_than` from Breathless and Loner
`creation.py` into `core/creation.py`. Part A does all of it, so B and C touch no shared file.

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

`SaveOption.where: str`. In `load_catalog`, in this order: the header in its existing `try`;
the `played_by`/`title` check as today; then a second `try` around
`state = engines[game.engine].restored(raw)` whose `except ValueError` logs the same "skipping
save" warning and continues (a stale save is invalid, never repaired); then
`history = engines[game.engine].history(state)` and `where = history[-1].where if history
else ""`. `_saved_card` reads `f"{saved.character_title} · turn {saved.turn}"` plus
`f" · {saved.where}"` when set.

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

## Phase 4 — the play issues

Six things seen in play, fixed together. Each is restated here so the phase stands on its
own; `ISSUES.md` is deleted at the end. **Split**: A (opus: 4.1–4.3) then B (sonnet: 4.4–4.6),
sequential, since both touch `ui/game.py` and `app/runtime.py`. About two hours of agent time
for A, one for B.

What was seen, and its cause:

1. A job taken from the hub ended in `the written world no longer fits: the scene rewrites
   'sil-marrow', who is already in the cast`, the player still at the hub, the reason in the
   log and a grey sidebar line. The worldsmith re-files a hub regular under `cast` because the `cast` field carries no
   description and `TAKE_BRIEF` says "anyone from the hub's cast the player names is present".
   The refusal lives in `apply_scene`, at install, after the worldsmith has answered; the bar
   the one retry sees (`scene_unmet`) never checks it. "Already met", "both present and
   hidden" and "filed under" are install-only refusals too. The retry is the agentic loop
   (`answered`, one re-prompt, `CLAUDE.md`); these refusals sit outside it.
2. The home page names a scenario and a save by title only; the rules they play are not shown.
3. A 24XX game is drawn as painterly fantasy: the style falls back to `MediaConfig.style`.
4. A turn's narration reaches the page only after the worldsmith has finished: `play` commits
   the turn, then awaits the crossing before returning, and `_send` refreshes after `play`.
5. A new game, a new job and a return home drop the player in: nothing is narrated at the
   opening, the situation is a grey line in the header, the stake is in the sidebar, the open
   job's terms reach the master and never the player, and the "New scene" card holds a title.
6. The dice land as static cards.

### 4.1 One bar, and the worldsmith may rewrite a brief

`engines/scenes.py`. A cast member's name and sheet are the rules'; their `brief` is the
worldsmith's, and may change between scenes (a scar, a new post, a changed loyalty):

```python
class SceneDraft[C: Person](Frozen):
    situation: str = Field(
        min_length=MIN_SITUATION,
        description="What the player sees and knows on arrival: where they are, why they are "
        "here, what is in front of them. Read to the player, so it holds nothing hidden.",
    )
    cast: dict[EntityId, C] = Field(
        default_factory=dict,
        description="New people and things, filed under their own id. An id already in THE "
        "WHOLE CAST re-files that person: their `brief` is rewritten and nothing else; their "
        "name and their sheet stay as the rules hold them.",
    )


def merged_cast[C: Person, P: Person](world: SceneWorld[C, P], draft: SceneDraft[C]) -> dict[EntityId, C]:
    """A re-filed member keeps the world's entry with the draft's brief."""
    return {
        **world.cast,
        **{
            one: held.model_copy(update={"brief": written.brief})
            if (held := world.cast.get(one)) is not None
            else written
            for one, written in draft.cast.items()
        },
    }
```

`scene_unmet` takes every refusal `apply_scene` made alone, in this order after the followers
check: `world.player.id in draft.cast` → "a cast that never rewrites the player"; an entry
whose `id` is not its key → `f"cast entries under their own id: {held.id!r} is filed under {key!r}"`;
`cast_unmet` as today over `everyone = {player.id: player, **merged_cast(world, draft)}`
(`dict(draft.cast)` at the opening); `present` and `hidden` resolved through `resolved_id`
with strays skipped (`cast_unmet` names them) that overlap → `f"nobody listed as both present
and hidden: {overlap}"`; resolved `hidden` whom `everyone` holds as known → `f"a hidden list
without {met}, whom the player has already met"`, the followers left out since their check
named them (a re-filed member's `known` is the world's, which is why the merge happens before
the check); `unwritten()` over the draft's new entries
only, since a re-filed sheet is dropped; then `hub_unmet`.

`apply_scene` opens with `if (refused := scene_refusal(draft, world)) is not None: raise
ValueError(refused)` and loses its own checks; its body is `world.cast = merged_cast(world,
draft)`, resolve, mark known, recap, append. The bar is one function: the retry loop runs it
on the snapshot `_grow` takes, which is the committed turn, so the worldsmith already sees the
turn's own changes; the install runs it again as a safety net that no test reaches.

The three `worldsmith.md`, after "may then be named in `present` or `hidden`.": "Someone
already in THE WHOLE CAST may be filed again to rewrite their `brief`; their name and their
sheet are the rules' and do not change."

`ui/game.py`: after `session.play` returns in `_send`, `if session.write_failure:
ui.notify(NO_WAY_ON, type="warning")`, `NO_WAY_ON` imported from `panels.py`, which keeps its
sidebar line. `restart()` clears `write_failure`, or the toast fires on a fresh game after a
failed crossing. Tests: `test_invalid_actor_from_crossing_is_rejected_before_commit` becomes "a
re-filed cast member takes the new brief and keeps their name and sheet" (Mara's name stays
`Mara`, her brief is the draft's), and `tests/twentyfourxx/test_worldsmith.py`'s "already in
the cast" case becomes the same rule at the `apply_scene` level. The outgrown-scene test in
`test_tool_surface.py` scripts two answers, `[_scene(), _scene()]`, and keeps its "already
met" assert: the bar refuses both, and `answered`'s "answered nothing usable" carries the
last refusal into `write_failure`; its docstring becomes "the bar sees the turn's own
changes". The `match=` strings "rewrites the player" and "is filed under" still hold.

### 4.2 The player knows where they are

- `install_scene`'s card carries what the chat has no other path to:
  `"\n".join((f"{label}: {title}", f"At stake: {question}", *([f"The job: {job}"] if JobDraft)))`.
  Not the situation: the header shows it. The chat draws the headline bold and each further
  line small, as `_card` does today.
- `scene_rows`: after the question row, `PanelRow(label="The job", detail=world.job)` when
  `world.job` is set. Tunnel Goons: nothing, its job is a name.
- The opening is narrated. `app/runtime.py`, beside `CROSSED`:

```python
BEGUN = "(the story begins)"
OPENING = (
    "The story begins here; the player has read nothing yet. Write the opening: who they are "
    "(WHO IS HERE names them first), where they stand, what is in front of them, and what pulls "
    "at them, from WHAT THIS SCENE IS ABOUT. They have not acted, so settle nothing."
)

class GameService:
    def unopened(self) -> bool:
        """No exchange yet: nobody has told the player where they stand."""
        return not self.busy and not self.engine.history(self.state)

    async def open(self, on_step: Callable[[TurnStep], None] | None = None) -> None:
        """A narrator that fails leaves the premise to do its work; a reload mid-opening is a no-op."""
        if not self.unopened():
            return
        announce = partial(self._announce, on_step=on_step)
        self.busy = True
        try:
            draft = self.state.draft()
            announce("narrator")
            lines = await self._narrate(draft, (), OPENING, fatal=False)
            if lines:
                view = self.engine.narrator_view(draft)
                self.commit(close_segment(self.engine, view, draft, BEGUN, lines, ()))
            self.illustrate(_latest_narration(self.engine, self.state))
        finally:
            self.step, self.busy = None, False
```

  `restart()` no longer illustrates: the page opens the game again. The opening costs a turn,
  as a crossing does (`close_segment`); the journal lists it as "turn 1: (the story begins)".
- `ui/game.py`: `_send`'s body becomes `_run(view, bubble, lambda: session.play(...))`, where
  `_run(view, bubble: str | None, playing: Callable[[], Awaitable[None]])` is today's `_send`
  from `view.live_prompt = bubble` to the final `_scroll`, plus the 4.1 toast. `_open(view)` is
  `_run(view, None, lambda: session.open(on_step=...))`. `game_page` replaces
  `session.illustrate()` with `if session.unopened(): ui.timer(0.1, lambda: _open(view),
  once=True) else: session.illustrate()`. `restart` becomes async and ends with `await
  _open(view)`.

### 4.3 The narration shows while the worldsmith works

`GameService.play` gains `on_commit: Callable[[], None] | None = None`, called right after
the first `self.commit(state)`, before `_grow`. `ui/game.py` gains `on_commit(view)` beside
`on_step` and `on_fact`: `view.live_prompt, view.live_facts = None, []`, then `chat.refresh()`,
`live_turn.refresh()`, `_scroll(view)`. `_run` passes it. `extend` does not take it: nothing is
committed before its write. About 12 lines.

### 4.4 The home page names the rules

`CatalogEntry.rules: str` and `SaveOption.rules: str`, the engine's title, set in
`load_catalog`, which holds `engines`. The scenario select's options read
`f"{entry.title} · {entry.rules}"`; `_saved_card` draws `ui.badge(saved.rules).props("outline")`
in a row with the campaign badge. The character select is unchanged: it already lists the
rules' own characters.

### 4.5 The engine's art

`Engine.art_style: str` after `title`, one line per `build()`:

- 24XX: "Clean science-fiction illustration: hard light, neon on steel, lived-in technology,
  no text or lettering."
- Breathless: "Grim survival-horror illustration: dim, desaturated, wet surfaces, no text or
  lettering."
- Loner 3e: "Painterly illustration, muted colours, no text or lettering."
- Tunnel Goons: "Old-school fantasy illustration in black ink, cross-hatched, no text or
  lettering."

`MediaConfig.style` is deleted: with every engine carrying one, it would never be read.
`tests/ui/test_settings.py` boxes and round-trips `("media", "style")` in two tests: both move
to `("media", "model")`, the quoted-string case included. `tests/core/test_media.py`'s
`STYLE = MediaConfig().style` becomes a literal. `open_illustrator(settings, target, store,
*, style: str)` takes the resolved style, and drops `scenario` and `character`, which it no
longer reads; `Runtime._open` passes `scenario.art_style or engine.art_style`. `ui/create.py`'s art style input reads `placeholder=f"Leave empty for:
{engine.art_style}"`, so the player sees what an empty box gives.

### 4.6 The dice tumble

`ui/theme.py`: `game-die-land` and its `.game-die` animation go; in their place:

```css
.game-die-live { animation: game-die-tumble 600ms cubic-bezier(.2, .8, .3, 1) both; }
@keyframes game-die-tumble {
  from { opacity: 0; transform: perspective(240px) rotateX(-220deg) rotateY(160deg) scale(.5); }
  60% { opacity: 1; transform: perspective(240px) rotateX(20deg) rotateY(-15deg) scale(1.08); }
  to { transform: none; }
}
@media (prefers-reduced-motion: reduce) { .game-die-live { animation: none; } }
```

`_card(fact, *, live: bool = False)` hands `live` to `_dice_group`, which adds `game-die-live`
when set. `live_turn` renders `_card(fact, live=fact is view.live_facts[-1])`: every step and
fact refreshes it, so only the newest card tumbles; `chat` renders still, so a refresh no
longer replays every roll in the history. Real 3D dice go to `IDEAS.md` (4.7).

### 4.7 Docs

- `CLAUDE.md`, design decisions, after the narrator line: "The worldsmith writes new cast
  entries and rewrites a brief; a name and a sheet are the rules'. The scene bar and the
  install share one refusal list, so the worldsmith's one retry sees every refusal."
- `README.md`, under the three roles: "The narrator opens the game with who the player is and
  where they stand; the player acts from there."
- `IDEAS.md`: add "17: Real 3D dice: a physics canvas; the CSS tumble is the cheap version."
- Delete `ISSUES.md`. `PROGRESS.md` gains this phase's entry.

### Done when

Green; every golden unchanged (no fixture holds a `scene_opened` card, and the draft schemas
render only in the worldsmith prompt, which has no golden). A draft that re-files Mara with a
new brief lands with her name and sheet intact; a draft that hides someone the player has met
is refused by the bar and the retry sees it; a write that still fails toasts. A new game opens
on a narrator passage filed as "(the story begins)" before the player acts, and restart does
it again; a turn's narration shows while the worldsmith works; the New scene card carries the
stake and the job; the sidebar shows the open job. The home page names each
scenario's and each save's rules; a 24XX game with no scenario style is drawn in the engine's;
live dice tumble and the history stands still. `src` about 9,580.

---

## Phase 5 — the seam as classes

Two outside readings of the code on 2026-09-02. The first proposed an engine object with a
`SceneEngine` base in place of the `Engine` callback record, one flat scene draft in place of
the five draft classes, one `advance()` transaction in place of `ready → write → install →
arrival_brief`, and the master as its own worldsmith. The second counted what the first was
reacting to, against the code after Phase 4: 19 callables wired into `Engine`, `Authoring` and
`Transition`; 45 `partial(...)` binding packs, cast types and ids at wiring time, because there
is no `self` to carry them; three scene `worldsmith.py` of 42–50 lines that only forward a cast
type and four strings; `GameService` running `ready → write → install → arrival_brief` as a
second state machine after the turn (`_grow`, `_write`, `_install`, about 55 lines); and in
`engines/scenes.py` one object split across two styles, `world.require()`, `world.here()`,
`world.jobs()` methods beside `enter(world, id)`, `kill(world, id)`, `settle(world, done)`,
`apply_scene(world, draft)` free functions on the same object, about fourteen of them, the line
between the two drawn nowhere.

This phase keeps the first proposal as a class and the third as written, and moves the fourteen.
It is not a rewrite: the value models, `Fact`, `apply_to_draft`, `Game.draft/committed`,
`NarratorView`, `Turn`, the resolvers as `(draft, args, rng) -> facts` and the Protocols in
`app/spawn.py` are the right shape and none of them moves. The maintainer's decisions
(2026-09-02): `Engine` is an abstract class, `SceneEngine` its one concrete base, each engine a
subclass; "write pure functions" stands, since a method that reads `self.packs` and its `state`
argument and writes nothing is as pure as the function that took both as parameters, and the
overridable surface is what the three engines differ on today, counted in 5.1, not a set built
for later; the five drafts stay, because they are the schema the worldsmith answers in and a
`match` on a frozen model is a match on a domain distinction; the master stays a player of the
world and the worldsmith its author.

Four steps, one commit; each step is green on its own. **One implementer, opus**: the base
changes shape, so all four engines move in the same step. 5.1 to 5.3 change no behaviour, no
prompt and no golden: `prompts/`, `schemas/`, `turn/`, `state/` and `save/` are their invariant,
and a step that moves one has a bug. 5.3 is the first to cut if the phase runs past its target
(rule 5); 5.4 stands whatever is cut. Fixtures that may change: the four
`prompts/<engine>/narrator.txt`, two lines each, in 5.4 only.

### 5.1 The object

`Engine` becomes a class whose methods are today's callables, one to one, under today's names;
`Authoring` and `Transition` fold into it as seven methods that 5.2 makes three. Every `partial`
in `engines/` goes, because `self` carries what it bound. The layout moves first, so the class
lands in its file: `engines/scenes.py` becomes a package mirroring the engines' own file shape,
a pure move, `engines/scenes/world.py` (the models, the arms, the seam functions),
`engines/scenes/worldsmith.py` (the drafts, the bar, the crossing), `engines/scenes/views.py`
(the lines, the panels); `Engine`, `Authoring`, `Transition` and `AnyEngine` move from
`engines/core.py` to `engines/seam.py`, leaving `core.py` the world toolkit. Imports cost about
40 lines; nothing else moves with them.

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
      # `Authoring` and `Transition` signatures, until 5.2.
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
  `new_game` and `validate` move in as methods (`validate` is the method's name, so the
  `check_game` rename the audit planned is moot), the other fifteen delegate one line each to
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
  The engine line: "An engine is self-contained under `engines/<id>/`, under 2,000 lines, with
  at most fifteen game-master tools, counted as tools plus `change_world` arms, the two shared
  party arms not counted; twenty in all for an engine whose SRD plays a crew, named in its
  `docs/<ENGINE>.md`. Every engine subclasses `Engine` in `engines/seam.py`; the three scene
  engines subclass `SceneEngine` in `engines/scenes/engine.py`; all four share the hub in
  `engines/hub.py`." `docs/<ENGINE>.md` name the engine class where they name the wiring file.
- **Tests.** The four `dataclasses.replace(...)` calls (`test_launcher.py` and
  `test_tool_surface.py` for `id`, `test_decisions.py` and `test_tool_surface.py` for `tools`)
  build a `Loner3eEngine(PACKS)` of their own and set the attribute; the transition test
  subclasses `Loner3eEngine` with `ready` returning True, `crossing = None` and a scripted
  `write`; `test_engine.py` in each engine reads `new_game` off the engine, not the module. A
  test that a fifth `SceneEngine` subclass with a bare `Person` cast, the base `Pack` and no
  tools builds a playable engine is the one new behaviour test: the review's litmus, "a fifth
  scene engine is its state model, its creation, its tools and its sections", is what this
  step buys. No test of prose or wiring is added.
- **Step done when.** Green; every golden unchanged; `grep -rn "partial(" src/aidm/engines`
  finds nothing; no scene `worldsmith.py` exists; the three scene `engine.py` under 60 lines.
  About -120 lines, the 40 of imports counted.

### 5.2 The transaction

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
  written.model_copy(update={...}))` with the same `update` dict (art style; Phase 7's voice),
  where `playable` runs `begin_game`. The UI's `transition_available` reads `engine.ready`.
- **Tests.** The transition test's subclass overrides `advance` in place of `write`;
  `test_authoring_build_raises_on_an_unmet_bar` becomes a scripted worldsmith that
  `engine.author` refuses on the bar; the four `test_worldsmith.py` call `engine.advance` and
  `engine.author` where they called the pairs, and `tests/loner3e/test_world.py` and
  `test_hub_play.py` keep calling `install_scene`. No test of prose or wiring is added.
- **Step done when.** Green; every golden unchanged; `grep -n BaseModel
  src/aidm/engines/seam.py` hits `new_game`'s return and the import only, and
  `src/aidm/app/runtime.py` not at all; a failed write and an install that no longer fits both
  leave the state untouched and set `write_failure`. About -70 lines.

### 5.3 The world's verbs

A pure move, and the first to cut.

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
  about thirty-five test call sites the same way. The drafts are left alone, and Tunnel Goons
  is left alone: `TunnelWorld` already owns its verbs.
- **Step done when.** Green; every golden unchanged; `grep -n "world: SceneWorld"
  src/aidm/engines/scenes/world.py` finds only `new_world`'s return; no
  `def .*\[C: Person, P: Person\]` remains outside the models. About -15 lines.

### 5.4 The opening, told plainly

The phase's one prompt change; no refactor step touches it. Played on 2026-09-02, the opening
reads as mood: the player closes it not knowing what they are there to do or what they could do
first. The narrator's inputs hold all four answers already (WHO IS HERE, SCENE, WHAT THIS SCENE
IS ABOUT); the brief asks for them in an order, and the length cap gives the room. The opening
is always the first scene, so no job exists yet: what they are here to do is the scene's
question, and at a hub it is the board, which the panel holds and the prose points at without
listing, since the narrator never sees the offers.

- **`app/runtime.py`.** `OPENING` becomes: "The story begins here; the player has read nothing
  yet. Tell them, in the fiction and in this order: who they are (WHO IS HERE names them first)
  and where they stand; what is in front of them, the situation as they see it now; what they
  are here to do, from WHAT THIS SCENE IS ABOUT, said as the thing pulling at them; and two or
  three things they could plainly do first, offered by the place and the people, in prose, never
  as a list. Six to eight sentences. They have not acted, so settle nothing."
- **`turn/prompts/narrator.md`.** The first line reads "Write 2-4 vivid sentences, or the length
  PLAYER ACTION asks for, in second person and present tense." **`core/play.py`.**
  `Narration.lines`' description reads "All narration and dialogue in order; 2-4 sentences, or
  the length PLAYER ACTION asks for." Both, so the schema the model reads does not contradict
  the brief. The four `prompts/<engine>/narrator.txt` change those two lines and nothing else.
- **No new test**: prose. Play one opening per engine and read it against the four questions:
  where am I, what do I see, what am I here to do, what could I do first.

### Done when

Green; every golden unchanged but the two narrator lines; `uv run aidm` opens a game in each
engine and the opening answers the four questions; `grep -rn "partial(" src/aidm/engines` finds
nothing; `README.md` and `docs/` name `Engine` and `SceneEngine` where they named the wiring
file; `PROGRESS.md` holds the phase's entry with both counts. `src` about 9,415.

---

## Phase 6 — the audit and the docs

No behaviour change. **One implementer, sonnet.**

### 6.1 Cuts and layout

- Delete the `hint` on Tunnel Goons' three ability steps (a step with options never shows it).
- `core/views.py`: `sections()` after the classes. `ui/game.py`: `on_fact` above the private
  functions. `core/model.py`: `AnyScenario`, `AnyCharacter`,
  `AnyGame` into the constants block under `ScenarioKind` (`type` aliases are lazy).
  `engines/seam.py`: `AnyEngine` likewise. The `WorldChange` unions, `DRIVERS`, `TURN_TOOLS`
  and Tunnel Goons' `Entity` alias must follow their classes: one comment each says so.
- Inline `Counter.clamped` into `adjust`, its one user; `tests/loner3e/test_counters.py`
  loses its two `clamped` asserts.
- Trim every docstring past one line where the code says the what.

### 6.2 `CLAUDE.md`

The engine line is Phase 5.1's. Design decisions gain two lines: "Non-goals: a shared
world layer, save migration, a built-in turn loop and its state keeper, retrieval over source
documents." and "A turn: the master is spawned with the rules and the action and changes the
world through tools only; a rule may leave a decision the player answers next turn; the
narrator receives revealed canon only; the exchange is recorded and the whole draft is
validated and committed; then the engine's transition may offer the way on."

### 6.3 `VISION.md` is deleted

Move first, then delete: content paths (characters, scenarios, saves) and "play costs the
subscription; illustration is the exception" into `README.md` (one short paragraph under "Start
the app"); Maze Rats (`2c3e8a5`, `62f95c6`) and the Pokémon–Showdown boundary into `IDEAS.md`
as two items. Then delete `VISION.md`, its line in `README.md`'s "Project information", and its
`extend-exclude` entry in `pyproject.toml`. `grep -r VISION` finds nothing.

### 6.4 `README.md`, `IDEAS.md`, `COMPETITOR-RESEARCH.md`

- `README.md` gains one architecture paragraph beside the campaign paragraph: the three roles
  as spawned CLIs returning typed proposals, the engine seam (`Engine` an abstract class,
  `SceneEngine` the base of the three scene engines, the registry the one composition point),
  imports one way `core <- engines <- turn <- app <-
  ui`.
- `IDEAS.md`: delete 3 and 9 (refused non-goals) and the built-in half of 4; fold 5, 6, 7, 8,
  14 into one line "audit: consistency, dead code, docstrings, one doc shape per engine", marked
  done by this phase; keep 4's eval loop, 11, 13, 16; add moving home with its sketch
  (`SceneWorld.hubs` tuple, `at_hub = place == hubs[-1]`, a `MOVE_HOME` row, `HubDraft`
  reused, a "New home: <title>" card, about 70 lines, no SRD prints it) and the two items from
  5.3.
- `docs/COMPETITOR-RESEARCH.md`: one dated note at the top: the "ours" columns, `ROADMAP.md`,
  "code mode" and `.agents/skills` are stale.

### 6.5 Engine docs, one shape

The four `docs/<ENGINE>.md` already share one heading order; only `docs/LONER-3E.md` lacks
`## The tools`. Add it between "Pack sources" and "Deviations", one line per tool as the other
three write them: `change_world` (its eight arms named), `next_scene`, `roll_question`,
`restore_luck`. Nothing else moves.

### Done when

Green; every golden unchanged. No document holds rules text; `grep -r VISION` finds nothing;
`src` about 9,390.

---

## Phase 7 — voices

Narration and dialogue read aloud, generated after the turn commits, cached beside the art,
played under the newest exchange. Off by default. The narrator's voice is the scenario's, as its
art style is. **Split**: A (sonnet: 7.1–7.3, config and the reader) then B (sonnet: 7.4–7.5,
the service and the page).

### 7.1 `config.py`

```python
ProviderName = Literal["openrouter", "local", "kokoro"]

class SpeechConfig(BaseModel):
    """Speech is optional presentation, so failures only log and the default is off."""
    model_config = ConfigDict(frozen=True)
    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-tts-preview"
    voice: str = "Kore"                                   # the narrator's, when the scenario names none
    voices: tuple[str, ...] = Field(                      # the pool dialogue draws from
        default=("Kore", "Puck", "Charon", "Zephyr", "Fenrir"), min_length=1
    )
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

### 7.2 The scenario's voice

`Scenario.voice: str = ""` in `core/model.py` beside `art_style`. `Runtime.new_scenario`
takes `voice: str` beside `art_style` and adds it to the `model_copy(update=...)` Phase 2
left there; `Authoring.build` does not change. `ui/create.py`: an input "Narrator voice" with
placeholder "Leave empty for the default voice" under the art style input, passed as `voice=`.

### 7.3 `app/media.py` shares, `app/speech.py` reads

In `media.py`, make module functions of the two things both files use: `claim(generating:
set[str], key) -> bool` (synchronous, as today's comment says) and `post_bearer(provider, path,
body, timeout) -> bytes` (the bearer POST with `raise_for_status`, returning `reply.content`;
`_generate` parses its JSON from that). `_existing` and `_write` stay media's: a clip has one
suffix and `wave` writes the file.

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

    def clip(self, exchange: Exchange) -> Path | None          # saves / f"{key}.wav" when it is a file
    def pending(self, exchange: Exchange) -> bool
    async def read(self, exchange: Exchange) -> None
        # key; skip when cached or not claimed; one POST per line; on any failure LOGGER.exception once and return;
        # join the pcm chunks; saves.mkdir(parents=True, exist_ok=True); wave.open(path, "wb") with
        # 1 channel, 2-byte samples, config.sample_rate

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

### 7.4 `app/runtime.py`

`GameService.reader: Reader | None = None`, set by `_open` through `open_reader`. Add
`speak()`: like `illustrate`, a retained `create_task(self.reader.read(history[-1]))` over
`self.engine.history(self.state)`, no-op when `reader` is None or the history is empty. Call it
right after each of the two `self.illustrate(...)` calls in `play`; the narrated crossing
commits inside that same `play`, so `_install` needs no hook. `newest_clip() -> Path | None`
and `clip_pending() -> bool` read the last exchange. Cards, situations and debriefs are not
spoken; a resumed game generates nothing for old exchanges.

### 7.5 `ui/game.py`

`chat` takes the `GameView` (it needs the session and one flag). After an exchange's lines,
when `session.reader is not None` and `session.reader.clip(exchange)` is a path:
`ui.audio(path, controls=True, autoplay=path == view.autoplay_clip)`. `GameView` gains
`shown_clip: tuple[Path | None, bool]`, initialised in `game_page` from
`(session.newest_clip(), session.clip_pending())` so a cached clip never autoplays on a page
load, and `autoplay_clip: Path | None = None`. `poll_art` keeps its art comparison and adds a
second: when `(session.newest_clip(), session.clip_pending())` differs from `shown_clip`,
store it, set `autoplay_clip` to the clip when it is a path, and `chat.refresh()`. `_send`
clears `autoplay_clip` before `refresh_all`, so the previous clip does not restart at the next
turn. The 3-second timer runs when `media` or `reader` is set. About 25 lines.

### 7.6 `IDEAS.md`

Item 1 (sounds and voices) is done: delete it.

### Done when

Green; every golden unchanged. With `SPEECH__ENABLED=true` and a key, a turn's narration plays
within seconds of the text in the scenario's voice, or the settings' when it names none; the
wav is reused on reload; with the provider down, the turn is unaffected and one warning logs.
`src` about 9,570.
