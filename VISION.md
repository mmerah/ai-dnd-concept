# VISION: a game you play in a browser, run by CLIs you already pay for

This file is the authority on the target and the reasoning. It is self-standing. A plan is
derived from it; this file is not the order of work.

## The one-line vision

> The app is the game, and you play it in a browser.
> Its three roles — game master, narrator, worldsmith — are one-shot CLI sessions the app
> spawns, so play costs a subscription the player already has.
> The world is what its kit says it is: sentence-driven scenes or an authored map.
> One engine ships. The other two come back on the new design.

## Why

1. **People should be able to play it.** One window. Type, read, look at the art. No terminal,
   no MCP setup, no split attention. The coding CLIs are the engine room, not the interface.
2. **The player already owns a strong model.** Claude Code, Codex, OpenCode or Pi on a
   subscription. The app spawns those and pays nothing per turn to play. *(Illustration is the
   one exception: it is optional, off by default, and needs its own image-API key.)*
3. **One process owns the game.** The app is the only writer. No second terminal, no save-file
   polling, no two servers racing over one save.
4. **A map is a deliberate kit choice.** Keeping a spatial graph valid — ways, locks, containment
   cycles, reachability and a frontier — costs real machinery, but Maze Rats needs that map for
   loops, shortcuts and dungeon procedures. The scene kit still avoids that tax by design.
5. **Three engines is three ports.** Porting one proves the design; porting three before it is
   proven pays for the same lesson three times, and carries the generic machinery that only
   exists to hold three.

`src` should land near **5,150**, down from 9,452, with Loner 3e playable end to end. Each
engine added back afterwards costs about 500 on the new design.

## Target architecture

```
                        ┌──────────── the browser ────────────┐
                        │  play page   art · transcript · dice │
                        │  home · new character · settings     │
                        └───────────────┬──────────────────────┘
                                        │
APP  (one process, the only writer)     │
  GameService     open, play, act, answer, commit
  three spawns    game master · narrator · worldsmith
  MCP endpoint    the tool surface the game master calls
  media, settings, composition root

        typed engine seam

ENGINE  aidm/engines/<engine>/
  its typed Game and payload, embedding the selected kit's world state
  its SRD procedure tools, with every deterministic consequence inside
  its validation, character creation and kit boundary hooks

KIT     aidm/kits/scenes/       sentence-driven scenes, or
        aidm/kits/rooms/        authored places and directed ways
  each kit supplies world state, change_world and world tools,
  boundary/record/history callbacks, worldsmith authoring, and views
```

**The kit fills the views**, not the engine. It holds the cast, the scene and the threads, which
is nearly everything a view carries; the engine contributes its sheet rows through one callback.
One implementation instead of one per engine.

## How a turn runs

```
player types in the page
   │
   ├─ APP spawns the GAME MASTER, serving it the MCP tools
   │     start_turn  → the whole picture: scene, cast, hidden, threads
   │     engine tools → the engine rolls; code applies; facts return
   │     change_world → one settled change per call
   │     next_scene   → say the question is settled (does not end the turn)
   │
   ├─ the spawn returns when the process exits
   ├─ APP builds the narrator prompt from NarratorView and the told facts
   ├─ APP spawns the NARRATOR → the lines the player reads
   ├─ APP validates, records, commits
   ├─ APP starts the illustration
   └─ if the player pressed MOVE ON this turn, APP crosses over:
         spawns the WORLDSMITH on a snapshot, installs the scene,
         and spawns the NARRATOR again for the leaving and the arriving
```

---

## 1. Three roles, three contexts, one subscription

| role | is given | returns | when |
|---|---|---|---|
| **Game Master** | the game state, all canon, hidden included | tool calls | every turn |
| **Narrator** | `NarratorView`, told facts, the last few told passages | the lines the player reads | every turn |
| **Worldsmith** | source, history, full cast, threads, packs, the GM's intent | one typed `Scene` | at a scene boundary |

Two reasons this is the design, not decoration:

1. **It is the only way secrecy survives.** The game master must read hidden canon in order to
   plan, so it cannot also be what writes the player's prose. It produces no prose at all.
2. **Isolation writes better.** A fresh worldsmith holding the source, the story so far and the
   cast writes a stronger scene than a game master whose context is twenty turns of dice.

**The player never sees a role's raw output except through the app.** The transcript renders the
narrator's lines. The dev tab shows the game master's stdout, raw.

### Every role is fresh. No role keeps a session.

All three are spawned, used once and dropped — the game master too. Continuity lives in state,
never in a model's context:

| what carries over | where it lives |
|---|---|
| what the game master needs this turn | `start_turn`'s picture, rebuilt from state |
| what this scene is really about | `Scene.note`, written by the worldsmith, never narrated |
| what the story has promised | the threads, with their private notes |
| what the player has read | the recent told passages, in the narrator's prompt |
| what happened, whole | the scenes played, in the worldsmith's prompt |

Both current drivers already spawn one conversation per turn, because `start_turn` hands back
the play so far and a kept session would only be that history twice.

Three things follow, all good. A crash loses nothing, because no context was the only copy of
anything. Each role can run on a different CLI or model. And anything worth remembering must be
written into state, where the save keeps it.

**Spawn cost is verified.** A session's spawn count and token spend were measured against a real
subscription and are acceptable. This is recorded because the whole design rests on it.

### The spawner

One helper serves all three: it builds a prompt in our code, runs a one-shot CLI, and validates
what comes back.

```python
class Spawner(Protocol):
    async def run[T](self, role: Role, prompt: str, expect: type[T]) -> T: ...
```

```
CliSpawner.run
  ├─ start the configured argv with the prompt as its last argument
  ├─ read its output under the role's timeout, killing the process group on abandon
  ├─ take the final assistant message: a JSON event stream for CLIs that emit one,
  │     the last fenced block otherwise — one small reader per CLI, not per role
  ├─ parse and validate against `expect`
  ├─ on a validation error, re-prompt once with that error
  └─ on a second failure, raise
```

Configured in `.env`, editable in the settings page:

```
ROLES__MASTER__COMMAND     = "codex exec --json"
ROLES__MASTER__TIMEOUT     = 300
ROLES__NARRATOR__COMMAND   = ""      # empty reuses the master command
ROLES__NARRATOR__TIMEOUT   = 120
ROLES__WORLDSMITH__COMMAND = ""
ROLES__WORLDSMITH__TIMEOUT = 600
```

- **The app controls each spawn's environment**, because all three are its own children, never
  nested inside one another.
- **Every role has its own timeout.** The worldsmith writes a whole scene and is slow; the
  narrator writes four sentences and is fast.
- **Failure is loud.** A spawn that fails or returns nothing valid fails its step. The turn does
  not commit, the scene does not change, and the page says why. Nothing falls back to a role
  that saw hidden canon.

`harness/exec.py` already spawns a CLI, streams its output and kills the process group; that is
the machinery this reuses.

### 1.1 The narration boundary

The text the player reads is built from `NarratorView` — a type with no field that can hold
hidden canon — and reaches the page without passing through the game master.

```
  ├─ view   = kit.narrator_view(draft)
  ├─ prompt = render_narrator(view, told_facts, recent_passages, action)
  ├─ lines  = spawn(narrator, prompt, Narration)
  ├─ validate: every speaker_id is in view.speakers
  └─ record and commit
```

Held by **type, by process, and by surface** at once. Continuity comes from the last few told
passages, which the player has already read, so they leak nothing.

**Output shape.** `Narration{lines: [{speaker_id, text}]}` as JSON, with the spawner's one
retry. Structured lines are what let the transcript draw named, iconned bubbles, which is the
difference between a game and a log. Plain prose is the recorded fallback if parsing proves
unreliable.

### 1.2 The turn, precisely

`GameService.play(action)` owns the turn. The MCP tools are what the game master calls *inside*
it.

```
play(action)
  ├─ turn = Turn.begin(state.draft(), action)
  ├─ spawn the game master against `turn`; every call is trial-validated, then applied
  ├─ the spawn's exit ends the turn
  ├─ narrate, unless a decision is pending and no told fact landed
  ├─ record, commit, start the illustration
  └─ cross over, if the player pressed MOVE ON
```

- **The exit is the only end signal.** There is no `end_turn` tool. A CLI that crashes, is
  compacted away or simply stops is not a failure if it applied legal changes — those changes
  are the turn. Only a turn that applied nothing is refused, and the draft is dropped.
- **A pending decision stops the turn early.** Remaining tools are refused with the decision's
  text. The turn commits, the page shows the decision, and the player's answer opens the next
  turn. The narrator runs only if a told fact landed, so a bare decision shows buttons and no
  prose.
- **`next_scene` does not end the turn, and does not write.** It sets `SceneState.settled`, and
  the page grows a **move on** button beside the composer. The scene stays playable. When the
  player presses it, *that* turn starts the worldsmith on a **deep copy taken as it began**, never
  the live state, and awaits it at the end of the same turn — so a scene never installs under an
  action written for the scene before it. A turn that dies cancels its own write.

---

## 2. The world kits

The engine chooses one world kit. The scene kit makes a player's sentence the brief for the next
place; the rooms kit makes an authored graph the space the player explores. Shared entities and
views do not erase the distinction between those world models.

### The scene kit

A scene, not a location, is the unit of the scene kit's world.

### State

```python
class Scene(Frozen):
    id: Slug
    place: Slug                          # names the art; reused when the story returns here
    title: str
    question: str                        # public: what this scene exists to settle
    situation: str                       # what is true here now, for the game master
    present: tuple[EntityId, ...]        # everyone and everything here and known
    hidden: tuple[EntityId, ...]         # here, not yet found
    secret: str = ""                     # what `question` does not say; never in a view

class SceneState[S](Mutable):
    cast: dict[EntityId, Entity[S]]      # persists across scenes; sheet: S | None
    played: tuple[Scene, ...]
    current: Scene
    threads: dict[Slug, Thread]
    companions: list[EntityId]
    player_id: EntityId
    source: str = ""
    settled: bool = False                # the way on is offered; the scene is still playable
```

`Entity` keeps `id`, `kind`, `name`, `brief`, `description`, `known` and `traits`, and gains
`sheet: S | None` and `carried_by: EntityId | None`. It loses `exits`, `parent_id` and
`when_reached`.

**`place` is why art still caches.** Scene ids are unique, so keying the image on the scene
would redraw every time. The worldsmith names the `place` and reuses an existing one when the
story comes back to it, so returning to the chapel reuses the chapel's picture. Portraits
already cache per entity. A genuinely new place costs one image; that is the expected cost of
illustration, which is optional and needs its own key.

### Where a thing is: one field, two kit readings

- In the **scene kit**, **carried** is `carried_by` and **here** is membership in
  `current.present`.
- **Dropping** clears `carried_by` and leaves the item in `present`. It is lying here.
- **When a scene closes, what the player and companions carry comes with them.** Everything
  else stays behind.
- **Nothing is lost.** The worldsmith gets the whole cast, and code computes each entity's last
  known place by scanning `played` backwards for the scene that held it. Come back to the
  chapel and the worldsmith can put the dropped lantern back on the floor.

Left behind is good fiction, not a bug. No `at_scene` field, no loose-item pool.

### The rooms kit

Rooms are an authored map for engines whose procedures need real routes. A place is a shared
`Entity` with kind `place`; `RoomWorld.ways` stores directed `Way(to, known, locked)` entries on
the world, not on entities. A two-way passage is two directed ways, so one-way and asymmetric
locks remain expressible.

Every non-place entity is held by an actor or a place through `carried_by`; places are held by
nothing. Holder chains cannot cycle. The player is an actor held by a place, and companions travel
with the player. `move` can traverse any unlocked way out of the current place, including an
unknown way; arrival reveals the destination and the return way. `unlock_way` clears a lock.

The map authoring bar requires a loop, a shortcut, a locked way and hidden content, and every place
must be reachable from the start by a directed walk (including through unknown or locked ways).
`frontier` counts unknown places reachable from known places. Extending a map adds an authored
region and joins it to the existing graph; it is not a scene crossing.

### `change_world` — one tool, one call, one change

`verb` picks the arm: `reveal`, `enter`, `leave`, `move_item`, `improvise_item`, `add_trait`,
`remove_trait`, `kill`, `join_party`, `leave_party`, `advance_thread`. Deterministic
consequences run inside the arm.

**Measured** (probe, §10): 11 arms in **5,479 bytes**, against the map version's 10 arms in
5,926 — one more verb in less schema, because no arm carries placement or exit reasoning. Over
five turns a real CLI made **0 invalid and 0 refused** calls. The arms are not the risk.

### The question ends the scene; the player chooses what follows

Every scene carries one public `question`: what it exists to settle, in a sentence the player
reads. The game master plays until it is settled — answered, refused, or made moot — and that
judgement is the boundary. Play proved the alternative: a computed boundary that counted props
ended the scene the turn the player found the one thing hidden in it, which punishes them for
playing well.

`scene_spent(state) -> str | None` survives as a safety net only, for the cases no reading of
the fiction can miss:

| signal | reason |
|---|---|
| a rule wrote `spent` — a thread resolved, a conflict settled | the engine says so, where it knows |
| an actor present died | someone here is dead |
| turns in this scene passed a cap | the safety net |

When it fires, the turn result appends a `NOTES FROM THE RULES` line. It is never appended on the
turn a scene opened, or the note would describe the scene the player has just left.

**`next_scene` offers; it does not decide, and it does not stop play.** It takes no arguments and
sets `SceneState.finished`. The narrator closes the scene and asks what the player wants to
pursue; the page then shows one box with two buttons — **send** keeps playing here, **move on**
leaves. It is deliberately not a `PendingDecision`: a decision blocks the game master's tools and
forces an answer, and the player may well have things left to try. The scene stays open until
they say where they are going, and that sentence is the worldsmith's whole brief.

No menu of destinations. It is a smaller world than the sentence the player would have written,
and the threads panel is already the standing list of what is open.

**`question` is public, `secret` is not.** The question is what the scene exists to settle, written
for the player. The secret is what the question does not say: how it settles, what it costs, or
what somebody here will not admit. A secret that restates the question is a wasted field.

---

## 3. Content: characters, scenarios, growth

Content the **player** chooses is a page. Content the **story** invents is the worldsmith. There
is no batch authoring agent and no draft object.

### Characters — a page

One form: a name, a brief, a concept, and picks from the selected pack. The engine supplies the
options; the page renders them. The per-engine step-machine (`PackCreation`, nested
`CreationStep` trees) goes — with one engine it is a flat form.

### Starting a game — a page and one worldsmith call

The home page offers a scenario and a character. "New scenario" is a small form: packs, a title,
and either a premise or an uploaded `.md`, `.txt` or `.pdf`.

1. The app reads the source to text — de-hyphenated, passages joined, capped — or takes the
   premise.
2. It builds the selected kit's worldsmith prompt with no history and no cast.
3. `spawn(worldsmith, prompt, kit-specific draft)` returns the authored opening world.
4. The app validates the kit's authoring bar, writes `scenarios/<id>/world.json`, copies the
   source beside it, and opens the game at turn zero.

```
scenarios/<id>/
  world.json      envelope { meta, engine, packs, art_style, payload }
                  payload  { kit-specific world, cast, threads, source }
  source.md|.pdf  optional
```

### Continuing the world — kit-specific authoring

The game master briefs; the worldsmith writes. The scene kit authors the next scene at its
boundary. The rooms kit authors a new region only when its authored map has no reachable frontier.

#### Scene kit growth

**Growth is not a mode. It is the scene boundary.**

```
next_scene()
```

That is the whole signature. The player answers the question it raises, and their sentence — not a
lead, not a reason string — becomes `intent`. Code resolves the rest:

```
  prompt = render_worldsmith(
      source    = the adventure text, whole
      played    = every scene: its place, situation, and what happened in it
      cast      = every entity: name, brief, traits, sheet, and where it was last seen
      threads   = status and private note on each
      packs     = the selected pack tables
      guidance  = the engine's authoring_guidance
      intent, include
      …and one standing instruction: surprise the player. Turn an established fact
      against them, or bring back something they have stopped thinking about. Surprise
      by recombining what exists, never by inventing what the source would not hold.)
```

**Packs belong in this prompt.** They are the setting's vocabulary — which skills, gear and
frailties this world uses. The source document is the *adventure*; the packs are the *setting*.
Without them the worldsmith writes fantasy tags into a cyberpunk game. They are dumped with
defaults excluded, so the cost is small.

Why this shape:

- **The game master's context stays clean.** The source, the whole cast and every past scene
  never enter its window. Its job stays small: play the turn, judge when a scene ends.
- **Code owns the material.** What the next scene is written from is a function of state, not
  something an agent assembles or forgets.
- **The source goes over whole**, into a fresh context, so the cap that already swallows a
  76-page adventure is not competing with twenty turns of play.
- **Same spawner as narration.** One mechanism, three uses, one failure rule.

### A scene change is slow. Start it early, then make it a beat.

**Measured: 335 seconds** (probe, §10). No prompt trick removes it.

1. **The write starts as the answering turn begins**, and is awaited at its end. The turn the
   player spends leaving is the wait, and it is spent inside the fiction.
2. **Never speculate.** An earlier design started the write when `scene_spent` fired, using the
   reason string as a stand-in intent. It hid the latency in the only case where latency did not
   matter, and let a diagnostic sentence author the story. A visible wait for a place the player
   named beats an instant arrival somewhere they did not.
3. **Make the remainder a beat.** The crossing is its own segment: the worldsmith spinner, then a
   second narrator spawn that writes the leaving and the arriving.

#### Rooms kit extension

When `frontier` is exhausted, the page offers the player a brief. The worldsmith writes a complete
new region with places, ways and hidden content; code joins it to the existing graph and validates
the whole map. The player stays where they are, with no arrival narration: an extension is not a
scene crossing.

### Ids are the worldsmith's failure mode

The probe's scene was good and still broke on one thing: it wrote `kael` where the id is
`player`. Three defences, in order:

1. **The worldsmith never names the player.** Code puts them in every scene.
2. **Unknown ids resolve by name** — a case-insensitive match against one cast member's name.
3. **Then the spawner's one retry**, with the unknown id named in the error.

A refusal that costs five minutes must be the last resort.

### The scene bar

Every scene must pass four checks before it is installed:

1. A situation of real substance, and at least one cast member besides the player.
2. At least one standing thread touched, opened or resolved.
3. At least one existing cast member brought back — after the opening.
4. When a source exists, a detail traceable to it.

Those are the failure signatures of railroading. A scene that misses one is re-prompted with the
reason, once, then refused. A validation rule that runs on every scene forever is worth more
than a test suite that runs when someone remembers.

---

## 4. The MCP surface

What the **game master** sees, served from the running app so the spawned CLI talks to the live
game rather than a save file.

| tool | purpose |
|---|---|
| `start_turn` | opens the turn; returns the whole picture |
| `scene` | the same picture again, after a compaction |
| `change_world` | one settled change; `verb` picks the arm |
| `next_scene` | say the scene's question is settled, so the player is asked what to pursue |
| *engine tools* | one per SRD procedure, never more than eight |

Four fixed tools plus the engine's. There is no `end_turn`: the process exiting is the signal.

Everything the player chooses — opening a game, making a character, restarting, answering a
decision — is a page control. The game master plays; it does not administer.

No tool hands the game master the source, the full cast, or the scene history in bulk. That
material goes to the worldsmith, in its own process.

**Transport.** MCP over localhost HTTP, mounted on the server the app already runs, with two
proven fallbacks behind it: an in-process SDK server where the CLI offers one, and a stdio
server otherwise. All three keep the app the only writer, because the spawns are sequential.

### Tool legality

| | `start_turn` | `scene` | engine tools · `change_world` | `next_scene` |
|---|---|---|---|---|
| no turn open | yes | yes | no | no |
| turn open | no | yes | yes | yes |
| turn open, decision pending | no | yes | `change_world` only | no |
| game over | no | yes | no | no |

A refused call says what to do instead. A pending decision is answered by the player on the
page; the next turn carries their answer.

---

## 5. The pages

### What the pages read

Two types the kit fills. The page imports neither the engine nor the kit.

```python
class Subject(Frozen):
    id: str; name: str; brief: str

class NarratorView(Frozen):        # no field can hold hidden canon
    place: Slug                    # names the art cache entry
    title: str
    situation: str                 # the public shape of the scene, never Scene.note
    art_prompt: str
    subjects: tuple[Subject, ...]  # who to draw, player included
    speakers: tuple[Speaker, ...]  # who may be given a line; nobody else

class PlayerView(Frozen):
    player: Subject
    sheet: tuple[tuple[str, str], ...]      # the engine's own rows, via one callback
    carrying: tuple[Subject, ...]
    present: tuple[Subject, ...]
    companions: tuple[str, ...]
    threads: tuple[tuple[str, str], ...]
    scenes: tuple[str, ...]                 # the breadcrumb
    prompt: PlayerPrompt | None
    over: str | None
```

The transcript reads `Exchange` from the save, not a view.

### The play page

```
┌───────────────────────────────┬──────────────────┐
│  SCENE ART  16:9              │  CAST            │
│  The Drowned Chapel           │  ◯ Mira   ◯ Rat  │
├───────────────────────────────┤  ◯ Kael (you)    │
│  › I edge along the wall      ├──────────────────┤
│  ┌ Chance d6=5  Risk d6=2 ─┐  │  SHEET           │
│  │ Mira: Luck -1 → 3/6     │  │  Luck  3/6       │
│  └─────────────────────────┘  │  skills: …       │
│  ◯ Water closes over your…    │  carrying: …     │
│  ◉ Mira: "Don't stop now."    ├──────────────────┤
│                               │  THREADS         │
│  [ What do you do? ______ ]   │  • the bell      │
└───────────────────────────────┴──────────────────┘
   scene 4 · ‹ 1 2 3 [4] ›              scene│journal│dev
```

- **The transcript** is the record: the action, the cards and dice the rules produced, then the
  narrator's lines as named bubbles with portraits.
- **The dice cards** are why this beats a chat app: visible proof that code rolled.
- **The right column**: scene (cast, sheet), journal (threads, chronicle), dev (raw stdout).
- **Decisions** are answered here, as buttons or in the player's own words.

### The home page

Saves to resume, and the forms to start one.

### The settings page

It reflects over the `Settings` model — walking the fields, rendering each by type, writing one
`.env` key per box — so a new setting appears for free. A key set in the shell is shown as such
and left alone, a cleared box restores the default, a stored secret is never read back, the
model is revalidated before writing, and saving applies live. It is where the player points the
three roles at their CLI.

---

## 6. The engine seam

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Engine[G: Game[Any]]:
    id: EngineId
    title: str
    instructions: str
    packs: tuple[DecisionOption, ...]
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    guidance: Callable[[Sequence[Slug]], str]
    world_tools: tuple[MasterTool[G], ...]
    tools: tuple[MasterTool[G], ...]
    creation_steps: Callable[[Picks], tuple[CreationStep, ...]]
    create_character: Callable[[str, str, Picks], AnyCharacter]
    preview_character: Callable[[AnyCharacter], Rows]
    validate: Validate[G]
    new_game: Callable[[AnyScenario, AnyCharacter], BaseModel]
    entity_known: Callable[[G, EntityId], bool | None]
    record: Callable[[G, str, tuple[SpokenLine, ...], Sequence[Fact]], tuple[str, ...]]
    history: Callable[[G], tuple[Exchange, ...]]
    master_sections: Callable[[G], Rows]
    narrator_view: Callable[[G], NarratorView]
    player_view: Callable[[G], PlayerView]
    over: Callable[[G], str | None]
    authoring: Authoring
    crossing: Transition[G] | None
    extension: Transition[G] | None
```

`Engine` is the extension point joining an engine's typed game to its chosen world kit. The
engine owns its sheet union, state and SRD mechanics; the kit supplies `world_tools`, entity
knowledge, recording, history, views and world authoring. `crossing` belongs to the scene kit and
may be absent; `extension` belongs to the rooms kit and may be absent.

Both are one `Transition`, a record of `ready`, `write`, `install` and an `arrival_brief`. They were
two identical records once, and the wiring above them duplicated with them; what actually differs is
the behaviour in the callables, not the shape holding them. A scene crossing moves the player and
narrates the arrival, so it supplies a brief; a map extension installs latent places and leaves the
player standing, so it supplies none. The app reads `Engine.crossing` and `Engine.extension` to know
which it holds, and never inspects a kit.

`world_tools` are published with `TURN_TOOLS` and the engine's mechanics tools. Scene engines put
`change_world` and `next_scene` there; rooms engines put `change_world`, `move` and `unlock_way`
there. `tools` therefore contains engine procedures only.

`AnyEngine` is the erased alias beside `Engine` in `engines/core.py`; the registry and per-engine
composition return with the second engine. `core/`, `turn/`, `app/` and `ui/` consume callbacks
through this seam and import neither concrete engine nor concrete kit.

The save payload is an engine-specific `Game` model. Its `EngineHeader` rejects a save for the
wrong engine before the concrete game validates it; there is no compatibility or migration path.

The untyped `mechanics` blob and everything servicing it — parse-on-entry, write-back, one-level
merge, delta, keyed-map cleanup, stray-id checks — is deleted.

---

## 7. What is kept, and what is deleted

**Kept, and load-bearing:** the model proposes and Python decides, with trial-validate then
apply; `Fact` with its `trace`/`told`/`card`/`dice` split; strict Pydantic at every boundary and
no save migration; scene art, portraits, named bubbles, dice cards, decisions; the save,
scenario and character envelopes.

**Deleted now:**

| | src |
|---|---:|
| 24XX and Breathless engines, returning later | −1,702 |
| `world/` map ontology → `kits/scenes/` | −544 |
| `authoring/` batch author, draft and patch machinery | −479 |
| the harness split: external mode, save polling, three drivers, stdio entry point | −466 |
| `ui/`: authoring chat page, launcher form, raw-state panel, per-CLI event parsers | −527 |
| in-app model agents; prompt building kept and extended | −233 |
| mechanics blob seam, payload shim, `AnyEngine`, registry, `PackCreation` | −350 |
| **`PlayerAction`** — two actions exist, both Breathless; returns with it | −80 |
| **succession** — 170 lines and a permanent transcript tax for one edge case; death ends the game | −80 |
| **`resolvers`** — a second hidden tool list; folded into `tools` with a legality flag | −25 |
| **`grows`** — every scenario grows now | −5 |
| `llm.py`, role model config, `content/model.py` | −91 |
| `evals/` | (1,817, its own tree) |

**Evals go.** They measured a weak model against the tool surface; the roles are frontier CLIs
now. Their job — catching a world that plays badly — passes to the scene bar, which runs on
every scene instead of on request. Cheap to write again if a small-model target returns.

### Staying testable offline

Removing the in-process agents removes `FunctionModel`'s guarantee, so **the spawner is a
protocol with one real and one fake implementation**, injected from the composition root.

- `CliSpawner` is the only thing in the codebase that starts a process. No test constructs it.
- `ScriptedSpawner` answers from a per-role queue and **records every prompt it was given**. That
  recording is what the boundary tests assert on: a golden of the narrator prompt is how "hidden
  canon cannot reach it" stays proven.
- The game master's fake plays a list of tool calls against the live MCP surface, which is what
  the golden-turn tests already do with a scripted model.

**Prompt files.** Everything under `world/prompts/` and each engine's `director.md` speaks the
map's vocabulary. They become four: a game-master brief, a narrator brief, a worldsmith brief,
and one short rules note per engine. The scenario-bar and extension prompts are deleted.

**Dependencies.** `pydantic-ai` leaves `pyproject.toml`. Two small replacements: a JSON-schema
generator that inlines `$defs` (~20 lines, checked against the current schema fixtures), and
`ModelRetry` becoming a plain `ValueError`.

---

## 8. Arithmetic

Base: **9,452** `src`; 6,044 `tests`; 1,817 `evals`.

| item | src |
|---|---:|
| 24XX + Breathless deleted (`236+534+430+502`) | −1,702 |
| `engines/core.py` 483 → ~250 (seam, `sheet_of`, `PackCreation`, `PlayerAction`) | −233 |
| `registry.py` and `AnyEngine` | −45 |
| `world/` 1,044 → `kits/scenes/` ~500 | −544 |
| `authoring/` 569 → ~90 source reader | −479 |
| `harness/` 836 → spawner ~120 + MCP ~250 | −466 |
| `turn/` 433 → ~200 prompt builders and `Turn` | −233 |
| `ui/` 1,557 → ~1,030 | −527 |
| `state/` shim, `_legacy`, succession, `Scene` to the kit | −220 |
| `llm.py`, role config, `content/model.py` | −91 |
| spawner protocol, fake, timeouts, retry | +120 |
| `render_worldsmith`, the scene bar, `scene_spent` | +160 |
| MCP legality, scene tools, `place` handling | +100 |
| **net** | **≈ 5,290** |

Range **4,900 to 5,600**. Tests fall to about **2,800**; evals to zero. Each engine added back
costs about **500** on the new design — no blob, no map impedance, one flat creation form.

Rules: every phase records `src` and `tests` before and after; a phase over its own estimate
stops and re-scopes; each phase leaves the game playable from the browser; no phase leaves two
implementations of one concept; goldens regenerate once per phase and every diff is read.

## 9. Acceptance tests

1. **The narration boundary holds by type.** Only `NarratorView` reaches the prompt builder, and
   a golden proves a hidden entity's name cannot appear in it.
2. **The prose never passes through the game master.** No tool result it receives holds the
   narrator's lines, the source, the full cast, or the history in bulk.
3. **A failed spawn refuses.** A dead narrator leaves the turn uncommitted; a dead worldsmith
   leaves the scene unchanged; each says why.
4. **A game master that exits without finishing still commits** what it legally applied, and one
   that applied nothing is refused.
5. **Loner 3e plays** end to end from the page: type, see cards and dice, read the prose, and
   the save validates.
6. **The scene bar catches a thin scene**, and a scene ends when the player presses **move on**
   — never under an action written for the scene before it, and never for a dead player.
7. **A worldsmith id slip recovers** without a retry: a name resolves to its id, and the player
   is injected by code.
8. **A dropped item comes back.** Left in scene 2, brought back by the worldsmith in scene 5,
   with its identity intact.
9. **`place` caches art.** Two scenes sharing a `place` share one image.
10. **A source document becomes a game.** Upload a `.pdf`, play five scenes, each drawn from it.
11. **The settings page round-trips** a switch, a select, a number and a secret.

## 10. Order of work

**A — the scene-kit probe. DONE. The kit is approved.**

| measured | result |
|---|---|
| `change_world` schema | 5,479 bytes, 11 arms (map: 5,926 / 10) |
| schema-invalid calls in 5 turns | **0** |
| rule-refused calls in 5 turns | **0** |
| threads advanced / `next_scene` called at the boundary | **0 / no** — fixed by `scene_spent` |
| worldsmith scene quality | strong: a complication straight from the source, two existing cast brought back, the secret kept, a private note with a real cost |
| worldsmith latency | **335 s** |
| worldsmith id errors | 1 — wrote the player's name for their id |

Verdict on the open question: **alive, not railroaded.** The four constraints did their job.

**B — the `SceneState[S]` spike.** Half a day, before the port. A generic, a discriminated sheet
union and a discriminated payload, round-tripped through the save envelope and back. This is the
riskiest unestimated piece; prove it in isolation.

**C — cut to one engine.** Delete 24XX and Breathless with their tests, packs, characters and
scenarios; delete `PlayerAction`, succession, `resolvers`, `grows`, `AnyEngine` and the registry.
Loner 3e still plays on the map. This is a clean, self-contained deletion phase.

**D — the scene kit and the port.** `kits/scenes/`: state, arms, `scene_spent`, the worldsmith
prompt, the scene bar, the views, the source reader. Port Loner onto it. Delete `world/`, the
mechanics seam and the payload shim.

**E — the three spawns.** The `Spawner` protocol, `CliSpawner`, `ScriptedSpawner`, timeouts, the
retry. `render_narrator` with continuity, `render_worldsmith`, speaker validation, loud failures.
Wire `play()` to game master → narrator → commit, and the boundary to the snapshot worldsmith.
Delete the in-app agents, `llm.py`, the role model config.

**F — the surface.** The MCP endpoint serving the live service, four fixed tools, the legality
table. Delete external mode, save polling and the drivers.

**G — the pages.** The play page with the transcript, the new-scenario form, the flat character
form, the trimmed settings page.

**H — the sweep.** Delete `evals/`. Drop `pydantic-ai`. Rewrite `README.md` and `CLAUDE.md`. Grep
every deleted name.

**I — the engines return.** 24XX, then Breathless, each rewritten on the new design from its SRD
notes in `docs/`. Breathless brings `PlayerAction` back with it. The second engine restores
`AnyEngine` and the registry.

## 11. Recorded, not scheduled

- **A narration-against-facts check.** Nothing verifies the prose matches the record. Worth one
  narrator retry on a contradiction, once the surface settles.
- **Scene summaries**, if long games show the worldsmith losing the thread.
- **A persistent worldsmith session**, if continuity across scenes proves thin.
- **Plain-prose narration**, dropping bubbles, if JSON parsing proves unreliable.
- **Lower reasoning effort or a chunked source** for the worldsmith, if 335 s still drags.
- **Succession**, if losing your character to a companion turns out to be missed.
- **A small-model target**, which would need a tool-accuracy suite over the MCP surface.
- **Multiplayer, save migrations, a database, event sourcing, undo.** No.
