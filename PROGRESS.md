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

## Phase 2 / 2b / 3 / 4 / 5 / 6 — NOT STARTED
