# PLAN: a smaller core

This file is self-standing; a
session needs nothing else.

## End state

- `src/aidm/state/` + `engines/core.py` is the core. It knows `Entity`, `WorldState`, `Game`,
  `Fact`, `DiceEvent`, `PendingDecision`, threads, `DirectorTool`, draft/commit, the turn loop,
  `render_director`/`render_narrator`, and one opaque `WorldState.mechanics` blob.
- `src/aidm/world/` is the rooms module: move/reveal/kill/traits/exits/party actions, the 10
  rooms Director tools exported one by one, succession, the rooms authoring bar, growth
  trigger, and the rooms prompt fragments. A non-rooms engine imports nothing from it.
- Every engine owns its mechanics in one typed model parsed from `mechanics`, its own
  chapter/advance code, its Director prompt (tool names included), its prompt sections, its
  `validate`, its `over`, its authoring brief.
- A pending decision is a deferred tool call. Facts are two strings plus typed dice; cards are
  derived from told facts.
- A character is one JSON file per (character, engine) under `characters/<id>/<engine>.json`.
- The turn trace is gone; evals keep their own.

Invariants that hold in every step:

1. The model proposes; Python decides. Tools return typed proposals; resolver code mutates.
2. The Narrator sees only revealed canon: `VisibleScene.revealed_from` refuses any listed id
   that is not known and carries only player text; `render_narrator` accepts only
   `VisibleScene`; `apply_to_draft` refuses a told fact about an unknown entity.
3. One pending decision at a time (`apply_to_draft` check).
4. `kill` is the only way to record a death: it drops what the dead carried and opens the
   succession decision, so `add_trait` refuses the reserved `dead` trait id.
5. Draft/commit round-trip: every mutation runs on `Game.draft()`, commit is
   `model_validate(model_dump())`. Dict writes on a `WorldState` skip validation; that is why.
6. Both harnesses (`turn/run.py` and `harness/codemode.py` + `harness/mcp.py`) share
   `render_director` and `Turn`. Never add a second turn loop.
7. The builtin loop commits every turn whole (`close_segment`); code mode commits per accepted
   tool call, and each commit is a legal state.

## Target shapes

All phases refer to these. Do not restate them in code comments.

### Facts and dice (`state/facts.py`)

```python
class DiceEvent(Frozen):
    label: str
    faces: tuple[int, ...]
    rolled: tuple[int, ...]
    result: str = ""                 # engine-computed: "5", "yes-but", "fail"
    highlight: tuple[int, ...] = ()  # indices into `rolled`; core checks range only
    # validator: len(rolled) == len(faces); 1 <= die <= face; highlight indices in range

class Fact(Frozen):
    kind: str
    trace: str                       # for the Director; names `name[id]`
    told: bool = False
    entity_id: EntityId | None = None
    card: str = ""                   # for the player; plain names, no ids, "" = no card
    dice: tuple[DiceEvent, ...] = ()

def roll(faces: Sequence[int], reason: str, rng: Random) -> tuple[tuple[int, ...], Fact]:
    """Fact(kind="dice_rolled", trace=f"{reason}: {_notation(faces)} [{shown}]")."""

def entity_fact(entity, kind, trace, *, narrate=True, card="", dice=()) -> Fact
def cards(facts) -> tuple[Fact, ...]      # told facts with card != ""
def traced(facts, *, told_only=False) -> str
def told_traces(facts) -> tuple[str, ...]
```

Rule: a fact about an unknown entity is never told (`entity_fact` sets `told = narrate and
entity.known`). Never construct a told `Fact` by hand for an entity that may be unknown.

### Decisions (`state/play.py`)

```python
class ToolCall(Frozen):
    name: str
    args: dict[str, JsonValue]

class DecisionOption(Frozen):    # unchanged: creation steps and every content pack hold this
    id: Slug
    label: str = Field(min_length=1)
    detail: str = ""

class PendingOption(DecisionOption):
    call: ToolCall               # applied when the player picks this option

class PendingDecision(Frozen):
    kind: Slug
    prompt: str = Field(min_length=1)
    options: tuple[PendingOption, ...]
    allows_text: bool
    # validator: option ids unique

class Exchange(Frozen):
    prompt: str
    scene: str                       # `Scene.label` at the time of the exchange
    lines: tuple[Line, ...]
    facts: tuple[Fact, ...] = ()     # told facts with a card
    decision: str = ""
```

`Game.turn_facts: tuple[Fact, ...]` replaces `Game.turn_events`. `Game.record(scene_label,
prompt, lines, facts)`; `close_segment` and `play_action` pass `engine.scene(draft).label`. Resume = clear `pending`,
find the tool by `option.call.name` in `(*engine.tools, *engine.resolvers)`, apply
`option.call.args` through `_apply`. `Engine.restored` checks every `option.call.name`
resolves to a tool or resolver and validates every `option.call.args` with that tool's
`args.model_validate`.

### Scene (`state/scene.py`, new)

```python
class SceneSection(Frozen):
    title: str
    player: str = ""
    director: str | None = None      # None means use `player`

class Scene(Frozen):
    key: str                         # media cache key
    label: str                       # history grouping, UI heading
    summary: str = ""
    sections: tuple[SceneSection, ...]
    public_entity_ids: frozenset[CheckedEntityId] = frozenset()
    present_entity_ids: frozenset[CheckedEntityId] = frozenset()
    prompts: tuple[tuple[str, str], ...] = ()   # button label, composer text
    art_prompt: str = ""
    art_subject_ids: tuple[CheckedEntityId, ...] = ()

class VisibleScene(Frozen):
    key: str
    label: str
    summary: str
    sections: tuple[tuple[str, str], ...]        # (title, player text)
    present_entity_ids: frozenset[CheckedEntityId]
    prompts: tuple[tuple[str, str], ...]
    art_prompt: str
    art_subject_ids: tuple[CheckedEntityId, ...]

    @classmethod
    def revealed_from(cls, scene: Scene, world: WorldState) -> "VisibleScene": ...
```

"Scene" is the current player-facing context, not a place. `revealed_from` has four rules:

1. Collect `public_entity_ids`, `present_entity_ids` and `art_subject_ids`.
2. Refuse if any id is absent from `world` or its `known` is false.
3. Copy only `SceneSection.player`; `VisibleScene` has no field that can hold `director`.
4. Return `VisibleScene`, never `Game`, `WorldState` or `Scene`.

Rule: entity-derived player text declares that entity in one of the id sets, as `entity_fact`
declares its entity. The rooms builder does this for every entity it names.

`world/scene.py:rooms_scene(describer, director_sections) -> Callable[[Game], Scene]` builds the
rooms projection: key = location id; label/summary = location name/brief; sections PLAYER, HERE,
EXITS, ELSEWHERE, hidden canon, placement, inventory and the engine's `director_sections`
(director-only); prompts = exits; art = place plus visible cast; present = player plus actors
here. It parses the blob once through `describer`.

### Core tools (`state/tools.py`, new)

```python
class NoArgs(Frozen): ...

@dataclass(frozen=True, slots=True)
class DirectorTool:
    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[Game, Mapping[str, JsonValue], Random], tuple[Fact, ...]]
    during_suspension: bool = False  # unchanged; the rooms tools export it True

def director_tool(name, description, args, resolve, *, during_suspension=False) -> DirectorTool

type Play = Callable[[Game, Random], tuple[Fact, ...]]
type Validate = Callable[[Game], None]

def apply_to_draft(validate: Validate, draft: Game, play: Play, rng: Random) -> tuple[Fact, ...]
    # keeps the 4-line "one decision at a time" check, refuses a told Fact whose
    # entity_id is not `known`, then validate(draft)
def transact(validate: Validate, draft: Game, play: Play, rng: Random) -> tuple[Game, tuple[Fact, ...]]
```

`state/threads.py` (new): `advance_thread(draft, AdvanceThread)` and the `ADVANCE_THREAD`
tool. Threads are core, so the tool is core.

### Entities and world (`state/entities.py`, `state/model.py`)

`Entity{id, kind, name, brief, description, when_reached, known, parent_id, traits, exits}`.
No `rules`. `Exit`, `Trait`, `DEAD` stay in `state/entities.py`: a field type cannot sit above
the model that holds it. `WorldState` gains `mechanics: dict[str, JsonValue] = {}`. Its
validator keeps only: id filed under its key, any `parent_id` names an existing entity, and the
parent chain is acyclic (walk `parent_id` until None; raise on revisit). `parent_id`, `exits`
and `party` stay in core as inert data; only a rooms engine gives them room semantics.
`_HOLDERS`, `check_placement`, `_check_exits` and `_check_party` move to
`world/topology.py:validate_rooms(world)` (holders: actor in location, item in actor or
location, location in nothing; known exits lead to places; party members are actors); every
rooms engine calls it from `validate`. `children`, `location_of`, `frontier`, `is_here`,
`player_location` leave `WorldState`/`Game` for `world/topology.py`; `Game.player_location`
and `Game.is_here` are deleted.

`Game{scenario_id, character_id, scenario, engine, packs (min_length=1), player_id, world,
turn_facts, history, turn, pending}`. No `"srd"` check anywhere.

### Mechanics blob

`WorldState.mechanics` is engine-owned JSON. Each engine defines one typed model and parses it
once per tool call:

```python
@contextmanager
def rules[M: BaseModel](world: WorldState, model: type[M]) -> Generator[M]:   # engines/core.py
    parsed = model.model_validate(world.mechanics)
    yield parsed
    world.mechanics = parsed.model_dump(mode="json")
```

Rules:
- Parse once at tool entry, write back once at exit, never nest `with rules(...)`. Pass the
  parsed object down to helpers.
- `Engine.validate` parses the blob and checks `sheets.keys() ⊆ world.entities` (and item
  sheets ⊆ items). A bad write is refused at the next `apply_to_draft`, with error path
  `mechanics.sheets.<id>.<field>: msg`.
- Engine models:
  - `Loner3eState{sheets: dict[EntityId, Sheet], twist: Counter(0..3), twist_pack: Slug}`.
    `Sheet` loses `twist` and `twist_pack`; keeps `chapters`, `milestones`.
  - `TwentyfourxxState{sheets: dict[EntityId, Sheet], items: dict[EntityId, ItemSheet]}`.
    `Sheet` keeps `chapters`, `jobs`.
  - `BreathlessState{sheets: dict[EntityId, Sheet], items: dict[EntityId, ItemSheet]}`.
    No `chapters`.
- A character's mechanics uses the same keys with the player sheet under `sheets.player` and
  item sheets under their item ids. `begin_game` builds the game's blob with
  `mechanics_merge(scenario_mechanics, character_mechanics)` (character wins on key clash,
  character scalars win). There is no `Engine.begin`: it would have one possible body.
- Core never reads inside the blob. `Engine.mechanics_merge(base, added) -> dict` and
  `Engine.mechanics_without(blob, entity_id) -> dict` are the only two operations on it, each
  parsing with the engine model; `aidm/world/` supplies nothing here.

### Engine (`engines/core.py`)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Engine:
    id: EngineId
    title: str                                    # "LONER 3E", "24XX", "BREATHLESS"
    instructions: str                             # Director prompt, tool names included
    tools: tuple[DirectorTool, ...]               # published to the Director and MCP
    resolvers: tuple[DirectorTool, ...] = ()      # deferred-decision targets only
    packs: Mapping[str, BaseModel]                # opaque provenance
    creation: CharacterCreation
    validate: Callable[[Game], None]
    scene: Callable[[Game], Scene]                # the one projection every consumer reads
    sheet_rows: Callable[[Game], tuple[tuple[str, str], ...]]
    mechanics_merge: Callable[[dict[str, JsonValue], dict[str, JsonValue]], dict[str, JsonValue]]
    mechanics_without: Callable[[dict[str, JsonValue], EntityId], dict[str, JsonValue]]
    player_actions: tuple[PlayerAction, ...] = ()
    over: Callable[[Game], str | None] = lambda state: None
    authoring_brief: Callable[[tuple[Slug, ...], WorldState | None, bool], AuthoringBrief]
    growth_due: Callable[[Game, int], bool] = lambda state, frontier: False

    def __post_init__(self) -> None: check_tool_names(self)
    def tool(self, name: str) -> DirectorTool | None   # searches tools, then resolvers
    def restored(self, raw: str) -> Game               # engine id, packs ⊆ self.packs, option calls resolve and their args validate, validate
```

Rooms engines register `scene=rooms_scene(describer, director_sections)`; their describer and
advance-section functions stay as plain functions in the engine module.

`check_tool_names(engine)` (one function in `engines/core.py`): names unique across `tools` +
`resolvers`. The clash with `harness/mcp.py:SERVER_TOOLS` and the authoring tools is refused in
`harness/mcp.py:offered`, the one place all three name lists are in scope; core holds no copy of
another layer's names.

Kept helpers in `engines/core.py`: `pool`, `adjust`, `spend`, `counter_fact`, `rules`,
`mechanics_of`, `mechanics_merged`, `keep_highest`, `stake_decision`, `sheet_of`, `check_packs`,
`party_member`, `ADVANCE_SPENT`, `describe_rows`, `CharacterCreation`, `PackCreation`,
`NamedPack`, `find_entry`, `load_packs` (no srd check), `PlayerAction`, `player_action`,
`offered`, `play_action` (returns `tuple[str, dict]` offers). The last group is engine
vocabulary that reads no engine model: `sheet_of` looks an entity up in a sheet map, and
`party_member` and `ADVANCE_SPENT` say who may take an advance.

Deleted from core: `rules_types`, `EntityRules`, `NoRules`, `SheetBase`, `describe_by`,
`checks`, `check_overlay`, `advances_owed`, `complete_chapter`, `chapter_tool`,
`ADVANCE_TOOL`, `ProposalBase`, `owed_notes`, `notes`, `Decision`, `Succession`, `decisions`,
`_decision`, `check_pending`, `resume`, `Offer`, `badge`, `CORE_TOOLS`. `during_suspension`
stays. `authoring_context` and `authoring_instructions` stay until 3.2 replaces them with
`authoring_brief`; deleting them at 2.6 would leave authoring with no guidance at all.
`Engine.check_overlay` becomes `Engine.character_mechanics(character) -> Mechanics`, which both
checks the overlay and shapes it into the blob; 3.1 deletes it with `Character.mechanics`.

### Authoring brief (`content/model.py`)

```python
@dataclass(frozen=True, slots=True)
class AuthoringTool:
    name: str
    description: str
    args: type[BaseModel]
    apply: Callable[[WorldState, Mapping[str, JsonValue]], str]

@dataclass(frozen=True, slots=True)
class AuthoringBrief:
    bar_prompt: str                                  # text, not a file name
    guidance: str                                    # engine authoring text + selected pack JSON
    unmet: Callable[[Scenario], list[str]]
    settled: frozenset[str] = frozenset()
    tools: tuple[AuthoringTool, ...] = ()
```

`AuthoringBrief` moves from `authoring/draft.py` to `content/model.py` in 2.1 (fields as
today); 3.2 gives it this shape.

`Scenario{meta, engine, packs (min_length=1), grows, art_style, player_parent_id:
CheckedEntityId | None = None, world}`. `player_parent_id` replaces `starting_location_id`;
`begin_game` copies it to `player.parent_id`. Its validator keeps `_playable_canon` reduced to
core checks (the id exists when set) and loses `_every_location_reachable`; "it is a location"
is the rooms brief's rule.

### Character (`content/model.py`)

```python
class Character(Frozen):
    id: Slug                             # the folder name; begin_game, write_character, _resumable, open_media read it
    engine: EngineId
    name: str
    brief: str
    traits: tuple[Trait, ...] = ()
    items: tuple[Entity, ...] = ()       # kind item, parent_id == "player", known
    mechanics: dict[str, JsonValue] = {}
```

File: `characters/<id>/<engine>.json`; icons in `characters/<id>/icons/`. `Character.id` is
the directory name; `load_character` checks they match. `read_characters` lists a directory once per `<engine>.json` it holds.
`begin_game` builds the player `Entity` from name/brief/traits, adds the items, sets
`world.mechanics = engine.begin(scenario.world.mechanics, character.mechanics)`.

### World package (`aidm/world/`)

```
world/actions.py     reveal, move, kill, improvise, add_trait, remove_trait, unlock_exit,
                     join_party, leave_party, require_actor_here, reveal_target
world/topology.py    children(world, id, kind=None), location_of(world, entity),
                     player_location(state), is_here(state, entity), frontier(world),
                     validate_rooms(world). `walk(entities, start)` arrives with 3.2, its
                     first caller
world/scene.py       rooms_scene(describer, director_sections) -> Callable[[Game], Scene]
world/tools.py       REVEAL, MOVE, GAIN_IMPROVISED_ITEM, ADD_TRAIT, REMOVE_TRAIT,
                     UNLOCK_EXIT, JOIN_PARTY, LEAVE_PARTY   (DirectorTool each; no tuple),
                     kill_tool(validate)
world/succession.py  TAKE_OVER (resolver), succession_decision(state, validate), player_over(state)
world/authoring.py   rooms_brief(packs, base, opening, guidance), MIN_*, bar/opening/extend
                     unmet, reachability, connect, diff(base, draft, mechanics_merge) -> Play
world/prompts/       director_world.md, scenario_world.md, scenario_bar.md,
                     scenario_opening.md, scenario_extend.md
```

`LAYERS = ("state", "content", "world", "engines", "turn", "authoring", "app", "harness")`.

### Turn (`turn/run.py`)

```python
class Turn:
    def call(self, name, raw) -> str:
        found = self.engine.tool(name)
        if found is None or found not in self.engine.tools:
            raise ValueError(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = self.draft.pending
        if pending is not None and not (found.during_suspension and self.suspended_at_start):
            return waiting_text(pending)                # a plain answer, not a refusal
        ...
```

Keep this gate exactly as today: after a resume that re-suspends, rooms tools (`add_trait`)
land and engine mechanics (`roll_attempt`) answer "waiting on the player". `_apply` trials
against the throwaway copy with a copy of the turn rng (`copy.deepcopy(rng)`), never
`Random(0)`, so a roll-dependent branch draws the same numbers in both runs.
`render_director(scene: Scene, scenario, threads, prompt, *, resumed="", notes=())` renders
generic framing only: scenario, then every `Scene.sections` (director text, `player` when
`director` is None), then active threads, rules notes, and the player action LAST. The action
stays last because that is where the prompt puts it today and where the evals measured it; only
the section contents move, which is why the golden `prompts/*` are byte-identical. `render_narrator(scene:
VisibleScene, ...)` accepts nothing else. Two call sites: `Turn.picture` and
`Harness._picture`, both through `engine.scene(draft)`. `run_segment` returns `Game`; `Turn.finish(lines)`
returns `Game`.

## Verification

From the repo root with `UV_CACHE_DIR` unset:

```
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

"Full check" below means all four. Goldens: `AIDM_GOLDEN_REGEN=1 uv run pytest` rewrites
`tests/core/fixtures/**`; that run reports failure by design. Read every fixture diff with
`git diff tests/core/fixtures` before the next plain `uv run pytest`. Evals: only
`uv run python evals/turn_eval.py run --label <step> --case <name>` on named cases, never a
full run; `--label` is required by `run_command` and every `--case` below implies it.

---

## Phase 1: facts, dice, deferred decisions (items 5, 6)

Branch `core-slim`. Phases 1 and 2 share it. Do not regenerate goldens until step 2.7.
Until then, golden tests fail; run `uv run pytest --deselect tests/core/test_golden_turn.py
--deselect tests/core/test_golden_state.py --deselect tests/core/test_golden_prompts.py
--deselect tests/core/test_golden_schemas.py` (call this "pytest minus goldens").

### Step 1.1: `DiceEvent` and `roll`

Change:
- `state/facts.py`: `DiceEvent` per Target shapes. Delete the `kept` field and its check.
- `state/actions.py`: replace `roll_pool` with `roll` (Target shapes). Move it to
  `state/facts.py`. Delete `_notation` duplicates; keep one.
- Each `rules.py` and `twentyfourxx/engine.py:advance`: call `roll`, compute `kept =
  max(rolled)` locally, build `DiceEvent(label, faces, rolled, result=str(kept),
  highlight=(rolled.index(kept),))`. Loner `result` is the die value; outcome stays on the
  question fact. Breathless/24XX `result` is the die value too.
- `ui/game.py:_dice_group`: highlight `index in die.highlight`, not `value == die.kept`.
- `evals/turn_eval.py`: `tied_a_roll` compares `dice[0].result == dice[1].result`;
  `luck_die` reads `int(die.result)`.

Delete: `tests/core/test_dice.py::test_a_pool_keeps_its_highest_die_and_traces_every_one`
re-targets to: `roll` traces every die and `DiceEvent` refuses an out-of-range highlight.
Delete `dice.kept` asserts in `tests/loner3e/test_loner3e_events.py`,
`tests/twentyfourxx/test_twentyfourxx_events.py`, `tests/breathless/test_breathless_engine.py`.

Verify: pytest minus goldens, ruff, format, basedpyright.

### Step 1.2: `Fact.card`, delete `MechanicEvent`

Change:
- `state/facts.py`: `Fact` per Target shapes. Delete `MechanicEvent`, `EventBadge`,
  `player_events`. Add `cards(facts)`. `entity_fact` takes `card=""`, `dice=()`.
- `state/play.py`: `Exchange.events` → `Exchange.facts: tuple[Fact, ...]`.
- `state/model.py`: `Game.turn_events` → `turn_facts: tuple[Fact, ...]`; `Game.record(prompt,
  lines, facts)` stores `cards(facts)`; `Game.move` and `_move_summary` return
  `(trace, card)` strings. Fix the leak: in `_move_actor`'s NPC-leaves branch, when
  `not destination.known`, card = `f"{actor.name} leaves"`; trace keeps the id.
- `state/actions.py`: every `MechanicEvent(title=...)` becomes `card="..."`. `reveal`
  standalone card = `"{name} discovered"`. Party-follow facts: `card=""`.
- `engines/core.py:counter_fact`: `card = moved` or `f"{entity.name}: {moved}"`; drop `icon`
  parameters from `counter_fact`, `adjust`, `spend`.
- Each `rules.py` and `engine.py`: compose `card` text from the old `title`, `badges`,
  `outcome`, `effects` on one line each, e.g. Loner Oracle:
  `card = f"Oracle — {position}{edge} → {outcome.name}" + "\n".join(effects)`; attach `dice=`
  to the same fact. Delete `_badges` (both), `_absorbed` keeps only the "strip inner cards"
  half (set `card=""` on exchange facts).
- `turn/run.py`: `TurnRecord.events` → gone; `on_event` → `on_fact: Callable[[Fact], None]`
  called for every fact, told or not (`dice_rolled` facts are untold and evals score them);
  `landed` writes `draft.turn_facts = cards(self.facts)`. `close_segment(..., facts)`.
- `engines/core.py:apply_to_draft`: refuse any told `Fact` whose `entity_id` names an entity
  that is not `known` (one check, before `validate`).
- `app/runtime.py:submit`: `on_fact`. `ui/game.py`: `_mechanic_event(fact)` renders
  `fact.card` lines + `_dice_group` per `fact.dice`; `live_events` → `live_facts`;
  `on_event` → `on_fact`, showing only facts with `told and card`. `ui/theme.py`: drop
  icon/badge/outcome classes no longer used.
- `harness/codemode.py`: no change beyond names.
- `evals/turn_eval.py`: `player_outcomes` reads the outcome from the trace tail
  (`trace.rsplit("-> ", 1)[1]`) of kinds `attempt_resolved`, `check_resolved`,
  `question_answered`; `card_badge` → `card_says(result, text)` reads `fact.card`.

Delete: `tests/core/test_player_events.py` (whole file). `tests/core/test_store.py`
`EventBadge` use → build an `Exchange` with one told `Fact`. Badge/outcome asserts in
`tests/*/test_*_events.py`: delete; keep asserts on `fact.kind`, `fact.trace`, `fact.told`.
Add one test in `tests/core/test_actions.py`: an NPC leaving for an unknown location is told
with a card that names no destination. Add one in `tests/core/test_integrity_boundaries.py`:
a hand-built told `Fact` about an unknown entity is refused by `apply_to_draft`.

Verify: pytest minus goldens, ruff, format, basedpyright.

### Step 1.3: deferred decisions

Change:
- `state/play.py`: `ToolCall`, `DecisionOption.call`, `PendingDecision` without `payload`
  (Target shapes).
- `engines/core.py`: add `Engine.resolvers`, `Engine.tool(name)`. Delete `Decision`,
  `Succession`, `succession_decision`, `_takeover_refusal`, `decisions`, `_decision`,
  `check_pending`, `resume`. `apply_to_draft` keeps the one-decision check and drops the
  `check_pending` call. `restored` checks each option call resolves and
  `found.args.model_validate(option.call.args)` passes. Keep `take_over` as a plain function
  for now (it moves in 2.2).
- Core succession: `succession_decision(state, validate)` builds options with
  `call=ToolCall("take_over", {"successor_id": id})`; eligible = party member for whom
  `draft_refusal(state, lambda draft: apply_to_draft(validate, draft, take_over(...)))` is
  None, as `_takeover_refusal` does today (a sheetless NPC such as saint-ivo's Dov Marek is
  in the party but not playable). Declare `TAKE_OVER = director_tool("take_over", ..., TakeOver{successor_id}, ...)` in
  `engines/core.py`; every engine lists it in `resolvers` (it moves to world in 2.2).
  `allows_text=False`.
- `loner3e/rules.py`: delete `Conflict`; `resolve_question` sets
  `draft.pending = PendingDecision(kind="conflict", prompt=..., options=(), allows_text=True)`.
- `twentyfourxx/rules.py`: delete `StakedAttempt`, `Defence`, `resolve_stake`'s class use.
  `stake_attempt` tool takes `Attempt` and sets pending kind `"stake"` with one option
  `proceed → ToolCall("roll_attempt", attempt.model_dump(mode="json"))`. `Defence` becomes
  resolver `defend` with args `Defend{goal: str, item_id: CheckedEntityId | None}`; options:
  one per unbroken carried item and `take-it` with `item_id: null`. `resolve_defence` keeps
  its body.
- `breathless/rules.py`: delete `StakedCheck`, `Loot`. `stake_check` → option `proceed →
  ToolCall("roll_check", check.model_dump(mode="json"))`. Loot 9+ → two resolvers:
  `loot_item{actor_id, seeking, rating}` and `loot_med_kit{actor_id}`.
- `turn/run.py:consume_answer`: after picking `option`, `found = engine.tool(option.call.name)`
  (raise if None), apply `lambda copy, dice: found.call(copy, option.call.args, dice)` via
  `_apply`. `close_segment` keeps `succession_decision` for now.
- `harness/codemode.py:_waiting`: unchanged output; reads `option.id/label/detail` only.
- `ui/game.py:decision_panel`: unchanged (reads `kind`, `prompt`, `options`, `allows_text`).

Delete: `tests/core/test_decisions.py::
test_a_save_carries_a_decision_and_restore_refuses_one_the_engine_cannot_play` re-targets to
"restore refuses an option whose call names no tool or resolver, or carries args its tool
rejects". Other tests in that file
keep their names; update construction to `ToolCall` options.

Verify: pytest minus goldens, ruff, format, basedpyright.

### Step 1.4: resolvers are not Director tools; the gate stays

Change:
- `during_suspension` stays exactly as today on `DirectorTool` and the ten rooms tools;
  delete nothing in `Turn.call`'s gate.
- `turn/run.py:Turn.call`: look up through `self.engine.tool(name)`; resolvers are not
  callable by name from the Director: `found not in self.engine.tools` raises.

Delete/keep tests: `tests/core/test_code_mode.py::
test_an_open_decision_blocks_every_other_tool_until_it_is_answered` and
`test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused` stay as written;
they cover both sides of the gate. Add one: calling a resolver name from the Director raises.

Verify: pytest minus goldens, ruff, format, basedpyright.

---

## Phase 2: core/world split and engine ports (items 1, 2, 3, 4, 7, 8, 12, 15)

Same branch. `engines/registry.py:ENGINES` and `tests/core/test_package_boundary.py` import
every engine at module load, so no step may leave an engine unimportable: 2.3 adds the new
contract beside the old one, 2.4 and 2.5 port the other two engines, 2.6 deletes the old
contract. The full suite (minus goldens), ruff, format and basedpyright pass at the end of
each of 2.3 to 2.6; no `-k` exclusions.

### Step 2.1: `state/tools.py`, `state/threads.py`, `aidm/world/`

Change:
- New `state/tools.py`: move `NoArgs`, `DirectorTool`, `director_tool`, `Play`,
  `apply_to_draft`, `transact` from `engines/core.py`. `apply_to_draft` and `transact` take
  `validate: Validate` instead of `Engine`; callers pass `engine.validate`.
- New `state/threads.py`: `advance_thread` + `ADVANCE_THREAD`.
- New `world/actions.py`: the rest of `state/actions.py`. Delete `state/actions.py`.
- New `world/topology.py`: `children`, `location_of`, `player_location`, `is_here`,
  `frontier`, `walk` as functions. Delete the `WorldState`/`Game` methods (`Game.player_location`
  and `Game.is_here` included); delete `_walk` from `content/model.py` and
  `_every_location_reachable` with it (item 12). Update every caller (`turn/context.py`,
  `app/media.py`, `authoring/draft.py`, all `rules.py`).
- `state/entities.py` and `state/model.py`: move `_HOLDERS`, `check_placement`,
  `WorldState._check_exits`, `WorldState._check_party` to `world/topology.py:validate_rooms`.
  The `WorldState` validator keeps only keys, existing parents, acyclic chains. Each engine's
  `validate` calls `validate_rooms(state.world)`.
- New `state/scene.py`: `SceneSection`, `Scene`, the reshaped `VisibleScene` with
  `revealed_from(scene, world)` (Target shapes). New `world/scene.py:rooms_scene`, built from
  today's `SceneSnapshot.from_game` and `_scene_sections`. Nothing calls either until 2.3;
  `turn/context.py` keeps `SceneSnapshot` until 2.6.
- `turn/run.py:_apply`: the trial run uses `copy.deepcopy(rng)`, not `Random(0)`.
- `content/model.py`: `AuthoringBrief` moves here from `authoring/draft.py`, fields unchanged;
  `authoring/draft.py` imports it.
- New `world/tools.py`: the ten `CORE_TOOLS` entries as named constants, minus
  `ADVANCE_THREAD` (core). Delete `engines/world.py`. Each engine lists the tools it wants:
  Loner and 24XX all ten, Breathless all but `GAIN_IMPROVISED_ITEM`.
- New `world/prompts/director_world.md`: the "Use the world" section and every sentence of
  `turn/prompts/director.md` that names a tool (`move`, `reveal`, `add_trait`,
  `unlock_exit`, `join_party`, `advance_thread`). `turn/prompts/director.md` keeps the role,
  "Run the turn", "Use the dice" rules and the "rules wait" sentence, tool-free. Each engine
  builds `instructions = engine_text(world director_world.md) + "\n\n" + own director.md`
  for now (the field renames in 2.3).
- `tests/core/test_package_boundary.py`: `LAYERS` gains `"world"` after `content`.

Delete: `tests/core/test_integrity_boundaries.py::test_a_location_no_walk_reaches_is_refused`
and `test_scenario_topology_is_validated` (reachability). Keep
`test_world_and_game_state_reject_inconsistent_topology` re-targeted to the core placement
rules (missing parent, parent cycle) and `validate_rooms` (an actor inside an item, a known
exit to a non-place, a party member that is not an actor). Add one in `tests/core/test_scene.py`:
`revealed_from` refuses an unknown id in each of the three sets and drops `director` text.

Verify: pytest minus goldens, ruff, format, basedpyright.

### Step 2.2: succession and `over` (item 7)

Change:
- New `world/succession.py`: `take_over`, `TAKE_OVER`, `succession_decision(state, validate)`,
  `player_over(state) -> str | None` (`"You died."` when the player has `DEAD` and `pending
  is None`).
- `world/actions.py:kill` takes `validate`; when `actor_id == draft.player_id`, set
  `draft.pending = succession_decision(draft, validate)` (None when nobody can carry on).
  `world/tools.py:kill_tool(validate) -> DirectorTool` replaces the `KILL` constant; each
  engine builds it with its own `validate`.
- `engines/core.py`: add `Engine.over`; delete `take_over`, `TAKE_OVER`,
  `succession_decision` from core. Each engine: `over=player_over`,
  `resolvers=(TAKE_OVER, ...)`.
- `turn/run.py`: `close_segment` stops reading `DEAD`. `consume_answer`: replace the `DEAD`
  read with `if chosen is None and (ended := engine.over(draft)) is not None: raise
  ValueError(f"{ended} The only way on is to restart.")`.
- `ui/game.py`: `_alive` → `engine.over(state) is None`; `decision_panel` drops its `_alive`
  read (succession has `allows_text=False`). "You died." text comes from `over`.
- `engine.validate` refuses an unplayable successor at resume (Loner and Breathless already
  require a player sheet).

Tests: `tests/core/test_succession.py` re-targets to the world module; keep all four names.

Verify: pytest minus goldens, ruff, format, basedpyright.

### Step 2.3: new `Engine` contract beside the old, mechanics blob, port Loner 3e (items 2, 4, 8, 15)

Change (core):
- `state/model.py`: `WorldState.mechanics`. `Game`: no `"srd"` check; `packs` `min_length=1`.
  `content/model.py:Scenario`: same.
- `state/entities.py`: `Entity.rules` stays until 2.6 (24XX and Breathless still read it).
- `engines/core.py`: add the Target-shapes `Engine` fields (`title`, `instructions`, `tools`,
  `validate`, `scene`, `sheet_rows`, `begin`, `mechanics_merge`, `mechanics_without`) as
  optional beside the old `describer`/`director_sections`, `rules(world, model)`,
  `check_tool_names` (called from `__post_init__`); delete nothing from the "Deleted from
  core" list yet. `authoring_brief` may be a stub `lambda *a: AuthoringBrief(...)` until 3.2;
  keep `authoring_instructions` as a plain string until 3.2. `load_packs` drops the srd check.
  Old-contract call sites branch on "engine has `describer`" only where a shared path needs
  both (`begin_game`, `Turn.picture`); the branch dies in 2.6.
- `engines/registry.py:begin_game`: player entity has no rules; `world.mechanics =
  engine.begin(scenario.world.mechanics, character.mechanics)`. Until 3.1, read
  `character.rules` + `character.item_rules` into a temporary blob shaped like the engine
  model (`{"sheets": {"player": rules}, "items": item_rules}`); 3.1 deletes this shim.
- `turn/context.py`: `render_director(..., sections=())`; `entity_state(entity, describe)`
  unchanged. `turn/run.py:Turn.picture` passes `self.engine.director_sections(draft)` and
  `self.engine.describer(draft)`; notes are `self.notes` only. `run_segment` narrator path
  uses `engine.describer(draft)`. `Scene` is not consumed yet. `harness/codemode.py:_picture` same two changes; `rules()`
  uses `engine.instructions`; `BeginScenario.packs` default `()` meaning "first installed
  pack" resolved in `begin_scenario`. `authoring/run.py:scenario_run`,
  `authoring/draft.py:playtest_check`, `ui/create.py`: default = `next(iter(engine.packs))`.
- `ui/app.py`, `ui/widgets.py`, `ui/create.py`, `ui/game.py`: `engine.title` string; drop the
  colour. `ui/create.py` preview rows: `engine.sheet_rows` on a throwaway `Game`? No: add
  nothing; show `creation.create(...)` traits and item names only until 4.2.

Change (Loner 3e):
- `loner3e/rules.py`: `Loner3eState`; `Sheet` without `twist`/`twist_pack`. Every tool:
  `with rules(draft.world, Loner3eState) as game:` once at the top; `_strike`, `_refill`,
  `_twist` take `game` and the sheet they need; no nested `rules`. `_sheeted` writes
  `game.sheets.setdefault(item.id, Sheet())`.
- `loner3e/engine.py`: own `complete_chapter` tool and `advance` (about 30 lines, from the
  deleted core code); `validate` = parse blob, `sheets ⊆ entities`, every actor has a sheet,
  `twist_pack in state.packs`; `describer` parses once and closes over `game.sheets`;
  `sheet_rows`; `begin`; `director_sections` = `(("ADVANCES OWED", ...),)` when a party
  member's `chapters > milestones` and `pending is None`, else `()`;
  `scene=rooms_scene(describer, director_sections)`; `title="LONER 3E"`;
  `instructions` = world fragment + `director.md`; `tools` list the rooms tools, `ADVANCE_THREAD`,
  its own; `resolvers=(TAKE_OVER,)`; `over=player_over`.
- `loner3e/director.md`: add the tool-naming lines removed from the core prompt that Loner
  needs (`complete_chapter`, `advance`).
- `scenarios/whispering-vault/world.json`: move every `rules` into
  `world.mechanics.sheets.<id>`; add `twist_pack: "srd"`.
- `characters/kael/loner3e.json`: unchanged this step (shim in `begin_game`).

Delete: `tests/core/test_engine_contract.py` srd assert; `test_integrity_boundaries.py`
`test_scenario_packs_include_one_srd`, `test_an_engine_refuses_an_authored_payload_it_cannot_read`
re-targets to a bad `mechanics` write refused with path `mechanics.sheets.<id>.<field>`;
`test_a_rules_mutation_lands_on_the_commit_and_nowhere_else` re-targets to `mechanics`.
`core_test_support.py`: delete `at_boundary`, `sheet_of`; Loner tests read
`Loner3eState.model_validate(state.world.mechanics).sheets[id]` through a local helper in
`tests/loner3e/loner3e_test_support.py`.

Verify: pytest minus goldens; ruff; format; basedpyright.
Eval (after the step is green): `uv run python evals/turn_eval.py run --label step-2.3
--case loner3e/fight-the-rat` and `--case loner3e/twist-on-the-brink`.

### Step 2.4: port 24XX

Change:
- `twentyfourxx/rules.py`: `TwentyfourxxState`; `resolve_attempt`, `apply_change_credits`,
  `resolve_defence`, `resolve_luck_test` each open `rules` once; `_require_playable` and
  `_helper_sheet` take the parsed `game`. `_carried` dies: creation and `buy_gear` write the
  item sheet into `game.items[item_id]` when `bulky` or `breaks > 1`.
- `twentyfourxx/engine.py`: own `complete_chapter` and `advance`; `validate` = parse,
  `sheets ⊆ entities`, `items ⊆ items`, player has a sheet; `describer`; `sheet_rows`;
  `begin`; `director_sections` for advances owed; `scene=rooms_scene(describer,
  director_sections)`; `title="24XX"`; tools/resolvers
  (`TAKE_OVER`, `defend`); `over`.
- `twentyfourxx/director.md`: tool-naming lines it needs.
- `scenarios/drowned-road/world.json`: `rules` → `mechanics.sheets.<id>` / `mechanics.items.<id>`.

Tests: `tests/twentyfourxx/*` read the blob through a local helper; delete `sheet_of` uses.

Verify: pytest minus goldens; ruff; format; basedpyright.
Eval: `--label step-2.4 --case twentyfourxx/fight-the-wrecker`, `--case twentyfourxx/buy-the-vest`.

### Step 2.5: port Breathless

Change:
- `breathless/rules.py`: `BreathlessState`; `resolve_check` opens `rules` once and passes
  `game` to `_rolls` (both rollers); `resolve_loot`, `loot_item`, `loot_med_kit`,
  `apply_change_stress`, `apply_catch_breath`, `apply_use_med_kit`, `breathers`,
  `med_kit_holders`, `_party` read the parsed state. `_found` writes `game.items[id]`.
- `breathless/engine.py`: drop `chapters`; `validate` = parse, subset checks, player sheet,
  carry limit; `describer`; `sheet_rows`; `begin`; `scene=rooms_scene(describer, lambda
  state: ())`; `title="BREATHLESS"`; tools (no
  `GAIN_IMPROVISED_ITEM`); resolvers (`TAKE_OVER`, `loot_item`, `loot_med_kit`); `over`.
- `breathless/director.md`: tool-naming lines it needs.
- `scenarios/saint-ivo/world.json`: `rules` → `mechanics.sheets` / `mechanics.items`.

Verify: pytest minus goldens; ruff; format; basedpyright.
Eval: `--label step-2.5 --case breathless/risky-climb`, one loot case from `evals/turn_eval.py`.

### Step 2.6: delete the old contract

Change:
- `engines/core.py`: delete everything in the "Deleted from core" list; the new `Engine`
  fields become required. `state/entities.py`: delete `Entity.rules`. Delete the 2.3
  call-site branches.
- Switch every consumer to `Scene` in one step:
  - `turn/context.py`: `render_director` renders generic framing (scenario, threads, rules
    notes, player action) plus `Scene.sections`; `render_narrator` takes `VisibleScene` only;
    `player_scene(state) = VisibleScene.revealed_from(engine.scene(state), state.world)`.
    Delete `SceneSnapshot`, `_scene_sections`, the `Scene` union alias.
  - `turn/run.py`: `Turn.picture` and `run_segment` call `engine.scene(draft)`;
    `speakers_refusal` reads `present_entity_ids`; `close_segment` passes
    `engine.scene(draft).label` to `record`. `harness/codemode.py:_picture` same.
  - `ui/game.py:scene_header`: label, summary, sections, prompts as composer buttons.
  - `app/media.py`: `scene_key` = `Scene.key`; `illustration_request` reads `art_prompt` and
    `art_subject_ids` for likeness references.
  - `state/play.py`: `Exchange.place` → `scene`; `Game.record(scene_label, prompt, lines,
    facts)`; `engines/core.py:play_action` passes the label.
  - `content/model.py`: `starting_location_id` → `player_parent_id` (Target shapes);
    `registry.py:begin_game` copies it; the three `scenarios/*/world.json` rename the field.
  - Delete `Engine.describer`, `Engine.director_sections`, `Game.player_location`,
    `Game.is_here`.
- `grep -rn "srd" src/` shows only `loner3e/rules.py:SRD_PACK` (twist-table fallback).
- `grep -rn "MechanicEvent\|EventBadge\|CORE_TOOLS\|rules_types\|SheetBase\|EntityRules\|\.rules\b" src/`
  is empty.
- `grep -rn "SceneSnapshot\|starting_location_id\|player_location\|describer\|director_sections" src/`
  is empty except `world/scene.py:rooms_scene` parameters and `world/topology.py:player_location`.
- `tests/core/test_package_boundary.py` passes with `world` in `LAYERS`; no engine module
  imports another engine; `engines/core.py` imports nothing from `aidm.world`.
- `.claude/skills/playing-aidm/SKILL.md`: delete step 8 (advance-owed is an engine section
  now); renumber.

Verify: full check minus goldens; the full suite runs with no `-k`.

### Step 2.7: regenerate goldens once

1. `AIDM_GOLDEN_REGEN=1 uv run pytest` (reports failure by design).
2. `git diff --stat tests/core/fixtures` then read every diff: `prompts/*` (world fragment
   order, sections), `instructions/*`, `schemas/*/director_tools.json` (no resolver appears;
   no `during_suspension`), `state/*.json` and `save/*.json` (`mechanics` present, no
   `rules`, `turn_facts`, `facts` on exchanges, `scene` replacing `place`,
   `player_parent_id` replacing `starting_location_id`, option `call`s), `turn/*.json`.
   Section ordering changes under `Scene.sections`; turn behaviour does not.
3. A diff you cannot explain from a step above is a bug. Fix it and regenerate.
4. Full check. Commit the branch.

---

## Phase 3: characters and authoring (items 11, 9, 10)

### Step 3.1: one character file per engine (item 11)

Change:
- `content/model.py`: `Character` per Target shapes. Delete `CharacterProfile`,
  `CharacterOverlay`, `Character.rules`, `item_rules`, the overlay validator.
- `content/io.py`: `read_characters(directory, engines)` yields `(id, Character, engines
  written)` from `<engine>.json` files; `load_character(directory, id, engine)` reads one
  file and checks `character.engine == engine`; `write_character` writes one file. Delete
  `PROFILE_FILE`.
- `engines/registry.py:begin_game`: delete the 2.3 shim; use `character.mechanics`.
- Each engine's `creation.create` returns a `Character` with `mechanics` in the engine's own
  keys (`sheets.player`, `items.<id>`).
- `app/runtime.py:open_media`: icon lookup order "scenario dir first, then character dir";
  `icon_dirs` no longer enumerates `character.items`. `app/launch.py`: unchanged shape.
- `ui/create.py`: preview reads `character.traits`, `character.items`; engine sheet preview
  waits for 4.2.
- `characters/kael/`: delete `base.json`; rewrite `loner3e.json`, `twentyfourxx.json`,
  `breathless.json` as full `Character` files (each carries name, brief, traits, the lantern
  item, and `mechanics`). `icons/` stays.
- `authoring/run.py:_instructions`: the "player sheet" example JSON is
  `character.mechanics`.

Delete: `test_integrity_boundaries.py::test_an_overlay_names_only_gear_the_character_carries`;
`test_a_character_knows_the_gear_they_start_with` re-targets to `Character.items`.
`core_test_support.py:character()` deleted; `game()` uses `load_character(CHARACTERS, "kael",
engine.id)`.

Saves and old character files are invalid after this step (no migration, by policy).
Regenerate goldens only if `state/*.json` or `save/*.json` diffs (they should not: `Game` is
unchanged).

Verify: full check.

### Step 3.2: authoring bar, prompts, growth trigger are engine property (item 9)

Change:
- `content/model.py`: `AuthoringTool`, `AuthoringBrief` (Target shapes).
- `world/authoring.py`: `MIN_*`, `_bar_unmet` (re-adds reachability, and with it
  `world/topology.py:walk(entities, start)`, which 2.1 deliberately did not write early),
  `_opening_unmet`, extend unmet, `connect(world, args) -> str` as an `AuthoringTool`,
  `rooms_brief(packs, base, opening, guidance)`, whose `unmet` requires
  `player_parent_id` to name a location; prompts read from `world/prompts/`
  (move `scenario_world.md`, `scenario_bar.md`, `scenario_opening.md`, `scenario_extend.md`
  there). `scenario_example.md` and `scenario_rules.md` stay in `authoring/prompts/`.
- `engines/core.py`: `Engine.authoring_brief`, `Engine.growth_due`; delete
  `authoring_instructions`. Each engine: `authoring_brief=lambda packs, base, opening:
  rooms_brief(packs, base, opening, guidance=<its text + json.dumps of selected packs>)`,
  `growth_due=lambda state, limit: frontier(state.world) <= limit`.
- `authoring/draft.py`: delete `AuthoringBrief`, `WHOLE_SCENARIO`, `OPENING_SLICE`,
  `extend_brief`, `_bar_unmet`, `_opening_unmet`, `MIN_*`. `scenario_refusal` takes the brief.
- `authoring/run.py`: `_instructions` reads `brief.bar_prompt` and `brief.guidance`;
  `authoring_toolset` wraps `brief.tools` generically (one `FunctionToolset` tool per
  `AuthoringTool`, `ModelRetry` on `ValueError`); `connect` is no longer inline.
  `scenario_run`/`growth_run` call `engine.authoring_brief(packs, base, opening)`.
- `app/runtime.py:GameSession.growth_due`: `self.scenario.grows and
  self.engine.growth_due(self.state, self.settings.authoring.growth_frontier)`. Delete the
  `frontier` import.
- A non-rooms brief may leave `player_parent_id` null and declares no `connect` tool.
- `harness/codemode.py:blank_authoring`: the union of every engine's `brief.tools`, one
  toolset; `check_tool_names` at startup refuses a name two engines both declare.
  `harness/mcp.py:offered` lists that union and `call` dispatches any name in it.
- `.claude/skills/authoring-aidm/SKILL.md`, `growing-aidm/SKILL.md`: `rules` → `mechanics`
  wording ("an NPC sheet goes under `mechanics` keyed by id"); `packs` default sentence:
  "defaults to the engine's first installed pack".

Tests: `tests/core/test_authoring.py` bar tests re-target to `world.authoring`; keep names.

Verify: full check. Fixtures `prompts/*` do not change (the Director prompt is untouched).

### Step 3.3: draft on `WorldState` (item 10)

Change:
- `authoring/draft.py`: `ScenarioDraft` becomes `Draft(Mutable){meta: ScenarioMeta | None,
  player_parent_id: EntityId | None, art_style: str, world: WorldState}`. Delete
  `entities`, `threads`, `starting_party` (use `world.*`), `ExitLink`, `ExtensionPatch`,
  `extension_patch`, `apply_patch`, `_added_entity`, `_added_exit`, `_opened`,
  `_materialized`. `Draft.scenario(engine, packs, grows)` builds `Scenario` from `world`
  directly. `ScenarioPatch` stays (the model writes patches; whole-draft writes were
  rejected). It already carries `mechanics: dict[str, JsonValue] = {}` from 2.3, applied
  through `engine.mechanics_merge(...)`, and `remove` already calls
  `engine.mechanics_without(...)`: a blob-backed engine cannot be authored without them. 3.3
  only moves them onto `Draft.world`. `Draft` carries the engine's two hooks; core never opens
  the blob.
- `world/authoring.py:diff(base: WorldState, draft: WorldState, mechanics_merge) -> Play`:
  adds entities not in `base` with `known=False` and every exit `known=False`, exits on
  existing locations not in `base` (`known=False`), threads not in `base`, and the mechanics
  delta: `mechanics_merge(game.world.mechanics, {keys of draft.mechanics not in base})`;
  refuses an id `base` holds. Facts: `kind="canon_materialized"`, untold.
- `authoring/run.py:GrowthRun.patch()` → `GrowthRun.play() -> Play` = `diff(base.world,
  draft.world, engine.mechanics_merge)`. `app/runtime.py:apply_growth(play)`; `harness/codemode.py:finish_growth`.
- `patch_refusal` keeps "a live game keeps its scenario-wide fields" and the settled-id guard.
- Rule: dict writes on the draft's `WorldState` skip validation. `scenario_refusal` validates
  through `Draft.scenario(...)` then `begin_game` (the playtest), never by trusting the dict.

Tests: `tests/core/test_extension.py::test_delta_is_the_canon_a_pass_added_and_the_ways_into_it`
deleted; the other four re-target to `diff`. `test_a_grown_world_is_briefed_with_its_sheets...`
asserts the briefing shows `mechanics`. Add one: a growth run that adds an NPC with a sheet
lands the sheet in the game's `mechanics`.

Verify: full check. Eval: none (authoring is unmeasured).

---

## Phase 4: evals split, UI, trace, small deletions (items 13, 14, 16)

### Step 4.1: split `evals/turn_eval.py` (item 13)

Change:
- `evals/turn_eval.py` keeps `Case`, `Expectation`, `Run`, `CaseResult`, `Report`, `begin`,
  the CLI and `compare`.
- New `evals/cases/shared.py`: `Canon` dataclass, `cases_for(engine_id, canon, settings)` for
  the four engine-parametrized cases (`find-and-take`, `walk-and-look`, `three-things`,
  `risky-climb`), reading state and fact kinds only.
- New `evals/cases/<engine>.py` (three files): `CANON: Canon`, `CASES(settings) ->
  tuple[Case, ...]` = shared cases + the engine's own, with its predicates and setups.
- The runner loads `evals.cases.<engine_id>` by `import_module`, like
  `tests/core/test_golden_turn.py`.

Verify: `uv run python evals/turn_eval.py run --label step-4.1 --case loner3e/walk-and-look`
(one cheap case); ruff; basedpyright.

### Step 4.2: UI consolidation (item 14)

Change:
- `ui/widgets.py`: `page_header(title, engine_title: str | None = None, home=True)`; delete
  `show_engine_badge`; `ui/app.py` two callers render `ui.badge(engine.title)`.
- `ui/create.py`: sheet preview = `engine.sheet_rows` on a throwaway `Game` built with
  `begin_game(engine, "preview", scenario, character)` when a scenario is selected, else
  traits and items only. No `rules_types`.
- `ui/game.py`: `_mechanic_event` → `_card(fact)`; `_dice_group` by index (done in 1.1).
  Visual consolidation only: `scene_header` already renders `Scene` since 2.6.
- Do not merge `ui/settings.py` or `ui/theme.py` into anything.

Verify: full check; `uv run aidm` opens and a game page renders.

### Step 4.3: delete the turn trace (item 16)

Change:
- `state/play.py`: delete `StepTrace`, `TurnTrace`.
- `turn/run.py`: delete `TurnResult`, `retry_prompts`, the `steps` list; `run_segment ->
  Game`; `Turn.finish(lines) -> Game`.
- `app/runtime.py`: delete `GameSession.entries`; `commit(state)`; `submit -> Game`.
- `ui/panels.py`: delete `trace_panel`; `ui/game.py` drops the dev tab call.
- `harness/codemode.py:end_turn`: `state = turn.finish(lines)`.
- `evals/turn_eval.py`: `TurnResult`/`TurnTrace` are replaced by an eval-owned
  `Played(Frozen){state: Game, facts: tuple[Fact, ...], narration: str, director_calls: int,
  retry_prompts: tuple[str, ...], prompts: tuple[str, ...]}`: `facts` through `on_fact`,
  `narration` from the committed exchange, the rest through a
  `pydantic_ai.models.wrapper.WrapperModel` around the director model that records requests
  (a retry prompt is the last `RetryPromptPart` of a request). Every predicate reads `Played`.
- `tests/core/core_test_support.py`: `played -> Game`; delete `shown`; golden prompts come
  from `recorded(...)` (the last `UserPromptPart` of the last request per role); golden turn
  fixture = facts collected through `on_fact` + the committed save.
  `tests/core/test_golden_turn.py`, `test_golden_prompts.py` re-target accordingly.

Regenerate goldens (`turn/*.json` shape changes); read the diffs.

Verify: full check.

### Step 4.4: non-rooms proof engine, green

Change:
- New `tests/nonrooms/engine.py`: a journal engine. `id="nonrooms"`, `JournalState(counter:
  int = 0)` as its mechanics model, one Director tool `mark_passage` (counter + 1, one untold
  fact), a one-step `creation`, a room-free `AuthoringBrief` (no `connect`), `growth_due`
  False, `over=lambda state: None`, `mechanics_merge`/`mechanics_without` on its model.
  `scene` returns `Scene(key="journal", label="Journal I", sections=(SceneSection("JOURNAL",
  player=<public journal text>, director=<counter text>),), present_entity_ids={player},
  art_prompt="an open journal ...")`. No import from `aidm.world`; no location entities,
  exits, party, threads, death, dice; `player_parent_id` null.
- `tests/nonrooms/test_nonrooms.py` asserts:
  1. `run_segment` with a `FunctionModel` calls `mark_passage`, commits counter `1`, records
     `Exchange.scene == "Journal I"`, leaves `player.parent_id` None.
  2. `Harness` (MCP) does the same through code mode.
  3. Authoring writes the scenario with no start location and no `connect`, and `load_scenario`
     reads it back; the character comes through the normal creation form.
  4. `game_page` renders "Journal I", its section, the composer and the art slot without a
     location.
  5. A stub illustrator receives the journal art prompt, keyed by `Scene.key`.
  6. A `Scene` whose `public_entity_ids` names an unknown entity is refused by
     `VisibleScene.revealed_from` before the Narrator runs; the same entity may appear in a
     section's `director` text.

No xfails: every assert is green.

Verify: full check.

### Step 4.5: small deletions and docs

Change:
- Delete `tests/cairn/`.
- `app/runtime.py:GameSession._resumable`: delete the second `engine.validate` call.
- `docs/NEXT-ENGINE-RESEARCH.md`: add one line at the top: "Stale after PLAN.md 2026-08:
  `Engine.seed()`, `Engine.resume()`, `authoring_context` no longer exist; decisions are
  deferred tool calls; mechanics live in `WorldState.mechanics`."
- `grep -rn "at_boundary\|sheet_of\|character()\|EventBadge\|TurnTrace" tests/` is empty.
- Delete this `PLAN.md` in the final commit; the git log is the record.

Verify: full check.

---

## Done when

- [ ] Full check green: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
      `uv run basedpyright`.
- [ ] `tests/core/test_package_boundary.py` passes with `LAYERS = (state, content, world,
      engines, turn, authoring, app, harness)`; `engines/core.py` and `state/` import nothing
      from `aidm.world`.
- [ ] `grep -rn '"srd"' src/` shows only `loner3e/rules.py:SRD_PACK`.
- [ ] `grep -rn "MechanicEvent\|EventBadge\|CORE_TOOLS\|rules_types\|
      SheetBase\|EntityRules\|Decision(\|check_pending\|TurnTrace\|StepTrace\|TurnResult\|
      CharacterOverlay\|CharacterProfile\|ExtensionPatch\|ScenarioDraft" src/ tests/ evals/`
      is empty.
- [ ] `grep -rn "Random(0)" src/` is empty; `grep -rn "mechanics\[" src/aidm/state
      src/aidm/world src/aidm/authoring src/aidm/turn` is empty (only engines open the blob).
- [ ] Every `rules.py` opens `with rules(...)` at most once per tool call and never nests.
- [ ] `Turn.call` keeps the suspension gate and `during_suspension`; `test_code_mode.py` gate
      tests pass unchanged.
- [ ] `check_tool_names` runs on every engine build; `harness/mcp.py` lists and dispatches
      every engine's authoring tools.
- [ ] `characters/kael/{loner3e,twentyfourxx,breathless}.json` are full `Character` files;
      `base.json` is gone; `icons/` stays.
- [ ] All three `scenarios/*/world.json` carry `world.mechanics`; no entity has `rules`.
- [ ] Golden fixtures regenerated at 2.7 and 4.3 only, each diff read.
- [ ] Evals: the named `--case` runs at 2.3, 2.4, 2.5, 4.1 pass at their prior score.
- [ ] `evals/cases/<engine>.py` exists per engine; `evals/turn_eval.py` holds no engine name.
- [ ] `.claude/skills/playing-aidm` has no step 8; authoring/growing skills say `mechanics`.
- [ ] `tests/nonrooms/` is green with no xfail: builtin, MCP, authoring, UI, illustration and
      the `revealed_from` refusal.
- [ ] `grep -rn "SceneSnapshot\|starting_location_id\|player_location\|describer\|director_sections" src/`
      is empty except `world/scene.py:rooms_scene` parameters and `world/topology.py:player_location`.
- [ ] `render_narrator` accepts only `VisibleScene`; `narrator_agent` is
      `Agent[VisibleScene, Narration]`.
- [ ] `tests/cairn/` and `PLAN.md` deleted in the last commit.
