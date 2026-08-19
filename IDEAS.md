## Loose ends

- [] Eval coverage: evaluate what pipeline does for different scenarios. Expected VS what happens. Light eval runs, re-use the codebase src because that's what we evaluate. In scripts
- [] Worldkeeper: wanted to add memory to player but said "we have no id". Makes no sense to add memory to player though? Or is that journal feature?
- [] Codex: Comment simplification round
- [] CONFIG_VARIABLES into config, no magic variable/global VARIABLE anywhere. Re-organization of codebase, clearer, easier to navigate, files have a structure that make sense, models are in separate files, clean functional programming. No change in behavior
- [] RAG on scenarios? .pdf -> source.md in scenario/<id>/ folder, then RAG on it?
- [] naming: variables, files, methods, classes generally need some renaming to represent more clearly what they do, and with more details
- [] Narrator does not see speaker memory when player adress someone.
- [] pyproject.toml should FIX versions.
- [] Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, ...)

## Ideas

- [] Codex: Comment simplification round
- [] Improved naming of variables, fields, methods, classes, ... Sometimes it is too unclear what they do
- [] Cleaner codebase: the global CONFIG_VARIABLES look very unclean everytime I see them. Wonder how we could do that a bit better.
- [] Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] Delete unused or used-once stuff. Functional programming. Models are separated from the domain correctly. Structure is consistent. Better SOLID to better reason? Or would that be too much indirection?
- [] NPC can join/leave player party. NPC can also level-up.
- [] Conversation/Message history: passed straight but without context. Would be nice if it had location where the message happened at least, would help when agent receive a list of message
- [] Engines: more modular? what about combat? should it also be similar to advancement where it ships with a UI as well. Thus we can have an oracle combat, story combat or any other combat system that the engine define?
