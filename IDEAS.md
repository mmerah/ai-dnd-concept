## Loose ends

- [] Investigation: bring the eval suite to 100%. What Phase 8 left (see baseline.md): the Groq
  `finish_reason: "error"` deaths (8/69 turns — gpt-oss answers a `tool_choice: required` call
  in prose; an OpenRouter routing preference excluding that provider needs a `RoleConfig` knob,
  then re-measure `spells`/`story`/`checks`, whose dips are those deaths, not quality); the
  conditions text-fallback (after a "Please include your response in a tool call" retry the model
  settles on a minimal branchless plan — 2/10 runs); and the roll-gated condition probes (a
  perfect plan still fails when the d20 misses, so 100% on `conditions` means deciding whether
  the probe should read the branch instead of the outcome).

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
- [] Refactor on codebase structure and organistation: Models in models/ or models.py instead of top of class or whatever. Delete unused or used-once stuff. Functional programming. Models are separated from the domain correctly. Structure is consistent. Better SOLID to better reason? Or would that be too much indirection?
- [] Adding a new engine (e.g. ironsworn) should be as easy as possible
- [] How to reduce lines of code? Maybe bake more 5e stuff into the srd-2014/*.json and thus the codebase can be more lean?
- [] New content pack: SRD-2014 extension. New backgrounds, new feats, anything else?
- [] NPC can join/leave player party. NPC can also level-up.
- [] Quest/Event/Hook system of some kind. Need brainstorming to decide the way to do that. Think about any kind of fiction book or D&D adventure: how would we have a general system to progress elements of a story, based on player actions but also in the background
- [] Is there ideas from straightjacket github project that could be used? It seems the closest in what we want (https://github.com/aradix85/straightjacket)
- [x] Trim AGENTS.md out of the code-specific stuff that is subject to change.
- [] Conversation/Message history: passed straight but without context. Would be nice if it had location where the message happened at least, would help when agent receive a list of message
- [] Engines: more modular? what about combat? should it also be similar to advancement where it ships with a UI as well. Thus we can have a 5e combat, story combat or any other combat system that the engine define?