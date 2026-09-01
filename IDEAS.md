## Ideas

- [] 0: Refactors once PLAN.md is in: ponytail-audit + Minimal engines so that there is as little deviations for each as possible (any deviation that look easy to close should be closed in the most elegant/clean/ponytail way) + Simplification of codebase if any available
- [] 1: Sounds/Voices. app/media.py is the template.
- [] 2: `recent_exchanges` caps what an agent remembers, so a long game forgets its start. A per-location summary, written when the player leaves it, would carry the places already played without carrying every turn. Maybe could be part of a memory system? Engines decides who/what carries a memory (list[str]) which are created in a controlled manner (e.g. when changing location or scene), created by a summarizer agent.
- [] 3: RAG? Scenario ingestion. .pdf -> source.md in scenario/<id>/ folder, then RAG on it? Leaning skip: the source cap already swallows a 76-page adventure whole, and there is no embedding provider in the stack.
- [] 4: Re-implement a builtin mode and Re-implement an eval (see history)
- [] 5: Multiple refactors: ponytail-audit, no change in behavior, improvements in consistency in the codebase, removing useless ceremony, SOLID/DRY/KISS, type safety, fail fast.
- [] 6: Doc sweep: LLM models performance, roadmap rewrite, readme rewrite, Ideas completed/deleted
- [] 7: De-aify the codebase
- [] 8: lots of testing to identify gaps of MVP0
- [] 9: a new agent, state keeper, that adds/removes traits/tags, reveals, cleans up after the game master. Observed with small/cheap models: sometimes trait modifications are forgotten, sometimes a reveal is not done when it should have been done, ... Limited set of tools but could improve builtin-harness mode performance
- [] 10: Rewrite: Skills, instructions, prompts. Easier english (ASD STE100). And content should be verified, not confusing, easy to understand. Particularly for instructions(prompts) since they describe how to actually play to the director (or whole session for codemode). Skills also need to be clearer, tell of everything, maybe indicate where (web link) to find SRD to reconciliate when needed? (but then harness need to authorize web fetch tool in some form, depend on the harness)
- [] 11: Demo path. One command and one GIF of a full Loner turn. The popular repos win on install friction and demos, not on play quality. This is the only thing they have that we do not.
- [] 12: Fold in competitor features. See `docs/COMPETITOR-RESEARCH.md`. First two: a re-read-before-you-state rule in the playing skill, and a session recap on resume (first step of L8).
- [] 13: Pack authoring: write a pack (skills, gear, tables) through the authoring loop, then a scenario or character that plays with it.
- [] 14: The docs for each engine: have a template/format for each? Engines that are not implemented have the sections content as "unimplemented"?
