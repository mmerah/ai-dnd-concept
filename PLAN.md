# Plan

Four phases. Each one ships on its own and reverts on its own. Do them in order: phase 4 does not
work without phase 3, and phase 2 makes phase 4's validation single-engine.

## How to work a phase

The gate, all four green, never with `UV_CACHE_DIR` set:
`uv run pytest` · `ruff check` · `ruff format --check` · `basedpyright` (0/0/0).

Golden fixtures live in `tests/core/fixtures/`. When a change is meant to move one, run
`AIDM_GOLDEN_REGEN=1 uv run pytest tests/core/test_golden_prompts.py`, then **read
`git diff tests/core/fixtures` line by line**. A regeneration run always reports failure on
purpose (`tests/conftest.py`); regenerate only in the commit that justifies it.

Live evals are manual, noisy, and comparable only within the same hour on the same tree:
`uv run python evals/turn_eval.py run --label <name>` (n=9, both engines, 10 cases). The
reference is `evals/results/baseline.json` — 90/90 runs pass.

## Standing rules

- The model proposes; resolver code mutates a draft; `draft.committed()` revalidates once.
  Never mutate committed state, and never write state from a model output.
- `VisibleScene` is the Narrator's input and must carry no field unrevealed canon can travel
  through. Any change to it is a leak risk — check `tests/core/test_context_boundary.py`.
- Import direction `state <- content <- engines <- turn <- app <- ui`, enforced by
  `tests/core/test_package_boundary.py`; `aidm/config.py` is a leaf anyone may read.
- Keep `__init__.py` empty. No `TYPE_CHECKING` or deferred imports. Tests stay offline.

---

# Phase 1 — Prompt debt and exit enums

**Goal.** Stop teaching the Director a call it does not need, and make the one id field with a
small legal set (`unlock_exit.to_id`) unrepresentable-when-wrong instead of
rejected-after-the-fact.

**Expected effect.** Fewer tool retries. The baseline is already clean (90/90), so the eval can
only confirm the change costs nothing, not show a rise.

### Step 1 — extract the enum-narrowing helper

`engines/twentyfourxx/actions.py:134` already has `_with_skill_enum`, which rewrites a tool's JSON
schema so a field becomes an `enum`. A second caller now exists, so extract it into
`engines/transact.py`:

```python
def with_enum(tool: ToolDefinition, fields: Sequence[str], values: Sequence[str]) -> ToolDefinition:
    """A field whose legal values are known at call time is an enum, not a free string."""
    properties: dict[str, ObjectJsonSchema] = dict(tool.parameters_json_schema["properties"])
    for name in fields:
        properties[name] = {**properties[name], "enum": list(values)}
    schema = {**tool.parameters_json_schema, "properties": properties}
    return dataclasses.replace(tool, parameters_json_schema=schema)
```

Then delete `_with_skill_enum` and make `_narrow_to_skills_in_play` call
`with_enum(tool, ("skill", "helper_skill"), ["", *sorted(skills)])`.

### Step 2 — narrow `unlock_exit.to_id`

In `turn/tools.py`, add this and a prepare function that rewrites only `unlock_exit`, attached
as `sequential_toolset([...]).prepared(_narrow_ids)` in `core_toolset()` (`possible()` already
drops the tool when nothing is locked, so `_narrow_ids` must tolerate its absence):

```python
def _unlock_targets(state: Game) -> list[str]:
    here = state.world.require_kind(state.player_location, "location")
    return sorted(w.to for w in here.exits if w.locked)
```

**`move` stays a free string on both fields.** Its legal set is not small: an actor standing
here may legally be moved to *any* location in canon, hidden ones included
(`state/actions.py:69-72`), and for an item the set is `player`, an actor here, or the player's
own location (`actions.py:76-91`). A faithful enum is therefore roughly the location list the
prompt already shows — and after phase 3 it would have to mirror the hidden-projection to stay
faithful. That re-encodes the prompt instead of shrinking a legal set; kind confusions are
already refused with the exact reason by the resolver's `ModelRetry`.

### Step 3 — delete the redundant instruction

In `turn/prompts/director.md`, under `FINISH WHAT THE PLAYER DID`, delete the clause
``finding a thing and taking it is `reveal` then `move`;`` — `move` already reveals what it moves
and where it goes. Leave the rest of that paragraph; the handover and trait rules still hold. Keep
the `reveal` tool: it is the only way to show something the player notices without acting on it.

### Verify

Expect `test_tools.py` and `test_golden_schemas.py` to fail on the new enum; read the failures,
then regenerate schema and prompt goldens. The prompt diff must show only the deleted clause.
Gate green, then one eval run at n=9 against `baseline.json`.

**Done when** the gate is green, the goldens show only intended changes, and the eval is within
noise of 90/90.

---

# Phase 2 — Compatibility collapse

**Goal.** A scenario names the engines it plays under, and the engine cross-product in characters
disappears.

### Step 1 — `Scenario.engines`, required

In `content/authored.py`, add to `Scenario`:

```python
engines: tuple[EngineId, ...] = Field(min_length=1)
```

Required and non-empty — no "empty means all". `content/` must not import `engines/`, so the model
checks only non-emptiness; that the ids name installed engines is checked in `app/launcher.py`. Add `"engines": ["loner3e", "twentyfourxx"]` to both `scenarios/whispering-vault/world.json` and
`scenarios/drowned-road/world.json`.

### Step 2 — the launcher reads it

`app/launcher.py:189` currently gives every scenario `engines=engine_ids`. Change to
`engines=scenario.engines`. In `load_catalog`, skip a scenario naming an engine that is not
installed and log a warning — `read_scenarios` already sets that precedent for unreadable files.

`LauncherController.available_engines()` and `_unplayable_reason` need no change — they already
read `ContentOption.engines`.

### Step 3 — the author picks the engines, not the agent

`WorldDraft.scenario()` will now fail without `engines`, so:

1. `app/authoring/draft.py`: add `engines: tuple[EngineId, ...] = ()` to `WorldDraft`, pass it in
   `scenario()`, and set it in `WorldDraft.of()`. **Do not** add it to `ScenarioPatch` — which
   rules a scenario supports is the human's choice, not the authoring agent's.
2. `app/authoring/session.py`: `AuthoringSession` takes `engines: tuple[EngineId, ...]` and sets
   `WorldDraft(expansion=..., engines=...)`.
3. `app/authoring/playability.py`: `playtests(config)` becomes `playtests(config, engines)` and
   builds only those engines.
4. `ui/scenario_create.py`: add a multi-select of engine ids beside the existing expansion toggle,
   defaulting to all installed, and pass it to `AuthoringSession`.

### Step 4 — delete the dead overlay field

`CharacterOverlay.entities` can never legally be non-empty: a `CharacterProfile` holds `items` only
(`authored.py:89`) and `actor_sheets` raises for any non-actor carrying authored rules
(`sheets.py:41-44`). Both shipped overlays are empty. So: in `content/authored.py` delete
`CharacterOverlay.entities`, `_require_authored` and `Character._overlay_fits_the_character`; in
`app/registry.py:53` `rules` becomes `{PLAYER_ID: character.overlay.character}`.

### Step 5 — delete `EngineBinding`

With `entities` gone it wraps one callable over one dict — a port with a single implementation.

1. `content/authored.py`: delete the `EngineBinding` dataclass.
2. `content/store.py`: `load_character(directory, name, engine, check_overlay)` where
   `engine: EngineId` and `check_overlay: Callable[[dict[str, JsonValue]], None]`. It calls
   `check_overlay(character.overlay.character)`.
3. `engines/engine.py`: delete `binding()`. `check_overlay` takes one payload, not an iterable.
4. Update the five call sites: `app/session.py:290`, `app/authoring/playability.py:39`,
   `tests/core/core_test_support.py:78,85`, `tests/core/test_integrity_boundaries.py:87`,
   `tests/core/test_store.py:52`, `tests/loner3e/test_create.py:34`.

### Verify

Gate green, expecting `test_store.py`, `test_authoring.py`, `test_launcher.py` and the save goldens
to need updating. No eval run — nothing in the turn loop changed.

**Done when** the gate is green and a scenario declaring only `["loner3e"]` offers only Loner 3e
on the home page.

---

# Phase 3 — Bound what hidden canon reaches the Director

**Goal.** `render_director` sends *every* unknown entity (`turn/prompts.py:27` reading
`SceneSnapshot.hidden`, built at `turn/scene.py:62` from all of `world.entities`). At 9 entities
that is fine; once phase 4 grows a world to 80 it blows `_ensure_input_budget`.

### Step

In `turn/scene.py`, `SceneSnapshot.of`, replace `hidden` with a local projection. An unknown entity
is shown when **any** of these holds:

1. its enclosing location (`world.location_of`) is the player's location;
2. its enclosing location is exited-to from the player's location;
3. it is itself a location exited-to from any *known* location.

Rule 3 keeps distant-but-signposted places steerable. `canon` stays the full list — this narrows
the *prompt*, not the state. Write it as one module function
`_reachable_hidden(world, here) -> tuple[Entity, ...]`.

### Verify

1. Regenerate prompt goldens and read the diff. On `whispering-vault` from the study, `elena`
   (in `bell_tower`, not adjacent to `study`) should leave the Director prompt, while `vault_map`
   (in `study`) and `bell_tower`/`vault` (exited-to from a known cloister) stay.
2. `tests/core/test_context_boundary.py` must still pass unchanged — this phase must not change
   what the *Narrator* sees.
3. Eval at n=9. Watch `take-the-chart` (chart is hidden in the player's own location) and
   `open-the-way-and-climb` (Elena hidden one exit away). Both must hold.

**Done when** goldens show only distant hidden canon leaving, and the eval is within noise.

---

# Phase 4 — Extension between turns, Expander deleted

**Goal.** The Director stops authoring canon. When a growing scenario runs thin, a background
authoring run appends a chunk to the save.

### Step 1 — delete the Expander

Delete `expander_agent`, `expansion_toolset`, `TurnAgents.expander` (`turn/agents.py`);
`render_expander`, `EXPANDER` (`turn/prompts.py`); `turn/prompts/expander.md`; `MAX_EXPANSIONS`,
`capped`, `record`, `written` (`turn/expansion.py`); `CanonSource`, `OpenSource`, `RecordSource`,
`SILENT`, `render` (`content/sources.py`); `open_source` (`app/session.py:54`); the `"expander"`
role (`config.py:10,49`); `tests/core/test_expansion.py`.

Delete `_written_entity` too — it only serves `written`.

**Keep** `ExpansionPatch`, `ExitLink`, `apply_patch`, `_added_entity`, `_added_exit`, `_opened` in
`turn/expansion.py` — phase 4 applies through them. With the Expander gone nothing renders their
schema, so strip the `Field` descriptions and the model-facing docstring from `ExpansionPatch`
and `ExitLink`: they become plain records. **Keep** `ingest` and `whole_text` in
`content/sources.py`; authoring reads documents with them.

### Step 2 — `grows` replaces `ExpansionPolicy`

Replace the `ExpansionPolicy` literal with `Scenario.grows: bool = False`. Update
`app/authoring/draft.py`, `app/authoring/session.py`, `ui/scenario_create.py` (the toggle stays and
writes a bool), and both `world.json` files: `drowned-road` had `"expansion": "open"` → gains
`"grows": true`; `whispering-vault` omits it.

### Step 3 — the frontier signal

In `state/world.py`, beside `check_player_playable`:

```python
def frontier(world: WorldState) -> int:
    """Unknown locations a known location leads to: doors the player can still find."""
    known = {e.id for e in world.entities if e.known}
    return len(
        {
            way.to
            for entity in world.entities
            if entity.id in known
            for way in entity.exits
            if not world.require(way.to).known
        }
    )
```

`whispering-vault` starts at 2.

### Step 4 — the EXTEND brief

In `app/authoring/playability.py`, add a third `Brief` beside `FULL` and `OPENING`:

- instructions: a new `app/prompts/scenario_extend.md`, same shape as `scenario_opening.md`, but
  telling the author it is *adding* to a world that exists: reuse existing ids as anchors, modify
  or remove nothing, and write at least one way from an existing location into what it adds.
- `unmet`: at least one new location, and at least one exit from a pre-existing location into it.

Add `WorldDraft.of_game(state: Game) -> WorldDraft` in `app/authoring/draft.py`. It is not a
plain copy: `Game` holds no `starting_location_id`, and the live world holds `PLAYER_ID` and
what it carries, which `Scenario`'s validators refuse (reserved id, placement, party-at-start).
So `of_game`:

- sets `meta = state.scenario` and `starting_location_id = state.player_location`;
- drops the player and every entity whose `world.location_of` walk ends at the player (their
  carried items, improvised ones included);
- keeps `starting_party = world.party` — party members stand with the player, so the
  party-placement validator holds.

`delta` is unaffected by the stripping: everything stripped exists in `before`, so it can never
be re-added.

### Step 5 — delta to patch

In `turn/expansion.py`:

```python
def delta(before: WorldState, after: WorldDraft) -> ExpansionPatch: ...
```

Three parts, all keyed by id:

- `entities`: every entity in `after` whose id `before` does not hold.
- `exits`: for each entity present in **both**, every `Exit` in `after` whose `to` the `before`
  copy did not have, as an `ExitLink(location_id=..., to=..., locked=...)`. This is the case a
  beginner misses: a way into new canon is a mutation of an *existing* location.
- `threads`: every thread in `after` whose id `before` does not hold.

Anything else the author changed is ignored — extension is add-only, and `apply_patch` refuses a
duplicate id anyway.

### Step 6 — the session hook

In `app/session.py`, model it on `_illustrate` (`:161`) — a fire-and-forget task held in
`self._tasks` — with one difference: canon is a state transaction, so a turn must not race it.

**Do not reuse `AuthoringSession`** — that is the UI chat session: it refuses an existing slug,
always starts from an empty draft, and `write()` targets `scenarios/`. All three are wrong here,
and no outer send/refusal loop is needed either: `world_agent`'s `finish` validator already
refuses an unplayable draft inside one run.

1. New `app/authoring/extend.py`, one function (~25 lines):
   `async def compile_extension(config, engine, character, state, document) -> ExpansionPatch`.
   It builds `WorldDraft.of_game(state)`, one `Playtest(engine=engine, character=character)` —
   the save's own engine and character, not STARTER times every engine — and
   `world_agent(playing, config, EXTEND)`, then one `agent.run(...)` under `REQUEST_LIMIT` with
   the source document (or the premise) as the prompt, and returns
   `delta(state.world, draft)`.
2. `state/trace.py` gains `Extended(TraceEntryBase)` — facts only, like `Applied` without a
   subject — so the trace panel shows what a compile added.
3. `GameSession` gains `_extending: Task[None] | None = None`. `_commit` starts `self._extend()`
   when `self.scenario.grows`, `frontier(state.world) <= 1`, and no `_extending` task is still
   running — never stack two compiles.
4. `_extend` awaits `compile_extension`, then
   `transact(self.engine, self.state.draft(), lambda d, _: apply_patch(d, patch), self.rng)`
   and `_commit`s the result with an `Extended` entry. A run that raises is logged and dropped —
   the game keeps playing the unextended world and tries again at the next qualifying commit.
5. `submit()` starts with `if self._extending is not None: await self._extending` — the player
   never waits for a compile, but a turn never drafts against a world mid-append. Advancement
   needs no guard: `apply_proposal` is synchronous, so it cannot interleave with the compile's
   own commit, and it already re-checks the offer against the current state.
6. `restart()` cancels `_extending` alongside the media tasks.

Canon lands in the **save**, never in `scenarios/<id>/world.json`. Writing to the scenario file
would mutate content other saves read and break the `state.scenario != self.scenario.meta` check
at `session.py:250`.

### Verify

New `tests/core/test_extension.py`: a `FunctionModel`-driven scenario staged at `frontier == 1`,
asserting one compile fires, the patch reaches the save, `scenarios/` is untouched on disk, a
second commit at `frontier >= 2` fires nothing, and an advancement applied after a compile lands
still applies cleanly. Note `drowned-road` ships at `frontier == 1`, so a new game fires its
first compile on the very first commit — that is intended, and the test may use it instead of
staging. Gate green. Then by hand: play `drowned-road` past its four locations and confirm the
world grows and the Director prompt stays inside its budget.

**Done when** no `"expander"` role exists anywhere, and a `grows` scenario extends itself in play.
