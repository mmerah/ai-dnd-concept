# PLAN: whole packs, twelve of them, and packs the player writes

A pack today is the least valuable third of an SRD adventure pack: four trait tables, bare
labels, dumped into the worldsmith prompt as JSON. The SRD page it came from is a whole genre
kit: setting prose, four trait tables, names and nicknames, a special rule, six factions, six
NPCs, six monsters, six locations and 36 adventure seeds. This plan makes the repo's pack that
whole kit, ships all twelve Loner packs from a converter over the SRD's own markdown, gives 24XX
and Tunnel Goons the same pack shape, lets the worldsmith write a pack from a premise or a
document, and lets the player edit the packs they wrote.

Decided on 2026-09-17 and not re-opened by any phase:

- A pack is the whole SRD kit (decision 1). Its special rules reach the master as prose; the one
  mechanic a shipped pack needs, AP01's magic that spends Luck, is one Loner tool, `spend_luck`
  (2). All twelve packs ship, from a checked-in converter over
  `github.com/zotiquestgames/lonersrd` `content/adventure_packs/APnn_*.md` (3). Trait labels
  stay bare as the SRD prints them; no model pass writes 144 details per pack (4).
- Authoring is a `/pack` page: rules, name, premise, a document upload, an optional licence line.
  The worldsmith answers in two typed sections, head then body; nothing is written to disk until
  both pass. Code makes every id (5). Packs the player writes live in a gitignored `packs/` at
  the repository root, `packs/<engine>/<id>.json`, never under `src` (5).
- Loner, 24XX and Tunnel Goons all take packs (6, 7, 8). The setting kit is one base model for
  all three; each engine adds its creation tables and its own cast block type (7). Tunnel Goons
  has no SRD pack and no shipped pack: an empty selection is `packs: None`, as today (8).
- The editor is one page per written pack, one field per section: tables one entry per line,
  cast blocks as `Key: value` lines, prose as textareas. Save parses, refuses with the line, and
  hot-installs. A shipped pack opens read-only. The home page lists packs per engine (9).
- The worldsmith reads setting, names, cast blocks and locations every time, seeds at the opening
  only, trait labels only and never their details; the master reads the rules prose and the
  glossary (10). Two packs plus a 48 KB source sit near the 131,072-byte argv cap, so the
  rendering rule is a constraint, not a preference, and a game plays the SRD and at most two
  supplements.

Not in this plan: twist-table authoring (the SRD's own 12 cells stay on `srd.json`); runtime
fetch of the SRD site; pack versioning or save migration (a missing pack leaves its saves
unresumable, as a missing scenario does); a delete button (the file is the player's); shipped
24XX or Tunnel Goons packs (neither SRD publishes any); a typed spell table (one pack has one,
and `spend_luck` takes an amount); a seed picker as a select (a "Roll a seed" button does the
same with no list).

Measured before any step: `src` **9,464** Python lines, `tests` **11,406**, `qa` **2,004**, at
`b40e50a`. Every anchor below is as of that commit. An SRD pack page is about 26 KB of markdown
(AP01 26,805 bytes, AP12 26,495, AP06 24,089); the AP01 sections weigh roughly: setting 1.7 KB,
traits 6.9 KB (2.5 KB as labels alone), names 1.3 KB, rules with spells 4.3 KB, cast 7.5 KB,
locations 2.6 KB, seeds 3.8 KB. In play a pack renders to about 15 KB; with the SRD pack, a
48 KB source, the role text, the schema and a long history the worldsmith prompt holds two
supplements and not three, which is where the cap of two comes from. Line targets below are
estimates for additive work, given as a range; a phase that lands outside its range by more than
20% stops and says why. The plan was reviewed adversarially once before phase 1; the shapes and
the phase split below are the reviewed ones.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each is one action on the files it names. Every `file.py:line` anchor
   is as of `b40e50a`; where an earlier step moved the code, find the named symbol and ignore
   the number.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted
   behaviour is deleted with it.
3. Count lines at the start and end of each phase and write both in `PROGRESS.md`, one entry per
   phase:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   find scripts -name '*.py' | xargs cat | wc -l
   ```
4. Every line target is a count after `uv run ruff format`.
5. Golden files live in `tests/core/fixtures/`. Exactly these are regenerated, each once, in the
   phase named, and read by a human before they are staged: phase 2,
   `prompts/loner3e/worldsmith.txt` (the pack renders as sections); phase 3,
   `schemas/loner3e/master_tools.json` (`spend_luck` joins the tools); phase 5,
   `prompts/twentyfourxx/worldsmith.txt` and `prompts/tunnelgoons/worldsmith.txt` (the packs
   reach both). Phase 1 leaves every golden byte-identical, which is its proof that the
   `srd`-only prompt did not move. A changed golden anywhere else is a bug in the step that
   changed it.
6. One commit per phase, full check green, reviewed adversarially against the staged diff first.
   Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the
   staged tree. `ruff format` also formats the Python fences in this file, so run
   `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of every
   phase: `uv run aidm`, open each shipped scenario, take a turn.
7. Delete, do not preserve. No compatibility path reads an old pack, scenario or character file.
   The three shipped scenarios and `characters/kael` are re-checked at the end of phase 1 and
   phase 5; a file the new shape refuses is rewritten by hand in that phase, never bridged.
8. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles,
   and no family imports a sibling family. No `Any` beyond the `Game[P]` bound and, from phase 5,
   the `Pack` bound of `AnyEngine`, which is `Any` for the same reason: `PackSet[K]` is
   invariant. Every `__init__.py` stays empty. Tests never start a process and never reach the
   network; the converter is run by hand and tested on a checked-in fixture. `Refusal` stays the
   one message-bearing exception. Only code changes state or rolls dice. The narrator reads
   revealed facts only. Module layout is imports, constants, classes, public functions, private
   functions. A comment is one line, only where the reason is not visible in the code.
9. Names shown to a role or the player are `id`, `label`, `detail`; a pack file keeps `name`.
   A cast block's `name` is the SRD's, and it is data the worldsmith copies, so it stays `name`.

## The shapes, once

Every phase refers to these. A phase that needs to change one says so in its own steps.

`src/aidm/engines/packs.py`, new in phase 1, family-neutral, imported by both families:

```python
MAX_SUPPLEMENTS = 2  # two packs in play beside the source fill the worldsmith's command line


class Names(Frozen):
    female: tuple[str, ...] = ()
    male: tuple[str, ...] = ()
    surnames: tuple[str, ...] = ()
    nicknames: tuple[str, ...] = ()


class Location(Frozen):
    label: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    encounters: str = ""  # the SRD's "Possible encounters" line, names the worldsmith may use


class Pack(Frozen):
    """The setting kit every engine's pack carries; an engine adds its tables and its cast."""

    name: str = Field(min_length=1)
    source: str
    license: str
    setting: str = ""
    names: Names = Names()
    rules: str = ""  # special rules as prose, read by the master alone
    locations: tuple[Location, ...] = ()
    seeds: tuple[str, ...] = ()

    def defined_ids(self) -> tuple[Slug, ...]:
        """The option ids this pack defines; two selected packs may not share one."""
        return ()

    def kit_sections(self, *, opening: bool) -> Sections:
        """Setting, names and locations always; seeds only when the opening is written."""

    def sections(self, *, opening: bool) -> Sections:
        """`kit_sections` plus the engine's own; the worldsmith reads this, never a JSON dump."""
        return self.kit_sections(opening=opening)


@dataclass(frozen=True, slots=True)
class PackSet[K: Pack]:
    engine: EngineId
    shipped: Mapping[Slug, K]
    written: Mapping[Slug, K]  # the player's, from `packs/<engine>/`; never shadows a shipped id

    @property
    def installed(self) -> Mapping[Slug, K]: ...  # shipped then written
    def srd(self) -> K: ...  # `ValueError(f"the {engine!r} engine ships no 'srd' pack")` on a miss
    def require(self, selection: PackSelection | None) -> PackSelection: ...  # as today
    def supplements(self) -> tuple[tuple[Slug, K], ...]: ...  # every installed pack but `srd`
    def chosen(self, selection: PackSelection | None) -> tuple[K, ...]: ...  # `()` for None
    def select(self, selection: PackSelection) -> PackSelection: ...
    def check_addable(self, pack_id: Slug, pack: K) -> None: ...  # trial-select beside `srd` if any
    def installing(
        self, pack_id: Slug, pack: K
    ) -> "PackSet[K]": ...  # a new set, `written` updated
    def guidance(self, selection: PackSelection | None, *, opening: bool) -> str: ...
    def rules_sections(self, selection: PackSelection | None) -> Sections: ...  # for the master


def read_packs[P: Pack](
    engine: EngineId, shipped: Path, written: Path | None, model: type[P]
) -> PackSet[P]:
    """`written` None or missing is empty; a written file that fails to parse is logged and skipped."""
```

`select` refuses an uninstalled id, two selected packs defining one id, and more than
`MAX_SUPPLEMENTS` ids beyond `srd` ("a game plays at most two packs beside the SRD"); it no
longer requires `srd`. `SceneEngine` alone requires `srd`, in `__init__` and `validate`.
`PackSet.guidance` renders `sections(opening=...)` of every chosen pack under `PACK: <name>`,
never `json.dumps`, and is `""` for `None`. `rules_sections` is one `("SPECIAL RULES: <name>",
rules)` per chosen pack whose `rules` is not empty.

`src/aidm/engines/seam.py`, phase 1: `Engine.authoring: str` is declared beside `title`, each
engine's `AUTHORING` constant; `guidance(self, selection, /, *, opening: bool) -> str` becomes
concrete on the seam, `f"{self.authoring}\n\n{self.packs.guidance(selection, opening=opening)}"`
with the trailing blank dropped when the pack text is empty. `SceneEngine.guidance` overrides only
to `require(selection)` first. The three engines' own `guidance` methods go.

`src/aidm/engines/loner3e/worldsmith.py`, phase 1:

```python
class Loner3eBlock(Frozen):
    """A faction, an NPC or a monster as the SRD prints it; the worldsmith copies it into cast."""

    name: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    skills: tuple[str, ...] = Field(min_length=1)
    frailties: tuple[str, ...] = Field(min_length=1)
    gear: tuple[str, ...] = ()
    goal: str = ""
    motive: str = ""
    nemesis: str = ""


class Loner3ePack(Pack):
    concepts: tuple[DecisionOption, ...] = Field(min_length=1)
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    frailties: tuple[DecisionOption, ...] = Field(min_length=1)
    gear: tuple[DecisionOption, ...] = Field(min_length=1)
    spends_luck: bool = False  # AP01: `rules` spends Luck, so `spend_luck` is allowed
    factions: tuple[Loner3eBlock, ...] = ()
    npcs: tuple[Loner3eBlock, ...] = ()
    monsters: tuple[Loner3eBlock, ...] = ()
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None
```

Its `sections` adds `TRAIT TAGS` (four lines of labels joined by `, `, no details) and one
section each for `FACTIONS`, `PEOPLE` and `MONSTERS` (blocks as `name — concept; skills: …;
frailties: …; gear: …; goal: …; motive: …; nemesis: …`, empty fields dropped). The master reads
`rules` through `rules_sections`, never the worldsmith.

`src/aidm/engines/twentyfourxx/worldsmith.py`, phase 5:

```python
class TwentyfourxxBlock(Frozen):
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    skills: tuple[str, ...] = Field(min_length=1)
    items: tuple[str, ...] = ()
    hindrances: tuple[str, ...] = ()


class TwentyfourxxPack(Pack):
    skills: tuple[DecisionOption, ...] = ()  # the SRD's seventeen; a supplement adds none
    specialties: tuple[Specialty, ...] = ()
    origins: tuple[Origin, ...] = ()
    starting_kit: tuple[Kit, ...] = ()
    factions: tuple[TwentyfourxxBlock, ...] = ()
    npcs: tuple[TwentyfourxxBlock, ...] = ()
    hostiles: tuple[TwentyfourxxBlock, ...] = ()
```

`src/aidm/engines/tunnelgoons/worldsmith.py`, phase 5:

```python
class TunnelGoonsBlock(Frozen):
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    hp: int = Field(ge=1)  # Health and Difficulty Score at once: 8 easy, 10 moderate, 12 hard


class TunnelGoonsPack(Pack):
    items: tuple[DecisionOption, ...] = ()  # names the create page hints with
    factions: tuple[TunnelGoonsBlock, ...] = ()
    npcs: tuple[TunnelGoonsBlock, ...] = ()
    monsters: tuple[TunnelGoonsBlock, ...] = ()
```

Authoring drafts, phase 7, one pair per engine, no `id`, no `name`, no `source`, no `license`:

```python
class Labelled(Frozen):  # engines/packs.py
    label: str = Field(min_length=1, max_length=60)
    detail: str = Field(default="", max_length=200)


class PackHead(Frozen):  # engines/packs.py; an engine subclasses it with its tables
    setting: str = Field(min_length=1)
    names: Names
    rules: str = ""


class PackBody(Frozen):  # engines/packs.py; an engine subclasses it with its blocks
    locations: tuple[Location, ...] = Field(min_length=3, max_length=6)
    seeds: tuple[str, ...] = Field(min_length=6, max_length=36)
```

`Loner3eHead` adds `concepts`, `skills`, `frailties`, `gear: tuple[Labelled, ...]` each
`Field(min_length=6, max_length=36)` and `spends_luck: bool`; `Loner3eBody` adds `factions`,
`npcs`, `monsters: tuple[Loner3eBlock, ...]` each `Field(min_length=1, max_length=6)`. 24XX and
Tunnel Goons follow the same pattern with their own tables and blocks. `Engine.pack_of(head,
body, *, name, source, license) -> K` builds the pack, making ids with `slug(label, taken)`.

## Phase 1: the whole pack

The base pack moves out of `engines/scenes/` and grows the setting kit. Loner's pack takes the
kit, the cast blocks and the magic flag. The worldsmith prompt renders sections, not JSON, and
never more than the cap allows. No pack file changes yet: `srd.json` and `ap01-fantasy.json`
parse as they are, every field new to them defaulted, and every golden stays byte-identical.

Target: `src` about **9,700**, within 9,640 to 9,780 (`engines/packs.py` about 170,
`scenes/packs.py` minus 69, `loner3e/worldsmith.py` plus 80, `seam.py` plus 10, three `guidance`
methods minus 12, `spawn.py` plus 6). `tests` about **11,520**, within 11,470 to 11,580. About
a day.

### Steps

1. Create `src/aidm/engines/packs.py` with `MAX_SUPPLEMENTS`, `Names`, `Location`, `Pack`,
   `PackSet` and `read_packs` as in "The shapes, once". `SRD_PACK: Slug = "srd"` moves here from
   `src/aidm/engines/scenes/packs.py:12`. `read_packs` reads `shipped` then `written`; a written
   file whose parse raises `Refusal`, or whose stem is a shipped id, is logged with
   `LOGGER.warning` and skipped, as `Library.read_scenarios` (`src/aidm/core/io.py:73-87`) skips
   a scenario. `Pack.kit_sections` renders `SETTING`, `NAMES` (four lines, `female: …`,
   `male: …`, `surnames: …`, `nicknames: …`, empty ones dropped), `LOCATIONS` (`- label — detail`
   and `  encounters: …` when given) and, when `opening`, `ADVENTURE SEEDS` (`- seed` lines).
   Delete `src/aidm/engines/scenes/packs.py`. Repoint every importer of `ScenePack`:
   `src/aidm/engines/twentyfourxx/worldsmith.py:8,59` (the class keeps its fields until phase 5;
   only its base changes to `Pack`) and `tests/support/fifth.py:10,37,47`.
2. `src/aidm/engines/scenes/engine.py`: import from `aidm.engines.packs` (`:30`). `__init__`
   (`:91-93`) becomes `self.packs = read_packs(self.id, self.directory / "packs", None, self.pack)`
   followed by `self.packs.srd()`, which raises `ValueError` when no shipped `srd` exists (the
   check `read_packs` made at `scenes/packs.py:66-67`). `validate` (`:106-108`) adds
   `if SRD_PACK not in selection.ids: raise Refusal(f"a {self.id!r} game plays the {SRD_PACK!r} tables")`,
   the line `select` loses. `chosen_packs` (`:110-114`) stays. `render_next` (`:245`) passes
   `opening=False`, `author` (`:281`) `opening=True`; `RoomEngine.author`
   (`src/aidm/engines/rooms/engine.py:176`) and `write_next` (`:226`) pass the same two, still
   with `None`. Move the pack tests now, not later: `tests/engines/test_scenes.py:238-271`
   become `tests/engines/test_packs.py`; the `select` case at `:260-263` asserts the refusal
   comes from `SceneEngine.validate` on a state instead, the `PackSet(...)` construction at
   `:268` takes the three fields, and one new case: a selection of three supplements is refused
   naming the cap.
3. `src/aidm/engines/seam.py`: declare `authoring: str` at `:63-80`; `guidance` (`:363`) becomes
   the concrete method in the shapes. `src/aidm/engines/loner3e/engine.py`: `authoring = AUTHORING`
   beside `title` (`:62`), delete `guidance` (`:143-145`), `_revised` (`:260-262`) and the
   `JsonValue` import. `src/aidm/engines/twentyfourxx/engine.py`: `authoring = AUTHORING`,
   delete `guidance` (`:254-256`). `src/aidm/engines/tunnelgoons/engine.py`:
   `authoring = AUTHORING`, delete `guidance` (`:78-79`). `SceneEngine.guidance` overrides to
   `require` then `super()`.
4. `src/aidm/engines/loner3e/worldsmith.py`: `Pack` (`:30-50`) becomes `Loner3ePack` as in the
   shapes, with `Loner3eBlock` above it; `defined_ids` stays; `_twist_columns_pair_up` stays.
   Add `Loner3ePack.sections(*, opening)` as described in the shapes. Rename every use:
   `loner3e/engine.py:44,60,68`, `tests/support/`, `tests/loner3e/`.
5. `src/aidm/engines/loner3e/engine.py` `master_sections` (`:147-163`) adds, before the
   glossary, `*self.packs.rules_sections(state.packs)`.
6. `AUTHORING` (`loner3e/worldsmith.py:10-27`) gains two sentences at the end: the packs'
   factions, people and monsters are written to be used; file one into `cast` under a new id with
   its tags and drives copied and a `brief` for this scene, and size its luck by the rule above.
   Names come from the pack's name lists when the setting has them. The `loner3e` worldsmith
   golden holds `LONER 3E AUTHORING`, so this sentence lands in phase 2 with the regeneration,
   not here: write it in phase 2 step 6.
7. `src/aidm/app/spawn.py`: `PROMPT_MAX_BYTES = 131_072` after `KEPT_ENV` (`:26`), with the
   one-line reason (Linux `MAX_ARG_STRLEN`: one argv element). `run_cli` (`:162`) refuses before
   `_spawn` when `len(prompt.encode()) >= PROMPT_MAX_BYTES`:
   `Refusal(f"the {role} prompt is {size} bytes; the command line takes fewer than {PROMPT_MAX_BYTES}")`.
   An `E2BIG` `OSError` was a bug; now it is a message the player reads. One test in
   `tests/app/` with a `Driver` stub: a prompt of the cap is refused before any command is built.
8. Tests: `tests/engines/test_packs.py` also covers `kit_sections` (seeds present at the opening,
   absent in play; empty name lists dropped) and `read_packs` skipping a written file that
   fails to parse and one whose stem is a shipped id, each with a warning. Full check; every
   golden unchanged. `PROGRESS.md` entry with all four counts.

## Phase 2: the converter, and AP01 complete

A script turns the SRD's markdown into a whole pack. AP01 is the first, and the ids of its four
trait tables do not move.

Target: `src` within 20 lines of phase 1's count. `tests` about **11,640**, within 11,590 to
11,700. `scripts` about **260**. About half a day.

### Steps

1. The converter, `scripts/srd_packs.py`, a module with a `main()`, outside `src`: given one or
   more `APnn_<name>.md` paths, it writes `src/aidm/engines/loner3e/packs/apnn-<name>.json`
   (stem from the file: `AP01_fantasy` to `ap01-fantasy`). Every heading is matched after
   stripping surrounding `**` and trailing spaces (AP06 writes `### **Concepts**`, AP01
   `### King Vaelor the Thornbound  `). It parses:
   - `## Setting Information` paragraphs to `setting`, markdown bold kept.
   - `### Concepts|Skills|Frailties|Gear`: each is a 6×6 grid, a pipe table with a row header
     `1`–`6` and six columns `1`–`6`; entries are read row-major, so d66 `11` is row 1 column 1
     and `36` is row 3 column 6. Each becomes `DecisionOption(id=slug(folded, taken), label,
     detail="")` where `folded` is the label NFKD-normalised with combining marks dropped, so
     `Naïve` makes `naive` as `ap01-fantasy.json:526` has it, not `na-ve`.
   - `#### Female Names|Male Names|Surnames` and the fourth list, `### Nicknames` (AP01),
     `#### Nicknames` (AP12) or `#### Codenames / Call Signs` (AP06), the same 6×6 grids, to
     `names`.
   - Every `## Special Rule*` section, its `###` subsections and tables included, to `rules` as
     plain text: a subsection heading becomes a `Heading:` line, a `| D66 | Spell |` row becomes
     `- **Heal** (1 Luck) – …` with the number dropped, a bullet list stays a bullet list, bold
     kept. `spends_luck` is true when `rules` contains `Luck cost`.
   - `## Factions`, `## NPCs`, and `## Monsters` | `## Hostile Entities` | `## Creatures`
     (AP01, AP12, AP06) `###` entries to blocks. A field line is `- **Key:** value` (AP01) or
     `* **Key**: value` (AP12) or `- **Key**: value` (AP06): match
     `^[-*]\s+\*\*(Key)\*\*:?\s*:?\s*(.*)$` with the key one of Concept, Skills, Frailty,
     Frailties, Gear, Goal, Motive, Nemesis; `Skills`, `Frailty` and `Gear` split on `, `;
     a missing optional key is the model's default and a missing required one stops the script
     naming the block.
   - `## Locations` `###` entries: bullet paragraphs joined by a space to `detail`, the bullet
     starting `Possible encounters:` to `encounters` with the prefix dropped.
   - `## Adventure Seeds` `| D66 | Adventure |` rows to `seeds`.
   `name` is `APnn <Title>` where the title is the `# ` heading minus ` Adventure Pack`, so
   `AP01 Fantasy` stays what `ap01-fantasy.json:2` and the supplements select show today.
   `source` is `https://lonersrd.zotiquestgames.com/adventure_packs/<original stem>.html`,
   `AP01_fantasy` and not `ap01-fantasy`. `license` is the line `ap01-fantasy.json:4` carries,
   the pack title substituted. The output goes through `parse(Loner3ePack, …)` before it is
   written, so a shape error stops the script. Every list keeps the SRD's order; the JSON is
   `indent=2`, keys in model order, so a second run is byte-identical.
2. `pyproject.toml:43-44,47`: add `"scripts"` to pytest `pythonpath` and to basedpyright
   `include`, so the converter is type-checked and importable by its test. Not to `testpaths`.
3. Run the converter on AP01 and replace `src/aidm/engines/loner3e/packs/ap01-fantasy.json`. The
   four trait tables' ids must equal today's, `naive` included, since `characters/` store labels
   and saves store pack ids, not entry ids; `git diff` of the file shows the four tables changed
   in nothing but whitespace, and the new sections added.
4. Fixture and test: copy `AP01_fantasy.md` to `tests/fixtures/srd/AP01_fantasy.md` (CC BY-SA
   4.0, attributed in `docs/LONER-3E.md`). `tests/scripts/test_srd_packs.py` runs the converter's
   parse function on the fixture and asserts 36 entries in each trait table and each name list,
   6 factions, 6 NPCs, 6 monsters, 6 locations, 36 seeds, `spends_luck`, `Naïve` at id `naive`,
   and that converting twice gives equal JSON.
5. Prompt budget test, `tests/loner3e/test_prompt_budget.py`: build a `Loner3eGame` from
   `whispering-vault` with `packs = (srd, ap01-fantasy)`, a `source` of 48,000 bytes, a cast of
   30 members, and a log of 40 chapters whose last two hold 20 exchanges each of 400-character
   transcripts and the rest a recap, then assert
   `len(ENGINE.render_next(state, "…").encode()) < PROMPT_MAX_BYTES`. When phase 4 lands the
   other eleven, the test picks the two largest pack files instead of naming AP01.
6. `AUTHORING` gains the two sentences phase 1 step 6 deferred. Regenerate
   `tests/core/fixtures/prompts/loner3e/worldsmith.txt`, read it, and confirm it shows
   `PACK: Starter tables` sections and no JSON.
7. `docs/LONER-3E.md` "Pack sources" (`:39-50`): the converter and its command, the fixture's
   attribution, and one line saying the four trait tables' ids are stable across runs and that
   `Naïve` folds to `naive`. Deviation 6: trait labels are the SRD's, bare; the glossary lists
   only entries with a detail. `README.md:54`: a pack is the whole SRD kit, one sentence.
8. Full check. `PROGRESS.md` entry.

## Phase 3: `spend_luck`, and the pack the character already chose

Two small things the whole pack now allows. About half a day.

Target: `src` about **9,780**, within 9,740 to 9,830. `tests` about **11,720**, within 11,680
to 11,780.

### Steps

1. `src/aidm/engines/loner3e/tools.py`: `SPEND_LUCK = "A character here spends luck on a cost the
   selected pack's SPECIAL RULES name, such as a spell."` and
   `class SpendLuck(Frozen): entity_id: Slug; amount: int = Field(ge=1); why: str = Field(min_length=1)`,
   with descriptions in the file's own voice.
2. `src/aidm/engines/loner3e/world.py`: `Loner3eCast.spend_luck(self, amount, why) -> list[Fact]`
   after `refill` (`:108`): refuses when `defeated` ("… lost their last conflict; nothing to
   spend") and when `amount > luck.current` ("… has {current} luck, not {amount}"); otherwise
   `self.change(self.luck, -amount, "Luck", why)`. Reaching 0 is allowed and marks no defeat: the
   next `strike` settles it.
3. `src/aidm/engines/loner3e/engine.py`: `master_tools` (`:79-86`) adds
   `master_tool("spend_luck", SPEND_LUCK, SpendLuck, self.spend_luck)`. `spend_luck(draft, args,
   _rng)`: refuse unless some chosen pack has `spends_luck` ("no selected pack spends luck"),
   `world.check_unnamed(args.why)`, `require_living_here`, then the cast method. Regenerate
   `tests/core/fixtures/schemas/loner3e/master_tools.json` and read the new entry.
   `docs/LONER-3E.md` "The tools" adds the line.
4. `src/aidm/engines/loner3e/rules.md`: under "Tags and drives" one paragraph: when SPECIAL
   RULES price something in luck, call `spend_luck` with the printed cost before the `roll`
   that decides it, and read the roll as those rules say.
5. Supplements default to the character's. `src/aidm/core/model.py` `CharacterHeader` (`:52-54`)
   gains `packs: PackSelection | None = None`; `src/aidm/app/launch.py` `CatalogEntry` (`:15-22`)
   gains `packs: tuple[Slug, ...] = ()`, filled at `:86-96` from the header. In
   `src/aidm/ui/create.py` `ScenarioForm.character_fields` (`:243-262`), the character select's
   `on_change` sets `self.supplements.value` to that character's packs minus `srd`; the first
   render does the same for the preselected character. A test in the create-page test file:
   picking a character made with `ap01-fantasy` selects it.
6. Tests: `spend_luck` refuses without the flag, refuses past the pool, and lands a `Luck -2`
   fact with the flag; the tool schema golden shows it. Full check. `PROGRESS.md` entry.

## Phase 4: the other eleven packs

The converter runs on AP02 through AP12. Where a page differs from the three already read, the
converter grows; where the SRD's own text is broken, the page wins and the difference is
recorded.

Target: `src` about **9,800**, within 9,770 to 9,840; `scripts` about 290; eleven new JSON files
under `src/aidm/engines/loner3e/packs/`. About two hours plus review.

### Steps

1. Download the eleven markdown files by hand (`curl` of the raw GitHub URLs; not in a test) to a
   scratch directory and run the converter on all twelve. Read every refusal it raises. The
   differences phase 2 already handles are the bold-wrapped headings, the three monster section
   names, the three field-line spellings and the three fourth-name-list headings; a page that
   differs beyond these grows the converter in one place and adds one line to the fixture test.
2. Every trait table across the twelve is checked for `defined_ids` collisions against `srd`:
   `PackSet.select` refuses a shared id, so a pack that shares one with `srd.json` cannot be
   selected at all. The repo's `srd.json` tables were written to avoid the AP01 words; check the
   other eleven with a one-off loop over `Loner3ePack.defined_ids()` and rename the `srd.json`
   entry, never the SRD's, where one collides. Two supplements may legitimately collide with
   each other; that is the existing rule and the refusal names both.
3. `src/aidm/core/creation.py:43`: `ANSWER_MAX` applies per part of a `multiple` step, not to
   the joined string, so two long pack ids never read as "takes at most 100 characters"; the cap
   on packs is `select`'s and says so. One test in `tests/core/`.
4. `tests/scripts/test_srd_packs.py` gains one test over the shipped JSON, not the network:
   every `loner3e/packs/ap*.json` parses as `Loner3ePack`, has 36 entries in each trait table
   and 6 blocks in each of the three cast lists, and no two of them share an id with `srd`.
5. `docs/LONER-3E.md`: the twelve packs listed with their page URLs; the open licence question
   stays open with the note that the site index declares CC BY-SA 4.0 and every page carries only
   the copyright footer. `README.md`: "twelve adventure packs" where it says one.
6. The prompt budget test of phase 2 now picks the two largest pack files. If it fails, the fix is
   in `kit_sections` (drop `encounters` in play, then shorten block rendering), never in the cap.
7. Full check. `PROGRESS.md` entry.

## Phase 5: packs on the seam, for 24XX and Tunnel Goons

The pack set moves from the scene family to the engine seam, so a room engine has one. 24XX's
pack becomes a supplement shape with the seventeen skills required of `srd` alone. Tunnel Goons
gets a pack model with no shipped pack and no `srd`. A "Roll a seed" button on the scenario page
reads the chosen packs. This is the phase that touches every engine; it is reviewed hardest.

Target: `src` about **10,000**, within 9,930 to 10,090. `tests` about **11,900**, within 11,820
to 12,000. About a day.

### Steps

1. `src/aidm/engines/seam.py`: `Engine[P, M, G]` becomes `Engine[P, M, G, K: Pack]` with
   `pack: type[K]` and `packs: PackSet[K]` declared at `:63-80`; `AnyEngine` (`:48`) becomes
   `Engine[Any, Any, Any, Any]`, the fourth for the invariance reason "How to work" 8 records.
   `__init__` (`:82-95`) reads `self.packs = read_packs(self.id, self.directory / "packs", None,
   self.pack)` before the tools. `supplement_options` (`:154`), `select_packs` (`:157`),
   `admit` (`:160`), `chosen_packs`, `supplement_steps` and `SUPPLEMENTS` move up from
   `src/aidm/engines/scenes/engine.py:47,98-124,222-233`. On the seam: `select_packs(supplements)`
   returns `None` for an empty sequence, else `self.packs.select(parse(PackSelection, {"ids": tuple(supplements)}))`;
   `chosen_packs(picks)` reads the picked supplements alone; `admit(packs, character)` refuses
   unless `set(character.packs.ids if character.packs else ()) <= set(packs.ids if packs else ())`,
   with the existing message; `validate` (`:325`) adds `if state.packs is not None:
   self.packs.select(state.packs)`. `SceneEngine` overrides `select_packs` and `chosen_packs` to
   prepend `SRD_PACK` (`Loner3eEngine.creation_steps`, `loner3e/engine.py:89-93`, pools its
   tables from that result) and `admit` to `require` first, and keeps the `srd`-in-selection
   check in its `validate`. `RoomEngine.validate` (`rooms/engine.py:67-70`) loses its "plays no
   table set" refusal. `RoomEngine.author` (`:176`) passes `self.guidance(packs, opening=True)`
   and `write_next` (`:226`) `self.guidance(draft.packs, opening=False)`, in place of `None`.
2. `TunnelGoonsEngine.creation_steps` (`src/aidm/engines/tunnelgoons/engine.py:102-118`) starts
   with `*self.supplement_steps()` and the item hint joins `STARTING_ITEM_LIST` with the chosen
   packs' `items` labels; `build_character` (`:120-135`) passes
   `self.select_packs(picked_many(picks, SUPPLEMENTS))` to `sheet_character`. A character made
   with no pack stores `packs: None`, as today.
3. `src/aidm/engines/tunnelgoons/worldsmith.py`: `TunnelGoonsBlock` and `TunnelGoonsPack` as in
   the shapes, `sections` adding `ITEMS`, `FACTIONS`, `PEOPLE`, `MONSTERS` (`- name — brief
   (hp N)`). `AUTHORING` gains one sentence: a pack's monster is written as an npc with that
   `hp`. `RoomEngine.master_sections` (`rooms/engine.py:93-107`) adds
   `*self.packs.rules_sections(state.packs)` after `WAYS OUT`. Regenerate
   `tests/core/fixtures/prompts/tunnelgoons/worldsmith.txt` once and read it.
4. `src/aidm/engines/twentyfourxx/worldsmith.py`: `Pack` (`:59-77`) becomes `TwentyfourxxPack` as
   in the shapes, `skills` no longer `min_length=17, max_length=17`; `_every_pick_told` stays.
   `TwentyfourxxEngine.__init__` checks `len(self.packs.srd().skills) == 17` and that
   `starting_kit` is not empty, raising `ValueError` otherwise, the check the model made.
   `sections` adds `SPECIALTIES` (`specialty_lines()`), `ORIGINS` (label — detail) and the three
   block sections. `write_sheet` (`:107-125`) keeps its own specialty lines. Regenerate
   `tests/core/fixtures/prompts/twentyfourxx/worldsmith.txt` once and read it.
5. `Engine.seeds(self, selection: PackSelection | None) -> tuple[str, ...]` on the seam, the
   chosen packs' seeds in order. `src/aidm/ui/create.py` `ScenarioForm.character_fields`
   (`:243-262`): under the supplements select, a "Roll a seed" button, shown when
   `engine.seeds(...)` is not empty for the current supplements, whose click writes one seed
   drawn with `random.choice` into `self.premise.value`. The premise stays editable; the seed is
   a starting point, not stored. The page's own `Random` is fine: it rolls no game die.
6. Tests: `tests/engines/test_packs.py` gains: a room engine accepts `packs: None` and a selection
   of one written pack; a scene engine still refuses a selection without `srd`; a 24XX supplement
   with no `skills` selects; the seam `admit` refuses a character whose packs exceed the
   scenario's and accepts `None` against anything; `seeds` is empty for `None`. Re-check
   `scenarios/buried-keep/world.json` and `characters/kael/tunnelgoons.json` still load.
7. `docs/24XX.md` "Pack sources" and `docs/TUNNEL-GOONS.md` gain a "Packs" paragraph each: what
   a pack holds for this engine, that none ships, and that a written one is selected on the
   character and the scenario like Loner's.
8. Full check. `PROGRESS.md` entry.

## Phase 6: packs the player owns

A `packs/` directory beside `saves/`, read at start, hot-installed after a write, listed on the
home page.

Target: `src` about **10,100**, within 10,050 to 10,170. `tests` about **11,980**, within 11,920
to 12,060. About half a day.

### Steps

1. `.gitignore`: `packs/` under "Play data". `src/aidm/config.py:140-142`:
   `packs_dir: Path = Path("packs")`, the sibling of the three directories there.
2. `src/aidm/core/io.py`: `class PackStore` after `Library` (`:56-140`), `directory: Path`,
   `folder(engine) -> Path` (`directory / engine`), `write(engine, pack_id, pack: BaseModel)`
   through `write_text` (`:165`) with `model_dump_json(indent=2)`; `exists(engine, pack_id)`.
   `core` stays shape-blind: it writes a `BaseModel`.
3. `src/aidm/engines/registry.py` `build_engines(packs_dir: Path) -> dict[...]`: each engine is
   built with `written=packs_dir / engine.id`; `Engine.__init__` takes `written: Path` and hands
   it to `read_packs`. `Runtime.__post_init__` (`src/aidm/app/runtime.py:321-325`) passes
   `settings.packs_dir`. `tests/support/table.py` and every `build_engines()` call pass a
   `tmp_path` or a path that does not exist.
4. `Engine.install_pack(self, pack_id, pack: K) -> None`: `self.packs.check_addable(pack_id, pack)`
   then `self.packs = self.packs.installing(pack_id, pack)`. Reinstalling an existing written id
   replaces it; a shipped id is refused by `check_addable`.
5. Home page. `src/aidm/app/launch.py` `LauncherCatalog` gains
   `packs: tuple[PackEntry, ...]` with `PackEntry(id, engine, label, rules, written: bool, tables: str)`
   where `tables` is a short count line (`36 concepts · 6 factions · 36 seeds` from the pack's
   own fields, rendered by `Pack.summary()` on the base model, engine tables counted by the
   subclass). `src/aidm/ui/app.py` `home_page` (`:87-108`) adds a "Packs" section after
   "Saved games": one row per pack, engine badge, `Written` badge for the player's own. No
   buttons yet; phase 8 adds View and Edit.
6. Test: a written pack file under `tmp_path / "loner3e"` is installed at build and listed;
   a file whose stem is `srd` is skipped with a warning; `install_pack` of a colliding pack is
   refused and leaves the set unchanged; a game whose save names a written pack that was deleted
   is filed under `unresumable` by `LauncherCatalog.read`.
7. Full check. `PROGRESS.md` entry.

## Phase 7: the worldsmith writes a pack

Two typed asks, nothing saved until both pass, one page.

Target: `src` about **10,370**, within 10,290 to 10,470. `tests` about **12,140**, within 12,060
to 12,240. About a day.

### Steps

1. `src/aidm/engines/packs.py`: `Labelled`, `PackHead`, `PackBody` as in the shapes, and
   `HEAD_ASK`, `BODY_ASK` intents: the head asks for the setting, the creation tables as labels
   with a one-line detail where the label does not explain itself, the four name lists, and the
   special rule as prose if the genre has one; the body asks for factions, people and monsters
   written to be met, locations with who is met there, and seeds the player could start from.
   Both say: from SOURCE MATERIAL when one is given, else from the premise; nothing outside it.
2. Per engine: `Loner3eHead`, `Loner3eBody` in `loner3e/worldsmith.py`; `TwentyfourxxHead`
   (specialties, origins), `TwentyfourxxBody`; `TunnelGoonsHead` (items), `TunnelGoonsBody`.
   `Engine.head: type[H]`, `Engine.body: type[B]` declared beside `pack`, and
   `Engine.pack_of(head, body, *, name, source, license) -> K` per engine, making ids with
   `slug(label, taken)` over the pack's own labels (`twentyfourxx/engine.py:528-535`
   `items_from_kits` is the pattern).
3. `Engine.author_pack(self, name, source, license, worldsmith: WorldsmithAnswer) -> K` on the
   seam, concrete: render the head prompt with `render_worldsmith(source, scope="", family=(),
   intent=HEAD_ASK, guidance=self.authoring, answer=self.head)`; `check` builds
   `self.pack_of(head, empty body, …)` and calls `self.packs.check_addable(pack_id, pack)`, so a
   trait id that collides with `srd` is re-prompted with the collision named; then the body prompt
   with the head rendered as family sections (`THE PACK SO FAR`: the head's `sections`), answer
   `self.body`, check by building the whole pack. `scope` is empty for a pack; `render_worldsmith`
   (`seam.py:205-224`) prints `SOURCELESS`-style text for an empty scope rather than a new
   render method.
4. `src/aidm/app/runtime.py` `Runtime.new_pack(engine_id, name, premise, document, license) ->
   Slug`: `given_text` as `new_scenario` (`:357-377`) does; `pack_id = slug(name, installed ids)`;
   `engine.author_pack(...)`; `self.packs.write(engine.id, pack_id, pack)` then
   `engine.install_pack(pack_id, pack)`. `Runtime` gains `packs: PackStore` in `__post_init__`.
   `source` is written by code: `"written in this app from the premise"` or `"… from <file
   name>"`; `license` is the page's field, empty allowed.
5. `src/aidm/ui/create.py` `PackForm`: rules select (`_engine_select`, `:323`), name, premise
   textarea, upload (`ui.upload` as `ScenarioForm.build:213-216`, same `_discard_uploads`),
   licence input, "Write the pack" button with "Writing takes several minutes." A refusal shows
   as `alert`; success notes "Wrote <name>. Pick it on a character and on a scenario." and
   navigates to `/`. `src/aidm/ui/app.py`: `_new_content` (`:129-136`) gains "New pack";
   `_register_pages` (`:185-221`) adds `/pack`.
6. Tests with `ScriptedSpawner`: a scripted head and body produce a pack on disk and in
   `engine.packs.written`; a head whose label slugs to an `srd` id is re-prompted once and the
   second answer lands; a body that fails twice leaves no file and no installed pack.
7. `IDEAS.md` item 13 checked. `README.md`: one paragraph on writing a pack. Full check.
   `PROGRESS.md` entry.

## Phase 8: the editor

One page per written pack, one field per section, text in and a validated pack out.

Target: `src` about **10,650**, within 10,550 to 10,770. `tests` about **12,300**, within 12,220
to 12,400. About a day.

### Steps

1. `src/aidm/engines/packs.py` text formats, free functions since the page and the tests call
   them on their own: `table_text(options) -> str` and `parse_table(text) -> tuple[Labelled, ...]`
   (one entry per line, `Label` or `Label — detail`, em dash only, a blank line skipped, a line
   with two dashes refused as `line N: one " — " at most`); `list_text` / `parse_list` for the
   name lists and seeds (one per line); `blocks_text(blocks, fields) -> str` and
   `parse_blocks(text, model) -> tuple[...]` (blocks separated by a blank line, first line the
   name, then `Key: value` lines with the model's field names title-cased, lists split on `, `;
   a missing required key refused as `block N (<name>): missing Goal`). `parse_*` raise
   `Refusal`. Model validators on `Labelled`, `Location` and each block refuse ` — ` inside a
   label and a newline inside any value, so the round-trip is lossless by construction.
2. Per engine, `Engine.edit_fields(pack) -> tuple[EditField, ...]` and
   `Engine.edited(pack, values: Mapping[str, str]) -> K`, where `EditField(id, label, text,
   rows: int)` is on `engines/packs.py`. The base builds setting, names (four fields), rules,
   locations (blocks with `Detail` and `Encounters`), seeds; each engine adds its tables and its
   block lists. `edited` parses every field, rebuilds the pack through `pack_of`-style id making,
   keeps `name`, `source`, `license`, and `parse`s it.
3. `Runtime.rewrite_pack(engine_id, pack_id, values) -> None`: refuse a shipped id ("shipped
   packs are read-only"), `engine.edited(...)`, `engine.packs.check_addable`, write, install.
4. `src/aidm/ui/create.py` or a new `src/aidm/ui/packs.py` if `create.py` passes 450 lines:
   `PackEditor` page at `/packs/{engine}/{pack}`: header with the pack name, one `ui.textarea` per
   `EditField` (`rows` tall, monospace), Save for a written pack, no Save for a shipped one, a
   refusal shown as `alert` with the line it names. `home_page` "Packs" rows gain View (shipped)
   and Edit (written) buttons that navigate there.
5. Tests: round-trip of every shipped Loner pack through `edit_fields` and `edited` gives an
   equal model; a table line with two dashes is refused naming its line; a block missing a
   required key is refused naming the block; saving a written pack that now collides with `srd`
   is refused and the installed pack is unchanged; a shipped id is refused before parsing.
6. Full check. `PROGRESS.md` entry. `README.md`: one sentence on editing.
