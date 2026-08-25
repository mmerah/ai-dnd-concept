# L5: Cut the ceremony an engine pays before it writes a rule

A third engine pays ~85 lines of ceremony before one mechanic exists: pack plumbing (~30), the sheet's
field list written three times (~25), a two-method `check_pending`/`resume` dispatch per decision kind
(~9 each), `__init__`/ledger (~15); FATE-CONDENSED.md:1369 calls decisions the largest part.

> **Step 2 already landed** (the `rule()`/`action()` constructors and the wrapper-per-command deletion),
> ahead of this phase, in the over-engineering pass that preceded it. Steps 1 and 3-8 are untouched.

## Where Fate does not fit

| Fate thing | Contract element | Why it bends |
| --- | --- | --- |
| 4dF, summed, signed | `DiceEvent._rolled_matches_faces` state/facts.py:24 | forbids `die < 1`, requires `kept in rolled`; a summed −4..+4 pool is unrepresentable. `roll_pool` (state/actions.py:13) keeps the highest, and `_dice_group` (ui/game.py:106) can only print `d{face}`, never `dF` |
| invoke after the dice are visible | `run_command` engines/core.py:98, `apply_to_draft` core.py:398 | the pause point sits *between* commands; Fate must pause *inside* one action's resolution, then re-enter it |
| 3 decision kinds (invoke, compel, absorb a hit) | `Engine.check_pending` core.py:232, `Engine.resume` core.py:225 | each kind costs a payload model, two dispatch branches in a third file, and a sentinel option id (cf. `TAKE_THE_HIT` twentyfourxx/rules.py:217) |
| aspects carry free invokes, and scenes carry them too | `Trait` state/entities.py:96, `add_trait` engines/world.py:18, `SheetMechanics.sheets` core.py:320 | core traits are frozen id/name/text and mechanics are per-actor; Fate shadows aspects in its own `Mechanics` plus a new scene-level field, so the Director sees two vocabularies for one thing |
| fate points, stress boxes, consequence slots | `Counter` state/entities.py:74, `adjust`/`spend`/`render_counters` core.py:253,264,312 | none are int pools with a hard `maximum`: refresh is a floor you may exceed, boxes are binary, slots hold aspects — so `Sheet.counters()` becomes a fake |
| milestone **and** breakthrough | `Advancement` ClassVars core.py:134-138 | one `proposal_type`/`occasion`/`offer_text`/ledger per engine; two tiers means overriding `offers()` and the ClassVars go dead |

Cairn fits: d20 roll-under needs no `DiceEvent` change, HP/deprivation are `Counter`s, slots copy 24XX's
`BULKY` trait (twentyfourxx/engine.py:270), scars are a resolver table. One hard stop — **no XP, no
levels**, yet `Engine.advancement` (core.py:194) is mandatory, read unguarded at app/runtime.py:215,
codemode.py:184,275, mcp.py:120.

## Hard-coded lists to kill

- `engines/registry.py:10` `ENGINES = (Loner3eEngine, TwentyfourxxEngine)` — the only manual engine
  list in the repo. Reflect: import each `engines/*/engine.py`, take its `Engine` subclass (CLAUDE.md
  sanctions discovery by module name). A new engine registers by existing.
- `loner3e/rules.py:122` `HARM: dict[Slug, int]` — outcome-name-keyed, keys built by f-string 30 lines
  away in `outcome_for` (rules.py:180), listed again in director.md. Colocate: `outcome_for` returns a
  frozen `Outcome(name, harm)`. Same for `twentyfourxx/rules.py:211` `HURT = ("disaster", "setback")`.
- `loner3e/engine.py:241` + `rules.py:99,108`, `twentyfourxx/engine.py:352` + `rules.py:56,76` — the
  sheet's fields hand-listed three times per engine (`sheet_view`, `counters`, `describe_entity`), far
  from `Sheet`. Colocate one `rows()`; core renders both views from it.
- `ui/create.py:133` `_preview_lines` — sniffs `{"current","maximum"}` keys out of the opaque rules
  dict, renders Fate's aspects as garbage. Reuse `sheet_type.model_validate(rules).rows()`.
- `twentyfourxx/rules.py:217` `TAKE_THE_HIT` + the match at `twentyfourxx/engine.py:331` — a magic
  option id read in another file. Colocate on the decision class.
- `ui/create.py:278` `_BRIEF_LABELS` + `brief.value == "full"` (`ui/create.py:359`) — name-keyed labels
  for two constants that live in `authoring/draft.py`. Colocate there.

Leave: `_HOLDERS` (entities.py:143) and the role-name literals (`_STEP_COPY`, `Role`, `TurnStep`) —
closed sets a new engine never extends. `harness/mcp.py:134` `DISPATCH` and `twentyfourxx/rules.py:44`
`get_args` already do this right; copy them.

## Approach

Five changes remain, each judged by "does the Fate engine file get shorter": a decision base class,
`rows()` on the sheet, a pack-creation base, optional advancement, a signed/summed `DiceEvent`. The
sixth, a rule-command constructor, has already landed. Everything else above is a list-killing edit,
not an abstraction.

**Not abstracted, on purpose.** No aspect/tag system in core — aspects are Fate mechanics. No dice DSL
— each engine rolls its own, only the card model is shared. No advancement tiering — Fate overrides
`offers()`, a tier framework would have one user. The ledger counter stays per-engine rather than
moving to `SheetBase`, because Fate needs two ledgers — which also means **no sheet field moves, so no
save breaks**. No plugin protocol beyond discovery, no command auto-registration.

## Steps

1. **Designed here, lands with L7.** `DiceEvent` (`state/facts.py:17`) gains `summed: bool = False` and
   `face_label: str = ""`, bounds become `abs(die) <= face` with `kept == sum(rolled)` when summed, and
   `ui/game.py:106` prints `die.face_label or f"d{face}"` with no kept highlight. It has zero users
   until Fate exists and costs exactly the same then, so it ships with Fate rather than adding a
   branch nothing exercises.
2. **Done.** `engines/core.py` grew `rule(name, description, args, resolve)` for resolvers that roll
   and `action(...)` for those that do not, both beside `command()` and both wrapping `apply_play` /
   `apply_action`. All 16 one-line command wrappers are gone; `_world_command` is now `action` with
   `during_suspension=True`, and each core command carries its resolver as one lambda beside its name.
3. `engines/core.py` — `class Decision(Frozen)` with `kind: ClassVar[Slug]`, `pending(draft)` building its
   own prompt/options/payload, and `resolve(draft, option_id, rng)`; `Engine.decisions:
   ClassVar[tuple[type[Decision], ...]] = ()`; `check_pending`/`resume` go concrete — match `kind`,
   validate the payload, delegate:
   ```python
   class Decision(Frozen):
       kind: ClassVar[Slug]

       def pending(self, draft: Game) -> PendingDecision: ...  # prompt, options, payload
       def resolve(self, draft: Game, option_id: Slug, rng: Random) -> tuple[Fact, ...]: ...


   # in SheetEngine, once:
   def resume(self, draft, option_id, rng):
       cls = next(d for d in self.decisions if d.kind == draft.pending.kind)
       return cls.model_validate(draft.pending.payload).resolve(draft, option_id, rng)
   ```
   Deletes `twentyfourxx/engine.py:328-347`, `rules.py:217,220,331-342`
   and `loner3e/engine.py:251-256`; Fate declares three classes and overrides no engine method.
4. `engines/core.py:316` — `SheetBase.rows() -> tuple[tuple[str, str], ...]` abstract; `SheetEngine`
   makes `describe` and `sheet_view` concrete over it (describe joins `f"{label.lower()}: {value}"`,
   dropping empties). Deletes `describe_entity`, `counters()`, `sheet_view` from both engines. Then
   `ui/create.py:133` `_preview_lines` becomes `sheet_type.model_validate(created.rules).rows()` plus
   the trait/item lines; `ui/panels.py:23` already consumes that shape.
5. `engines/packs.py` — `class PackCreation(CharacterCreation)` holding `self.packs`, doing the pack-step
   preamble, exposing `options`/`find`/`picked_entry`; subclasses implement `steps_for(pack, picks)` +
   `create`. Deletes `loner3e/engine.py:169-178,209-216`, `twentyfourxx/engine.py:184-192,287-311`.
6. **Designed here, lands with L8.** `Engine.advancement` (`engines/core.py:194`) becomes
   `Advancement | None`, since Cairn has no XP. The real site list is larger than it looks: five reads
   in `app/runtime.py` — `offers` (216), `propose` (229), `preview` (236), `apply_proposal` (249) and
   `advisor_agent(engine.advancement, …)` (377), the last building an agent from
   `advancement.instructions` and so yielding *no advisor at all* when advancement is None — plus
   `offered()` (`harness/mcp.py:157-163`), which publishes `PROPOSE_ADVANCE`/`APPLY_ADVANCE`
   unconditionally, and `Harness.advance_args` (`harness/codemode.py`). `harness/mcp.py` never reads
   `.advancement` itself. Eight `None` branches with no None-engine to exercise them is dead weight
   until Cairn.
7. `engines/registry.py:10` — discovery over `engines/*/engine.py`: for each package directory,
   `importlib.import_module(f"aidm.engines.{d.name}.engine")`, then take the one module attribute that
   is a strict `Engine` subclass (CLAUDE.md sanctions importing an engine module by name for exactly
   this). Keep the `engine_class` and `build_engine` signatures so `app/launch.py` and `ui/create.py`
   are untouched.
8. `loner3e/rules.py:122,180`, `twentyfourxx/rules.py:211,235` — outcomes become frozen values carrying
   their own harm/hurt; the tables go. Then `ui/create.py:278,359` — move the two brief labels next to
   `WHOLE_SCENARIO`/`OPENING_SLICE` in `authoring/draft.py`.

## Risk / size

~+90 / −240 lines remaining, net ≈ −150 (step 2 already took +35 / −60), across `engines/core.py`,
`packs.py`, `registry.py`, both engines'
`engine.py` + `rules.py`, `ui/create.py` and `authoring/draft.py`. Both engines are edited in every step but no `Sheet` field moves, so **saves survive**; step 4
changes the Director prompt's `state:` block, so golden prompts move and the turn-eval baseline needs one
re-run (tests that move: `tests/core/test_sheet_view.py`, `test_decisions.py`, `test_golden_prompts.py`).
One check: `uv run pytest` green with fixtures regenerated, plus one live loner3e turn, dice card unchanged.

Order (line numbers as of 2ce9dfa): L1 first — its root cause is loner's optionless conflict decision and
whatever field it adds belongs on `Decision` in step 3 — then this, L6, L7/L8. With steps 1 and 6
deferred to their first user, nothing here touches `state/facts.py`, `mcp.py` or `codemode.py`, so this
phase is fully independent of the harness work and of I4.
