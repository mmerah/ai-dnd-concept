## Loose ends

- [] L1: Run "uv run python evals/turn_eval.py run --label my-run" multiple times and identify where things are inconsistent. Then figure out fixes (maybe the tools are too difficult to use, need to be separated, or a multi-step thing converted into a tool that combine operations, maybe instruction clarity, maybe examples in tools description to teach the model, maybe we need an agent whose sole role is suggesting what tools to call in what order to remove some decision making out of the director? ...). Same loop covers: try again gpt-oss-20b? 120b? cheaper than ds4 flash or not? narrator with a cheaper model
- [] L2: Few shot learning examples in instructions? Engines ship with them (5 scenarios of low-high complexity presenting how the SRD work) plus core as well (entities/threads/… manipulation). Only worth writing once L1 says which calls the model actually gets wrong.
- [] L7: Sounds/Voices. app/media.py is the template.
- [] L8: `TURN__RECENT_EXCHANGES` caps what an agent remembers, so a long game forgets its start. A per-location summary, written when the player leaves it, would carry the places already played without carrying every turn. Maybe could be part of the docs/MEMORY-SYSTEM.md? Each entity (npc, location) carries a memory (list[str]) which are created when the player change location (for the npc/location it just left), created by a summarizer agent. Builtin mode is clear on how to do that, but for codemode we need some brainstorm
- [] L9: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Is the drowned-road scenario extending based on source.md? Leaning skip: the source cap already swallows a 76-page adventure whole, and there is no embedding provider in the stack.

## Ideas

- [] I1: Multiple rounds of refactors: no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] I2: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, IDeas completed/deleted
- [] I3: De-aify the codebase
- [] I4: lots of testing to identify gaps of MVP0
- [] I5: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the director. Observed with builtin-harness and cheap models: sometimes trait modifications are forgotten, sometimes a reveal is not done when it should have been done, ... Limited set of tools but could improve builtin-harness mode performance
- [] I6: Rewrite: Skills, instructions, prompts. Easier english (ASD STE100). And content should be verified, not confusing, easy to understand. Particularly for instructions(prompts) since they describe how to actually play to the director (or whole session for codemode). Skills also need to be clearer, tell of everything, maybe indicate where (web link) to find SRD to reconciliate when needed? (but then harness need to authorize web fetch tool in some form, depend on the harness)
- [] I7: Demo path. One command and one GIF of a full Loner turn in builtin mode. The popular repos win on install friction and demos, not on play quality. This is the only thing they have that we do not.
- [] I8: Fold in competitor features. See `docs/COMPETITOR-RESEARCH.md`. First two: a re-read-before-you-state rule in the playing skill, and a session recap on resume (first step of L8).

## Working order

- Phase 4: L7
- Phase 5: L1
- Phase 6: I4
- Phase 7: I3
- Phase 8: I2
- Phase 9: I5
- Phase 10: L8
- Never: L9. Only if L1 proves it: L2