# Simplification plan

Five phases, in order. Each one lands on its own: run the full check, commit, move on.
Do not start a phase before the one above it is green.

| # | Phase | Net lines | Effort |
|---|---|---|---|
| 0 | One rule in `AGENTS.md` | +3 | 5 min |
| 1 | One identifier grammar | −15 | 1 h |
| 2 | Required engine capabilities | −60 | 2 h |
| 3 | Framework-free commands | −190 | 1 day |
| 4 | Package moves | ±0 | 2 h |

## Rules for every phase

- The check, from the repo root, with `UV_CACHE_DIR` unset:
  `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`
- No compatibility shims. Update every caller instead. Existing saves may break; delete them.
- When a golden fixture changes, read the diff and be able to say why each line moved.
- Text a model reads (tool and field descriptions, prompt files) is behaviour: move it verbatim.

---

## Phase 0 — One rule in `AGENTS.md`

Under `## Engineering`, after the "Build every agreed capability..." bullet, add:

> - This project is pre-stability. Choose the simplest final architecture. Rename, move, delete,
>   merge, or replace any module, schema, prompt, file format, save, or test that a simpler
>   design needs, and update every caller.

`CLAUDE.md` is a simlink of `AGENTS.md`

---

## Phase 1 — One identifier grammar

Four grammars today — `Slug` (kebab), `ContentSlug` (kebab plus doubled/leading hyphens),
`OptionId` (kebab plus underscores), `EntityId` (no rule at all). After this phase: one,
kebab-case, max 64 characters.

### 1.1 Move `Slug` out of `config.py`

`Slug` is a domain grammar, not an operator knob, but `state/entities.py:8` imports it from
`aidm.config` — the wrong direction.

1. Move the `SLUG_PATTERN`, `SLUG_MAX` and `Slug` lines from the top of `src/aidm/config.py` into
   `src/aidm/state/entities.py`, just below its imports and above `class Frozen`.
2. Delete `from aidm.config import SLUG_MAX, SLUG_PATTERN, Slug` from `state/entities.py`, and add
   `from aidm.state.entities import Slug` to `config.py` (`AuthoringConfig` uses it).
3. In `tests/core/test_package_boundary.py`, add `"aidm.config"` to the `state` forbidden set.

### 1.2 Delete `ContentSlug`

Every shipped pack id already satisfies `Slug`, so this is a pure rename with no data change.

1. Delete `ContentSlug` from `state/entities.py` (around line 37, with its comment).
2. Replace every `ContentSlug` with `Slug` in: `engines/loner3e/rules.py`,
   `engines/twentyfourxx/rules.py`, `state/creation.py`. Fix the imports on each file.

### 1.3 Give `EntityId` the grammar

`EntityId` stays a `NewType` so `EntityId("mara")` keeps working; the rule goes on the fields.
In `state/entities.py`, add near the id types:

```python
ID_RULE = Field(pattern=rf"^{SLUG_PATTERN}$", max_length=SLUG_MAX)
```

Then, using `Field(...)` as the default keeps the field required:

- `class Exit`: `to: EntityId = ID_RULE`
- `class Entity`: `id: EntityId = ID_RULE`
- `class Entity`: `parent_id: EntityId | None = Field(default=None, pattern=..., max_length=...)`
  — same pattern and length, spelled out because it needs a default.

Do **not** touch `EntityId` annotations anywhere else. Director tool parameters are still derived
from function signatures in this phase, so their JSON schemas must not change.

### 1.4 Make the generator write hyphens

In `state/entities.py::slug`, change the `re.sub` replacement, the `.strip()` argument and the
`_unused` join character from `_` to `-`. That makes it `text_slug` without the length cap.

### 1.5 Collapse `OptionId`

24XX defence option ids are carried-item entity ids, now kebab, so the underscore allowance is dead.

1. Delete `OptionId` from `state/play.py` (around line 34, with its comment).
2. Replace every `OptionId` with `Slug` in: `state/play.py`, `engines/core.py`,
   `engines/twentyfourxx/engine.py`, `engines/twentyfourxx/rules.py`, `app/codemode.py`, and
   `tests/core/test_decisions.py`.

### 1.6 Rewrite the data

Ten ids use underscores. Rewrite them in one pass:

```bash
rm -f saves/*.json          # stale saves are invalid, not migrated
IDS="bell_tower cloister_rat vault_map bell_house bronze_key crypt_entrance
     lantern_chapel mara_voss ovid_sarn tarns_end"
for id in $IDS; do
  grep -rlZ --exclude-dir=.venv --exclude-dir=.git --exclude-dir=.ruff_cache "$id" . \
  | xargs -0 -r sed -i "s/$id/${id//_/-}/g"
done
```

That touches two `world.json` files, the golden fixtures, several tests, `evals/turn_eval.py` and
`src/aidm/app/prompts/scenario_world.md`.

### 1.7 Fix the authoring prompt

In `src/aidm/app/prompts/scenario_world.md` line 15, change `unique lowercase underscore id` to
`unique lowercase id of words joined by hyphens`.

**Done when:** the check is green and `grep -rn "ContentSlug\|OptionId" src/ tests/` finds nothing.

---

## Phase 2 — Required engine capabilities

Both shipped engines set `advancement` and `creation`, and both planned ones (Fate Condensed,
Cairn Barebones) will too. Stop pretending otherwise.

### 2.1 Merge `sheets.py` into `core.py`

1. Copy all of `src/aidm/engines/sheets.py` into `src/aidm/engines/core.py` below `class Engine`,
   dropping its import block and adding anything missing to core's. Delete `sheets.py`.
2. Fix the imports in `engines/loner3e/engine.py`, `engines/twentyfourxx/engine.py`,
   `engines/loner3e/rules.py`, `engines/twentyfourxx/rules.py`, and any test naming
   `aidm.engines.sheets`.

### 2.2 Keep `Engine` and `SheetEngine` as two classes

Do **not** fold them into one generic `Engine[S: SheetBase]`. It does not typecheck: `S` appears
in `SheetMechanics.sheets: dict[EntityId, S]`, so basedpyright infers it invariant, and
`type[Loner3eEngine]` stops being assignable to `type[Engine[SheetBase]]` — breaking
`ENGINES: tuple[type[Engine], ...]` and every `engine: Engine` parameter. Verified against the
repo's own basedpyright 1.39.10.

The merged file keeps both classes and the existing one-line
`# pyright: ignore[reportIncompatibleVariableOverride]`. Ordering: `SheetBase`, `SheetMechanics`
and `SheetAdvancement` go above `class SheetEngine`.

### 2.3 Make both capabilities required

In `Engine.__init__`, delete the two `= None` assignments and declare them as class attributes
next to `mechanics_type` instead: `advancement: Advancement` and `creation: CharacterCreation`.
Each engine's `__init__` already assigns both; only the type was optional.

Now delete every `is None` branch that guarded them. (`GameSession.advisor` stays `Agent | None`
— code mode has none. Leave that one alone.) The full list:

| File | What to delete |
|---|---|
| `engines/core.py` (was `sheets.py`) | the `if self.advancement is not None:` guard in `seed` — keep its body |
| `app/runtime.py` | `build_advisor`'s `None` return; `advancement is None or` in `offers`; the whole `_advancement` helper — call `self.engine.advancement` directly |
| `app/codemode.py` | the `None` branch in `open_game`; the `advancement is None` branch in `rules`; the `advancement is None or` guard in `propose_advance` |
| `ui/game.py` | `advancement is None` around line 431/435 — the tab is now always built |
| `ui/create.py` | `if creation is None` around line 30 |

`app/mcp.py` publishes `PROPOSE_ADVANCE` and `APPLY_ADVANCE` conditionally via
`harness.advance_args is not None`. Keep that shape for now; Phase 3 rewrites it.

`tests/core/test_engine.py`'s stub sets neither capability and asserts `engine.advancement is
None`: delete the assertion, assign both. Minimum to get green, no more.

**Done when:** the check is green and `grep -rn "advancement is None\|creation is None" src/`
finds nothing.

---

## Phase 3 — Framework-free commands

A director command becomes a Pydantic argument model plus a Python function; Pydantic AI and MCP
each become a thin adapter over the same list, and `pydantic_ai` leaves `engines/`. Dynamic tool
gating and schema rewriting go with it — the prompt already carries what they encode.

### 3.1 The command record

All of this goes **into `src/aidm/engines/core.py`**, not a new module: `Engine.director_commands`
needs `Command` and `Command` needs core's `DirectorContext`, so a separate `commands.py` would be
an import cycle. Core loses `apply_tool_call`, `sequential_toolset` and `with_enum` here anyway.
Nothing in this section imports `pydantic_ai`.

```python
@dataclass(frozen=True, slots=True)
class Command:
    """One director command: what the model reads, and the resolver that runs it."""

    name: str
    description: str
    args: type[BaseModel]
    call: Callable[[DirectorContext, Mapping[str, JsonValue]], str]
    # Core world commands may still run in a turn that opened suspended; engine mechanics may not.
    during_suspension: bool = False


def command[A: BaseModel](
    name: str,
    description: str,
    args: type[A],
    run: Callable[[DirectorContext, A], str],
    *,
    during_suspension: bool = False,
) -> Command:
    """Validation lives here, so both harnesses reject the same arguments the same way."""

    def call(deps: DirectorContext, raw: Mapping[str, JsonValue]) -> str:
        return run(deps, args.model_validate(raw))

    return Command(name, description, args, call, during_suspension)


def run_command(found: Command, deps: DirectorContext, raw: Mapping[str, JsonValue]) -> str:
    """The one gate: a decision on the table blocks everything but developing its answer."""
    pending = deps.draft.pending
    if pending is not None and not (found.during_suspension and deps.suspended_at_start):
        raise ValueError(
            f"the rules are waiting on the player: {pending.prompt}\n"
            "Put that to the player, then start the next turn with their answer."
        )
    return found.call(deps, raw)
```

Also move `apply_tool_call` here from `engines/core.py` and rename it `apply_command`. Change its
first parameter from `ctx: RunContext[DirectorContext]` to `deps: DirectorContext`, delete the
`deps = ctx.deps` line, and change `raise ModelRetry(refused)` to `raise ValueError(refused)`.

Delete `sequential_toolset` and `with_enum` from `engines/core.py`.

### 3.2 The core world commands

New file `src/aidm/engines/world.py`. Move the nine functions out of `core_toolset()` in
`turn/run.py`. Each becomes an args model plus a handler.

Pattern, for `move`:

```python
class Move(Frozen):
    entity_id: EntityId = Field(
        description="Exact actor or item id. The item must be carried by the player or loose here."
    )
    to_id: EntityId = Field(
        description="Exact destination id. Use a location for an actor; for an item, use `player`,\n"
        "an actor here, or the player's location."
    )


def _move(deps: DirectorContext, args: Move) -> str:
    play = lambda draft, _rng: tuple(actions.move(draft, args.entity_id, args.to_id))
    return apply_command(deps, play)


CORE_COMMANDS: tuple[Command, ...] = (
    ...,
    command(
        "move",
        "Move an actor to a new location, or move a nearby item.",
        Move,
        _move,
        during_suspension=True,
    ),
    ...,
)
```

Rules while moving them:

- The `description` is the old docstring's **summary line**, verbatim; each field's `description`
  is its `Args:` entry, verbatim, newlines and backticks included.
- Annotate ids as bare `EntityId` / `Slug`, matching the old signature. Do not add patterns —
  3.8 adds them everywhere at once, after 3.7's fixture gate has passed.
- All nine get `during_suspension=True`. `advance_thread` reuses `AdvanceThread` as its args type.

Delete from `turn/run.py`: `DirectorTool`, `core_toolset`, `_resolved`, `_unlock_targets`,
`_narrow_unlock_targets`, `_a_locked_way_out`, `_an_actor_to_recruit`, `_a_party_member`,
`_an_unresolved_thread`, `_a_trait_in_reach`, and `gated_toolsets`.

### 3.3 The engine commands

`Engine` gains `director_commands: tuple[Command, ...] = ()` in `__init__`, replacing
`director_toolsets`. Delete the `director_toolsets` attribute.

Convert `engines/loner3e/engine.py::director_toolset` and
`engines/twentyfourxx/engine.py::director_toolset` the same way as 3.2, leaving
`during_suspension` at its `False` default. Three things 3.2 does not cover:

- `roll_question`, `roll_attempt`, `stake_attempt` and `roll_luck_test` already take one model —
  reuse it as `args`. `restore_luck`, `settle_defence`, `change_credits` and `complete_chapter`
  need new ones, including a **zero-field** model for `complete_chapter`.
- loner3e's tools close over `twists`, so its list is built by a function taking `twists` and
  assigned to `self.director_commands` in `__init__`, not a module constant.
- `_defence_to_settle` takes `ctx: RunContext[DirectorContext]` today. Change the parameter to
  `deps: DirectorContext` and drop the `ctx.deps` hops, or it will not compile once `RunContext`
  leaves the module.

Delete the dynamic machinery from `engines/twentyfourxx/engine.py`: `_skills_in_play`,
`_narrow_to_skills_in_play`, `_with_skills`, and the `.filtered(...)`/`.prepared(...)` chain at the
end of `director_toolset`. `settle_defence` already raises its own "no hit is waiting to be
settled" retry, which becomes a `ValueError` with the same text. The skill enum and the
`unlock_exit` enum go on purpose: the prompt already prints every actor's skills under `state:`
and every exit under `EXITS FROM HERE`.

### 3.4 The Pydantic AI adapter

These three functions go at the top of `src/aidm/turn/run.py`, which loses ~150 lines in 3.2.
Do not make a new module for them.

```python
def command_schema(found: Command) -> dict[str, JsonValue]:
    """One schema function, so what MCP publishes is what the agent is offered."""
    schema = found.args.model_json_schema(schema_generator=GenerateToolJsonSchema)
    # A model carries its class name; a tool schema built from a signature never did.
    schema.pop("title", None)
    return schema


def as_tool(found: Command) -> Tool[DirectorContext]:
    async def call(ctx: RunContext[DirectorContext], **raw: JsonValue) -> str:
        try:
            return run_command(found, ctx.deps, raw)
        except ValueError as refused:
            raise ModelRetry(str(refused)) from refused

    return Tool.from_schema(
        call,
        found.name,
        found.description,
        command_schema(found),
        takes_ctx=True,
        sequential=True,
    )


def director_toolset(engine: Engine) -> FunctionToolset[DirectorContext]:
    commands = (*CORE_COMMANDS, *engine.director_commands)
    return FunctionToolset(tools=[as_tool(one) for one in commands], max_retries=2)
```

`GenerateToolJsonSchema` comes from `pydantic_ai.tools`. With `title` popped it reproduces every
current golden schema except five — `advance_thread`, `roll_question`, `roll_attempt`,
`stake_attempt`, `roll_luck_test` already take a model, so each loses one `"title"` line. Those
five deleted lines are the **only** expected fixture diff; anything else means a paraphrase.
`Tool.from_schema` calls with keywords only and skips its own validation, which is why `command()`
validates. In `director_agent`, use `toolsets=[director_toolset(engine)]`.

### 3.5 The MCP adapter

In `app/mcp.py`:

1. Delete `reshapes` only. `_as_mcp_tool`, `_authoring_tools`, `AUTHORING_TOOLS` and
   `_advance_tools` all stay — authoring tools are still published and routed through them, and
   `_advance_tools` is still what puts `propose_advance`/`apply_advance` on the wire. After
   Phase 2 `_advance_tools` is called unconditionally.
2. `offered()` stays a function, because which director commands exist depends on the open engine,
   but it stops calling `await harness.director_tools(None)`. Instead:

   ```python
   def _published(found: Command) -> types.Tool:
       return types.Tool(
           name=found.name, description=found.description, input_schema=command_schema(found)
       )
   ```

   extending the list with `_published(one)` for each of
   `(*CORE_COMMANDS, *harness.session.engine.director_commands)`.
3. Keep `NotificationOptions(tools_changed=True)` and `send_tool_list_changed`, but fire it only
   when `params.name == "open_game"` — that is now the one call that changes the list. This is
   what replaces `reshapes`: one notification per game, not one per tool call.
4. `on_call_tool` already catches `(ModelRetry, ValueError)`, so `run_command`'s plain
   `ValueError` refusals need no change.

In `app/codemode.py`:

1. Delete `director_tools()` entirely, along with the `TestModel`, `RunUsage`, `RunContext`,
   `AbstractToolset` and `ToolsetTool` imports, the `toolsets` field on `Harness`, the
   `self.toolsets = tuple(gated_toolsets(session.engine))` line inside `open_game`, and the
   `gated_toolsets` import.
2. `call_director_tool` becomes:

   ```python
   def call_director_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
       session = self.opened()
       turn = self.started()
       found = next((one for one in self._commands() if one.name == name), None)
       if found is None:
           raise ModelRetry(f"{name!r} is not a command of the {session.engine.id!r} engine.")
       deps = DirectorContext(
           engine=session.engine,
           draft=session.state.draft(),
           rng=session.rng,
           log=turn.log,
           suspended_at_start=turn.suspended_at_start,
           answered=turn.answered,
       )
       answered = run_command(found, deps, raw)
       session.commit(deps.draft.committed())
       return answered
   ```

   `_commands()` returns `(*CORE_COMMANDS, *self.opened().engine.director_commands)`. This is no
   longer `async`; drop the `await` at its one call site, `mcp.py::call`.
3. Delete `_unavailable` — `run_command` now carries that message.

### 3.6 Advancement without `create_model`

Delete `_advance_args` from `app/codemode.py`. Make `AdvanceArgs` generic instead:

```python
class AdvanceArgs[P: ProposalBase](ToolArgs):
    subject_id: EntityId
    """Exact id of the character the offer names."""
    proposal: P
    """The change to draft, in this engine's own vocabulary."""
```

`Harness.advance_args` becomes `AdvanceArgs[engine.advancement.proposal_type]`, built where
`_advance_args` was called. Since Phase 2 made `advancement` required, drop the `| None` on the
field and the `advance_args is None` guard.

### 3.7 Tests

Do the minimum to get green; tests are not the point of this phase. Five files name the deleted
machinery — `test_tools.py`, `test_golden_schemas.py`, `test_engine.py`, `test_decisions.py`,
`tests/twentyfourxx/test_twentyfourxx_engine.py`. Point them at `CORE_COMMANDS`,
`engine.director_commands` and `command_schema`, and delete any assertion about tool filtering or
schema enums outright rather than rewriting it.

Keep `test_golden_schemas.py` working, though: it is what proves the schemas did not move.

**Done when:** the check is green, `grep -rn pydantic_ai src/aidm/engines/` finds nothing, and
the only fixture diff is the five deleted `"title"` lines from 3.4.

### 3.8 Fold the grammar into `EntityId`

Phase 1 left `EntityId` a bare `NewType` and put the kebab rule on three `Entity`/`Exit` fields
through `CheckedEntityId`, because tool schemas were still derived from function signatures and had
to stay byte-identical. Once 3.1-3.7 are green the arguments are Pydantic models, so:

```python
EntityId = NewType("EntityId", Slug)
```

Pydantic 2.13 unwraps the `NewType` and rejects `bell_tower`, so `CheckedEntityId` is deleted and
`Exit.to`, `Entity.id` and `Entity.parent_id` go back to bare `EntityId`.

This one **does** move the golden schemas, on purpose: every `EntityId` parameter gains the same
`pattern` and `maxLength` pair. Read the fixture diff and confirm it is only that. Do it before
3.9, so the eval measures the added pattern along with the removed enums.

### 3.9 Measure the enums you removed

The baseline already exists: `evals/results/after-stake-flatten.json`, with no code change since.
Do not re-run it. After Phase 3 (real model calls, needs an API key):

```bash
uv run python evals/turn_eval.py run --label after-commands
uv run python evals/turn_eval.py compare \
  --baseline evals/results/after-stake-flatten.json \
  --candidate evals/results/after-commands.json
```

Watch `score` and `director_calls`. Case ids and expectation names are already kebab, so Phase 1
does not disturb the comparison. If the score drops, the missing enums are the first suspect — but
do not bring back per-call schema rewriting. The resolver knows the legal values, so make its
refusal name them (`"no locked exit leads to 'x'; the locked ways out are: ..."`). One retry beats
machinery that ran on every call.

---

## Phase 4 — Package moves

Mechanical. `app/` is currently runtime, launch, media, authoring, authoring_run, codemode, mcp.
Split it so the rule is one line: **game and engines know no UI, MCP, or agent framework.**

Target flow: `state <- content <- engines <- turn <- authoring <- app <- {ui, harness}`

### 4.1 Split `app/launch.py`

`authoring/` needs `build_engine` and `begin_game` while `app/` needs `authoring/`. Break the
cycle by moving the engine registry below both.

1. New file `src/aidm/engines/registry.py`. Move exactly these six names into it: `ENGINES`,
   `engine_ids`, `engine_class`, `build_engine`, `as_engine_id`, `begin_game`.
2. `app/launch.py` keeps everything else (the catalog, the launch target, the controller) and
   imports the registry.
3. Update every importer of `aidm.app.launch` for the six moved names.

### 4.2 Create `src/aidm/authoring/`

- `app/authoring.py` → `authoring/draft.py`
- `app/authoring_run.py` → `authoring/run.py`
- `app/prompts/` → `authoring/prompts/`

Fix `_PROMPTS_DIR` in `authoring/run.py` (it is `Path(__file__).parent / "prompts"`, so it keeps
working after the move). Add an empty `authoring/__init__.py`.

### 4.3 Create `src/aidm/harness/`

- `app/codemode.py` → `harness/codemode.py`
- `app/mcp.py` → `harness/mcp.py`

Add an empty `harness/__init__.py`. Update `.mcp.json`: `"args": ["run", "python", "-m",
"aidm.harness.mcp"]`.

### 4.4 Update the boundary test

`tests/core/test_package_boundary.py`:

1. Rewrite the comment on line 8 to the new flow, and replace `FORBIDDEN` with:
   ```python
   FORBIDDEN = {
       "state": {
           "aidm.config",
           "aidm.content",
           "aidm.engines",
           "aidm.turn",
           "aidm.authoring",
           "aidm.app",
           "aidm.ui",
           "aidm.harness",
           "nicegui",
       },
       "content": {
           "aidm.engines",
           "aidm.turn",
           "aidm.authoring",
           "aidm.app",
           "aidm.ui",
           "aidm.harness",
           "nicegui",
       },
       "engines": {
           "pydantic_ai",
           "aidm.turn",
           "aidm.authoring",
           "aidm.app",
           "aidm.ui",
           "aidm.harness",
       },
       "turn": {"aidm.authoring", "aidm.app", "aidm.ui", "aidm.harness", "nicegui"},
       "authoring": {"aidm.app", "aidm.ui", "aidm.harness", "nicegui"},
       "app": {"aidm.ui", "aidm.harness", "nicegui"},
       "ui": {"aidm.engines"},
       "harness": {"aidm.ui", "nicegui"},
   }
   ```
   `"pydantic_ai"` on `engines` is Phase 3's grep turned into a standing test; it makes the two
   per-file `rules.py` rows redundant, so they go.
2. `test_only_the_loader_names_a_concrete_engine` now expects `{"engines/registry.py"}` — that
   file naming the two concrete engines is the one allowed exception, and this is what pins it.

**Done when:** the check is green, `uv run aidm` starts, and the MCP server answers
`list_games` from a fresh Claude Code session.
