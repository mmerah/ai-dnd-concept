# PROGRESS

One entry per PLAN.md phase: the counts before and after, the decisions taken off-plan, the
review findings refuted and why, and what is known and accepted.

## Phase 1: words

Counts: `src` 10,432 → 10,471 (target about 10,480), `tests` 11,882 → 11,881, 759 tests before
and after. Four commands green; `uv run aidm` boots and serves the home, create, settings and
pack pages. No golden under `tests/core/fixtures/` moved.

Reviews: two independent Opus reviewers (no `codex` on the machine). Both said the phase was
complete; sixteen findings between them, fourteen fixed, one refuted, one recorded here.

Decisions taken off-plan:

- `render_worldsmith` sits with the public functions of `engines/packs.py`, after the classes,
  not beside `HEAD_ASK` at the top: `CLAUDE.md` fixes the module layout.
- `Engine.author_pack` renders its two prompts through one local closure `asked(intent,
  world_sections, answer_model)` instead of spelling the seven-keyword call twice.
- `Labelled` is `Named`, and `with_ids(rows, taken)`: a class called `Labelled` whose fields are
  `name` and `brief` said the old word. Nothing serialised carries the class name.
- `Echoed` is `_Echoed` in `app/builtin.py`: every other model there is module-private and it
  has no user elsewhere.
- `core/entities.py` gains `headline_of(name, entity_id, brief)` beside `tag_of`; `Thing.headline`
  and `Subject.headline` both call it.
- `twentyfourxx/engine.py::_item_lines` and `CrewSheet.gear_text` spell `name[id]` through
  `tag_of`; the local holding a skill's name in `build_character` and the parameter of
  `Crewmate.raise_skill` are `skill`, not `label`.
- `qa/agents.py` says `conversations`/`conversation_id`; `qa/s_requests.py`'s docstring says
  "commission".

Refuted:

- "`render_worldsmith(role: str)` carries the text of `worldsmith.md`, while `role` elsewhere is
  a `Role` id; rename to `role_text`." Refuted: `app/roles.py::render_interjection` already
  binds the rendered role text to a local `role`, so the renderers share one word; and the
  section it fills is `YOUR ROLE`.

Known and accepted:

- PLAN.md's "nothing serialised changes except the pack JSON keys" was not exact. `PendingOption`
  (`label`/`detail`/`name` → `name`/`brief`/`tool_name`) and `Scene.offered` → `way_offered`
  live inside a saved `Game`, so a save written before this phase is invalid, which is the
  documented rule (saves have no version). A pack the player wrote under `packs/<engine>/`
  before this phase still carries `label`/`detail` rows (and, for 24XX, `hostiles`), so
  `read_packs` logs a warning and skips it at startup until the player edits the keys; no
  compatibility path was added.
