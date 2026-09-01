# PLAN — Breathless and 24XX

The order of work for engines three and four. `VISION.md` says what we build and why; read it
once, first. This file says what to do, step by step, and is self-standing.

Both engines are scene games. They play on Loner's lifecycle: the worldsmith writes scenes, the
player names the way on, the arrival is narrated. Neither has a map. Tunnel Goons stays the one
engine that extends a map in silence.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Rules:

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step**, except the two steps a phase marks "checked
   together": registering an engine makes the core golden tests look for its fixtures, so the
   registry edit and the fixture regen are always the last two steps of an engine phase.
3. **Tests must be green.** Change a shape and update its tests in the same step. Test lines are
   not budgeted.
4. **Golden files** live in `tests/core/fixtures/`. Rebuild them **once**, at the end of a phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. If a change surprises you, stop and ask.
5. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never pad, never invent a deletion.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive.
9. **Review each phase adversarially against its staged diff before the commit.**
10. **Verify every rule against the SRD page before you build on it.** The docs under `docs/`
    hold sources and deviations, never rules text. A rule this file states is a reading of the
    SRD; if the page says otherwise, the page wins and this file gets a fix.

| phase | `src` after |
|---|---|
| start (`6fabe08`) | 6,750 |
| 1 — Breathless | about 8,250 |
| 2 — fold the identical scene code | about 8,160 |
| 3 — 24XX | about 9,560 |
| 4 — the enduring documents | about 9,560 |

Targets are targets. The cap is Settled 2's 2,000 lines per engine.

---

## Settled. Do not re-open these inside a phase.

1. **No shared world layer, in any name.** No `kits/`, no `World` protocol, no generic
   `SceneWorld[C]`. Each engine owns its world model. A helper moves to `engines/core.py` only
   when two engines hold the identical function or the identical model, and it moves verbatim.
   Phase 2 is that move, and nothing more.
2. **An engine is self-contained and at most 2,000 Python lines.** Seven files — `world.py`,
   `creation.py`, `tools.py`, `views.py`, `worldsmith.py` + `worldsmith.md`, `engine.py`,
   `rules.md` — plus `packs/srd.json`, all under `engines/<id>/`.
3. **At most fifteen game-master tools per engine, one per SRD procedure.** The count is tools
   plus `change_world` arms. `start_turn` and `scene` are the platform's and do not count.
   Loner 6+8, Tunnel Goons 6+3, Breathless 8+5, 24XX 6+9.
4. **Packs are a core concept.** `Scenario.packs` and `Game.packs` stay in the envelope. Each
   engine defines its own `Pack` model and loads it with `load_packs`; `validate` is Loner's
   `check_packs` (at least one selected, all installed). Tables the engine rolls on are read from
   the `srd` pack, as Loner's `twist_table` does. `engines/<id>/packs/srd.json`
   is the transcription of record; `docs/<ID>.md` holds sources and deviations only.
5. **Only the player rolls, and only the player has a sheet.** As in Tunnel Goons: an NPC is
   `id`, `name`, `brief`, `known`, `alive`. A threat to the player is the player's own roll. Every
   place where the SRD gives an ally a die is a documented deviation in `docs/<ID>.md`.
6. **No companions in the two new engines.** Neither SRD prints a join-the-party rule; the
   worldsmith's bar ("one existing member brought back") carries the cast between scenes.
   Loner keeps its companions: its SRD prints them.
7. **Fidelity first, then minimal.** A rule the SRD prints is implemented as printed. A rule the
   SRD does not print is not invented. A reading the SRD leaves open is settled in `docs/<ID>.md`.
8. **`Engine` stays a frozen dataclass of typed callables.** `build()` passes module functions.
   One `partial(fn, packs)` per member that reads the loaded packs is allowed.
9. **The transition is Loner's.** `Transition(ready=settled, write=write_next, install=install_scene,
   arrival_brief=arrival_brief)`. `arrival_brief=None` belongs to map engines only.
10. **Shared helpers in `engines/core.py`:** `PLAYER_ID`, `Entity`, `Counter`, `pool`, `adjust`,
    `counter_fact`, `check_filing`, `labeled`, `entity_fact`, `reveal`, `keep_highest`,
    `load_packs`. Import them; do not redefine them. `Entity` is `id`, `name`, `known` — nothing
    else; do not widen it.
11. **The player is not in `cast`.** `world.player` is the sheet; `cast` is everyone else.
    `PLAYER_ID` never appears in `run.present` or `run.hidden`. `here()` yields the player first,
    then `cast[i] for i in run.present`. `require(id)`, `require_here(id)` and
    `require_alive_here(id)` return the player for `PLAYER_ID`, else the cast member; their
    return type is `Survivor | Npc` (24XX: `Operator | Npc`). `Leave(PLAYER_ID)` refuses with
    Loner's message by id compare, before any lookup. The worldsmith resolves names against
    `{PLAYER_ID: world.player, **world.cast, **draft.cast}`, and a draft that names the player in
    `present` or `hidden` has that entry dropped, not refused (Loner's behaviour). The worldsmith
    prompt lists the player first, then the cast.
12. **Items are keyed, not filed.** `items: dict[EntityId, Item]`; the key is the id and `Item`
    has no `id` field, so `check_filing` does not apply. Items are not in `known()`. Every fact
    about an item is `entity_fact(player, ...)`: the holder is the entity.
13. **No backwards compatibility.** Stale saves are invalid; no version field, no migration.
14. **`NarratorView` has no field that can hold hidden canon.** It stays one type.
15. **`next_scene` is not a `PendingDecision`.** An offer does not block the master's tools.
16. **A pending option replays through the tool that offered it.** `Engine.answer` calls the
    tool named in `PendingOption.name` with `PendingOption.args`; `consume_answer` clears
    `pending` first. So a tool that offers a decision takes nullable args the master leaves
    null, and with them filled it rolls nothing and applies the choice. It cannot tell a replay
    from a direct call; Tunnel Goons' `level_up` has the same hole, accepted.

---

## Phase 1 — Breathless

Engine id `breathless`. Title `BREATHLESS`. Source: the SRD v2.1 at
<https://keeper.farirpgs.com/resources/fari-rpgs/breathless/breathless-srd/>. Licence: ORC. The
credit line below goes verbatim at the top of `rules.md` and in `packs/srd.json` `license`:

> This work is based on Breathless, product of Fari RPGs (https://farirpgs.com/), developed and
> authored by René-Pier Deshaies-Gélinas. This product is licensed under the ORC License available
> online at various locations including www.azoralaw.com/orclicense.

Copy Loner's scene machinery where the shape is the same: `Scene`, `SceneRun`, `SceneCanon`, the
world's scene methods, `record`, `history`, `settled`, `SceneDraft` and `worldsmith.py`'s
resolution and rendering. Change only what Settled 5, 6, 11 and 12 change. Phase 2 folds what
came out identical. Do not fold in this phase.

**Split:** sequential A, then B and C in parallel, then D. Files per part are listed at the end
of the phase.

### 1.1 `world.py`

```python
type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
STRESS_MAX = 4          # vulnerable at 4
CARRY = 3               # items beside the med kit
LOOT_START: Die = 12
STUNT_DIE: Die = 12
STARTING_ITEM: Die = 10
MED_KIT_CLEARS = 2


class Item(Mutable):
    name: str
    die: Die


class Survivor(Mutable):
    """The played character: the only one with dice."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = True
    pronouns: str = ""
    job: str = ""
    skills: dict[Skill, Die]          # as created; a validator fills every missing skill with d4
    worn: dict[Skill, Die]            # where each stands now; a validator fills from `skills`
    items: dict[EntityId, Item] = Field(default_factory=dict)   # the backpack
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=partial(Counter, current=0, maximum=STRESS_MAX))
    stunted: bool = False
    alive: bool = True

    @property
    def vulnerable(self) -> bool: ...   # stress.current >= STRESS_MAX

    def rows(self) -> Rows: ...
    # ("Pronouns", ...), ("Job", ...), ("Skills", "Bash d10 (rated d12), Dash d4, ..."),
    # ("Loot die", "d12"), ("Stress", "1/4" + ", vulnerable"), ("Stunt", "spent" when stunted),
    # ("Med kit", "yes"); empty values dropped as Loner's rows() does.


class Npc(Mutable):
    """Everyone else, exactly as the SRD leaves them: no dice."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = False
    alive: bool = True


class Scene(Frozen): ...              # Loner's, unchanged
class SceneRun(Mutable): ...          # Loner's, unchanged


class SceneCanon(Mutable):            # Loner's, with `cast: dict[EntityId, Npc]`
    cast: dict[EntityId, Npc]
    opening: Scene
    present: list[CheckedEntityId]
    hidden: list[CheckedEntityId]
    source: str = ""


class BreathlessWorld(Mutable):
    cast: dict[EntityId, Npc]
    player: Survivor
    runs: list[SceneRun] = Field(min_length=1)
    source: str = ""
    # Validators: check_filing(cast); Loner's _check_named(run.present, run.hidden, cast);
    # player.known; PLAYER_ID not in present or hidden; player.id == PLAYER_ID.
    # Methods per Settled 11: require, require_here, require_alive_here, run, current,
    # exchanges, here, label, reveal, last_seen — Loner's, minus companions.


class BreathlessState(Mutable):
    world: BreathlessWorld


class BreathlessScenario(Mutable):
    world: SceneCanon


class BreathlessCharacter(Mutable):
    pronouns: str
    job: str
    skills: dict[Skill, Die]          # exactly three entries: one d10, one d8, one d6 (validator)
    item: str                         # the one starting d10 item


class BreathlessGame(Game[BreathlessState]): pass
class BreathlessScenarioFile(Scenario[BreathlessScenario]): pass
class BreathlessCharacterFile(Character[BreathlessCharacter]): pass
```

Functions: `stepped(die: Die) -> Die` (one step down, floor d4); `scene_spent(run: SceneRun,
someone_dead: bool) -> str | None` — Loner's, with the dead check passed in so the function
reads only `SceneRun` (Phase 2 moves it); `known(state, id)` answers for the player and the cast,
`None` otherwise; `record` — Loner's, it returns the spent note the same way, calling
`scene_spent(world.run, any(not one.alive for one in world.here()))`; `history`; `settled`;
`player_over` ("You died."); `player_survivor(character) -> Survivor` with `id=PLAYER_ID`,
`known=True`, and `items={slug(item, ()): Item(name=item, die=STARTING_ITEM)}`.

### 1.2 `creation.py`

```python
class Pack(Frozen):
    name: str
    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=6, max_length=6)
    jobs: tuple[str, ...]
    weapons: tuple[str, ...]
    long_range_weapons: tuple[str, ...]
    locations: tuple[str, ...]
    complications: tuple[str, ...] = Field(min_length=12, max_length=12)   # one d12
    missions: tuple[str, ...]
```

Steps, in order: `pack` (select), `pronouns` (text), `job` (text; hint = three pack jobs),
`skill-d10`, `skill-d8`, `skill-d6` (select from `pack.skills`, each excluding the earlier picks),
`item` (text; hint = three pack weapons). `create_character` builds `skills` from the three
picks. `preview_character` = `player_survivor(character).rows()` plus a `("Backpack", item)` row.
`pack_options`, `guidance(packs, selected_ids)` as Loner's; the guidance text is the pack's
`locations`, `complications` and `missions`, for the worldsmith.

`packs/srd.json`: `git show 70d1a57:src/aidm/engines/breathless/packs/srd.json` matches this
`Pack` field for field. Copy it, then check every entry against the SRD page.

### 1.3 `tools.py` — eight tools, five arms (13)

Every args field carries `Field(description=...)`; `master_tool` refuses a bare one.

| tool | args | what the engine does |
|---|---|---|
| `change_world` | `change: Reveal \| Enter \| Leave \| Kill \| DropItem` | Loner's scene verbs, minus tags, drive and the party verbs. `Kill` on `PLAYER_ID` sets `player.alive = False`. `DropItem(item_id)` removes the key from `player.items` for good; fact under the player. `during_suspension=True`. |
| `check` | `what: str`, `skill: Skill \| None = None`, `item_id: CheckedEntityId \| None = None`, `stunt: bool = False`, `dangerous: bool = False` | Exactly one of skill / item / stunt (validator). Die: `worn[skill]`, or `items[item_id].die`, or `STUNT_DIE` (refused while `stunted`; sets it). `roll((die,), ...)`. 1–2 `fail`, 3–4 `success-but`, 5+ `success` — the SRD's bands, its words. Then the die wears: a skill steps down (floor d4); an item steps down, and an item **that was rolled at d4** "breaks, gets lost, or fades away" and leaves the backpack (fact under the player). `dangerous` and `fail` on a vulnerable player: a note to the master — taken out or dead is their ruling, by `Kill`. |
| `catch_breath` | none | Reset `worn` to `skills` and `loot` to `LOOT_START`, clear `stunted`; items keep their dice; stress stays. The SRD says the GM "looks at the scene and introduces a new complication": the engine rolls one d12 on the `srd` pack's `complications` as a suggestion into `draft.notes` only — no card, no told fact; the master brings it in through the story. |
| `change_stress` | `amount: int`, `why: str` | `counter_fact(player, player.stress, amount, "Stress", why, PLAYER_ID)`. Description: a complication costs stress; laying low somewhere secure clears "an amount at the GM's discretion"; never a stand-in for `use_med_kit`. |
| `use_med_kit` | none | Refused without a kit. Clears `MED_KIT_CLEARS`, spends the kit. |
| `loot_check` | `item: str`, `granted: Die \| None = None`, `choice: str \| None = None` | See below. |
| `next_scene` | none | Loner's, on `BreathlessGame`. |
| `test_luck` | `question: str`, `die: Die` | The SRD's "disclaim decision-making by testing for luck": the master picks the die by the odds; the engine rolls it and reads it on the 1–2 / 3–4 / 5+ ladder. Untold fact: the trace reaches the master, no card reaches the narrator. |

`loot_check`: always rolls — the SRD forbids nothing at a full backpack. With `granted` and
`choice` both null: roll the loot die, then step it down. 1–2 trouble here, 3–4 trouble ahead
(notes to the master, no item). 5–6 a d6 item, 7–8 d8, 9–10 d10, 11–12 d12. `item` is "what is
found if the roll finds anything; the die sets how good it is". On an item result the turn waits
on one decision:

```python
PendingDecision(
    kind="loot",
    prompt=f"You found {item} (d{granted}). Take it?",
    options=(...),   # one PendingOption per choice below, name="loot_check",
                     # args={"item": item, "granted": granted, "choice": <id>}
    allows_text=False,
)
```

Choices, in this order: `take` ("Take it") when the backpack holds fewer than `CARRY`; one
option per carried item, id = that item's key, label `f"Swap for {carried.name}"`, when the
backpack is full; `med-kit` ("Take a med kit instead") when `granted >= 10` and no kit is held.
With `granted` and `choice` filled (validator: both or neither): no roll; `take` adds
`Item(item, granted)` under `slug(item, player.items)`; a carried key drops that item and adds
the new one; `med-kit` sets `med_kit`. One told fact under the player either way.

`rules.md` says plainly: catching breath does not clear stress; `test_luck` is a question about
the world with nobody acting, `check` is an action; `use_med_kit` is the only way a kit clears;
`loot_check` is the only way an item enters the backpack; `granted` and `choice` are left null.

### 1.4 `views.py`

`narrator_view`, `player_view`, `master_sections` as Loner's, with panels
`Character` (the `rows()`), `Backpack` (one row per item: `label=name, detail=f"d{die}"`, and a
`Med kit` row when held), `This scene`, `Here`, `Trail`. `master_sections`: `SCENE`, `THE
QUESTION THIS SCENE SETTLES`, `YOU PLAY FOR` (the player's card line with the sheet rows),
`BACKPACK`, `HERE WITH THE PLAYER`, `HIDDEN HERE`, `THE SCENE'S SECRET`.

### 1.5 `worldsmith.py` + `worldsmith.md`

Loner's, with `cast: dict[EntityId, Npc]` in `SceneDraft`, and Settled 11 for resolution. The
bar (`_scene_unmet`): one cast member besides the player; after the opening, one existing member
brought back; no hidden name in `situation`; every cast member alive. Drop Loner's luck check.
`apply_scene` has no followers: `present` is what the draft resolves, minus the
player. `worldsmith.md`: Loner's text, minus the luck line and the companions line, plus one
line: the cast carries no dice; a threat is written as a brief, and the player's own roll meets
it.

### 1.6 `engine.py`, `rules.md`

`build(user_packs: Path) -> Engine[BreathlessGame]` as Loner's: `packs=pack_options(packs)`,
`validate=partial(check_packs, packs)`, `instructions` from `rules.md`. `rules.md` in Tunnel
Goons' register: the credit line, the sheet, when to call `check`, reading the result, catching
breath, stress and the med kit, scavenging and the loot decision, luck tests, then Loner's
`## Let the player choose where the story goes` copied whole.

### 1.7 Content, tests, registry

- `characters/kael/breathless.json`: pronouns `he/him`, job `Park Ranger`, think d10, sneak d8,
  bash d6, item `Fire Axe`. Name and brief as the Loner file's.
- `scenarios/<one>/world.json`, exactly one (the test support requires exactly one scenario per
  engine): hand-written from `tests/core/fixtures/source/drowned-road.md`, opening scene plus
  three cast members, one hidden. No worldsmith run.
- `pyproject.toml`: add `tests/breathless` to `pythonpath` and to `extraPaths`.
- `tests/breathless/breathless_test_support.py` (constants and a built state, as
  `tunnelgoons_test_support.py`), `golden_turn.py` exporting `SCRIPT: tuple[Call, ...]` and
  `behind(state: AnyGame) -> AnyGame` as `tests/tunnelgoons/golden_turn.py` does, and tests
  for creation, each tool, the loot decision resume, the vulnerable-fail note, catch-breath
  reset, world validation, worldsmith refusals.
- Registry + regen, checked together (rule 2): register in `engines/registry.py`, then regen; the
  core golden tests are parameterised over the registry, so `prompts/`, `save/`, `schemas/`,
  `state/`, `turn/` gain `breathless` entries.
- `docs/BREATHLESS.md`: replace the engine sections with the tool table and every deviation this
  phase made, each with its reason. Expected: no ally rolls (Settled 5); an item reduced to d4
  leaves for good — the SRD's "fades away ... until it's made relevant again" has no way back; a
  med kit is a mark, not an item. Readings, not deviations: the catch-breath complication is a
  rolled suggestion; a luck test reads on the check ladder.

**Split.** A: `world.py`, `creation.py`, `packs/srd.json`, `tests/breathless/test_world.py`,
`test_create.py`. B (needs A): `tools.py`, `rules.md`, `tests/breathless/test_tools.py`.
C (needs A, parallel with B): `views.py`, `worldsmith.py`, `worldsmith.md`,
`tests/breathless/test_worldsmith.py`, `test_views.py`. D (needs B and C): `engine.py`,
`registry.py`, `pyproject.toml`, the content files, `breathless_test_support.py`,
`golden_turn.py`, `test_engine.py`, `docs/BREATHLESS.md`, regen.

**Done when:** the four commands are green, `uv run aidm` plays a Breathless turn end to end,
engine at target 1,700 lines (cap 2,000), `docs/BREATHLESS.md` lists every deviation.

---

## Phase 2 — fold the identical scene code

One implementer. Put `engines/loner3e/` and `engines/breathless/` side by side. Move to
`engines/core.py` **only** what is byte-identical. Measured on Loner today, the movable set is
about 96 lines; the net after moving from two engines is about −90. Names that were private go
public on the move: `resolve_ids`, `named_in`, `scene_history`, `told_tail`.

- `Scene`, `SceneRun`.
- `scene_spent(run, someone_dead)`, `SPENT_NOTE`, `SCENE_SETTLED`, `SCENE_TURN_CAP`.
- `resolved_id`, `resolve_ids`, `named_in` — typed on `Mapping[EntityId, Entity]` (`dict` is
  invariant; basedpyright refuses `dict[EntityId, Npc]` at a `dict[EntityId, Entity]` parameter).
- `scene_history(runs)`, `told_tail`, `TAIL_EXCHANGES`, `CROSSING`, `SURPRISE`, `arrival_brief`.

Not moved: `next_scene` (reads the engine's game type), `SceneCanon`, either world class,
`SceneDraft`, `apply_scene`, `_scene_unmet`, `render_worldsmith`, `install_scene`. If two of them
turn out identical, move them; if a move needs a type parameter, a protocol or a callback to
work, it does not move. `tests/loner3e/golden_turn.py` imports `Scene, SceneRun` from
`loner3e.world`; repoint it.

Files: `engines/core.py`, `loner3e/{world,worldsmith,tools}.py`,
`breathless/{world,worldsmith,tools}.py`, `tests/loner3e/golden_turn.py`.

**Done when:** green; `AIDM_GOLDEN_REGEN=1 uv run pytest; git diff --exit-code tests/core/fixtures`
is clean (the prompts did not change by a byte); `src` smaller by about 90; no new abstraction.

---

## Phase 3 — 24XX

Engine id `twentyfourxx`. Title `24XX`. Source: the SRD v1.4 at <https://24xx-srd.carrd.co/>.
Licence CC BY 4.0. Credit, verbatim at the top of `rules.md`, with the version number:

> 24XX rules (v1.4) are CC BY Jason Tocci. <https://24xx-srd.carrd.co/>

Call it "24XX", never "2400". Build on Phase 2's shared scene code; copy Breathless where the
shape is the same. **Split:** as Phase 1, four parts along the same file lines.

### 3.1 `world.py`

```python
type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)
DEFAULT_DIE = 6          # a skill not on the sheet
HINDERED_DIE = 4
HELP_DIE = 6
STARTING_CREDITS = 2
MAIMED = "Maimed"


class Kit(Frozen):
    """An item as a pack or a character file names it."""

    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)


class Item(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)     # a vest breaks once; battle armor "up to 3×"
    broken_times: int = Field(default=0, ge=0)

    @property
    def broken(self) -> bool: ...            # broken_times >= breaks


class Operator(Mutable):
    """The played character: the only one with dice, credits and hindrances."""

    id: CheckedEntityId
    name: str
    brief: str
    known: bool = True
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()          # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)   # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    hindrances: tuple[str, ...] = ()      # the SRD's word: injuries and the like
    alive: bool = True

    def die(self, skill: str) -> int: ...  # skills.get(skill, DEFAULT_DIE)
    def rows(self) -> Rows: ...
    # Specialty, Origin, Traits, Skills ("Stealth d10, Climbing d8"), Credits ("₡2"),
    # Hindrances; empty values dropped.


class Npc(Mutable): ...                   # Breathless', unchanged
class SceneCanon(Mutable): ...            # Breathless', unchanged
class TwentyfourxxWorld(Mutable): ...     # Breathless', with `player: Operator`


class TwentyfourxxCharacter(Mutable):
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()
    skills: dict[str, SkillDie]
    items: tuple[Kit, ...]                # the comm, the specialty kit, Muscle's weapon


# TwentyfourxxState, TwentyfourxxScenario, TwentyfourxxGame, ...ScenarioFile, ...CharacterFile:
# as Breathless.
```

`player_operator(character)` keys items by `slug(kit.name, taken)` in order.

### 3.2 `creation.py`

```python
class SkillChoice(Frozen):
    """One printed pick: Muscle's Hand-to-hand or Shooting; Psychic's both at d8 or one at d10."""

    id: Slug
    label: str
    skills: dict[str, SkillDie]


class Specialty(Frozen):
    id: Slug
    label: str
    detail: str
    skills: dict[str, SkillDie]           # the fixed ones, at d8
    choice: tuple[SkillChoice, ...] = ()  # Muscle, Psychic
    kit: tuple[Kit, ...] = ()
    kit_choice: tuple[Kit, ...] = ()      # Muscle: "a sword, firearm, or cyber-arm" — pick one


class Origin(Frozen):
    id: Slug
    label: str
    detail: str
    increases: int = 0                    # human 3, android 1
    invents: int = 0                      # alien 2
    choice: tuple[DecisionOption, ...] = ()   # android: synth skin | case


class Pack(Frozen):
    name: str
    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=17, max_length=17)
    specialties: tuple[Specialty, ...]
    origins: tuple[Origin, ...]
    starting_kit: tuple[Kit, ...]         # the comm
```

Steps: `pack`, `specialty`, then `specialty-choice` when the picked specialty has `choice`, and
`weapon` (select from `kit_choice`) when it has `kit_choice`; `origin`, then per origin:
`trait-1`, `trait-2` (text) for alien; `body` (select from `choice`) for android;
`increase-1..n` (select from the 17) for human (3) and android (1). An increase on a skill
already at d8 raises it to d10; the same skill picked twice raises it twice; a pick that would
pass d12 is refused by `create_character`. Credits start at 2, all unspent: buying is play.

`packs/srd.json`: `git show e2cb7c4:src/aidm/engines/twentyfourxx/packs/srd.json` has the
strings, not the shape. Reshape it to this `Pack`: kits become `Kit{name, bulky, breaks}`;
specialty `skills` become `dict[str, SkillDie]`; `choices` become `choice: SkillChoice`; the
alien's `traits` list goes into `detail`; Muscle gains `kit_choice` (sword, firearm, cyber-arm)
— the old file has none, and the page says "Take a sword, firearm, or cyber-arm". Then check
every entry against the page, including "Reading People" (Face) which is not one of the 17: a
specialty skill may sit outside the list, and `attempt` resolves against both.

### 3.3 `tools.py` — six tools, nine arms (15)

| tool | args | what the engine does |
|---|---|---|
| `change_world` | `change: Reveal \| Enter \| Leave \| Kill \| ChangeHindrances \| GainItem \| DropItem \| RepairItem \| Spend` | Scene verbs as Breathless. `ChangeHindrances(gained, lost)` on the player. `GainItem(name, bulky, breaks, cost)` spends `cost` credits, refused when short; "`cost` 0 only for a thing found or given". `DropItem(item_id)`. `RepairItem(item_id, cost)` zeroes `broken_times`. `Spend(amount: int = Field(gt=0), why)` for the SRD's other expenses: bribes, medical care. `during_suspension=True`. |
| `attempt` | `what: str`, `skill: str = ""`, `helped: str = ""`, `hindered: str = ""`, `risking_death: bool = False` | `skill` resolves case-folded against the sheet's keys and the pack's skill labels; anything else is refused with both lists. Die: the sheet's, or `DEFAULT_DIE`; `HINDERED_DIE` instead when `hindered` names why; an extra `HELP_DIE` when `helped` names why (both may apply: "d4 if hindered" and "an extra d6" are separate sentences). `keep_highest`. 1–2 `disaster`, 3–4 `setback`, 5+ `success`. `risking_death`: on 1–2 the player dies ("If risking death, you die"); on 3–4 `MAIMED` joins the hindrances ("you're maimed"). |
| `test_luck` | `question: str` | "Test as needed for bad luck": one d6. 1–2 trouble now, 3–4 signs of it, 5+ nothing. Untold fact. |
| `defend` | `item_id: CheckedEntityId`, `hindrance: str` | The SRD's Defense as one procedure: the item takes one break (refused when already `broken`), and `hindrance` joins the player's. One fact. |
| `next_scene` | none | as Breathless |
| `job_done` | `skill: str` | "After a job, each character increases a skill and gains d6 credits": raise `skill` one step (none → d8 → d10 → d12; refused at d12), roll d6 and add it to `credits`. Two facts, the dice on the second. Called once per adventure, from the player's words on the skill — no ledger, no advance owed, as Loner now writes growth at the story's end. |

An ally who helps is `helped` with the ally named in it: the SRD gives them their own skill die;
here it is the d6 of circumstance, because an NPC carries no dice (Settled 5). Load: more than
one bulky item *may* hinder — the master cites it in `hindered` when it plausibly does; the
engine does not count.

### 3.4 `views.py`, `worldsmith.py`, `engine.py`, `rules.md`

As Breathless, with panels `Character` (the `rows()`), `Gear` (`label=name`, `detail` = "bulky",
"broken", or `broken_times/breaks` when it can break more than once), `This scene`, `Here`,
`Trail`. The worldsmith bar is Breathless'. `rules.md`: the credit line, the sheet, `attempt` and
its three outcomes, risking death, luck tests, `defend`, harm as hindrances, load, credits and
gear, `job_done` from the player's words, the scene rules.

### 3.5 Content, tests, docs

As 1.7, for `twentyfourxx`. `characters/kael/twentyfourxx.json`: Sneak, Human, increases
Stealth, Stealth, Piloting (Stealth d10, Climbing d8, Piloting d8). `pyproject.toml`: add
`tests/twentyfourxx`. `docs/24XX.md`: replace the engine sections with the tool table and the
deviations: no ally dice; no succession on death (the SRD's "make a new character" is not
modelled; dying ends the game as in the other three engines); the d6 job-finding setup is not
modelled (scenarios are authored). Readings: help and hindrance may both apply; the ally's help
is the circumstance d6; a job is the adventure.

**Done when:** green, a 24XX turn plays end to end, engine at target 1,600 lines (cap 2,000),
`docs/24XX.md` lists every deviation.

---

## Phase 4 — the enduring documents

One implementer.

1. `README.md`: four engines in one paragraph each, one licence line per engine.
2. `VISION.md`: the engine list; nothing else unless a phase above contradicted it.
3. `CLAUDE.md`: unchanged unless a rule above proved false; then fix the rule, not the code.
4. `docs/LONER-3E.md`, `docs/TUNNEL-GOONS.md`: read once; fix only what Phase 2 moved.
5. Delete `PLAN.md` and `PROGRESS.md`; remove `PLAN.md` from `pyproject.toml` `extend-exclude`.
   The git log is the record.

**Done when:** every document says what the code does, and no document holds rules text.
