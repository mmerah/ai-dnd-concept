# VISION: kernel, engines, kits

This file is self-standing. It supersedes the old "smaller core" plan (Phases 1–3.5 shipped;
git log is the record). PLAN.md is derived from this file and judged by the measurement rules
at the end. Three adversarial reviews audited this document (two agent reviews of the first
draft, one Codex/gpt-5.6-sol review of the derived plan against the code); their corrections
are folded in, most visibly in the arithmetic and the phase boundaries.

## The one-line vision

> The kernel stops defining what a game is. The kernel hosts an engine. Each engine owns its
> complete typed game. The current world model becomes the first kit: a set of modules an
> engine composes.

## Why — and what the payoff honestly is

Three taxes recur in today's code:

1. **The ownership seam.** Engine state lives as an untyped JSON blob (`WorldState.mechanics`)
   inside a typed core world. `rules()`, `mechanics_of`, `mechanics_patched`,
   `mechanics_delta`, `entity_maps`, and the authoring blob plumbing exist only to service
   that seam.
2. **A shared ontology posing as a platform.** Actors, locations, items, exits, traits,
   party, threads, discovery flags, death, frontier growth: one adventure-game design every
   engine must shape its SRD onto. A 24XX ship is a `location` because upgrades need
   somewhere to attach; Breathless scenery must not be an `item` because kit items carry dice.
3. **The Director executes our object model.** Nine or ten bookkeeping verbs sit beside the
   SRD procedure tools, and the prompt teaches the model to sequence them.

**The payoff is fidelity and cost-of-the-next-engine, not lines.** Review finding, verified:
the eight deviations recorded in `docs/*.md` are procedure-level (solo tables, twist timing,
"Before We Start") and this refactor closes none of them. What it closes is the *impedance*
layer — concepts forced into the wrong shape — and what it cheapens is every future engine,
which arrives writing its SRD's own nouns instead of ours. The line count is a **ceiling**,
not the goal: `src` `.py` lines must end at or below today's 9076 (see Arithmetic).

## Target architecture

```
KERNEL  (aidm/kernel/, aidm/app/, aidm/ui/, aidm/harness/)
  turn loop: Director -> Narrator, history replay, request limits
  draft -> validate -> commit transaction (validation is the engine's)
  save/scenario/character envelopes around one engine payload
  secrecy type boundary: the Narrator input type has no private field
  kernel-owned view types (Director/Narrator/Player), filled by engines
  authoring loop: run the agent, retry refused patches, gate finish()
  GameService: today's GameSession renamed and extended — not a new layer
  config, LLM roles, media, launch, settings

        tiny typed engine protocol

ENGINE  (aidm/engines/<name>/)
  its complete typed State, Scenario payload, Character payload
  its SRD procedure tools, with all deterministic consequences inside
  its decisions (continuations) and answer()
  fills the kernel view types from its state
  its validation, creation (with a preview), player actions
  its authoring module (usually the kit's)

KITS    (aidm/kits/rooms/, later aidm/kits/scenes/)
  a kit is a SET OF MODULES an engine composes a la carte:
    state model  RoomsState[S] — S is the ENGINE'S DISCRIMINATED SHEET UNION
                 (actor/item/ship sheets differ; one plain type cannot hold them);
                 entities carry `sheet: S | None`; the kit state holds `player_id`
    change_world (one fiction-settlement tool + its consequences + leak checks)
    views        (fills the kernel view types from kit state)
    authoring    (draft model whose patch carries `connections`, bars, growth)
```

Three design rules the reviews forced, adopted because each keeps an arithmetic row honest:

1. **`GameService` is `GameSession` renamed.** It already exposes open/submit/act/offers/
   scene/commit/reload/growth. It gains `view` and explicit begin/call/end turn methods,
   because the two commit modes are real semantics: builtin commits once per segment, code
   mode per accepted call, plus the closing narration. A new layer above it would add lines.
2. **View types are kernel-owned generic presentation data; engines fill them.** This keeps
   the package-boundary test (`ui` may not import `aidm.engines`) alive and pays the view
   cost once, not three times. The boundary test itself is rewritten for `kernel`/`kits`
   the moment those packages exist, not after.
3. **The kit entity carries the engine's sheet as a discriminated union** (`RoomsState[S]`,
   `Entity[S].sheet: S | None`). This is what actually deletes `sheet_of`, the per-engine
   stray-id checks, and the sheets-keyed-by-id merge in growth. A parallel `sheets` map
   would keep all of them; a single non-union sheet type cannot represent any current engine.

## The kernel

The kernel knows: engine id, save envelope, turn/history, player input, one open player
prompt, public/private evidence, role orchestration, generic presentation data.

**Architecture test:** an AST/identifier-level check (word boundaries, not substrings — a
naive grep false-positives on `.items()` and Codex CLI event names) that no module under
`aidm/kernel`, `aidm/app`, or `aidm/ui` names the rooms ontology as an identifier: `actor`,
`location`, `exit`, `party`, `thread`, `trait`, `dead`, `inventory`, `sheet`, `frontier`,
`item`, `known`. `aidm/harness` is covered with an explicit allowlist for the Codex CLI's
own `item.completed`/`thread.started` event names. Scope and node kinds are part of the
test's definition, or it either misses leaks or rejects legitimate names.

What the kernel keeps, with the review corrections:

- **Draft → validate → commit**, with the throwaway trial application. The four
  trial-then-apply wrappers (`apply_to_draft`, `transact`, `draft_refusal`, `Turn._apply`,
  49 physical lines) collapse toward one survivor.
- **The turn loop.** One loop, ever. The kernel's single fact-kind branch
  (`entity_discovered` → `when_reached`, ~10 lines) moves inside the kit's `change_world`.
  The `during_suspension` flag survives on the kernel tool type — "legal while a prompt is
  open" is turn-loop semantics (the kit's `change_world` opts in; procedure tools do not),
  not something continuations replace.
- **The resolution record.** Tools and `answer()` return a typed resolution: facts plus
  rules-notes. `Fact` keeps `trace`/`told`/`card`/`dice`; notes move off kit state onto the
  save envelope through that return path — engines write notes in five places today, so the
  channel must be in the return type, not a side door.
- **Denormalized speech, without leaking it to the Narrator.** The Narrator proposes minimal
  lines (`speaker_id`, `text`); the resolver validates them and records a *persisted* line
  carrying speaker name + icon key. `Exchange` records the prompt's speaker the same way —
  otherwise, after succession, old player messages render under the successor's name. Chat,
  journal, and replay stop resolving ids through engine state. Views carry
  `(id, name, brief)` art subjects **including the player** (today's illustrator draws the
  player icon from state even though scenes exclude the player from subjects).
- **The secrecy boundary, weakened knowingly.** The kernel keeps the type boundary: the
  Narrator input type has no field for private text, and only that type reaches the narrator
  prompt. The leak *checks* (told facts about unmet entities, speaker ids, unknown names in
  sections) move into the rooms kit and are mandatory there. An engine with no hidden canon
  pays nothing. The secrecy golden survives, rebuilt on views.
- **Two-stage parse everywhere content crosses disk**, not just the launcher: envelope
  first, then the named engine's payload model — in `content/io.py` catalog reads, save
  restore/reload, and authoring writes. Parsing the envelope alone would admit
  payload-invalid content into the catalog. The launcher keeps skip-unreadable behavior.
- **GameService and its four adapters:** builtin loop, MCP/code mode, the NiceGUI pages, and
  the read-only `external` viewer (save polling + `reload()`). The service carries the rule
  that a change outside a turn may not open a player prompt (today `transact`'s check, read
  post-inversion off the view's prompt field).
- **The authoring loop only.** The kernel runs the authoring agent: send instructions, turn
  refusals into `ModelRetry`, gate `finish()` through the engine's unmet list, write the
  file. Draft model, patch dialect, bars, prompts, growth: engine-supplied (usually the
  kit's authoring module). **Per-engine authoring tools are dissolved, not deferred**: the
  kit's patch gains a `connections` field, deleting `AuthoringTool` and the publication
  machinery in the same phase (a split would run two connection-writing paths). Two
  constraints ride the fold: the authored entity shape must not also expose writable
  `exits`, and every connection is preflighted before the patch's first mutation — today's
  `connect` validates before its first append, and `Draft.apply` must not regress that
  atomicity. This also dissolves the Claude SDK blocker: the SDK bridge drops
  `tools/list_changed` and cannot learn tools after connect (`harness/claude.py`).

## The engine protocol

Small, typed with generics; the composition root holds engines behind one erased base
(Python has no existential generics — that one seam is accepted and named here). The
protocol must name the *payload* types, not just the state — `Scenario` and `Character`
stop being concrete shared models:

```python
class Engine[S: BaseModel](Protocol):
    id: EngineId
    title: str
    instructions: str
    state: type[S]                                   # save payload, validated strictly
    scenario: type[BaseModel]                        # scenario payload
    character: type[BaseModel]                       # character payload
    tools: tuple[Tool[S], ...]                       # static; SRD procedures + change_world

    def new_game(self, scenario, character, packs) -> S: ...
    def validate(self, state: S, packs) -> None: ...  # pack ids ride the envelope
    def answer(self, state: S, answer: Answer) -> Resolution: ...
    def views(self, state: S) -> Views: ...
    def over(self, state: S) -> str | None: ...
    creation: CharacterCreation                       # create() returns payload + CreationPreview
    player_actions: tuple[PlayerAction, ...]
    def authoring(self) -> Authoring | None: ...
```

The exact member list is PLAN work; two rules are fixed: **the kernel asks the engine what
to do**, and the envelope's pack ids are passed into `new_game`/`validate` because engines
read them (Loner's twists, `check_packs`). `tools` is static; per-turn legal toolsets are
recorded future work.

Decisions become engine continuations. The kernel sees `PlayerPrompt {prompt, options,
allows_text}` on the view and routes the player's `Answer` to `engine.answer`. `resolvers`,
`PendingOption.name/args`, and `Engine.restored`'s per-option revalidation leave the kernel
(`during_suspension` stays, see above). Reviewer caution, kept visible: the kit supplies one
shared frozen-call continuation for its own flows (succession, stakes), or three engines
re-invent `PendingOption` privately and the deletion inverts into growth.

## The Director's surface

**Decided: one `change_world` tool** — the rooms kit collapses reveal / move / improvised
item / traits / kill / unlock / party / threads into one discriminated-union tool. Engines
select arms as their own union model (Breathless ships no improvised-item arm), and the
wrapper field carries a description (the schema guard requires one). One call, one
transaction, one readback; deterministic consequences (drops on death, reveal cascades,
`when_reached` notes, the succession prompt) happen inside it. The Director's whole surface
is then: the engine's SRD procedure tools plus `change_world`.

**Sequencing correction from review: probe it first, against today's code — properly.**
The probe is bigger than a tuple swap and the plan budgets it: ~22 test references call the
old tool names and must move to union arms; the director prompt goldens move with
`director_world.md`, not only the schema fixtures; the eval record must gain arm telemetry
(today it discards successful tool names, so "wrong-arm rate" is unmeasurable); and the
multi-verb baseline (`*/three-things`) must be run on the old surface *before* the swap —
`phase3-5` holds only the three named cases. The metric is the union arm's schema size
(complete per-engine tool lists already run 10.9–15.9 KB). If the union measurably loses,
revert and the kit keeps separate verbs — the decision flips by recorded procedure at
near-zero sunk cost.

## Feature-by-feature impact

Every current feature survives except the raw-state panel (decision below).

| Feature | After the inversion |
|---|---|
| Loner3e, 24XX, Breathless | Each gets a typed `State` embedding `RoomsState[S]` with its own sheet union plus its own fields. Blob glue, `sheet_of`, stray-id checks deleted. A 24XX ship becomes a 24XX model. |
| SRD deviations | Recorded procedure-level deviations stay (they are design choices). Impedance mismatches close; future engines land writing their SRD's own nouns. |
| Character creation | Flow unchanged: `CreationStep`/`Picks` stay the kernel↔UI contract. `create()` returns the payload plus a `CreationPreview` the page renders — defined with the envelope, not later, or the page breaks a phase early. |
| Scenarios & characters | Envelope + engine payload; two-stage parse at every disk boundary. All shipped JSON is rewritten once. |
| Saves & launcher | Envelope + payload; launcher lists from the envelope alone, keeps skip-unreadable. Old saves invalid; no migration (standing policy). |
| Packs | Engine-owned end to end (`load_packs`, `check_packs`, `PackCreation`, `authoring_guidance`); envelopes keep the pack-id list, and it is passed into `new_game`/`validate`. |
| Authoring (premise + PDF) | Same product, same skills, same source path. Kernel runs the loop; rooms kit ships the draft model with `connections` (preflighted, no second exits path). Both authoring pages stay. |
| World growth | Rooms kit module: same frontier rule, extension pass, growth skill. |
| Threads | Rooms kit state, in the Director view, advanced through `change_world`. |
| Death & succession | Inside the kit's `change_world` death arm; the succession continuation uses the kit's shared frozen-call shape. |
| Player actions | Unchanged concept, engine-owned; the service refuses one while a prompt is open. |
| UI (NiceGUI) | Pages render kernel view types and stop traversing game state. Chat/journal read persisted denormalized lines. Settings/theme untouched. **Raw-state panel deleted (decision); the code-driver agent log is kept** — it is the only live view of driver activity. |
| Media / illustration | Views carry `art_prompt` + `(id, name, brief)` subjects including the player; `media.py` stops reading engine state. |
| Code mode (MCP + Claude/Codex drivers) | Adapter over `GameService`'s begin/call/end. Its LLM-facing prose stays. Both drivers stay (decision). |
| Evals & tests | ~1.8k eval + ~5.7k test lines rewritten against payloads and views — priced work, measured per phase. The 55 case ids survive: the existing `twentyfourxx/fit-the-skiff` case converts to the typed ship (a ship fixture already exists, as a location). Goldens regenerate once per atomic phase; targeted cases only. |
| Narrator secrecy | Type in the kernel, checks in the kit; the secrecy golden survives with its meaning intact. |

## What is deliberately not changing

- The model proposes; Python decides. Draft → validate → commit with trial application.
- One turn loop; every harness drives it through `GameService`.
- All player-facing prose flows through the Narrator.
- Tests offline (`FunctionModel`); settings in one `.env`; one composition root.
- No event sourcing, no ECS, no capability framework. The inversion is ownership, not new
  abstraction.
- **Kept by decision, do not re-propose:** the Codex driver (`harness/codex.py` + `exec.py`),
  the builtin in-app authoring chat page, and the code-driver agent log. Offered as
  deletions and refused.

## Honest arithmetic

Three audits recounted this table (two agent reviews, then Codex against the derived plan).
Each round moved the numbers the same direction; the structural reason: whatever does not
fit the kit cleanly gets multiplied by three engines. Base: **9076** `src` `.py` lines
(the counter is `.py` files only; also tracked: ~5691 `tests`, ~1783 `evals`).

| item | third-audit estimate |
|---|---:|
| Phase 0 `change_world` probe (arg models survive as arms) | −10 to −40, or 0 if reverted |
| kernel types, envelopes, protocol, service, shim | +180 to +300 |
| hostile engine | ≈ 0 src (tests grow ~150) |
| atomic port: seam + old `Engine` + world→kit + authoring fold + engine payloads | −110 to −250 |
| code mode onto service begin/call/end; UI/media onto views | 0 to −40 |
| scheduled deletions (wrappers −20, raw-state −5, carryovers, pack meanings −10..−20) | −40 to −70 |
| extra cuts from the Codex review (media `AliasPath` model, `write()` double-construction, `ItemSheet.broken`, inline `take_notes`/`close_segment`/`offered`/`play_action`, merge `ui/panels.py`, mapping wrappers) | −60 to −76 |
| **net** | **≈ −300 to +80** |

**Read that plainly: the ceiling is reachable but not assured.** So the rules, per the
standing bar (smaller, or break-even and more maintainable):

1. Every PLAN phase records `src`, `tests`, and `evals` `.py` counts before and after.
2. **`src` must end at or below 9076.** A phase tracking above its estimate stops and
   re-scopes; no invented cuts, no reaching for the refused deletions.
3. Weak-model criterion decides tool-surface questions by measured eval, targeted cases only.
4. No interim stand-ins for decided features; each phase leaves the game playable, and no
   phase leaves two implementations of the same concept alive (the reason the kit move and
   the port are one atomic phase).

## Acceptance tests

1. **The hostile engine, before any port.** A tiny playable engine with no locations, items,
   other actors, party, threads, discovery, death, or growth: one resource, two procedures,
   built on the new protocol and driven end to end through `GameService`. If it must stub
   any kernel concept, the kernel is still too opinionated. (Replaces the old Phase 4.2
   journal engine, which targeted the pre-inversion `Engine`.)
2. **Port 24XX first among the three.** The litmus: `twentyfourxx/fit-the-skiff` and the
   ship-upgrade test, converted so the upgrade installs into a 24XX ship model, not a
   `location`.
3. **The identifier-level kernel-vocabulary test**, with its scope and allowlist defined, as
   a standing CI check.
4. **Secrecy regression:** the golden proving hidden canon cannot reach the narrator prompt
   survives, rebuilt on views.

## Planned future work (recorded, not scheduled)

- **Scenes kit.** The world as a sequence of scenes; the Director decides a new scene is
  due; authoring draws it from premise, source document, and play so far. Second kit, proof
  that kits compose, and a product change to how games play; waits until the inversion has
  shipped and 24XX is ported.
- **`change_world` fallback.** If the Phase-0 probe or post-port evals show the union losing
  (score, retries, wrong-arm rate on the standing cases), the kit splits it back into verbs.
  Local change either way.
- **Dynamic legal toolsets** (no advance tool when no advance is owed): after the surface
  settles.
- **`ClaudeDriver` as `ExecDriver` subclass** the day it bills like the API (standing note).
