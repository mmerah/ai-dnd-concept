# The interruptible turn

Decision record, 2026-08-21, second revision. The first revision reached the same goal through
more machinery — a `Settled | Staked` output union with a live probe, a separately enforced
resolution entry point, a zero-model-call fast path. This revision deletes that machinery by
routing every suspension through the tool layer the pipeline already has. What the extra
machinery bought and why it was cut is recorded under **Considered and rejected**. A third-round
adversarial review ran against the codebase; its accepted fixes are folded in. A fourth,
pre-implementation review against the codebase (2026-08-22) folded in the clarifications an
implementer would otherwise have to re-derive: the exact narrator rule, the `decision` field on
`Exchange`, the run-start context on `PlanContext`, option-id typing, each engine's precise
suspension points, and the standing of step 4. This file is the authority on the turn pipeline
until a later decision supersedes it.

## The problem

The pipeline today is one shape, forced on every engine:

```text
player message → Director (autonomous, up to 16 tool calls on one draft) → Narrator → commit whole
```

There is no suspension point between the player's message and the commit, so every choice a
system's rules give the player *mid-resolution* is taken by the Director on their behalf. That is
not an implementation bug; the architecture cannot express the rules:

- **24XX** — the SRD's core loop is advise-and-revise: the GM states impossibility, cost, or
  risk, and the player may revise before committing. Defence is "*say* how one of your items
  breaks to turn a hit". Both are player utterances inside a resolution. Deviations 1–2 in
  `docs/24XX.md` record the compression, plus the settle-beat and three-beat-cap machinery built
  to contain it.
- **Loner** — a conflict is a series of key actions the player chooses one at a time; the current
  loop lets the Director chain beats autonomously, and a twist fires a beat late through
  `pending_notes` (deviation 3 in `docs/LONER-3E.md`).
- **2d20** (planned) — a single test is: framing → player buys up to 3 extra d20s with
  Momentum/Threat → roll → optional Fortune reroll → Momentum spent one point at a time, each
  spend seen before the next is chosen → complication buy-offs. Unimplementable in one
  autonomous run without deciding for the player.
- **FATE** (planned) — compels are accept/refuse with a fate point; invokes are post-roll spends.
  Same shape.

The common cause: **a player message is not a turn.** A tabletop resolution is a conversation
with typed decision points, and the pipeline models it as a single command.

## The decision

One rule:

> **Control returns to the player when a resolver sets a pending decision. Nothing else hands
> control back, and only a player input takes it forward again.**

A pending decision is valid, persisted game state. The loop it produces:

```text
                    ┌───────────────────────┐
                    │        PLAYER         │
                    │ message / answer      │
                    └──────────┬────────────┘
                               │  closed answer: engine resolves it
                               │  deterministically first, then
                               ▼
                    ┌───────────────────────┐
                    │       DIRECTOR        │
                    │ interprets, judges    │
                    └──────────┬────────────┘
                               │ tools
                               ▼
                    ┌───────────────────────┐
                    │        ENGINE         │
                    │ resolvers on draft    │──── a resolver may set
                    └──────────┬────────────┘     pending: hand back
                               ▼
                    ┌───────────────────────┐
                    │       NARRATOR        │  iff facts landed
                    └──────────┬────────────┘
                               ▼
                       commit the segment
                (with or without a pending decision)
```

The routing rule for answers:

> **A closed answer (an option the engine enumerated) resolves in engine code,
> deterministically. An open answer (free text) is interpreted by the Director. Either way, a
> Director run follows — fresh for open input, a continuation for a resolved answer — so the
> Director always sees and develops what the answer caused.**

The click skips interpretation, never judgment. An enumerated option carries nothing to
interpret — the button already names the one legal resolver call — so a model between the click
and the resolver would add latency and misfire risk while changing nothing. Judgment is never
skipped: the continuation run receives the landed facts and settles trivially when there is
nothing to develop. We chose small, cheap, fast models precisely so that call count does not
drive design; a continuation that only settles is an acceptable cost, not a case to engineer
away.

Suspensions have one producer: resolvers. The two kinds of interruption are two callers of it:

1. **Rules-driven** — a resolver, mid-resolution, sets the draft's pending decision instead of
   running to completion: 2d20's dice buys and Momentum spends, 24XX's break-an-item defence,
   FATE's compels. The Director does not decide whether these opportunities exist; the rules do,
   in Python.
2. **Table-talk** — the Director calls an engine's stake tool: "you can make it, but a miss
   drops you into the machinery; still going?". The tool's typed argument is the frozen,
   engine-validated action, so what the player confirms is exactly what rolls; its resolver sets
   a stakes decision with one `proceed` option and free text open. Proceed is a closed answer
   that rolls the frozen action; revise is an open answer, table talk. Only an engine whose
   rules have an advise step declares the tool (24XX does, Loner does not) — it is not a core
   offering, and there is no generic "ask the player" tool.

Seats do not move: the Director keeps Loner's oracle seat (framing questions, interpreting
answers) — AI-as-GM remains this app's accepted adaptation, recorded as such in
`docs/LONER-3E.md`. This architecture removes the *compression* deviations, not that one.

## Invariants

Kept, verbatim:

- The model proposes typed, validated output; engine code resolves it deterministically. The
  model never writes state; every roll and ledger change happens in resolver code.
- Only the Narrator writes player-facing fictional prose, and its input type has no field a leak
  could travel through. Engines and core may render deterministic mechanical UI (a decision
  prompt, options, pool counts) — that is rules text, not fiction. The stake tool's risk line is
  the one Director-authored string the player reads: the advise step *is* the GM saying the risk
  out loud, a warning the rules require, not narration.
- Resolvers run against a draft, refused against a throwaway copy first; only a revalidated
  commit replaces state.

Changed, one sentence each:

- **Was:** one player message = one transaction, committed whole after the full turn.
  **Now:** one machine segment between human boundaries = one transaction, committed whole. A
  segment is everything from one player input (message or answer) to the next hand-back.
- **New:** a pending player decision is valid persisted game state. A save may hold one; the
  engine that owns it validates it on restore and refuses one it cannot play, like any other
  state.
- **Was:** one `Exchange` per player message.
  **Now:** one `Exchange` per segment. A closed answer's exchange carries the chosen option's
  label as its `prompt`; `Exchange.events` renders the mechanics visibly in the chat, as it
  already does today. `Turn` traces stay one per segment the same way. No new history model.
  A prose-less segment (a stake hand-back) renders into model history from its `events` and the
  decision prompt: `Exchange` gains `decision: str = ""`, carrying the suspending decision's
  prompt at commit — the pause must survive after `Game.pending` clears, and the risk line the
  Director authored is what names the staked action there. `exchanges_to_messages` renders
  narration plus a bracketed paused-for-the-player line from `decision`, and must never build an
  empty model message — fail fast if one would be.

## The shapes

Core types (in `state/model.py` unless noted). Sketches, not final signatures.

```python
# Laxer than Slug: 24XX's defence options are carried-item entity ids, which allow underscores.
OptionId = Annotated[str, Field(pattern=r"^[a-z0-9_-]+$", max_length=64)]

class Option(Frozen):
    id: OptionId
    label: str
    detail: str = ""

class PendingDecision(Frozen):
    """One decision the game is waiting on. Lives at Game.pending; None means the composer
    is the only input surface."""
    kind: Slug                      # which engine rule resumes it
    prompt: str                     # engine-rendered rules text; the stake's risk line is the recorded exception
    options: tuple[Option, ...]     # the closed answers; engine-enumerated, so always legal
    free_text: bool = True          # closed-only is the exception, not the default (see below)
    payload: dict[str, JsonValue]   # frozen context, validated by the engine against its own type

class Answer(Frozen):
    """What the UI submits. Exactly one of the two is set."""
    option_id: OptionId | None = None  # closed → engine resolves, then the Director continues
    text: str = ""                     # open → Director interprets
```

`free_text` defaults to open because a closed-only menu can itself mint a deviation: 24XX's
defence rule hands the player narrative authority ("*say* how an item breaks" — or they dive
behind the crate instead), and options-only would take it back. Reserve `free_text=False` for
pure bookkeeping (banking Momentum), where every legal answer really is on the buttons.

`Game` gains `pending: PendingDecision | None`.

**How a resolver suspends.** No new callable type, no new signatures: a resolver that reaches a
player-owned choice sets `draft.pending` and returns its facts. `Play`, `apply_to_draft`, and
`transact` are unchanged. Enforcement is the prepare filter the toolsets already run through:

- Once a resolver sets `pending` during a run, `act()` appends "the rules now wait on the
  player's decision" to that call's answer and the filter offers no further tools; the run closes
  naturally with its trace string. The Director's output type stays `str`.
- A continuation run that *begins* with a re-suspended decision (a resume both landed facts and
  suspended again) gets core's fiction tools only — it develops what the answer caused, it
  cannot open new mechanics.
- The run-start context is two `PlanContext` fields, both defaulting to their empty value:
  `suspended_at_start: bool` (the run began with a re-suspended decision — core tools stay
  offered, engine tools do not, and `act()`'s pending guard stands down) and
  `answered: PendingDecision | None` (the decision an open answer just consumed, so an engine
  can offer its settling tool and read the frozen context back). The filters live in
  `director_agent`: core's toolset is offered when `pending is None or suspended_at_start`,
  every engine toolset only when `pending is None` — engines never wrap their own.
- A resolver that sets `pending` while one is already set is refused in `apply_to_draft`: one
  decision at a time. `transact` — advancement, authoring — refuses a pending the play
  *introduced*, while one that pre-existed unchanged passes: the worldsmith extension may run on
  a suspended state.
- `Engine.check_pending(pending)` is the semantic gate — the base refuses everything, an engine
  overrides it for the kinds it plays — and core calls it wherever it calls `engine.validate` on
  a state that carries one (`apply_to_draft`, restore), so a future engine cannot forget it.

Engine contract addition (`engines/core.py`), two concrete methods — the base of each refuses,
so an engine with nothing to suspend on overrides neither:

```python
class Engine(ABC):
    ...
    def resume(self, draft: Game, pending: PendingDecision, option_id: OptionId,
               rng: Random) -> tuple[Fact, ...]:
        """Applies a closed answer through the same resolvers the tools use. May set
        draft.pending again to chain. An engine with nothing to suspend on never receives
        a call."""

    def check_pending(self, pending: PendingDecision) -> None:
        """Refuses a pending decision whose kind this engine does not play or whose
        payload does not validate."""
```

- Internal dispatch on `pending.kind` is the engine's own business (a `match` suffices at two
  kinds); no registry, no per-decision class. Extract one if a third engine makes the dispatch
  painful, not before.
- The trial-draft refusal is unchanged: a resume is checked against a throwaway copy before it
  touches the turn's draft. A refused closed answer raises rather than retrying: the engine
  enumerated the option, so a refusal is a bug or stale state, never model error.

## The loop

`run_turn` becomes `run_segment(state, input)` where input is a player message or an `Answer`.
The runtime calls it once per human input; each call is one transaction. Consuming any input —
closed or open — clears `pending` first: a closed answer hands it to `resume`, an open answer
hands it to the Director as context (a pending_note), and a revision simply discards the stake.
A decision that cannot be abandoned — 24XX's un-applied hit — must not evaporate on a typed
answer: its engine exposes the settling resolver as a tool to that run (the same resolver
`resume` calls), so the consequence lands or is turned, never dropped. (`restart()` already
rebuilds state from scratch, so it clears a pending for free.)

```text
run_segment(state, input):

  1. input is a closed Answer:
       engine.resume applies it on the draft, deterministically.

  2. Director run — fresh for a message or an open Answer; a continuation, fed the landed
       facts and any pending_notes, after a resume. Tools resolve on the draft as today.
       The run ends when the Director settles, or structurally when a resolver suspends.
       A resume's facts reach the continuation as a rendered prompt section (what was asked,
       what was chosen, the fact traces it landed); an open answer's consumed decision reaches
       the fresh run as a pending_note, and the answer text is the PLAYER ACTION.

  3. Narrator runs when the segment settles — always, as today, so a quiet turn keeps its
     prose — and, when it suspends, iff narrator-visible facts landed, so the player reads
     the hit before choosing how their vest breaks, and reads the roll before spending
     Momentum on it. A hand-back that moved no fiction gets no prose: the decision panel is
     rules text, engine-rendered. ("Iff facts landed" alone would silence the settled quiet
     turn, which the fast-path guarantee below forbids.)

  4. Commit the whole segment: state (with or without pending), exchange, trace.
       A failure anywhere leaves committed state untouched, exactly as today —
       the transaction is just smaller.
```

Consequences of the shape:

- **No frozen model runs are ever persisted.** A suspension ends the Director's run; resumption
  is a fresh run built from state + history, the same way a restored save already rebuilds
  message history. Suspend-for-30-seconds and suspend-overnight are the same code path.
- **The beat-cap and settle-beat machinery is deleted.** The Director no longer needs a bounded
  autonomous multi-beat loop with prose guards ("may not roll again") — the moment the next move
  needs the player, a resolver suspends, structurally. The director.md instruction "stop when
  the next move needs the player's own intent" stays, but now names a real mechanism instead of
  fighting the architecture.
- **The UI already has its rule.** "A panel only renders state and submits typed decisions" is
  in CLAUDE.md today; the decision panel is that rule made load-bearing. `Game.pending` set:
  render `prompt` + options (+ composer iff `free_text`). Not set: composer as today.
  Advancement is offered only while `pending is None` — an advance mid-suspension could
  invalidate the frozen payload under it.
- **`pending_notes` stays** as the resolver→Director channel, and now reaches the continuation
  run of the same interaction — or the same run, since `act()` already echoes new notes in the
  tool answer — not the next turn.

## What each engine does with it

**24XX** — deviations 1 and 2 in `docs/24XX.md` are erased:

- Advise-and-revise: the engine declares a stake tool; the Director calls it with the frozen
  `Attempt` and the risk named. Proceed rolls that exact attempt; revise is table talk.
  Trivially safe attempts still resolve without a stake — the Director judges, as the SRD's GM
  does.
- Defence: the *player's own* attempt resolving `disaster` or `setback` suspends with kind
  `"defence"` — `Attempt` names no target, so an NPC's roll cannot know it hit the player, and
  the printed rule is the player's own defence anyway. Options are the player's carried,
  not-yet-broken items ("break the vest…") plus "take-it", free text open for any other
  response the fiction allows; the payload holds the outcome. Resume writes a `broken` trait on
  the chosen item and records the hit turned into a brief hindrance, or lets it land; an open
  answer routes to the Director, whose toolset for that run includes the settle-defence tool
  (the same resolver `resume` calls — it reads the consumed decision from `PlanContext.answered`
  and takes the item judged to break, or null to let the hit land) — the hit lands or is
  turned, never dropped. The player *says* how their gear breaks, as printed.
- The stake resumes by validating the payload back to `Attempt` and calling the same
  `resolve_attempt` the roll tool calls, which may itself chain into the defence decision.
- The beat-cap and settle-flag machinery this design obsoletes was already deleted from code in
  the 2026-08-17/21 reorgs; what remains of it is the prose in `docs/24XX.md` deviations 1–2,
  which this step rewrites out.

**Loner** — deviation 3 shrinks and the conflict flow is the SRD's:

- A conflict runs one exchange per segment: question → resolution → luck moves → hand back.
  Mechanism: `resolve_question`, when `opponent_id` is set and both sides still hold luck, sets
  a pending of kind `"conflict"` with *no options* and free text open — the hand-back is the
  whole decision, the next key action arrives as an open answer, and `resume` is never called
  for it. A conflict ending at 0 luck does not suspend: the defeat note steers the same run's
  development, as today. The player chooses each key action, which is the SRD's
  series-of-questions procedure; the oracle seat stays with the Director (framing, position
  judgment, interpretation) — the recorded, accepted adaptation.
- A twist develops in the same interaction it fired in — the note reaches the running Director
  through the tool answer, or the continuation through the prompt — no longer one player-turn
  late. `act()` already echoes run-written notes into the tool answer, so this needs no new
  code: deviation 3 is rewritten to match reality, not re-implemented.

**2d20** (build next, as the proof) — the full test procedure, rules-exact:

```text
player: "I hack the terminal"
  Director: frames the test (attribute + skill + difficulty), calls the stake tool
player: proceed / buy 2d20 with Threat        (closed)
  engine: Threat ticks, dice roll, Momentum generated; suspends "spend-momentum"
  Director continuation: judges the outcome    Narrator: the player reads the result
player: spend 1 for information                (closed)
  engine: spends the point, suspends "spend-momentum" again
  Director continuation: authors the information bought
player: bank the rest                          (closed)
  engine: banks; pending clears
  Director continuation: nothing to develop; settles
```

**FATE** (later) — compels are engine decisions (accept the fate point / refuse and pay);
post-roll invokes are a spend chain like Momentum. Nothing new is needed beyond content.

## Persistence and compatibility

- A save with a pending decision restores to the decision panel, mid-interaction. Strict
  validation is the only gate, as the design rules already say: the engine refuses a pending it
  cannot play.
- `Game` gains `pending` and exchanges change meaning (one per segment), so existing saves must
  refuse to load. The gate is the field itself: `SavedGame.pending` is required (nullable, no
  default), so a save written before this design fails validation by omission. No version field,
  no conversion — strict validation stays the only compatibility gate. The checked-in
  `saves/whispering-vault--kael--loner3e.json` predates the gate and becomes permanently
  unloadable: delete it in the same change.
- Evals (`evals/turn_eval.py`) drive `run_segment` with scripted answers where a fixture
  suspends: a `Case` scripts them as a pending-kind → option-id mapping, applied while the
  committed state suspends (bounded at a few segments), with facts, steps, and state merged
  across the interaction for the assertions — under the harness's seeded rng, the resumed half
  of a turn is fully deterministic, which makes the interesting assertions *cheaper* than
  today, not harder. The 24XX risky-lock case scripts `{"stake": "proceed", "defence":
  "take-it"}`.

## Considered and rejected

Cut by this revision, from the first:

- **A `Settled | Staked` output union on the Director.** It needed a live schema probe under the
  weak-model criterion, an engine-typed generic output, and a documented fallback — which was a
  stake *tool*. The tool is strictly less machinery and identical in power, so it is the design,
  not the fallback. The Director's output type never changes.
- **A zero-model-call fast path for bookkeeping answers.** A branch, a rule for when it applies,
  and a class of bugs where a continuation was owed but skipped — to save one model call on
  "bank the rest". We optimize for small, cheap, fast models so call count does not drive
  design; the continuation always runs. Re-add the skip only if measured latency on button
  answers warrants it.
- **All input through the Director** (the loop diagram taken literally). A clicked enumerated
  option has nothing to interpret; the run it would trigger could only call the one resolver the
  button already names. The continuation preserves everything the uniform loop wanted — the
  Director sees every answer's consequences — without a model between a button and its resolver.

Standing, from the first revision:

- **A `Resolution` return type widening `Play`.** Suspension would have leaked into `transact`
  and every advancement/authoring path where it is meaningless. Setting `draft.pending` costs
  nothing and touches only the paths that want it.
- **A `Decision` ABC with an `Engine.decisions` registry.** A registry for two kinds in one
  engine and zero in the other is an abstraction ahead of need; the repo's rules say extract it
  when a second real implementation hurts, and none does yet.
- **A typed event log replacing `Exchange`.** One `Exchange` per segment, with its `events`
  field, covers multi-utterance interactions, visible mechanics, journal and LLM-history
  rendering — at a fraction of the blast radius of four new event classes.
- **A generic `ask_player` tool.** An unrestricted tool lets the model invent interruptions; an
  engine's stake tool and its rules-driven suspensions say *why* control changes hands, typed.
- **Seat reassignment** (rules-faithful solo Loner where the human frames oracle questions). The
  architecture permits it — a seat is just who a decision routes to — but we build one mode.
- **Richer answer shapes** (numbers, multi-select). `options` + `free_text` covers every
  decision named in this document; widen when an engine's real rule needs it, not before.
- **Streaming, undo, summarised history.** Same standing items as before; nothing here blocks
  them, and the smaller transactions make undo easier later, not harder.

## Build order

1. Core shapes: `PendingDecision`, `Answer`, `Game.pending`, per-segment `Exchange`/`Turn`
   (with `Exchange.decision`), `Engine.resume`/`check_pending`, suspension through the prepare
   filter, and `run_segment` with the routing rule. The decision panel in the UI, the
   advancement gate (`offers()` empty while a decision is pending), and one short
   when-the-rules-hand-back paragraph in the core director prompt land here too. Both engines
   compile with no suspending resolvers and no stake tool; the fast path (message → Director →
   Narrator → commit) behaves as today. Rename `GameSession.pending()` (advancement on offer)
   to `advancement_offered()` so it cannot be confused with `Game.pending` (decision awaited).
   Golden fixtures regenerate (`AIDM_GOLDEN_REGEN=1`); the expected drift is `pending: null` in
   saves and `"decision": ""` in exchanges — read the diff for anything else.
2. 24XX accuracy: the stake tool + the defence decision + the settle-defence tool; rewrite
   deviations 1–2 out of `docs/24XX.md` (the beat-cap/settle machinery they describe is already
   gone from code — the rewrite is the deletion).
3. Loner accuracy: one-exchange conflict segments, same-interaction twists; rewrite deviation 3.
4. 2d20 engine, the first engine designed against the interruptible turn — the proof that a new
   engine lands with near-zero deviations. **Blocked until two prerequisites exist:** a faithful
   SRD extraction at `docs/2D20.md` in the style of `docs/24XX.md`, and a licensing decision —
   Modiphius' 2d20 carries no CC license the way 24XX (CC BY) and Loner (CC BY-SA) do. Do not
   start it, and do not invent a stand-in ruleset, before both land.
