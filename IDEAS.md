## Loose ends

- [] docs/chat-claude-mock: Shows claude-sdk usage to have the UI directly drive claude, with the tool output of end turn ending in the chat bubble. Then the dev tab can probably show that claude code log stuff (so yousee tool calls, costs, ...). We would ideally focus on supportting 2 coding harnesses: codex and claude code. CC through the sdk, codex has a SDK as well.
- [] UI should be clearer when there is a pending decision. Engine should really want to mark those modes clearly. Loner conflicts for example. Right now it’s just a small text mess that is extremely unclear and badly written
- [] Few shot learning examples in instructions? Engines ship with them (5 scenarios of low-high complexity presenting how the SRD work) plus core as well (entities/threads/… manipulation)
- [] Support of "codex" in code mode -> it can generate images!
- [] Support of "opencode" and "pi" in code mode
- [] Sounds/Voices
- [] What refactor to make fate condensed and cairn barebones as easy as possible to implement
- [] RAG? Scenario ingestion
- [] New agent: state keeper. Add/remove traits/tags, reveal, … Always what happens is the director forgets something. Does not reveal what we interact with. You get bit by something but doesn’t always add a tag/trait or remove it, you kill something but the entity still exists (is death a tag or tool? but description on ui for example of the bloated rat would stay with just a tag?). Generally handling of "death" state. Player should die/end game?
- [] Try again gpt-oss-20b? 120b? cheaper than ds4 flash or not? narrator with a cheaper model
- [] add fate-condensed system
- [] research and add cairn barebones edition
- [] Look and replace hard-coded manually built list that are maintenance nightmares.
- [] Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, maybe we need an agent whose sole role is suggesting what tools to call in what order to remove some decision making out of the director? ...)
- [] Best explanation of loner I found: https://keeper.farirpgs.com/resources/zotiquest-games/loner/introduction/ -> Use to make sure the engine is fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach
- [] Best explanation of 24xx I found: https://keeper.farirpgs.com/resources/jason-tocci/24xx/ -> Use to make sure the engine is fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach

## Ideas

- [] Cleaner codebase: the global CONFIG_VARIABLES look very unclean everytime I see them. Wonder how we could do that a bit better.
- [] Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] NPC can join/leave player party. NPC can also level-up.
- [] RAG on scenarios? .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Is the drowned-road scenario extending based on source.md?
- [] Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, IDeas completed/deleted
- [] De-aify the codebase
- [] Lots of testing to identify gaps of MVP0
