# ADR-0001 — Core owns the fictional world, an engine owns all mechanics

Date: 2026-08-11
Status: Accepted
Context: PLAN.md phase 7 (test-only boundary probe); binds phase 8 (world/mechanics split).

## Context

At HEAD, `WorldState.Record` pairs an `Entity` with a `Sheet` — one universal mechanical
aggregate that core defines, validates, and mutates on every engine's behalf. Story and 5e both
fit it, which proves nothing: two engines that grew inside the same aggregate cannot show where
the aggregate ends and the engine begins.

`tests/probe/probe_engine.py` is the executable counterexample — an Ironsworn-shaped engine
(bounded momentum with a per-fighter ceiling, progress tracks with their own resolution rule, one
action settled by an action die against two challenge dice). It is not registered in
`ENGINE_MODULES` or the launcher and ships no content, no advancement, and no `Sheet`. Its whole
import list is `aidm.state.base` (entities, ids, the two model bases), `aidm.state.dice`, and
`aidm.state.facts`; `tests/probe/test_probe_boundary.py` asserts that by AST, so a future
refactor that pushes engine concepts back into core fails a test rather than passing review.

## Decision

**Core owns** entities, placement, discovery, relations, threads, hooks, the `Fact` stream, ids,
dice, and uninterpreted fictional traits. Everything core owns is fiction: a thing that is true
in the story regardless of which rules are being played.

**An engine owns** all numeric and mechanical state, its whole plan lifecycle (typed plan,
check, resolution), and its own validation. Core never branches on a mechanical field and never
names one.

**Persisted mechanics is JSON to core and a strict Pydantic model inside the engine.** Core
carries an opaque payload in the save envelope and hands it back unread. The engine is the only
validator of that payload; a corrupt one fails at load and at commit, never silently.

**One engine-owned commit path validates both halves.** Core's `GameState` validation checks the
envelope and the world; the engine's commit revalidates the whole mechanics payload. A failed
transaction never replaces committed state — the existing rule, now applied to both halves.

**Core hooks write world operations only.** A shared hook can author fiction (a trait, a reveal,
a thread advance); it cannot reach into an engine's numbers.

## The contract phase 8 implements

The probe engine spells it as five functions. Phase 9 folds them onto one engine object; the
shapes do not change.

| Probe function | What it must do |
|---|---|
| `create(payload: JsonValue) -> Mechanics` | Validate the persisted half into the engine's own strict model. The only reader of those bytes. |
| `commit(mechanics) -> Mechanics` | Revalidate the whole payload at the transaction boundary. |
| `initialize(mechanics, entity) -> None` | Give an entity created during play its mechanics, in the same commit that adds it to the world. Beginning a game is the same call over the authored entities. |
| `render(mechanics, entity) -> str` | The engine's own view of an entity for a prompt. Core has no fallback rendering. |
| `resolve(mechanics, action, rng) -> list[Fact]` | Mutate mechanics directly and report `Fact`s. No shared effect union stands between the engine and its own numbers. |

Advancement and content are **optional capabilities**, not part of this contract: the probe
exposes neither and is still a complete engine.

## Consequences

- `Sheet`, `SheetEffect`, `SheetDelta`, and every counter/number/note/ref effect leave core.
- Sheet tags that describe lasting fiction (`warded`, conditions a shared hook authors) migrate
  to a core `Trait` facility so both engines can read them without core interpreting them.
- Direct engine mutation replaces `apply_effect` for damage, healing, costs, refills, and
  bookkeeping. `TurnPlanBase` stops fixing a mechanical effect union.
- `SAVE_VERSION` bumps; stale saves are refused, never converted.
- Story migrates first, then 5e, reading state/turn fixture diffs at each step, and the probe is
  run through the real initialization, resolution, rendering, creation, and commit paths at the
  end.

## Alternatives rejected

- **Generic path/value mechanical patches** — would let core address mechanics it cannot type.
- **Keeping `Sheet` as a "good enough" universal aggregate** — the probe's momentum ceiling and
  resolved-track rule are cross-field invariants no shared aggregate can express.
- **Building a third shipped engine** — the pressure is architectural, not a product need. The
  probe stays behind tests permanently.
