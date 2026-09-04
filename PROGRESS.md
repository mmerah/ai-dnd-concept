# PROGRESS

One entry per PLAN.md phase: the counts, what was decided off-plan, what was refuted in review
and why, and what is known and accepted.

## Phase 1 — the fixes and the two boundary conventions

- `src` lines: 9,481 before, 9,483 after. The plan's band was 9,430 to 9,460. The five
  `parse(model, {...})` spellings of step 4 cost three lines each over the keyword form they
  replace, and `Observed` costs eleven over the tuple; the `panels.py` fold and the two
  `__init__` deletions did not cover that. Nothing was padded and nothing was cut past the plan.
- Split: B (platform) then A (engines), sequential. Off-plan assignment: step 13's `WORLDSMITH`
  constants edit `engines/scenes/engine.py` and `engines/rooms/engine.py`, so they went to A;
  step 3's `CLAUDE.md` line went to B, which owns `CLAUDE.md`. No file was edited by two parts.
- Off-plan edit: `PLAN.md` added to ruff's `extend-exclude` in `pyproject.toml`, beside
  `NEXT-SPECS.md` and for the same reason (ruff 0.16 formats markdown code blocks). On HEAD,
  `uv run ruff format --check` was already red on `PLAN.md`'s Phase 2 code block; the four
  commands cannot be green without it. Awaiting the maintainer's call; revert the one line if
  formatting `PLAN.md` is preferred.
- Cut folded from review: the `canon = deepcopy(canon)` in `SceneWorld.begin` and
  `RoomWorld.begin` went. `parse` with `revalidate_instances="always"` rebuilds every nested
  `Mutable` instance and container (checked: no npc, dict, list or way is aliased after `begin`).
- Cut folded from review: the unasserted `caplog` in the new `read_characters` test went.
- Refuted: "restore keyword construction in `begin_game` and the four `parse(cls, {...})` sites;
  a construction bug now reads as a `Refusal` and the dict loses static field checking." PLAN.md
  Phase 1 step 4 names all five sites and the reason (`Engine.compose` re-prompts only on a
  `Refusal` from `build`); `Game.commit` already turns a refused state into a `Refusal` the same
  way. The lost static check on the dict keys is known and accepted (below).
- Refuted: "`content_id` inside the engine loop warns twice for a non-slug folder holding two
  engine files." PLAN.md step 1 names that shape; the case needs a backup folder that also holds
  two engine sheets, and the cost is a repeated log line.
- Refuted: "`can_type` was made public only for the test." PLAN.md step 10 names the rename.
- Refuted: "the `PanelRow` class comment duplicates the two field comments." The field comments
  say what the sidebar draws for each shape (an icon, a Move-on button); the class comment says
  the order the shapes are told apart in. Neither is in the code.
- Known and accepted: the five `parse(model, {...})` sites pass a `dict[str, object]`, so a
  renamed field there fails at runtime, not under basedpyright; the phase's own tests cover each.
- Known and accepted: `PendingOption.name` is required. Every `src` site names its tool, so no
  save changes; a save whose open decision held a nameless option would now be stale.
- Known and accepted: the two new comments (`EngineId`, `PanelRow`) wrap onto two `#` lines to
  stay under the 100-column limit.
- Reviews: Fable (`reviewer` agent) and Opus (`reviewer` agent, `model: opus`); no `codex` on
  the machine, so no Codex Sol review ran.
- Verified: four commands green; golden regen changes no fixture; `uv run aidm` serves the home
  page with a `My Backup` folder and a `.DS_Store` under `characters/`;
  `ROLES__NARATOR__MODEL=x` makes `read_settings()` exit naming `narator`.
