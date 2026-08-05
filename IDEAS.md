## Loose ends

- **Eval drift is unmeasured.** Two suite runs on an identical tree differed by 9.6 points on
  interpretation, against a 2.2-point historical drift. Re-measure drift on an unchanged tree
  before trusting the next prompt change.
- **The Referee guarantees *objected*, not *corrected*.** One live transcript showed the Director
  ignoring a correct objection. Consider verifying that the correction actually landed.
- **Owed eval coverage.** Two scenarios never written: advantage via keep-highest, and
  concentration replacing a spell. Also outstanding: the story checks that only test one
  direction, and fact traces for failed runs.
- **The Director's free-form `advancement-ready` path is weak** — 0–33% in measurement.
  Scenario-marked milestones are the reliable path; treat the tag as a fallback.
- **Prove "engines are data" with a third engine.** Two engines can share an accident; a third
  one is the test.

## Ideas

- [] Codex: Comment simplification round
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