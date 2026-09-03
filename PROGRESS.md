# PROGRESS

One entry per phase of `PLAN.md`: the `src` line counts at start and end, decisions made off-plan,
refuted review findings and why, and what is known and accepted.

## Standing decisions

The two decisions that leave with `PROPOSALS.md`, quoted:

- "A base class where we own every implementation; a `Protocol` only where a test double or a
  foreign object must fit without inheriting."
- "The page polls the service; the service never calls the page."

## Phase 1 — the ground

`src` lines: 9,205 at start (`ae6be39`), 9,249 at end after the fold; the target was about 9,190. Tests: 472 to
475. Every golden under `tests/core/fixtures/` unchanged; `prompts/*`, `schemas/*`, `turn/*`,
`rules.md`, `worldsmith.md`, `master_tools.json`, `scenarios/`, `characters/` byte-identical.

What landed: §1.1 mechanical cleanups, §1.2 `Refusal` and `parse`, §1.3 the boundary test over
four engines and one `kill()` per world, §1.4 verbs, one reading verb, one stem per engine,
`engines/core.py` → `engines/base.py`.

### Decisions made off-plan

1. **`type` aliases, §1.1.1: only the four in `config.py`.** Measured on pydantic 2.13.4: a PEP
   695 `TypeAliasType` field is emitted in JSON schema as `$defs/<Alias>` plus a `$ref`, where an
   assigned alias is inlined. `Slug`, `CheckedEntityId`, `TagKind`, `Ability` and `Boost` sit in
   tool-argument models, so converting them changes `schemas/*/master_tools.json`. "How to work"
   rule 9 (`schemas/*` byte-identical throughout) wins; those five stay assigned aliases.
   `ui/settings.py` reads a `TypeAliasType` through as planned (`_unaliased`).
2. **`opening_canon(draft, source, cast_type)` and `build_scenario(..., cast_type)`.** With
   `revalidate_instances="always"` a bare `SceneCanon(...)` revalidates each `Loner3eSheet` cast
   entry as the unbound `C`'s bound, `Person` (`extra="forbid"` refuses `concept`). The canon is
   parametrized at runtime, `SceneCanon[cast_type]`, as `opening_draft` already parametrizes the
   drafts. PLAN §2.2.5 says `opening_canon(draft, source)` "stays a free function": Phase 2's
   engine method has `self.cast` at hand and should pass it.
3. **`parse` prefixes the error's `loc`** (`item: Field required`) when it is non-empty; PLAN
   §1.2.1 spelled `errors()[0]["msg"]` alone. A refusal that names no field is not actionable by
   the master, and the skip log for a stale save would name none.
4. **`core/io.py::_read_text` maps `UnicodeDecodeError` to `Refusal`**, as `decode` maps
   `JSONDecodeError`: a `ValueError` subclass the old `except ValueError` swallowed would
   otherwise escape the narrowed `except Refusal` and empty the home page for one bad file.
5. **Tunnel Goons `create_character` parses its payload** (`parse(TunnelGoonsPayload, {...})`)
   instead of keyword construction: the ability-sum rule lives in the sheet's validator, so a
   legal-per-pick split that does not sum to 3 raised `ValidationError` past the create page's
   narrowed `except Refusal`. Breathless and 24XX keep keyword construction (§1.1.7): their picks
   are fully checked before the payload is built. Breathless narrows `str` to `Skill` with a
   lookup over `SKILLS` (`_skill`) rather than a cast.
6. **Two extra renames by the same rule:** test support `_opened` → `_open_game`, and the
   test-local `FifthScenarioFile` → `FifthScenario` in `tests/core/test_seam.py`.
7. **`tests/core/test_tool_surface.py`: a second game in flight now crashes the call** rather than
   being routed as a refusal. PLAN §1.2.4 keeps `Runtime.playing` a `ValueError` (a bug, not a
   message), and the narrowed catches no longer turn it into a tool result.
8. Two tests that expected `ValidationError` from a boundary that now parses expect `Refusal`
   (`tests/core/test_integrity_boundaries.py::test_a_save_whose_payload_the_engine_rejects_is_refused`,
   `tests/core/test_decisions.py::test_an_option_whose_call_names_no_tool_or_carries_args_it_rejects_is_refused`).
   Every other `pytest.raises(ValueError)` stays (§1.2.6).

### Refuted findings and why

- `app/media.py::Illustrator` and `app/speech.py::Reader` dropped `frozen=True` (Opus review):
  PLAN §1.1.10 says so in those words. Refuted by the plan, not by taste.
- Breathless and 24XX should parse their payload like Tunnel Goons (Opus review): Breathless's
  skill steps exclude earlier picks (`tests/breathless/test_create.py::test_skill_steps_exclude_earlier_picks`),
  so `_three_skills` cannot fire on a checked pick; `TwentyfourxxPayload` has no validator.
  Keyword construction stays where no validator can refuse a checked pick.
- `breathless/creation.py::_skill`'s bare `next()` (Opus review): unreachable after
  `check_picks`, which holds the answer to the six skill ids. A message for an impossible state
  is a comment in code.
- `core/model.py`: drop `SerializeAsAny` from `payload` (Opus cut): payload shapes are Phase 3's
  (§3.4); not touched here.
- `deepcopy` in `tunnelgoons/engine.py::new_game` and `scenes/world.py::new_world` (Fable cut):
  left in place; the copy is cheap and the aliasing it prevents is not covered by a test.
- `app/launch.py::read_catalog`: `files.load(slug)` runs outside the skip `try`, so a non-UTF-8
  save file still takes the home page down. Not a regression of this phase (the old code had the
  same shape) and PLAN §2.7.4 restructures `read_catalog`; left for Phase 2.

### Known and accepted

- The line count is 59 over the plan's estimate: one `Refusal` import per raising module and the
  `parse`, `decode`, `_read_text` and `kill` bodies the estimate did not count. Nothing padded,
  nothing invented.
- A `Refusal` raised inside a pydantic validator is wrapped into a `ValidationError` (PLAN §1.2.4
  accepts this); `ask`'s `except ValidationError` still re-prompts a worldsmith whose draft
  builds an unvalidatable canon.
- Reviews: the implementing session had no `Agent` tool and no `codex`, so it ran the
  `/code-review` skill and `.claude/prompts/review.md` itself; the orchestrator then ran two
  independent `reviewer` agents (Fable and Opus) over the staged diff and folded both. Fixed
  from them: `Game.commit` goes through `parse`; `working()`'s docstring; `Ask` → `Spawn` in
  `app/spawn.py`; `ban-relative-imports = "all"` so `TID252` guards single-dot imports too;
  `build_scenario` called with keyword arguments; one test that a `type`-aliased `Literal`
  field is still a dropdown; the now-unreachable relative-import resolver in
  `tests/core/test_package_boundary.py` deleted.
- `uv run aidm` smoke: the home, settings and both game pages (`whispering-vault`, `amber-tap`)
  serve 200 on the staged tree. No tool call was played end to end (no CLI roles here); the
  refusal and crash paths are covered by `tests/core/test_tool_surface.py`.
