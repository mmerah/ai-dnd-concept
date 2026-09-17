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
  rendering rule is a constraint, not a preference.

Not in this plan: twist-table authoring (the SRD's own 12 cells stay on `srd.json`); runtime
fetch of the SRD site; pack versioning or save migration (a missing pack leaves its saves
unresumable, as a missing scenario does); a delete button (the file is the player's); shipped
24XX or Tunnel Goons packs (neither SRD publishes any); a typed spell table (one pack has one,
and `spend_luck` takes an amount).

Measured before any step: `src` **9,464** Python lines, `tests` **11,406**, `qa` **2,004**, at
`b40e50a`. Every anchor below is as of that commit. An SRD pack page is about 26 KB of markdown
(AP01 26,805 bytes, AP12 26,495, AP06 24,089); the AP01 sections weigh roughly: setting 1.7 KB,
traits 6.9 KB (2.5 KB as labels alone), names 1.3 KB, rules with spells 4.3 KB, cast 7.5 KB,
locations 2.6 KB, seeds 3.8 KB. Line targets below are estimates for additive work, given as a
range; a phase that lands outside its range by more than 20% stops and says why.

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
5. Golden files live in `tests/core/fixtures/`. Phase 1 changes what the worldsmith prompt holds
   for `loner3e`, so `tests/core/fixtures/prompts/loner3e/worldsmith.txt` is regenerated once, in
   phase 1 step 12, and read by a human before it is staged; phase 4 does the same for
   `twentyfourxx`. No other phase regenerates a golden; a changed golden elsewhere is a bug in
   the step that changed it.
6. One commit per phase, full check green, reviewed adversarially against the staged diff first.
   Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the
   staged tree. `ruff format` also formats the Python fences in this file, so run
   `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of every
   phase: `uv run aidm`, open each shipped scenario, take a turn.
7. Delete, do not preserve. No compatibility path reads an old pack, scenario or character file.
   The three shipped scenarios and `characters/kael` are re-checked at the end of phase 1 and
   phase 4; a file the new shape refuses is rewritten by hand in that phase, never bridged.
8. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles,
   and no family imports a sibling family. No `Any` beyond the `Game[P]` bound. Every
   `__init__.py` stays empty. Tests never start a process and never reach the network; the
   converter is run by hand and tested on a checked-in fixture. `Refusal` stays the one
   message-bearing exception. Only code changes state or rolls dice. The narrator reads revealed
   facts only. Module layout is imports, constants, classes, public functions, private functions.
   A comment is one line, only where the reason is not visible in the code.
9. Names shown to a role or the player are `id`, `label`, `detail`; a pack file keeps `name`.
   A cast block's `name` is the SRD's, and it is data the worldsmith copies, so it stays `name`.

## The shapes, once

Every phase refers to these. A phase that needs to change one says so in its own steps.

`src/aidm/engines/packs.py`, new in phase 1, family-neutral, imported by both families:

```python
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
    def supplements(self) -> tuple[tuple[Slug, K], ...]: ...  # every installed pack but `srd`
    def chosen(self, selection: PackSelection | None) -> tuple[K, ...]: ...  # `()` for None
    def select(self, selection: PackSelection) -> PackSelection: ...  # installed, no shared ids
    def check_addable(self, pack_id: Slug, pack: K) -> None: ...  # trial-select beside `srd` if any
    def installing(
        self, pack_id: Slug, pack: K
    ) -> "PackSet[K]": ...  # a new set, `written` updated
    def guidance(self, selection: PackSelection | None, *, opening: bool) -> str: ...


def read_packs[P: Pack](
    engine: EngineId, shipped: Path, written: Path, model: type[P]
) -> PackSet[P]:
    """A missing directory is empty; a written file that fails to parse is logged and skipped."""
```

`select` refuses an uninstalled id and two selected packs defining one id; it no longer requires
`srd`. `SceneEngine` alone requires `srd`, in `__init__` and `validate`. `PackSet.guidance`
renders `sections(opening=...)` of every chosen pack under one heading per pack, never
`json.dumps`.

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
`rules` from `master_sections`, never the worldsmith.

`src/aidm/engines/twentyfourxx/worldsmith.py`, phase 4:

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

`src/aidm/engines/tunnelgoons/worldsmith.py`, phase 4:

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

Authoring drafts, phase 6, one pair per engine, no `id`, no `name`, no `source`, no `license`:

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

## Phase 1: the whole pack, and AP01 complete

The base pack moves out of `engines/scenes/` and grows the setting kit. Loner's pack takes the
kit, the cast blocks and the magic flag. The worldsmith prompt renders sections, not JSON, and
never more than the cap allows. A converter turns the SRD's markdown into `ap01-fantasy.json`,
whole.

Target: `src` about **9,760**, within 9,700 to 9,840 (`engines/packs.py` about 150, `scenes/packs.py`
minus 69, `loner3e/worldsmith.py` plus 90, `loner3e/engine.py` plus 20, `spawn.py` plus 6).
`tests` about **11,620**, within 11,560 to 11,700. `scripts` about **220**. About a day and a
half.

### Steps

1. Create `src/aidm/engines/packs.py` with `Names`, `Location`, `Pack`, `PackSet` and
   `read_packs` as in "The shapes, once". `SRD_PACK: Slug = "srd"` moves here from
   `src/aidm/engines/scenes/packs.py:12`. `read_packs` reads `shipped` then `written`, both
   optional directories; a written file whose parse raises `Refusal`, or whose stem is a shipped
   id, is logged with `LOGGER.warning` and skipped, as `Library.read_scenarios`
   (`src/aidm/core/io.py:73-87`) skips a scenario. `Pack.kit_sections` renders `SETTING`,
   `NAMES` (four lines, `female: …`, `male: …`, `surnames: …`, `nicknames: …`, empty ones
   dropped), `LOCATIONS` (`- label — detail` and `  encounters: …` when given) and, when
   `opening`, `ADVENTURE SEEDS` (`- seed` lines). `PackSet.guidance` joins each chosen pack's
   `sections` under `PACK: <name>`. Delete `src/aidm/engines/scenes/packs.py`.
2. `src/aidm/engines/scenes/engine.py`: import from `aidm.engines.packs` (`:30`). `__init__`
   (`:91-93`) becomes `self.packs = read_packs(self.id, self.directory / "packs", Path(), self.pack)`
   and then `self.packs.srd()`, which raises `ValueError` when no shipped `srd` exists (the
   check `read_packs` used to make, `scenes/packs.py:66-67`). `validate` (`:106-108`) adds
   `if SRD_PACK not in selection.ids: raise Refusal(f"a {self.id!r} game plays the {SRD_PACK!r} tables")`,
   the line `select` loses. `chosen_packs` (`:110-114`) stays. The seam's `guidance` gains a
   keyword: `guidance(self, selection, /, *, opening: bool) -> str` at
   `src/aidm/engines/seam.py:363`; `author` (`:281`) passes `opening=True`, `render_next`
   (`:245`) `opening=False`. `RoomEngine.author` (`src/aidm/engines/rooms/engine.py:176`) and
   `write_next` (`:226`) pass the same two.
3. `src/aidm/engines/loner3e/worldsmith.py`: `Pack` (`:30-50`) becomes `Loner3ePack` as in the
   shapes, with `Loner3eBlock` above it; `defined_ids` stays; `_twist_columns_pair_up` stays.
   Add `Loner3ePack.sections(*, opening)` as described in the shapes. Rename every use:
   `loner3e/engine.py:44,60,68`, `tests/support/`, `tests/loner3e/`.
4. `src/aidm/engines/loner3e/engine.py`: `guidance` (`:143-145`) returns
   `f"{AUTHORING}\n\n{self.packs.guidance(self.packs.require(selection), opening=opening)}"`;
   delete `_revised` (`:260-262`) and the `JsonValue` import. `master_sections` (`:147-163`)
   adds, before the glossary, one `("SPECIAL RULES", rules)` section per chosen pack whose
   `rules` is not empty, titled `SPECIAL RULES: <pack name>`. `PackSet.require` moves with the
   class; keep its refusal text.
5. `AUTHORING` (`loner3e/worldsmith.py:10-27`) gains two sentences at the end: the packs' factions,
   people and monsters are written to be used; file one into `cast` under a new id with its
   tags and drives copied and a `brief` for this scene, and size its luck by the rule above.
   Names come from the pack's name lists when the setting has them.
6. `src/aidm/app/spawn.py`: `PROMPT_MAX_BYTES = 131_072` after `KEPT_ENV` (`:26`), with the
   one-line reason (Linux `MAX_ARG_STRLEN`: one argv element). `run_cli` (`:162`) refuses before
   `_spawn` when `len(prompt.encode()) >= PROMPT_MAX_BYTES`:
   `Refusal(f"the {role} prompt is {size} bytes; the command line takes fewer than {PROMPT_MAX_BYTES}")`.
   An `E2BIG` `OSError` was a bug; now it is a message the player reads.
7. The converter, `scripts/srd_packs.py`, outside `src` and outside the test tree: given one or
   more `APnn_<name>.md` paths, it writes `src/aidm/engines/loner3e/packs/apnn-<name>.json`
   (stem from the file: `AP01_fantasy` to `ap01-fantasy`). It parses: `## Setting Information`
   paragraphs to `setting`; the four `### Concepts|Skills|Frailties|Gear` d66 pipe tables to
   `DecisionOption(id=slug(label, taken), label, detail="")`; `#### Female Names|Male Names|
   Surnames` and `### Nicknames` (AP12 files it under `####`) to `names`; every `## Special Rule*`
   section, its subsections and tables included, to `rules` as plain text (a `| D66 | Spell |`
   row becomes `- **Heal** (1 Luck) – …` with the number dropped, headings kept as `Heading:`
   lines, bold kept); `## Factions`, `## NPCs`, `## Monsters` or `## Hostile Entities` `###`
   entries to blocks, reading `**Concept:**`, `**Skills:**`, `**Frailty:**`, `**Gear:**`,
   `**Goal:**`, `**Motive:**`, `**Nemesis:**` lines, lists split on `, `; `## Locations` `###`
   entries to `Location(label, detail, encounters)` where `encounters` is the text after
   `Possible encounters:`; `## Adventure Seeds` d66 rows to `seeds`. `spends_luck` is true when
   `rules` contains `Luck cost`. `name` is the `# ` title minus ` Adventure Pack`; `source` is the
   page URL `https://lonersrd.zotiquestgames.com/adventure_packs/<stem>.html`; `license` is the
   line `ap01-fantasy.json:4` carries today, with the pack name substituted. The output goes
   through `parse(Loner3ePack, …)` before it is written, so a shape error stops the script. Every
   list keeps the SRD's order; the JSON is `indent=2`, keys in model order, so a second run is
   byte-identical. Trailing spaces on headings (AP01 `### King Vaelor the Thornbound  `) and
   curly quotes in names are handled: strip, keep.
8. Run the converter on AP01 and replace `src/aidm/engines/loner3e/packs/ap01-fantasy.json`. The
   trait ids it makes must equal today's (`ap01-fantasy.json:7,189,371,553` and on), since
   `characters/` files store labels, not ids, and nothing else stores them; a diff of the four
   tables against the old file shows label-only changes at most.
9. Fixture and test: copy `AP01_fantasy.md` to `tests/fixtures/srd/AP01_fantasy.md` (CC BY-SA
   4.0, attributed in `docs/LONER-3E.md`). `tests/scripts/test_srd_packs.py` runs the converter's
   parse function on the fixture and asserts 36 entries in each trait table, 6 factions, 6 NPCs,
   6 monsters, 6 locations, 36 seeds, `spends_luck`, and that converting twice gives equal JSON.
   `pyproject.toml` adds `scripts` to the pytest path only if the test cannot import it
   otherwise; the converter is a module with a `main()`, not a package.
10. Prompt budget test, `tests/loner3e/test_prompt_budget.py`: build a `Loner3eGame` from
    `whispering-vault` with `packs = (srd, ap01-fantasy)`, a `source` of 48,000 bytes, two
    chapters of 20 exchanges each of 400-character transcripts, and assert
    `len(ENGINE.render_next(state, "…").encode()) < PROMPT_MAX_BYTES`. When phase 3 lands the
    other eleven, the test picks the two largest by file size instead of naming AP01.
11. `docs/LONER-3E.md` "Pack sources" (`:39-50`): the twelve packs, the converter and its command,
    the fixture's attribution, and one line saying the four trait tables' ids are stable across
    runs. Deviation 6: trait labels are the SRD's, bare; the glossary lists only entries with a
    detail. `README.md:54`: a pack is the whole SRD kit, one sentence.
12. Regenerate `tests/core/fixtures/prompts/loner3e/worldsmith.txt` (the only golden that holds
    a Loner worldsmith prompt), read it, and confirm it shows `PACK: Starter tables` sections
    and no JSON. Full check. `PROGRESS.md` entry with all four counts.

## Phase 2: `spend_luck`, the seed picker and the pack the character already chose

Three small things the whole pack now allows. About half a day.

Target: `src` about **9,850**, within 9,810 to 9,900. `tests` about **11,720**, within 11,680
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
   `world.check_unnamed(args.why)`, `require_living_here`, then the cast method.
   `docs/LONER-3E.md` "The tools" adds the line.
4. `src/aidm/engines/loner3e/rules.md`: under "Tags and drives" one paragraph: when SPECIAL
   RULES price something in luck, call `spend_luck` with the printed cost before the `roll`
   that decides it, and read the roll as those rules say.
5. Seeds on the scenario page. `src/aidm/engines/seam.py`: `Engine.seeds(self, supplements:
   Sequence[Slug]) -> tuple[DecisionOption, ...]`, default `()`; `SceneEngine` and `RoomEngine`
   override after phase 4, `SceneEngine` now: for each chosen pack (`srd` included) and each
   seed, `DecisionOption(id=f"{pack_id}-{n}", label=seed[:60], detail=seed)`.
   `src/aidm/ui/create.py` `ScenarioForm.character_fields` (`:243-262`): under the supplements
   select, a `ui.select` "Adventure seed" filled from `engine.seeds(chosen supplements)`, rebuilt
   on supplements change, whose `on_change` sets `self.premise.value` to the seed's `detail`.
   The premise stays editable; the seed is a starting point, not stored.
6. Supplements default to the character's. `src/aidm/core/model.py` `CharacterHeader` (`:52-54`)
   gains `packs: PackSelection | None = None`; `src/aidm/app/launch.py` `CatalogEntry` (`:15-22`)
   gains `packs: tuple[Slug, ...] = ()`, filled at `:86-96` from the header. In
   `character_fields`, the character select's `on_change` sets `self.supplements.value` to that
   character's packs minus `srd`; the first render does the same for the preselected character.
   A test in `tests/ui/test_create.py` or the nearest existing create-page test file: picking a
   character made with `ap01-fantasy` selects it.
7. Full check. `PROGRESS.md` entry.

## Phase 3: the other eleven packs

The converter runs on AP02 through AP12. Where a page differs from AP01 the converter grows;
where the SRD's own text is broken, the page wins and the difference is recorded.

Target: `src` unchanged within 20 lines; `scripts` about 260; eleven new JSON files under
`src/aidm/engines/loner3e/packs/`. About two hours plus review.

### Steps

1. Download the eleven markdown files by hand (`curl` of the raw GitHub URLs; not in a test) to a
   scratch directory and run the converter on all twelve. Read every refusal it raises. Known
   differences to handle: `## Hostile Entities` (AP12) beside `## Monsters`; `## Special Rules`
   with `###` subsections beside `## Special Rule: Magic`; `#### Nicknames` under `### Names`
   (AP12) beside `### Nicknames`; names with quotes (`Hannah "Blackout" Garcia`); a
   `**Frailty:**` that holds two frailties split by `, `; an entry missing a key, which becomes
   the model's default when the field allows one and a stop otherwise.
2. Every trait table across the twelve is checked for `defined_ids` collisions against `srd`:
   `PackSet.select` refuses a shared id, so a pack that shares one with `srd.json` cannot be
   selected at all. The repo's `srd.json` tables were written to avoid the AP01 words; check the
   other eleven with a one-off loop over `Loner3ePack.defined_ids()` and rename the `srd.json`
   entry, never the SRD's, where one collides. Two supplements may legitimately collide with
   each other; that is the existing rule and the refusal names both.
3. `tests/scripts/test_srd_packs.py` gains one test over the shipped JSON, not the network:
   every `loner3e/packs/ap*.json` parses as `Loner3ePack`, has 36 entries in each trait table
   and 6 blocks in each of the three cast lists, and no two of them share an id with `srd`.
4. `docs/LONER-3E.md`: the twelve packs listed with their page URLs; the open licence question
   stays open with the note that the site index declares CC BY-SA 4.0 and every page carries only
   the copyright footer. `README.md`: "twelve adventure packs" where it says one.
5. The prompt budget test of phase 1 now picks the two largest pack files. If it fails, the fix is
   in `kit_sections` (drop `encounters` in play, then shorten block rendering), never in the cap.
6. Full check. `PROGRESS.md` entry.

## Phase 4: packs on the seam, for 24XX and Tunnel Goons

The pack set moves from the scene family to the engine seam, so a room engine has one. 24XX's
pack becomes a supplement shape with the seventeen skills required of `srd` alone. Tunnel Goons
gets a pack model with no shipped pack and no `srd`. This is the phase that touches every engine;
it is reviewed hardest.

Target: `src` about **10,050**, within 9,980 to 10,140. `tests` about **11,900**, within 11,820
to 12,000. About a day.

### Steps

1. `src/aidm/engines/seam.py`: `Engine[P, M, G]` becomes `Engine[P, M, G, K: Pack]` with
   `pack: type[K]` and `packs: PackSet[K]` declared at `:63-80`; `__init__` (`:82-95`) reads
   `self.packs = read_packs(self.id, self.directory / "packs", Path(), self.pack)` before the
   tools. `supplement_options` (`:154`), `select_packs` (`:157`), `admit` (`:160`),
   `chosen_packs`, `supplement_steps` and `SUPPLEMENTS` move up from
   `src/aidm/engines/scenes/engine.py:47,98-124,222-233`. On the seam: `select_packs(supplements)`
   returns `None` for an empty sequence, else `self.packs.select(parse(PackSelection, {"ids": tuple(supplements)}))`;
   `admit(packs, character)` refuses unless `set(character.packs.ids if character.packs else ()) <= set(packs.ids if packs else ())`,
   with the existing message; `validate` (`:325`) adds `if state.packs is not None:
   self.packs.select(state.packs)`. `SceneEngine` overrides `select_packs` to prepend `SRD_PACK`
   and `admit` to `require` first, and keeps the `srd`-in-selection check in its `validate`.
   `RoomEngine.validate` (`rooms/engine.py:67-70`) loses its "plays no table set" refusal.
2. `Engine.creation_steps` callers: `TunnelGoonsEngine.creation_steps`
   (`src/aidm/engines/tunnelgoons/engine.py:102-118`) starts with `*self.supplement_steps()` and
   the item hint joins `STARTING_ITEM_LIST` with the chosen packs' `items` labels;
   `build_character` (`:120-135`) passes `self.select_packs(picked_many(picks, SUPPLEMENTS))` to
   `sheet_character`. A character made with no pack stores `packs: None`, as today.
3. `src/aidm/engines/tunnelgoons/worldsmith.py`: `TunnelGoonsBlock` and `TunnelGoonsPack` as in
   the shapes, `sections` adding `ITEMS`, `FACTIONS`, `PEOPLE`, `MONSTERS` (`- name — brief
   (hp N)`). `TunnelGoonsEngine.guidance` (`:78-79`) returns `AUTHORING` followed by
   `self.packs.guidance(selection, opening=opening)` when `selection` is not `None`. `AUTHORING`
   gains one sentence: a pack's monster is written as an npc with that `hp`. The master reads
   `rules` through `RoomEngine.master_sections`, one section per chosen pack with rules, the same
   shape as Loner's; put the helper that builds those sections on `PackSet`
   (`rules_sections(selection) -> Sections`) since two families need it.
4. `src/aidm/engines/twentyfourxx/worldsmith.py`: `Pack` (`:59-77`) becomes `TwentyfourxxPack` as
   in the shapes, `skills` no longer `min_length=17, max_length=17`; `_every_pick_told` stays.
   `TwentyfourxxEngine.__init__` checks `len(self.packs.srd().skills) == 17` and that
   `starting_kit` is not empty, raising `ValueError` otherwise, the check the model made.
   `sections` adds `SPECIALTIES` (`specialty_lines()`), `ORIGINS` (label — detail) and the three
   block sections. `guidance` (`twentyfourxx/engine.py:254-256`) returns `AUTHORING` plus
   `self.packs.guidance(...)`. `write_sheet` (`:107-125`) keeps its own specialty lines.
   Regenerate `tests/core/fixtures/prompts/twentyfourxx/worldsmith.txt` once and read it.
5. `src/aidm/engines/registry.py` stays; `build_engines()` takes nothing until phase 5.
6. `Engine.seeds` from phase 2 step 5 moves to the seam in full: chosen packs' seeds, `srd`
   included where present.
7. Tests: `tests/engines/test_scenes.py:238-271` move their pack cases to
   `tests/engines/test_packs.py` and gain: a room engine accepts `packs: None` and a selection of
   one written pack; a scene engine still refuses a selection without `srd`; a 24XX supplement
   with no `skills` selects; the seam `admit` refuses a character whose packs exceed the
   scenario's and accepts `None` against anything. Re-check `scenarios/buried-keep/world.json`
   and `characters/kael/tunnelgoons.json` still load.
8. `docs/24XX.md` "Pack sources" and `docs/TUNNEL-GOONS.md` gain a "Packs" paragraph each: what
   a pack holds for this engine, that none ships, and that a written one is selected on the
   character and the scenario like Loner's.
9. Full check. `PROGRESS.md` entry.

## Phase 5: packs the player owns

A `packs/` directory beside `saves/`, read at start, hot-installed after a write, listed on the
home page.

Target: `src` about **10,150**, within 10,100 to 10,220. `tests` about **11,980**, within 11,920
to 12,060. About half a day.

### Steps

1. `.gitignore`: `packs/` under "Play data". `src/aidm/config.py:140-142`:
   `packs_dir: Path = Path("packs")`.
2. `src/aidm/core/io.py`: `class PackStore` after `Library` (`:56-140`), `directory: Path`,
   `folder(engine) -> Path` (`directory / engine`), `write(engine, pack_id, pack: BaseModel)`
   through `write_text` (`:165`) with `model_dump_json(indent=2)`; `exists(engine, pack_id)`.
   `core` stays shape-blind: it writes a `BaseModel`.
3. `src/aidm/engines/registry.py` `build_engines(packs_dir: Path) -> dict[...]`: each engine is
   built with `written=packs_dir / engine.id`; `Engine.__init__` takes `written: Path` and hands
   it to `read_packs`. `Runtime.__post_init__` (`src/aidm/app/runtime.py:321-325`) passes
   `settings.packs_dir`. `tests/support/table.py` and every `build_engines()` call pass a
   `tmp_path` or `Path()`.
4. `Engine.install_pack(self, pack_id, pack: K) -> None`: `self.packs.check_addable(pack_id, pack)`
   then `self.packs = self.packs.installing(pack_id, pack)`. Reinstalling an existing written id
   replaces it; a shipped id is refused by `check_addable`.
5. Home page. `src/aidm/app/launch.py` `LauncherCatalog` gains
   `packs: tuple[PackEntry, ...]` with `PackEntry(id, engine, label, rules, written: bool, tables: str)`
   where `tables` is a short count line (`36 concepts · 6 factions · 36 seeds` from the pack's
   own fields, rendered by `Pack.summary()` on the base model, engine tables counted by the
   subclass). `src/aidm/ui/app.py` `home_page` (`:87-108`) adds a "Packs" section after
   "Saved games": one row per pack, engine badge, `Written` badge for the player's own. No
   buttons yet; phase 7 adds View and Edit.
6. Test: a written pack file under `tmp_path / "loner3e"` is installed at build and listed;
   a file whose stem is `srd` is skipped with a warning; `install_pack` of a colliding pack is
   refused and leaves the set unchanged; a game whose save names a written pack that was deleted
   is filed under `unresumable` by `LauncherCatalog.read`.
7. Full check. `PROGRESS.md` entry.

## Phase 6: the worldsmith writes a pack

Two typed asks, nothing saved until both pass, one page.

Target: `src` about **10,420**, within 10,340 to 10,520. `tests` about **12,140**, within 12,060
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
   intent=HEAD_ASK, guidance=<engine AUTHORING>, answer=self.head)`; `check` builds
   `self.pack_of(head, empty body, …)` and calls `self.packs.check_addable(pack_id, pack)`, so a
   trait id that collides with `srd` is re-prompted with the collision named; then the body prompt
   with the head rendered as family sections (`THE PACK SO FAR`: the head's `sections`), answer
   `self.body`, check by building the whole pack. A `PackBody` for a scene engine also passes
   `Loner3eBlock`-level checks the model already makes. `scope` is empty for a pack; add
   `SOURCELESS`-style text for a scope-less prompt rather than a new render method.
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

## Phase 7: the editor

One page per written pack, one field per section, text in and a validated pack out.

Target: `src` about **10,700**, within 10,600 to 10,820. `tests` about **12,300**, within 12,220
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
