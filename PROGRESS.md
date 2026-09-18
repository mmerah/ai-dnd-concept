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

## Phase 2: engines

Counts: `src` 10,471 → 10,439 (target about 10,411), `tests` 11,881 → 11,918 (target about
11,856: the fold added three tests, and every `Goon` a test builds now passes `hp` and `place`),
759 → 760 tests. Four commands green; `uv run aidm` boots. Goldens moved:
`tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json` (the npc schema lists `kit`),
`tests/core/fixtures/schemas/twentyfourxx/master_tools.json` (`kill`'s own description) and
`characters/kael/tunnelgoons.json` (gains `place` and `hp`).

Reviews: two independent Opus reviewers (no `codex` on the machine). Both said the phase was
complete; twenty findings between them (eight shared), all but two fixed, two refuted below.

Decisions taken off-plan:

- `Operation[W: World[Any]]` with `write: Callable[[Game[W], ...]]`, and `operations() ->
  Mapping[Slug, Operation[W]]`: the plan's `AnyGame` erased the world type the engine carries.
- `require_hireable` is a free function in `engines/hiring.py`, with `ALREADY_SHEETED`, not a
  method on `World`: only the two hiring engines call it, and `hiring.py` is where hiring lives.
  `hire_target(world, commission)` holds the `NO_HIRE_TARGET` check both `write_hire` heads
  copied; `file_hire(draft, target_id, terms)` takes the id, so each `hire` tool is one line.
  `signed_on[M: Person](world: World[M], member: M, summary)` ties the member to the cast.
- `_args_of` reads the third parameter and requires its name, with a leading underscore allowed,
  to be `args` and its annotation a `BaseModel`: `_published.call` binds positionally, and the
  repo spells an unused parameter `_rng`, so `rest` and the test's `strike` keep `_args: NoArgs`
  and no `del args` line was added.
- `Goon.kit` carries `description="Leave empty."`, `Goon.required()` refuses a fresh npc that
  arrives with a kit, and the class docstring is worded for the worldsmith who reads it as the
  npc schema's description.
- `TwentyfourxxEngine.kill` describes what it adds (the succession pick) instead of copying
  `Engine.kill`'s sentence; the 24XX `master_tools.json` golden moved for it.
- `Engine.guidance` reads `self.authoring`, not `self.pack_author.authoring`: the same string,
  one hop fewer. `PackAuthor.author` keeps the plan's named closures `check_head`/`check_body`;
  a lambda returning the pack does not satisfy `Check[T] = Callable[[T], None]`.
- The drift test Part A removed was parametrised over three engines, so the count fell by three,
  not one. `test_seeds_lists_the_packs_own_seeds` stays, renamed, against
  `packs.require(...).seeds`.
- One test each for the three new behaviours the fold added: a kit-carrying npc refused, a
  sheetless Tunnel Goons player refused, a tool whose third parameter is not `args` refused.

Refuted:

- "`HIRED` and `UNWRITTEN_CAST` are pack-authoring prose and belong in `engines/tools.py` or
  each `pack.py`, not `hiring.py`, which now pulls `engine.py` into two leaf modules." Refuted:
  both strings are hiring prose (`HIRED` heads the `write_hire` intent, `UNWRITTEN_CAST` says the
  cast is hired in play); `engines/tools.py` held them only because no hiring module existed;
  and every engine module already imports `engine.py`, so the chain adds no cycle and no cost.
- "`PackAuthor.author(*, source, origin, ...)` writes `"source": origin`; rename the prompt
  parameter." Refuted as a rename: `source` means source material on `Game`, `Scenario`,
  `Engine.author` and `render_worldsmith`; the odd one is the serialised `Pack.source` key,
  which means provenance in fourteen shipped JSON files. A comment on that line says so.

Known and accepted:

- The played `Goon` carries `place=PLAYER_ID`, a slug that is not a place and is never read
  (`RoomWorld.current` is where the player stands); a comment in `build_character` says so.
- `_player_carries_a_sheet` lives on both `TunnelGoonsWorld` and `TwentyfourxxWorld`: Loner 3e
  has no sheet, so `World` cannot hold it.
- A Tunnel Goons save written before this phase is invalid (its `Goon` player lacks `hp` and
  `place`), which is the documented rule.
