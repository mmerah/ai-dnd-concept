## Loose ends

- [] Eval coverage: evaluate what pipeline does for different scenarios. Expected VS what happens. Light eval runs, re-use the codebase src because that's what we evaluate. In scripts
- [] Worldkeeper: wanted to add memory to player but said "we have no id"

## Ideas

- [] Codex: Comment simplification round
- [] Improved naming of variables, fields, methods, classes, ... Sometimes it is too unclear what they do
- [] Cleaner codebase: the global CONFIG_VARIABLES look very unclean everytime I see them. Wonder how we could do that a bit better.
- [] Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] Delete unused or used-once stuff. Functional programming. Models are separated from the domain correctly. Structure is consistent. Better SOLID to better reason? Or would that be too much indirection?
- [] NPC can join/leave player party. NPC can also level-up.
- [] Conversation/Message history: passed straight but without context. Would be nice if it had location where the message happened at least, would help when agent receive a list of message
- [] Engines: more modular? what about combat? should it also be similar to advancement where it ships with a UI as well. Thus we can have an oracle combat, story combat or any other combat system that the engine define?
