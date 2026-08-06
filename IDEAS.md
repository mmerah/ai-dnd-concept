## Loose ends

- [] Investigation: bring the eval suite to 100%. Right now 'condition' related fail often and 'story-no-risk-needed' as well (model calls an action when not needed). ROLES__DIRECTOR__MODEL='qwen/qwen3.6-27b' is extremely reliable and a good candidate for eval run comparison. 120b is faster and cheaper though but not as reliable. But if qwen 27b can reach 100% (it only fails at condition-lifted/rider) then the loose end is closed. It always fails there though so something is definitely off (look /home/toto/repos/ai-dnd-concept/scripts/evals/results/2026-08-06-f974934+ca1d91a.json). Settled by the two `eb4d8d3` suites: the header sentence added to counter no-op turns did **not** move `story-no-risk-needed` (4/6, unchanged), so that case is not a prompt-wording problem. `condition-lifted`/`condition-rider` are still the two lifetime signatures. See the last section of `baseline.md`.

## Ideas

- [] Eval coverage owed: an advantage scenario, a concentration-replacing-a-spell scenario, and
  story checks that test both directions.
- [] `milestone_earned` is unmeasured: no eval scenario tags advancement; the free-form
  `advancement-ready` tag call it replaced measured 0–33%. Scenario-marked milestones remain the
  reliable path.
- [] Prove "engines are data" with a third engine. Two engines can share an accident; a third
  one is the test.
- [] Probe the advisor's `NativeOutput` on gpt-oss: the maintainer's small schema works in native
  mode (probed 3/3); the advisor's `SheetDelta` is likewise small but has never been probed live.
- [] Codex: Comment simplification round
- [] Improved naming of variables, fields, methods, classes, ... Sometimes it is too unclear what they do
- [] Cleaner codebase: the global CONFIG_VARIABLES look very unclean everytime I see them. Wonder how we could do that a bit better.
- [x] Leaner AGENTS.md/CLAUDE.md, remove all elements that are subject to change (architecture concepts, file name, ...)
- [] Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] Delete unused or used-once stuff. Functional programming. Models are separated from the domain correctly. Structure is consistent. Better SOLID to better reason? Or would that be too much indirection?
- [] New content pack: SRD-2014 extension. New backgrounds, new feats, anything else?
- [] NPC can join/leave player party. NPC can also level-up.
- [] Quest/Event/Hook system of some kind. Need brainstorming to decide the way to do that. Think about any kind of fiction book or D&D adventure: how would we have a general system to progress elements of a story, based on player actions but also in the background
- [] Is there ideas from straightjacket github project that could be used? It seems the closest in what we want (https://github.com/aradix85/straightjacket)
- [] Trim AGENTS.md out of the code-specific stuff that is subject to change.
- [] Conversation/Message history: passed straight but without context. Would be nice if it had location where the message happened at least, would help when agent receive a list of message
- [] Engines: more modular? what about combat? should it also be similar to advancement where it ships with a UI as well. Thus we can have a 5e combat, story combat or any other combat system that the engine define?