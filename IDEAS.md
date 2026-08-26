## Loose ends

- [] L1: Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, maybe we need an agent whose sole role is suggesting what tools to call in what order to remove some decision making out of the director? ...). Same loop covers: try again gpt-oss-20b? 120b? cheaper than ds4 flash or not? narrator with a cheaper model
- [] L2: Few shot learning examples in instructions? Engines ship with them (5 scenarios of low-high complexity presenting how the SRD work) plus core as well (entities/threads/… manipulation). Only worth writing once L1 says which calls the model actually gets wrong.
- [] L3: What refactor to make fate condensed and cairn barebones as easy as possible to implement. plus: look and replace hard-coded manually built list that are maintenance nightmares.
- [] L4: Best explanation of loner I found: https://keeper.farirpgs.com/resources/zotiquest-games/loner/introduction/ and of 24xx: https://keeper.farirpgs.com/resources/jason-tocci/24xx/ -> Use to make sure both engines are fully compliant (drastic changes might be needed!). Only thing obviously is our AI-as-GM approach. Read both before adding a third engine, so a drastic change hits the base shape once.
- [] L5: add fate-condensed system. docs/FATE-CONDENSED.md is already written.
- [] L6: add cairn barebones edition. docs/CAIRN-BAREBONES.md is already written.
- [] L7: Sounds/Voices. app/media.py is the template.
- [] L8: `TURN__RECENT_EXCHANGES` caps what an agent remembers, so a long game forgets its start. A per-location summary, written when the player leaves it, would carry the places already played without carrying every turn. Maybe could be part of the docs/MEMORY-SYSTEM.md? Each entity (npc, location) carries a memory (list[str]) which are created when the player change location (for the npc/location it just left), created by a summarizer agent. Builtin mode is clear on how to do that, but for codemode we need some brainstorm
- [] L9: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Is the drowned-road scenario extending based on source.md? Leaning skip: the source cap already swallows a 76-page adventure whole, and there is no embedding provider in the stack.

## Ideas

- [] I1: Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] I2: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, IDeas completed/deleted
- [] I3: De-aify the codebase
- [] I4: lots of testing to identify gaps of MVP0
- [] I5: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the director. Observed with builtin-harness and cheap models: sometimes trait modifications are forgotten, sometimes a reveal is not done when it should have been done, ... Limited set of tools but could improve builtin-harness mode performance

## Working order

- Phase 1: L3
- Phase 2: L4
- Phase 3: L6, L5
- Phase 4: L7
- Phase 5: L1
- Phase 6: I4
- Phase 7: I3
- Phase 8: I2
- Phase 9: I5
- Phase 10: L8
- Never: L9. Only if L1 proves it: L2