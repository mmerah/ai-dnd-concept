## Loose ends

- [] L1: UI should be clearer when there is a pending decision. Engine should really want to mark those modes clearly. Loner conflicts for example. Right now it’s just a small text mess that is extremely unclear and badly written. Root cause: loner sets a conflict decision with no options, and the panel then draws one bold label and nothing else.
- [] L2: Generally handling of "death". The director forgets: you kill something and the entity still exists, you get bit and nothing gets added or removed. Nothing can remove an entity today. Is death a tag or a tool? Description on the UI of the bloated rat would stay with just a tag? Player should die/end game? Second half, only if the eval says the director really does forget: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the director.
- [] L3: Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, maybe we need an agent whose sole role is suggesting what tools to call in what order to remove some decision making out of the director? ...). Same loop covers: try again gpt-oss-20b? 120b? cheaper than ds4 flash or not? narrator with a cheaper model
- [] L4: Few shot learning examples in instructions? Engines ship with them (5 scenarios of low-high complexity presenting how the SRD work) plus core as well (entities/threads/… manipulation). Only worth writing once L3 says which calls the model actually gets wrong.
- [] L5: What refactor to make fate condensed and cairn barebones as easy as possible to implement. plus: look and replace hard-coded manually built list that are maintenance nightmares.
- [] L6: Best explanation of loner I found: https://keeper.farirpgs.com/resources/zotiquest-games/loner/introduction/ and of 24xx: https://keeper.farirpgs.com/resources/jason-tocci/24xx/ -> Use to make sure both engines are fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach. Read both before adding a third engine, so a drastic change hits the base shape once.
- [] L7: add fate-condensed system. docs/FATE-CONDENSED.md is already written.
- [] L8: research and add cairn barebones edition. No doc yet (would be docs/CAIRN-BAREBONES.md), that comes first.
- [] L9: docs/chat-claude-mock: Shows claude-sdk usage to have the UI directly drive claude, with the tool output of end turn ending in the chat bubble. Then the dev tab can probably show that claude code log stuff (so you see tool calls, costs, ...). We would ideally focus on supporting 2 coding harnesses: codex and claude code. CC through the sdk, codex has a SDK as well.
- [] L10: Other harnesses, config-level. Support of "codex" in code mode -> it can generate images! Support of "opencode" and "pi" in code mode. Codex already runs through .codex/config.toml, so images are the only real work here.
- [] L11: Sounds/Voices. app/media.py is the template.
- [] L12: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Is the drowned-road scenario extending based on source.md? Leaning skip: the source cap already swallows a 76-page adventure whole, and there is no embedding provider in the stack.

## Ideas

- [] I1: Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] I2: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, IDeas completed/deleted
- [] I3: De-aify the codebase
- [] I4: Settings can easily be changed from the UI? Write .env and restart, not live reload.
- [] I5: lots of testing to identify gaps of MVP0

## Working order

- Phase 0: L1
- Phase 1: L5 + L2
- Phase 2: L9, L10, I4
- Phase 3: L6
- Phase 4: L8, L7
- Phase 5: L11
- Phase 6: L3
- Phase 7: I5
- Phase 8: I3
- Phase 9: I2
- Never: L12. Only if L3 proves it: L4