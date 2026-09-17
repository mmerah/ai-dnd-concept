# PROGRESS

One entry per phase of `PLAN.md`: the four line counts at its start and its end, the decisions
taken off-plan, the review findings refuted and why, and what is known and accepted.

## Phase 1: the whole pack, and AP01 complete

| count     | before | after  | plan target      |
| --------- | ------ | ------ | ---------------- |
| `src`     | 9,464  | 9,582  | 9,640 to 9,780   |
| `tests`   | 11,406 | 11,668 | 11,590 to 11,700 |
| `qa`      | 2,004  | 2,004  | unchanged        |
| `scripts` | 0      | 333    | about 260        |

`src` lands 58 lines under its floor because the reviews cut what the plan's shape carried for
phase 3 (below). `scripts` lands over its estimate because the reviews added the boundary
checks the converter lacked. Both are inside the 20% band "How to work" allows.

Decisions taken off-plan:

1. **`written` packs wait for phase 3.** The plan's `PackSet` shape carried `written`,
   `check_addable`, `installing` and a `written` parameter on `read_packs` with no caller before
   phase 3 part B. Both reviews named it against "do not build for future needs"; it is cut.
   `PackSet(engine, installed)` and `read_packs(engine, directory, model)` are what phase 1
   calls. Phase 3 part B adds the written directory beside `Engine.install_pack`.
2. **`guidance` lives on `SceneEngine` alone.** The seam has no `packs` until phase 3, so a
   concrete seam `guidance` was a two-argument pass-through for `authoring`. The seam declares
   `authoring: str`; the room family passes it directly; `SceneEngine.guidance(selection, *,
   opening)` renders `authoring` plus the chosen packs' sections. Phase 3 part A moves it up
   with `packs`.
3. **`Pack.sections` is one method.** The plan's `kit_sections` plus `sections` was two public
   names for one behaviour; the base `sections` renders the kit and an engine adds its own after
   `super()`. Phase 2 part B step 5's "the fix is in `kit_sections`" reads `Pack.sections`.
4. **`PackSet.guidance` takes a `PackSelection`, not an optional.** Its one caller narrows with
   `require` first. `rules_sections` and `chosen` keep the optional: the master's sections read
   `state.packs`, which a room game leaves `None`.
5. **The loner3e worldsmith golden moved in part A, not only in part B.** The pack text went
   from `json.dumps` to sections in part A, so the golden could not stay byte-identical there;
   part B regenerated it once more after `AUTHORING` grew. Every other golden is byte-identical
   to `9a87851`, which is the proof the `srd`-only master and narrator prompts did not move.
6. **The converter refuses what it cannot read.** A trait or name table that is not 6×6, a seed
   row with no adventure cell, and a cast field key outside the SRD's eight are refusals naming
   the heading or the block, not silent short tables. Headings are matched by level as well as
   title.

Refuted findings: none. Every finding of both reviews was fixed.

Known and accepted:

- **AP01's magic rule reaches the master before `spend_luck` exists.** `SPECIAL RULES: AP01
  Fantasy` tells the master to spend Luck per spell; the tool lands in phase 2 part A. Until
  then a game that selects `ap01-fantasy` has a rule the master can read and not execute.
- **Three AP01 gear labels changed apostrophe.** `Seer’s lens`, `Medic’s satchel` and
  `Thieves’ tools` now carry the SRD's curly apostrophe where the hand-written file had a
  straight one. Decision 4 says labels are the SRD's; no shipped character or scenario names
  them; the ids are unchanged.
- The prompt-budget game (two packs, a 48 KB source, 30 cast, 40 chapters) renders to about
  95 KB of the 131,072-byte cap.

## Phase 2: `spend_luck`, the character's own packs, and the other eleven

| count     | before | after  | plan target      |
| --------- | ------ | ------ | ---------------- |
| `src`     | 9,582  | 9,634  | 9,760 to 9,850   |
| `tests`   | 11,668 | 11,815 | 11,720 to 11,820 |
| `qa`      | 2,004  | 2,004  | unchanged        |
| `scripts` | 333    | 396    | about 290        |

`src` stays under its floor by the same margin phase 1 left: the plan's targets carry
`written` and the seam `guidance` that phase 1 cut, and this phase adds the 52 lines it
budgeted. `scripts` lands over because the plan budgeted a cut where the eleven pages needed
six more readings (below), each with its refusal; the reviews then took every cut they found.

Decisions taken off-plan, all from running the converter on the twelve pages before the brief:

1. **`Names.neutral`.** AP02 prints `#### Neutral Names` and no fourth list; the field is data
   the page has, rendered as `neutral: …` like the others. The fourth list (`Nicknames`,
   `Codenames / Call Signs`, `Superhero Names`, `Epithets or Reputation`) is optional.
2. **Eleven monsters-section titles** in one constant, one per page.
3. **The SRD's own typos are read, not bridged.** AP04's `# Locations` at level 1 reads as a
   section whose body still ends at the next `##`; AP09's duplicated, empty `## Adventure Seeds`
   is skipped because `_found` skips any heading with a blank body, and zero seed rows refuse.
4. **Locations may be paragraphs** (AP03), and the encounters line is matched in every spelling
   the pages use, bold and colon placement included, the colon required.
5. **A rules table row keeps its first cell** when the header names it (`Roll`) and drops it for
   `D66` or a blank (a grid row number); the rest join with `, `. AP02's starship trait grids
   and AP03's public-response table reach the master whole; AP01's spell lines are unchanged.
6. **`ui` filters the SRD out through the engine's `supplement_options`**, not `SRD_PACK`: the
   package boundary test forbids `ui` importing `engines`, which the plan's step overlooked.
7. **Only character catalog entries carry `packs`.** The scenario page reads the character's;
   a scenario entry's would have had no reader before phase 3's seed button.
8. **`docs/LONER-3E.md` was part B's alone**, "The tools" line included, so no file had two
   implementers.

Refuted findings: none. Every finding of both reviews (two Opus reviewers; no `codex` on the
machine) was fixed: the encounters colon made required, the empty rule-table row skipped, the
duplicated form state dropped, the dead scenario `packs` dropped, the twelve asserted, the
prompt-budget test reading the engine's directory and `MAX_SUPPLEMENTS`, the docs naming the
markdown source, and the cuts above.

Known and accepted:

- **The prompt budget with the two largest packs** (`ap05-mystery`, `ap12-cyberpunk`) renders
  to 110,529 bytes of the 131,072-byte cap, about 20 KB of headroom, down from 95 KB with AP01.
- **AP01 alone sets `spends_luck`.** No other page prices anything in Luck.
- **The licence question stays open** for all twelve pages, as the docs say.

## Phase 3: packs on the seam, and packs the player owns

| count     | before | after  | plan target      |
| --------- | ------ | ------ | ---------------- |
| `src`     | 9,634  | 9,869  | 10,030 to 10,190 |
| `tests`   | 11,815 | 11,990 | 11,900 to 12,060 |
| `qa`      | 2,004  | 2,005  | unchanged        |
| `scripts` | 396    | 396    | unchanged        |

`src` lands under its floor for the reason phases 1 and 2 did, plus the cuts below: the plan's
target carries `PackStore`, `install_pack`, `check_addable` and `installing`, all deferred.

Decisions taken off-plan:

1. **Nothing writes a pack in this phase.** `PackStore`, `Engine.install_pack`,
   `PackSet.check_addable` and `PackSet.installing` had no production caller before phase 4's
   `new_pack`, the same cut phase 1 made; phase 4 part A adds them with that caller. Phase 3
   reads `packs/<engine>/` at start and lists it.
2. **One SRD override point.** `Engine.pack_ids(supplements)` returns the ids a creation pick
   selects; `SceneEngine` prepends `srd` there. `select_packs`, `chosen_packs`, `picked_packs`
   (the `supplements` pick to a selection, the one spelling for all three `build_character`s),
   `admit`, `guidance`, `supplement_options` and `supplement_steps` are concrete on the seam.
3. **`admit` runs in `Engine.begin`.** Both reviews found the seam's `admit` dead for the room
   family: the launcher pairs any saved character with any scenario through `begin`, and only
   `SceneEngine.new_game` called it. It now runs once, on the seam, before the game is parsed.
4. **`rules_sections` renders on `SceneEngine.master_sections`**, not on Loner alone, so a
   written 24XX pack's special rules reach its master. Same position; no golden moved.
5. **`seeds` lives on `PackSet`** beside `chosen`, `guidance` and `rules_sections`; the page
   reads `engine.packs.seeds(...)`. `PackSet.guidance` takes an optional selection again: a
   room game's `None` is a real caller now (phase 1 decision 4, re-opened as it foresaw).
6. **`PackSet.installed` is a field computed once** in `__post_init__` from `shipped` and
   `written`, so `select` and `chosen` read it with no local alias and no rebuild per id.
7. **`TunnelGoonsPack.items` is `tuple[str, ...]`**: nothing read an id or a detail.
8. **The supplements step is labelled "Packs"** (`SUPPLEMENTS_LABEL` on the seam; the literal
   on the scenario page, which may not import engines). "Table sets beyond the SRD" was wrong
   the moment Tunnel Goons, which has no SRD pack, could offer the step. `qa/s_create.py`
   follows.
9. **`PackEntry` has no `engine` field**; `rules` carries the engine's title, and nothing else
   read it before phase 4's View/Edit buttons.
10. **24XX's `counts` leave out `skills`**: a supplement's skills are never offered, so the home
    page does not count them.
11. **Two helpers in `engines/packs.py`** with three users each: `block_line` (Loner and 24XX
    cast blocks) and `bullets` (nine `- line` sections). Byte-identical output.
12. **A `Refusal` is never raised to be caught four lines below.** `read_packs` logs a written
    file that shadows a shipped id with an `if`, and reserves `try` for the parse.

Refuted findings: none. Every finding of both reviews (two Opus reviewers; no `codex` on the
machine) was fixed, including the cuts: `sheet_character`'s dead `packs` default, the duplicate
construction test in `tests/engines/test_seam.py`, and `SceneEngine.admit` binding the required
selection once.

Known and accepted:

- **Only the two named goldens moved**: `prompts/twentyfourxx/worldsmith.txt` now carries
  `PACK: Core tables` with `SPECIALTIES` and `ORIGINS`; `prompts/tunnelgoons/worldsmith.txt`
  the one new `AUTHORING` sentence. Every other golden is byte-identical.
- **Tests build every engine on a directory that never exists** (`tests/no-packs`), so a
  developer's own `packs/` never reaches the suite.
- **`tests/app/test_game_service.py` changed beyond part B's file list**: its engine subclass
  needed the `written` argument; nothing else moved there.
