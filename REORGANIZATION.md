# Reorganization plan

Pure code-organization work: **no behavior changes**. Every step is a move, a rename, or a
re-import. Tests, `ruff`, and `basedpyright` must stay green after each step with zero logic edits.

This supersedes `GEMINI_REORGANIZATION.md`. That draft was written against an assumed layout; the
real tree is already further along (events already imports from a decomposed `domain/models/`
package, `models/` is already split into `base`/`entities`/`state`/`direction`/`consequences`). The
*spirit* of all five of its proposals holds; the specifics below are corrected to the actual code
and extended.

## Ground rules for every step

- **No logic changes.** If a diff changes anything other than imports, file location, or symbol
  location, it does not belong in this reorg.
- **Preserve the dependency direction** (AGENTS.md): `domain/` and `engine/` import nothing from
  `agents/`/`ui/` and do no I/O. A new `utils/` package is a leaf: `utils/` may import `domain/`,
  but `domain/` must never import `utils/` (that would invert the arrow). If a helper is needed by
  `domain/`, it belongs *in* `domain/`, not `utils/`.
- **Keep the flat model namespace.** The convention is `from ..domain.models import X`. Anything
  moved into `domain/models/` gets re-exported from `domain/models/__init__.py` so import sites
  change module path but not shape.
- **No import cycles.** Where a split risks one (R3), the file boundary is chosen to keep imports
  one-directional. This is called out inline.
- **Verify per step:** `uv run ruff check && uv run basedpyright && uv run pytest`. Commit per step
  so any regression is bisectable.

Execution order below is dependency-safe: R1 → R2 → R3 → R4 → R5 → R6 → R7. Forward-looking items
(F1–F3) are staged with explicit triggers.

---

## R1 — Split event data from the reducer; move `Turn` into `models/`

**Why.** `domain/events.py` (125 lines) mixes the event Pydantic classes *and* the reducer
(`apply`, `_apply_one`, `_with_entities`, `render`). The 5e ruleset will multiply event types
(`AttackRolled`, `DamageRolled`, `ConditionApplied`, …); data and reduction logic must not grow in
one file. `Turn` is a pure record and belongs with the other data models, not alone at
`domain/turn.py`.

**Target:**

```text
domain/
├── models/
│   ├── base.py
│   ├── entities.py
│   ├── events.py     # NEW — event classes + Event union only (the `.summary` props stay on them)
│   ├── direction.py
│   ├── consequences.py
│   ├── state.py
│   ├── turn.py       # MOVED from domain/turn.py
│   └── __init__.py   # re-exports events + Turn
└── reducer.py        # NEW (was events.py) — apply, _apply_one, _with_entities, render
```

**Steps.**

1. Create `domain/models/events.py`. Move from `domain/events.py`: `CheckRolled`,
   `InventoryChanged`, `HpChanged`, `Moved`, `EntityDiscovered`, `EntityCreated`, and the `Event`
   union — with their `.summary` properties. Its imports become sibling imports:
   `from .base import Frozen` and `from .entities import Entity, EntityId` and
   `from .base import Ability` (pull exactly the names the classes use; `Ability`/`EntityId` from
   `base`, `Entity` from `entities`).
2. Create `domain/reducer.py` from the remainder of `domain/events.py`: `_with_entities`,
   `_apply_one`, `apply`, `render`. Its header docstring stays (“Typed events and the single pure
   reducer”). Imports:
   `from .models import Ability, Entity, EntityId, GameState, find, updated` and the event classes
   `from .models import CheckRolled, EntityCreated, EntityDiscovered, Event, HpChanged, InventoryChanged, Moved`
   (all now re-exported — see step 4).
3. Move `domain/turn.py` → `domain/models/turn.py`. Rewrite its imports to siblings so it never
   imports the package `__init__` from inside the package:
   `from .events import Event`, `from .base import Frozen, Role`, `from .direction import Direction`,
   `from .entities import Entity, Growth, RejectedGrowth`, `from .state import GameState`.
4. In `domain/models/__init__.py`: add an `from .events import (...)` group (all six event classes
   + `Event`) and `from .turn import Turn`; add each to `__all__`. Import `.turn` **last** in the
   file (it depends on `.events`, `.direction`, `.state`).
5. Delete `domain/events.py` and `domain/turn.py`.

**Import rewrites (every external site):**

| File | Old | New |
|---|---|---|
| `domain/reducer.py` | (was events.py body) | event classes + helpers `from .models import …`; nothing else |
| `engine/resolve.py` | `from ..domain.events import (EntityDiscovered, Event, HpChanged, InventoryChanged, Moved, apply)` | `from ..domain.models import EntityDiscovered, Event, HpChanged, InventoryChanged, Moved` **and** `from ..domain.reducer import apply` |
| `engine/rules.py` | `from ..domain.events import CheckRolled` | `from ..domain.models import CheckRolled` |
| `agents/context.py` (→ see R3) | `from ..domain.events import Event, render` | `from ..domain.models import Event` **and** `from ..domain.reducer import render` |
| `pipeline.py` | `from .domain.events import EntityCreated, apply` + `from .domain.turn import Turn` | add `EntityCreated`, `Turn` to the existing `from .domain.models import …`; `from .domain.reducer import apply` |
| `store.py` | `from .domain.turn import Turn` | add `Turn` to the existing `from .domain.models import …` |
| `ui/panels.py` (→ see R6) | `from ..domain.events import render` + `from ..domain.turn import Turn` | `from ..domain.reducer import render`; `Turn` from `..domain.models` |
| `ui/session.py` | `from ..domain.turn import Turn` | `from ..domain.models import GameState, Role, Turn` |
| `tests/test_events.py` | `from aidm.domain.events import (EntityCreated, EntityDiscovered, HpChanged, InventoryChanged, Moved, apply)` | event classes `from aidm.domain.models import …`; `from aidm.domain.reducer import apply` |
| `tests/test_resolve.py` | `from aidm.domain.events import CheckRolled, EntityDiscovered, InventoryChanged, Moved` | `from aidm.domain.models import …` (all four are re-exported) |

**Note on `render`.** It projects events → player-visible text and is not, strictly, reduction.
Keeping it beside `apply` in `reducer.py` is deliberate: both are “operations that consume
events”, and it keeps `models/events.py` pure data. Leave it in `reducer.py`.

---

## R2 — Extract agent instruction prompts into `agents/prompts/`

**Why.** `director.py`, `narrator.py`, `maintainer.py`, `creator.py` each open with a 10–30 line
instruction string before any wiring. The roadmap calls for modular instructions. Storing them as
**Python string modules** (not runtime-loaded files) keeps them type-checked, adds no I/O to agent
construction, and keeps `test_instructions.py` network-free.

**Target:**

```text
agents/
├── prompts/
│   ├── __init__.py
│   ├── director.py    # TEMPLATE (the raw text with the {consequences} token)
│   ├── narrator.py    # INSTRUCTIONS
│   ├── maintainer.py  # INSTRUCTIONS
│   └── creator.py     # INSTRUCTIONS
├── director.py        # wiring + consequence_menu + INSTRUCTIONS assembly
├── narrator.py        # wiring only
├── maintainer.py      # wiring only
└── creator.py         # wiring only (slug leaves too — see R7)
```

**Steps.**

1. `agents/prompts/__init__.py`: empty (package marker) — a module docstring is fine.
2. `agents/prompts/narrator.py`, `maintainer.py`, `creator.py`: each holds
   `INSTRUCTIONS = """…"""` — the exact current string, verbatim. The role file replaces its literal
   with `from .prompts.<role> import INSTRUCTIONS`.
3. `agents/prompts/director.py`: holds `TEMPLATE = """…"""` — the current `_TEMPLATE` text,
   including the literal `{consequences}` token. **`consequence_menu` stays in `director.py`** — it
   introspects the consequence classes and is assembly logic, not text. `director.py` becomes:
   ```python
   from .prompts.director import TEMPLATE
   # …consequence_menu unchanged…
   INSTRUCTIONS = TEMPLATE.replace("{consequences}", consequence_menu(CONSEQUENCE_TYPES))
   ```
4. No import-site churn: each role module still exposes `INSTRUCTIONS` and `agent`.
   `tests/test_instructions.py` (asserts against `director.INSTRUCTIONS`) keeps passing unchanged.

**Do not** split a single role’s prose into finer sections. Per-role file is the right grain today;
the only dynamic seam is the Director’s assembled `consequence_menu` (see F2).

---

## R3 — Split `agents/context.py` into primitives / vocabulary / policy

**Why.** `context.py` (141 lines) holds three concerns: the render **primitives** (`TurnContext`,
`Block`/`DirectionBlock`/`RequestBlock`, `RolePolicy`), the **block vocabulary** (`PREMISE`,
`CHARACTER`, … — the concrete renderable fragments), and the **policy** (the `CONTEXT` table plus
`prompt_for`/`reads_history` that consume it). AGENTS.md names this table the source of truth for
what each role sees; it should be readable on its own.

**Why three files, not two.** The dependency chain is
`prompt_for → CONTEXT → block instances → Block types`. Gemini’s two-file cut (types+vocabulary in
`context.py`, `CONTEXT` in `policy.py`) forces `prompt_for` and `CONTEXT` apart, which creates a
cycle (`policy` needs the `Block` types, `context` needs `CONTEXT`). Putting the primitive types in
their own leaf breaks it cleanly.

**Target:**

```text
agents/
├── context.py   # primitives: TurnContext, Block, DirectionBlock, RequestBlock, AnyBlock, RolePolicy
├── blocks.py    # NEW — the block instances (PREMISE … PLAYER_PROMPT)
└── policy.py    # NEW — CONTEXT table + reads_history + prompt_for
```

Import arrows: `blocks → context`, `policy → context, blocks`. No cycle.

**Steps.**

1. `context.py` keeps **only** the primitives: `TurnContext`, `Block`, `DirectionBlock`,
   `RequestBlock`, `AnyBlock`, `RolePolicy`. Imports shrink to
   `from collections.abc import Callable, Sequence`, `from dataclasses import dataclass`, and
   `from ..domain.models import Direction, Exchange, GameState, GrowthRequest`. (`Event` stays here
   too — it is a field type of `TurnContext`: `from ..domain.models import Event`.)
2. `blocks.py` (NEW): move the block instances `PREMISE`, `CHARACTER`, `KNOWN_ENTITIES`,
   `UNREVEALED_CANON`, `ENTITY_CATALOGUE`, `RECENT_PLAY`, `DIRECTOR_PLAN`, `DIRECTOR_TONE`,
   `SPEAKER`, `WHAT_HAPPENED`, `NARRATION`, `GROWTH_REQUEST`, `PLAYER_PROMPT`. Imports:
   `from .context import Block, DirectionBlock, RequestBlock`, `from . import views`,
   `from ..domain.models import hidden, known`, `from ..domain.reducer import render` (for
   `WHAT_HAPPENED`).
3. `policy.py` (NEW): move the `CONTEXT` dict, `reads_history`, and `prompt_for`. Imports:
   `from .context import Block, DirectionBlock, RequestBlock, RolePolicy, TurnContext`,
   `from .blocks import (PREMISE, CHARACTER, …every block referenced by CONTEXT…)`,
   `from ..domain.models import Direction, GrowthRequest, Role`. `prompt_for` and `reads_history`
   move verbatim.

**Import rewrites:**

| File | Old | New |
|---|---|---|
| `pipeline.py` | `from .agents.context import TurnContext, prompt_for, reads_history` | `from .agents.context import TurnContext` **and** `from .agents.policy import prompt_for, reads_history` |
| `tests/test_context.py` | `from aidm.agents.context import TurnContext, prompt_for` | `from aidm.agents.context import TurnContext` **and** `from aidm.agents.policy import prompt_for` |

`README.md` and `AGENTS.md` point at `agents/context.py` as “the table”. Update both references to
`agents/policy.py` (the table now lives there). Documentation-only edit; make it in the same step.

---

## R4 — Move starting-state construction into the domain

**Why.** `store.new_game` reads two JSON files *and* composes a `GameState` from them. Composition
is domain knowledge; `store.py` should be a pure I/O boundary. The rule for “what a valid starting
state is” belongs in `domain/`.

**Correction to the Gemini draft:** the factory takes a **`CharacterSheet`**, not a `Character` —
a `Character` needs a `location_id`, which only the scenario supplies.

**Steps.**

1. Add a classmethod to `GameState` in `domain/models/state.py` (it is defined last, so it can
   reference `Character`, `ScenarioDef`, `CharacterSheet` directly):
   ```python
   @classmethod
   def from_scenario(cls, scenario: ScenarioDef, character: CharacterSheet) -> Self:
       """Compose a starting state: a sheet placed at the scenario's start, over its canon."""
       return cls(
           character=Character(**character.model_dump(), location_id=scenario.starting_location_id),
           scenario=scenario.meta,
           world=scenario.as_world(),
       )
   ```
   (`Self` is already imported in `state.py`.)
2. Slim `store.new_game` to pure I/O + delegation:
   ```python
   def new_game(scenario: str, character: str = "kael") -> GameState:
       conf = settings()
       definition = ScenarioDef.model_validate_json(
           (conf.scenarios_dir / f"{scenario}.json").read_text(encoding=ENCODING)
       )
       sheet = CharacterSheet.model_validate_json(
           (conf.characters_dir / f"{character}.json").read_text(encoding=ENCODING)
       )
       return GameState.from_scenario(definition, sheet)
   ```
   `store.py` keeps importing `Character`? No — it no longer constructs one; drop `Character` from
   its `domain.models` import, keep `CharacterSheet`, `GameState`, `ScenarioDef`, `SAVE_VERSION`.

No call-site changes: `store.new_game` keeps its signature. Behavior is identical.

---

## R5 — Extract the UI controller from the view

**Why.** `ui/app.py` (78 lines) mixes NiceGUI layout (`@ui.page`, splitter, `start`) with the
turn-loop actions (`submit`, `restart`, `_on_step`, `_refresh`). The roadmap adds several panels;
separating orchestration from layout keeps both legible. AGENTS.md: keep domain logic out of `ui/`
and drive updates through refreshables — the controller is the seam that does the orchestration.

**Keep the filename `app.py`** (do not rename to `layout.py` as the draft suggested): `__main__`
imports `from .ui.app import start`, and `app.py` still owns `start`/`page`. Renaming buys nothing
and costs an entry-point edit.

**Target:**

```text
ui/
├── controller.py   # NEW — submit, restart, _on_step, _refresh (orchestration)
├── app.py          # page + start (layout + bootstrap), imports controller
├── panels/         # see R6
└── session.py
```

**Steps.**

1. `ui/controller.py` (NEW): move `_refresh`, `_on_step`, `submit`, `restart`. Imports:
   `from nicegui import ui`, `from ..domain.models import Role`, `from ..pipeline import run_turn`,
   `from . import panels`, `from .session import current_session`. Functions move verbatim.
2. `ui/app.py`: keep `start` and the `@ui.page("/") def page`. Replace the moved functions with
   `from .controller import restart, submit`. `page`’s button/`on_click` wiring is unchanged
   (`on_click=restart`, `lambda: submit(box)`).

The controller still touches `ui.input`/`ui.notify` — that is orchestration of NiceGUI, acceptable
in a controller; no *domain* logic moves into it.

---

## R6 — Turn `ui/panels.py` into a `ui/panels/` package

**Why (forward-looking, chosen).** The roadmap adds scenario picker, character sheet, journal, and
known-world panels. One file per panel scales that cleanly; the trace panel (the point of the app)
gets its own module with its private helpers.

**Target:**

```text
ui/panels/
├── __init__.py   # re-exports: chat, role_badges, state_panel, trace_panel
├── chat.py       # chat
├── roles.py      # role_badges
├── state.py      # state_panel
└── trace.py      # trace_panel + _turn_trace + _mechanics + _rejected + _section
```

**Steps.**

1. Create the `ui/panels/` package; delete `ui/panels.py`.
2. `chat.py`: `chat`. `roles.py`: `role_badges`. `state.py`: `state_panel`. `trace.py`:
   `trace_panel`, `_turn_trace`, `_mechanics`, `_rejected`, `_section`, and `_REJECTION_TEXT`
   (`_section` is used only by the trace, so it lives here — no shared-helper module needed).
3. Each module imports what it uses: `from nicegui import ui`, `from .session import Session`
   (note: `session.py` is a sibling of the package’s parent — use `from ..session import Session`),
   and for `trace.py` also `from ...domain.models import ROLES, Mechanics, RejectedGrowth`,
   `from ...domain.turn`→`from ...domain.models import Turn`, `from ...domain.reducer import render`.
   For `roles.py`: `from ...domain.models import ROLES`.
4. `ui/panels/__init__.py`:
   ```python
   from .chat import chat
   from .roles import role_badges
   from .state import state_panel
   from .trace import trace_panel

   __all__ = ["chat", "role_badges", "state_panel", "trace_panel"]
   ```
   This keeps `app.py`/`controller.py`’s `from . import panels; panels.chat(…)` and the
   `(panels.chat, panels.role_badges, panels.state_panel, panels.trace_panel)` tuple in `_refresh`
   working unchanged.

**Watch the relative-import depth:** moving files one level deeper turns `..domain` into
`...domain` and `.session` into `..session`. Fix each moved import accordingly.

---

## R7 — Add a `utils/` package; move `slug` into it

**Why.** `slug` (name → unique `EntityId`) sits in `agents/creator.py` but has no LLM involvement:
it is deterministic id-minting — “the model proposes, Python decides”. It belongs outside the agent
wiring. Per your preference, collect such cross-cutting helpers under a `utils/` package of small,
**targeted** files (one concern per file) rather than one catch-all module.

**Dependency rule (important):** `utils/` is a leaf that may import `domain/`, but `domain/` must
never import `utils/`. `slug` is used only by `agents/creator.py` today, so no cycle arises. If a
future helper is needed *by* `domain/`, put it in `domain/`, not here.

**Target:**

```text
utils/
├── __init__.py
└── ids.py        # slug(name, taken) -> EntityId
```

**Steps.**

1. `utils/__init__.py`: empty (package marker).
2. `utils/ids.py`:
   ```python
   """Deterministic id-minting: a name becomes a unique, stable EntityId."""
   import re
   from collections.abc import Iterable

   from ..domain.models import EntityId

   def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
       # …body moved verbatim from agents/creator.py…
   ```
3. `agents/creator.py`: delete the `slug` definition and the now-unused `import re`; add
   `from ..utils.ids import slug`. `create()` is otherwise unchanged.

No test currently imports `slug` directly, so no test churn. (`agents/creator.py`’s
`from collections.abc import Iterable` stays only if still used elsewhere — after the move it is
not; drop it too.)

---

## Forward-looking (staged — do when the trigger lands, not now)

These are documented so the shape is agreed, but building them before their trigger is speculative
abstraction (AGENTS.md). Each is a small, well-defined move when its time comes.

### F1 — `engine/rules.py` → `engine/rules/` package
**Trigger:** the D&D 5e ruleset replaces the micro-ruleset (roadmap). Today `rules.py` is 18 lines;
splitting it now adds nothing. When 5e lands, grow `engine/rules/` with `checks.py`, `attacks.py`,
`damage.py`, `conditions.py`, keeping `engine/resolve.py` as the mechanics→events dispatcher. The
`engine/ ← agents/` boundary stays the wall this is built behind.

### F2 — Generalize prompt/tool-menu assembly
**Trigger:** a second role gains an assembled, self-documenting menu (today only the Director’s
`consequence_menu` assembles from typed classes). At that point, lift the introspection pattern
(`__doc__` + `GUIDANCE` + field descriptions → menu text) into a shared
`agents/prompts/menu.py` builder and have each role assemble its own menu the way `director.py`
does. Until there are two, keep it inline in `director.py`.

### F3 — Additional `utils/` homes
**Trigger:** the first genuinely cross-cutting, `domain`-independent helper appears. Candidates the
roadmap implies: `utils/text.py` for history windowing/summarisation when history stops being
verbatim. Do **not** relocate `updated` (needs `Frozen`; `domain/` depends on it — must stay in
`domain/models/base.py`) or `render`/`find`/`known`/`hidden` (domain projections — stay in
`domain/`).

---

## Resulting tree (after R1–R7)

```text
src/aidm/
├── agents/
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── director.py      # TEMPLATE
│   │   ├── narrator.py      # INSTRUCTIONS
│   │   ├── maintainer.py    # INSTRUCTIONS
│   │   └── creator.py       # INSTRUCTIONS
│   ├── __init__.py
│   ├── context.py           # render primitives + TurnContext + RolePolicy
│   ├── blocks.py            # the block vocabulary (PREMISE … PLAYER_PROMPT)
│   ├── policy.py            # CONTEXT table + prompt_for + reads_history
│   ├── views.py             # fragment renderers
│   ├── history.py           # exchanges → native messages
│   ├── llm.py               # provider + build_agent
│   ├── director.py          # wiring + consequence_menu + INSTRUCTIONS assembly
│   ├── narrator.py          # wiring
│   ├── maintainer.py        # wiring
│   └── creator.py           # wiring (slug removed)
├── domain/
│   ├── models/
│   │   ├── base.py
│   │   ├── entities.py
│   │   ├── events.py        # event data classes
│   │   ├── direction.py
│   │   ├── consequences.py
│   │   ├── state.py         # + GameState.from_scenario
│   │   ├── turn.py          # moved from domain/turn.py
│   │   └── __init__.py      # re-exports events + Turn
│   └── reducer.py           # apply / render (was events.py)
├── engine/
│   ├── resolve.py
│   ├── rules.py
│   └── growth.py
├── ui/
│   ├── panels/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── roles.py
│   │   ├── state.py
│   │   └── trace.py
│   ├── app.py               # page + start
│   ├── controller.py        # submit / restart / step / refresh
│   └── session.py
├── utils/
│   ├── __init__.py
│   └── ids.py               # slug
├── config.py
├── pipeline.py
└── store.py                 # pure I/O
```

## Verification checklist (run after each step)

```bash
uv run ruff check
uv run basedpyright        # strict; catches a missed import path immediately
uv run pytest              # deterministic, no network
```

Because every step is a move + re-import with zero logic change, a green `basedpyright` + `pytest`
is sufficient proof the step is behavior-preserving. Commit per step (suggested prefix
`refactor(CLEAN): …`, matching the existing history) so any regression bisects to one move.
```
