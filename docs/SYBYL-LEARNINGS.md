# Sybyl learnings

Status: adopted 2026-08-17 where it fit — item 3 fused into PLAN.md Phase 3 (one source system
with PDF ingestion), item 1 as the Phase 5 journal export; items 2, 4, 5 are in PLAN.md's
deferred list with their triggers.

## Decision

Keep the deterministic game architecture. Borrow Sybyl's human-readable journal and player-assist
workflows, but not its prompt-based treatment of rules or state.

Sybyl is an Obsidian assistant for solo play, not a rules engine. It supports **Lonelog**, a
system-neutral journal notation; it does not implement Loner's Chance/Risk dice, Luck, Harm, or
Twist Counter. The player supplies a roll for an action, while the model interprets it. When an
oracle result is omitted, the model generates one from a prompt hint.

Our product serves a different goal: the model proposes a typed plan, engine code resolves it,
hooks react, and a fully revalidated transaction commits. That remains the right foundation for an
autonomous, mechanically faithful AI game master.

## What Sybyl does better

- **Low-friction play:** discrete commands for starting a scene, declaring an action, asking the
  rules, requesting options, and expanding prose.
- **Player authorship:** the assistant does not decide or narrate the player character's actions,
  thoughts, or choices.
- **Portable records:** play lives in readable, editable Markdown instead of an application-only
  representation.
- **Immediate ruleset breadth:** attached rules can ground prompts without implementing an engine.
- **Accessible configuration:** provider/model selection, local Ollama support, connection checks,
  and optional token counts are exposed in the UI.

These advantages trade away mechanical guarantees. Sybyl's requests are stateless, its compact
context is parsed from a recent slice of Markdown, and its rules digest and outputs are unvalidated
model prose. Those are useful UX shortcuts, not suitable sources of canonical game truth here.

## Candidate adoption plan

1. **Markdown journal projection** — about 1–2 days

   Render committed turns, rolls, facts, and narration as readable Markdown, optionally compatible
   with Lonelog. Treat it as a projection or export: `GameState` and the trace remain authoritative,
   and no state is reconstructed from journal text.

2. **Read-only player assistance** — about 1–2 days

   Add `What can I do?`, `What now?`, and `Ask the rules`. Suggestions must use visible state and
   engine vocabulary, must not choose for the player, and must never mutate state. Rules answers
   should use the curated engine SRD and instructions rather than a model-generated digest.

3. **Source-assisted authoring** — about 2–4 days after the scenario creator

   Accept Markdown, text, or PDF notes as input to scenario, character, and pack authoring. Model
   output must still pass the existing strict authored-content models and engine validation before
   any file is written. Source ingestion must not move into the turn loop.

4. **Player-agency and narration modes** — about 1–2 days

   Add an eval for the existing boundary that a turn stops when the next move requires player
   intent. Consider an optional neutral-referee narration style without changing resolution.

5. **Provider and cost UX** — about 2–3 days

   Surface provider/model selection, connection validation, per-turn latency, and token use in the
   UI. Preserve per-role configuration; a single global model would be a regression.

## Guardrails

Do not adopt runtime rules interpreted from prose, model-generated dice, Markdown as canonical
state, lossy rules digests as mechanical truth, or stateless prompting as a replacement for world
state and transactions.

A drastic pivot is justified only if the product goal changes from an autonomous AI game master to
a lightweight companion for a player who rolls dice and maintains the truth manually. Until then,
Sybyl should influence the product shell, not the core.

## Sources

- [Sybyl README](https://github.com/zeruhur/sybyl/blob/main/README.md)
- [Sybyl commands](https://github.com/zeruhur/sybyl/blob/main/src/commands.ts)
- [Sybyl prompt builder](https://github.com/zeruhur/sybyl/blob/main/src/promptBuilder.ts)
- [Sybyl Lonelog parser](https://github.com/zeruhur/sybyl/blob/main/src/lonelog/parser.ts)
- [This project's architecture](../README.md)
- [This project's weaknesses and direction](ROADMAP.md)
