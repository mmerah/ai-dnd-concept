## Loose ends

- [] RAG on scenarios? .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Is the drowned-road scenario extending based on source.md?
- [] Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, maybe we need an agent whose sole role is suggesting what tools to call in what order to remove some decision making out of the director? ...)
- [] Best explanation of loner I found: https://keeper.farirpgs.com/resources/zotiquest-games/loner/introduction/ -> Use to make sure the engine is fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach
- [] Best explanation of 24xx I found: https://keeper.farirpgs.com/resources/jason-tocci/24xx/ -> Use to make sure the engine is fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach

## Ideas

- [] Cleaner codebase: the global CONFIG_VARIABLES look very unclean everytime I see them. Wonder how we could do that a bit better.
- [] Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] NPC can join/leave player party. NPC can also level-up.
