# Refactor progress

Tracking `PLAN.md`. One line per numbered step; only what is done or in flight.

## Phase 0 — Free deletions — DONE (`920d5c9`)

- Shipped before this log started. `TurnRecord.steps`, `Advancement.id` gone; `Slug` lives in `config.py`.

## Phase 0b — Delete `CharacterOverlay` — DONE (`69f0a2c`)

- [x] 1. `Character.rules` / `CreatedCharacter.rules: dict[str, JsonValue]`; `CharacterOverlay` deleted.
- [x] 2. `characters/kael/{loner3e,twentyfourxx}.json` unwrapped (one nesting level gone).
- [x] 3. Six readers updated: `content/io.py`, `app/launch.py`, `ui/create.py`, both engines' `create()`.
- [x] 4. Suite green: 259 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.
- Net: −10 lines in `src`; `io.py` gained `_read_text` so the rules dict and the models share the missing-file error. Rules read with `json.loads` and validated by `Character` itself; written with `json.dumps`.

## Phase 1 — Typed facts and resolver-built events — DONE (staged, uncommitted)

- [x] 1. `MechanicEvent.source` deleted. Save format changed on purpose: `Exchange.events` no longer
      carries it, so old saves fail loudly.
- [x] 2. `Fact.narrator: str | None` -> `Fact.told: bool`; `narrator_lines` reads `fact.trace`.
- [x] 3. `Fact.entity_id: EntityId | None` promoted to a field; `_seed_created` and `_reached` read it.
- [x] 4. `Chip` folded into `MechanicEvent`; `Fact.chip` -> `Fact.event`. `EventBadge`/`DiceEvent`/
      `MechanicEvent` moved from `state/play.py` to `state/facts.py` (play imports facts, so the
      event types had to sit under the cycle). `Engine.player_events`, `EventCause` and both engine
      overrides deleted for the free `facts.player_events(facts)`.
- [x] 5. Composite events built in their resolvers: `resolve_question` attaches the Oracle card,
      `_twist` the Twist card, `resolve_attempt` the Attempt card, `resolve_luck_test` the Luck Test
      card. `question_events`, `_twist_event`, `attempt_events`, `luck_test_events`, `_skill_badge`,
      `_help_badge`, `_hindered_badge` deleted.
- [x] 6. `Fact.data` deleted with every reader: `dice_event`, `counter_effect`, `_ints`,
      `dice_by_slot`, `require_dice_slot`, `chipped`, `explained_fact`'s `data` argument.
      `roll_pool(..., slot=)` -> `roll_pool(..., label=)` returning `(DiceEvent, Fact)`.
- [x] 7. Tests and `evals/turn_eval.py` read the typed fields; `tests/twentyfourxx/test_twentyfourxx_events.py`
      lost `test_an_answered_stake_shows_the_same_attempt_card_as_the_tool` (with `source` gone the
      two causes are identical by construction).
- [x] 8. Golden fixtures regenerated. The diff is facts-only: `narrator`/`data`/`chip` out,
      `told`/`entity_id`/`event` in, and `source` off the saved `Exchange.events`. No `narration`,
      no `prompt` and no `output` key moved — the turn plays exactly as before.
- Suite: 258 passed, ruff clean, basedpyright 0 errors. `src` 8,638 -> 8,392 lines (-246).

Decisions taken inside the phase:

- `adjust`/`spend`/`counter_fact` take an `icon` and always attach the counter's card; `chipped` is
  gone. The Oracle card absorbs the exchange's cards into its `effects` and strips them, so a
  conflict still shows one card, not four.
- Behaviour changed on purpose, one case: a standalone `roll_luck_test` that comes up clear now
  shows no card. It used to show the die with an empty outcome, which was the one card that did not
  pass the narrator gate. Invariant 3 says cards pass that gate, so the gate won.

## Phase 2 — One turn envelope, notes taken not sliced — DONE (staged, uncommitted)

- [x] 1. `Game.take_notes()` replaces the saved index. `SceneSnapshot.from_game(state, notes=())`
      takes its notes instead of reading `world.pending_notes`; only the director's snapshot in
      `run_segment` passes any (`draft.take_notes()`), the narrator's and `player_scene` take the
      default. Both `shown = len(...)` locals and the builtin slice are gone.
- [x] 2. `close_segment(draft, prompt, lines, events)` in `turn/run.py` owns the `Exchange` append,
      the turn bump and `committed()`. `run_segment` and `Harness.end_turn` both call it; neither
      passes `place` or `decision` — it reads both off the draft.
- [x] 3. Stopped there: no shared turn object across the two harnesses.
- Suite: 258 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.

Decision taken inside the phase: `mcp.py`'s notes bookkeeping was left alone here (it passed
`state.world.pending_notes` explicitly, behaviour unchanged) rather than half-moved to `take_notes`
against committed state. Phase 2b moves the take to `start_turn`, which is where it belongs.

## Phase 2b — One way into a turn in code mode — DONE (staged, uncommitted)

- [x] 1. `start_turn(prompt, option_id=None)` drafts, calls `consume_answer` with the three shapes
      it already tells apart (bare string / `Answer(option_id=)` / `Answer(text=)`), takes the
      notes, commits, and opens `Turn`. It returns the same picture `scene()` returns, with the
      player's action rendered under PLAYER ACTION, plus what a closed answer resolved.
- [x] 2. `answer_decision`, `AnswerDecision` and `ACTION_IS_IN_THE_CHAT` deleted. `Answer`'s own
      "an option or text, never both" validator is the only copy left; `_unavailable` names
      `start_turn`.
- [x] 3. `end_turn(lines)` only — the prompt comes off `Turn`, so it cannot disagree with the
      scene. `Harness.turn` is `Turn | None`; `started()` refuses `end_turn` and every director
      tool with a `ModelRetry` naming `start_turn` when no turn is open.
- [x] 4. `Turn.notes` holds what `take_notes` took; `scene()` renders those first and whatever
      `world.pending_notes` holds now, so a compaction mid-turn still reads the rules notes.
- [x] 5. `PREAMBLE` and steps 4-6 of `playing-aidm/SKILL.md` are now
      `start_turn(message)` -> director tools one at a time -> `end_turn(lines)`.
- Suite: 259 passed (one new test: no tool runs a turn before `start_turn` opens one), ruff clean,
  basedpyright 0 errors. No golden fixture moved — code mode is not in them.

Adversarial review pass (fable), on top of both phases:

- `consume_answer` pops `draft.pending` itself. Both callers ran the identical pop-and-comment
  before calling it, where forgetting the pop let a decision survive its own answer.
- The resumed-decision section is rendered once, by `render_director`'s own `resumed=` parameter,
  so code mode places it where builtin does instead of appending its own header.
- `render_director as render_scene` alias and `_player_input` deleted: `Answer(text=prompt)` with
  nothing pending already behaves exactly as a bare string inside `consume_answer`.
- Rejected after pricing: an `open_segment` beside `close_segment` (the shared head is four
  one-line calls that cannot drift, and an extractor would return six values); merging `Turn` into
  `DirectorContext` (per-turn vs per-call draft lifetime — the merge would reintroduce the bug the
  fresh-draft-per-call rule prevents); an always-present `Turn` with a sentinel prompt.
- `src/aidm` ends at 8,389 lines, below the 8,392 the two phases started from.

Decisions taken inside the phase:

- `scene()` survives as the compaction path only. With no turn open it renders
  `NO_TURN_OPEN` under PLAYER ACTION rather than refusing, because the growth-due notice and the
  picture are both worth reading between turns.
- Listing tools needs no open turn (`_director_tools` falls back to a throwaway `Turn`): gating
  reads committed state, and a driver must see what is offered before it opens anything.
- A second `start_turn` while one is open replaces it, discarding that turn's uncommitted cards.
  Left as is: the driver's escape hatch is `scene()`, and a guard here would block recovery.

## Phase 3 / 4 / 5 / 6 — NOT STARTED
