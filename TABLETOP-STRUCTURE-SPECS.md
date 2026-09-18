# Tabletop content structure: options

Input for a future PLAN.md. Not scheduled. Facts about today's code were checked against the
tree and by two adversarial reviews; anything marked *decide* is open. Option 2 (rename `packs`
to `setting`, keep the list) was dropped: no simplification.

## How real tables layer content

| Layer | Real name | Holds | This repo today |
| --- | --- | --- | --- |
| 1 | Core rules, or a hack (replacement core rules: a 24XX hack, a Tunnel Goons derivative) | Dice, oracle, the sheet, rules tables (Loner twists, 24XX's 17 skills) | `rules.md` + the rules-level fields of `packs/srd.json`. A hack is its own engine, never a pack |
| 2 | Setting book (supplement, sourcebook, genre pack) | Lore, creation tables, names, one special rule, factions, NPCs, monsters, places, hooks | A pack (`Pack` subclass). Loner's "Adventure Packs" are this layer, not layer 3 |
| 3 | Adventure (module, scenario) | One story: hook, opening, its own cast, secrets, rough end. Portable: run in any campaign of a fitting setting | `scenarios/<id>/world.json`: `meta` + opening `payload` |
| 4 | Campaign | One setting, one party, several adventures in order | Not a thing. Saves are `<scenario>--<character>` |
| 5 | Play | What happened at the table | Saves |

What real tables do that this repo does:

- Keep the module (3) apart from the setting (2).
- Keep a list of allowed source books for character options (D&D session zero, Pathfinder
  Society's legal list, Dungeon World third-party playbooks). `packs: tuple[...]` is that list.

What real tables keep singular, and this repo does not:

- The setting a module and a character share. A table plays "Loner + Fantasy". The list of
  source books is a separate thing from the one setting.

What the real world does about a sourcebook changing under a running game:

- Errata and reprints reach live campaigns (2024 PHB, PF2 remaster). Tables pin ("we play
  the 2014 rules"); they do not photocopy the book. A drift pin is the cheap fix; a copy is the
  strong one.

A fact that limits what Loner can prove: the Loner 3e core publishes no creation tables. The
`srd.json` starter tables (5 concepts, 6 skills, 5 frailties, 6 gear) are this repo's own
(`docs/LONER-3E.md` deviation 4). An Adventure Pack is the only creation table a real Loner
player has. So "AP replaces generic" is true of the printed game only because the printed game
has no generic.

## Today's shape (facts)

- `packs: Packs` on `Scenario`, `Character`, `Game`, `CharacterHeader` (`core/model.py`), a
  unique-checked `tuple[Slug, ...]`. `"srd"` must be in the list (`Engine.validate`).
- `PackSet` (`engines/packs.py`): `shipped`, `written`, `installed`; `select` checks unique,
  installed, `MAX_SUPPLEMENTS = 2`, and `defined_ids` overlap between packs; `chosen` returns
  the packs in order; `guidance`, `rules_sections`, `seeds` concatenate over the selection;
  `check_addable` = "selectable beside the SRD".
- `Engine` (`engines/seam.py`): `select_packs` prepends `"srd"`; `admit(packs, character)`
  runs `select` and refuses unless `character.packs ⊆ packs` (a plain-SRD character can start
  any supplement scenario today); `begin` calls `admit`; `restore` calls `select(state.packs)`;
  `guidance(selection)` prepends `authoring`; `sheet_character` and `build_scenario` carry
  `packs` into the files. `app/launch.py::CatalogEntry.packs` carries the character's list to
  the scenario form.
- The three shipped `srd.json` files hold rules-level and creation tables only. None has
  `setting`, `names`, `rules`, `locations` or `seeds`, so with `("srd",)` selected
  `Pack.sections` is empty, the worldsmith gets no `PACK:` block, and the scenario page offers
  no seed. README's "A pack is the whole SRD kit: setting, traits, names…" describes a written
  pack or a Loner AP, not the SRD packs.
- Rules-level tables read the SRD pack alone: Loner twists (`Loner3eEngine.__init__`), 24XX
  `skills` and `starting_kit` (`self.packs.srd()`). Creation tables pool across the selection:
  Loner `concepts/skills/frailties/gear` (`creation_steps`, `master_sections`), 24XX
  `specialties/origins` (`_offered`, `write_sheet`, `SheetDraft.check`), Tunnel Goons `items`
  hint. Loner `spends_luck` is any-of over the selection. The twelve Loner APs' tables are
  disjoint from the SRD's; 44 ids are shared between APs (PROGRESS.md), which is why
  `defined_ids` exists.
- UI (`ui/create.py`): `_packs_select` (`multiple=True`), `_selected_packs`, `_drop_stale`;
  `CharacterForm.choose_packs`; `ScenarioForm.follow_character_id`, `_offered`,
  `choose_packs`, `follow_supplements`, `roll_seed`. Home lists packs (`app.py::_packs`); the
  pack page (`ui/packs.py`) edits a written pack as JSON boxes; `rewrite_pack` re-installs live.
- Files: shipped packs `src/aidm/engines/<engine>/packs/*.json`; written packs
  `packs/<engine>/<id>.json` (`PackStore`, `Settings.packs_dir`, gitignored `/packs/`);
  scenarios `scenarios/<id>/world.json` (+ `icons/`); characters
  `characters/<id>/<engine>.json` (+ `icons/`); saves `<scenario>--<character>.json`
  (`LaunchTarget.slug`, `GAME_ROUTE` two segments, `game_path`).
- Editing or deleting a written pack changes or breaks every scenario, character and save that
  names it: `restore` refuses a missing pack; a rewritten pack changes the tables in play.
- Surface: 20 source files and 25 test files mention `packs`; three worldsmith goldens carry
  one `PACK:` block each; `qa/s_create.py` picks AP01 on the multi-select and then picks SRD
  skills and gear (pooling, end to end); README and `docs/24XX.md` describe the list.

## Option 1: one setting per character and per scenario

One id, not a list. The SRD pack stays as the engine's rules kit and is offered as the "no
setting" choice, so the field is never empty and Tunnel Goons and 24XX change nothing visible.

### Rule

- A character is made for one setting. A scenario is written for one setting. A game plays the
  scenario's setting.
- The SRD pack is always read for rules-level tables. The chosen setting is read for setting
  prose, names, rules, locations, seeds and cast. For each creation table the engine declares
  in code whether the setting *replaces* the SRD's entries or *extends* them; nothing pools two
  chosen packs. `setting="srd"` means no setting prose and no seeds, exactly as today.
- Admission: `character.setting in (SRD_PACK, setting)`. A generic character travels; a
  character made for a setting stays in it. This keeps today's subset behaviour for the one
  case anyone uses.

### Creation tables per engine, replace or extend (*decide*, with counts)

| Engine | Table | SRD holds | A setting holds | Recommendation |
| --- | --- | --- | --- | --- |
| Loner | concepts, skills, frailties, gear | 5 / 6 / 5 / 6, this repo's | 36 each (AP) or 6 to 36 (written) | replace: the printed game has no generic list |
| 24XX | skills | 17 | none (`()` by shape) | rules-level, SRD always |
| 24XX | specialties, origins | 6 / 3 | 1 to n (written; `min_length=1`) | extend: a written setting with one specialty is a poor create page alone |
| 24XX | starting_kit | 1 | none | rules-level |
| Tunnel Goons | items (hint text) | 18 | 0 to n | extend |
| Loner | twists | 6 + 6 | `None` | rules-level |

`spends_luck`, `rules`: the setting's alone.

### Model (`core/model.py`)

```python
class Scenario[P: BaseModel](Frozen):
    meta: ScenarioMeta
    engine: EngineId
    setting: Slug  # a pack id; "srd" is the engine's rules kit, no setting prose
    source: str = ""
    payload: P

class Character[P: BaseModel](Frozen):
    id: Slug
    engine: EngineId
    setting: Slug
    payload: P

class Game[P: BaseModel](Mutable):
    ...
    setting: Slug
```

Delete `Packs`, `_distinct_packs`. `CharacterHeader.packs` → `setting`; `CatalogEntry.packs`
→ `setting`.

### Pack set (`engines/packs.py`)

```python
@dataclass(frozen=True, slots=True)
class PackSet[K: Pack]:
    engine: EngineId
    shipped: Mapping[Slug, K]
    written: Mapping[Slug, K]
    installed: Mapping[Slug, K]

    def srd(self) -> K: ...

    def require(self, setting: Slug) -> K:
        found = self.installed.get(setting)
        if found is None:
            raise Refusal(f"setting {setting!r} is not installed for {self.engine!r}")
        return found

    def settings(self) -> tuple[tuple[Slug, K], ...]:
        return tuple(self.installed.items())

    def guidance(self, setting: Slug, *, opening: bool) -> str: ...
    def rules_section(self, setting: Slug) -> Sections: ...
    def seeds(self, setting: Slug) -> tuple[str, ...]: ...
```

Delete `MAX_SUPPLEMENTS`, `select`, `chosen`, `supplements`, `Pack.defined_ids` and its two
overrides, `check_addable` (a written pack must only not shadow a shipped id and must parse).

### Seam (`engines/seam.py`)

```python
def setting_options(self) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.packs.settings())

def admit(self, setting: Slug, character: AnyCharacter) -> None:
    self.packs.require(setting)
    if character.setting not in (SRD_PACK, setting):
        raise Refusal(
            f"{character.id!r} was made for {character.setting!r}; "
            f"this scenario plays {setting!r}"
        )
```

- `select_packs`, `supplement_options` go. `guidance(setting, *, opening)`.
- `creation_steps(setting, picks)`, `create_character(name, brief, setting, picks)`,
  `build_character(...)`, `sheet_character(name, sheet, setting)`, `build_scenario(meta,
  setting, ...)`, `author(meta, source, setting, ...)`.
- `validate`: drop the `SRD_PACK in state.packs` check. `restore`: `self.packs.require
  (state.setting)`.
- `edited`, `author_pack`: unchanged.

### Engines

- Loner: `pack = self.packs.require(setting)`; tables per the table above; `spends_luck =
  pack.spends_luck`; `master_sections` glossary reads the SRD and the setting. Twists stay
  `srd()`.
- 24XX: `_offered(setting)` = SRD + setting (extend); `write_sheet` and `SheetDraft.check`
  take that pair; `skills` and `starting_kit` stay `srd()`.
- Tunnel Goons: `items` hint = SRD + setting.
- `SceneEngine`, `RoomEngine`: `rules_sections` → `rules_section`; `guidance(draft.setting, ...)`.
- Test engines `tests/support/fifth.py`, `sixth.py` (their `packs=` fixtures at lines 54 to 59
  and 91 to 96): same contract.

### UI

- `create.py`: one `ui.select` (not `multiple`), label "Setting", default `"srd"` shown as the
  SRD pack's name. `CharacterForm.choose_setting` resets picks; `ScenarioForm.
  follow_character_id` sets the select to the character's setting. Delete `_packs_select`,
  `_selected_packs`, `_offered`, `choose_packs`, `follow_supplements`; keep `_drop_stale`.
  `roll_seed` reads one pack.
- Home: `_packs` lists "Settings"; `PackEntry` unchanged. Pack page: unchanged.
- Player-facing word: "setting". *decide*: rename `pack` in code and file names too.
  Recommendation: no; a setting book is a pack of tables, and the rename buys nothing.

### Content, docs, qa

- `scenarios/*/world.json` (3), `characters/kael/*.json` (3): `"packs": ["srd"]` →
  `"setting": "srd"`.
- Saves: stale, skipped with a warning (accepted rule).
- Shipped pack JSON and `scripts/srd_packs.py`: unchanged.
- Goldens (three `worldsmith.txt`): unchanged text expected; regenerate and diff.
- `qa/s_create.py`: the `loner-supplements` block picks AP01 on a single "Setting" select and
  then AP01's own skills and gear (the SRD's "Quiet Hands", "Pry Bar" no longer exist there
  under replace); the `loner-supplements` shot is retaken.
- README: the pack paragraph and "Pick it on a character and on a scenario"; `docs/24XX.md`
  lines 36 to 38 ("selected on the character and on the scenario").

### Tests

- `tests/engines/test_packs.py`: drop overlap, cap and `select` cases; add `require` refusal.
- `tests/engines/test_integrity_boundaries.py` (lines 126, 159, 167) and
  `tests/engines/test_scene_bar.py` (338, 345: `..._no_packs_is_refused...`): the duplicate,
  missing and uninstalled cases become one uninstalled-setting case.
- `tests/engines/test_seam.py`, `test_rooms.py`: `admit` with `srd`, same, and other setting.
- `tests/loner3e/test_create.py`, `tests/twentyfourxx/test_create.py`, `tests/tunnelgoons/
  test_engine.py`: replace or extend per the table.
- `tests/loner3e/test_tools.py` (163, 174): `draft.setting = "ap01-fantasy"` for `spend_luck`.
- `tests/loner3e/test_prompt_budget.py`: worst case is the single largest AP file; the
  `MAX_SUPPLEMENTS` import goes.
- `tests/scripts/test_srd_packs.py` (13, 156): drop the `defined_ids` collision assertion.
- `tests/ui/test_create.py`: single select; character setting follows into the scenario form.
- `tests/app/test_launcher.py`, `test_pack_authoring.py`, `test_pack_editing.py`,
  `test_master_tools.py` (257), `tests/twentyfourxx/test_worldsmith.py` (11), `tests/support/
  tunnelgoons.py` (119), `twentyfourxx.py` (53): field rename.

### Feature impact

Gains:

- One select on both create pages. No cap, no overlap refusal, no subset refusal to explain.
- A fantasy Loner character picks from the fantasy tables (replace), as the printed game.
- The worldsmith prompt carries one `PACK:` block. Smaller, on point.
- `PackSet` loses half its methods; `create.py` loses five helpers.

Losses:

- Stacking two adventure packs (fantasy + horror). No shipped content does it; a written pack
  is the way to "dark fantasy".
- The allowed-sources list as a concept. A written 24XX setting and a second written 24XX
  setting can no longer both feed one character.
- Under replace, Loner's SRD starter tables vanish once a setting is chosen (5/6/5/6 entries).
  Under extend for 24XX and Tunnel Goons nothing vanishes.

Unchanged problems:

- Editing a written setting still changes scenarios and characters that name it. Deleting one
  still breaks their saves. See the drift pin below, or option 3.

### Add-on 1b: a drift pin

Store a content hash of the pack on `Scenario`, `Character` and `Game` beside `setting`
(`setting_hash: str`), computed from the pack's JSON dump. `restore` and `begin` compare it to
the installed pack's hash and refuse with "the setting changed since this was written". Same
mechanism as `ScenarioMeta.check_drift`. Half a day. Buys option 3's headline gain without a
campaign layer. *decide*: refuse, or warn and play on. Recommendation: refuse; the launcher
already skips a drifted save with a warning.

### Contract for a future engine

1. Ship `packs/srd.json`: rules-level tables and, where the game has one, a starter creation
   set. No setting prose. A hack is a new engine, not a pack.
2. Rules-level fields come from `self.packs.srd()`. Setting prose, names, rules, locations,
   seeds and cast come from `self.packs.require(setting)`. Each creation table is read as
   replace or extend, decided in the engine's code. A written pack leaves rules-level fields
   empty or `None` (today: Loner twists `None`, 24XX `skills` `()`).
3. Never pool two chosen packs.

Shapes checked against this contract: a D&D-like (classes in the SRD, subclasses extend; a
setting adds races and backgrounds: replace or extend as the engine decides), PbtA (playbooks
in the SRD, a setting extends them), a game with no creation tables (SRD ships tables `()`,
`creation_steps` ignores the setting), a game whose setting is its rules (Mothership: the SRD
pack carries the setting prose too, and the engine offers no other setting).

### Estimate

One day, plus half a day for 1b. 20 source files, 25 test files, one qa script, two docs.

## Option 3: a campaign embeds its setting

The real-life shape: a table starts a campaign in one setting with one party, then plays
adventures inside it. The campaign holds a *copy* of the setting, so a sourcebook edit or
deletion never reaches a game in play. Includes option 1 (one setting) and adds layer 4.

### Rule

- A campaign is made once from an installed pack: the campaign folder holds the copy.
- A character is made inside a campaign, from the copy's tables.
- A game is one campaign, one scenario, one character.
- The installed packs (shipped and written) are templates. The pack page edits templates only.
- Scenarios, *decide*: (a) written inside a campaign, under its folder; (b) stay top-level,
  each naming the setting it was written for, and any campaign of that setting (or of `srd`)
  may run it. Real modules are portable (Tomb of Horrors runs in any world), which is (b).
  Recommendation: (b). Then `admit` survives as `scenario.setting in (SRD_PACK, campaign
  setting id)`, and the copy is the campaign's, not the scenario's.

### Files (with (b))

```
campaigns/<campaign>/
  campaign.json                 # meta, engine, the setting copy (a full Pack)
  characters/<id>/character.json
  characters/<id>/icons/        # runtime.py:472 reads a per-character icons dir
scenarios/<id>/world.json       # as option 1: setting id, no copy
saves/<campaign>--<scenario>--<character>.json
```

`characters/<id>/<engine>.json` today lets one person play three engines from one folder. A
campaign character is one engine's by construction. Kael becomes three characters in three
shipped campaigns. Accept: the cross-engine folder was a filing trick, not a rule of play.

### Model (`core/model.py`)

```python
class CampaignMeta(Frozen):
    title: str
    brief: str = ""

class Campaign[K: BaseModel](Frozen):
    """`campaigns/<id>/campaign.json`: the setting this table plays, copied at creation."""
    meta: CampaignMeta
    engine: EngineId
    setting_id: Slug  # the template it was copied from; the scenario admission reads it
    setting: K

class Character[P: BaseModel](Frozen):
    id: Slug
    engine: EngineId
    payload: P

class Game[P: BaseModel](Mutable):
    campaign_id: Slug
    scenario_id: Slug
    character_id: Slug
    ...
```

`Campaign[K: BaseModel]` in `core` is the same shape as `Scenario[P: BaseModel]`: core still
knows no world shape, and `tests/core/test_package_boundary.py` holds.

### How the engine reaches the copy during play (*decide*, one choice)

Today `self.packs.chosen(draft.packs)` is read inside tools and requests: 24XX `write_sheet`,
Loner `spend_luck`, `master_sections`, scene and room `guidance`. Three ways:

1. `Game` gets `setting: K`. `Game[P]` → `Game[P, K]`, which ripples into `AnyGame`,
   `MasterTool[G: Game[Any]]` (`core/tools.py`), `Request[G]`, `Engine.game`, `tools`,
   `requests`, every `*Game` alias including `FifthGame`/`SixthGame`. A Loner AP is 38 KB
   (`ap01-fantasy.json`) against a 3.6 KB scenario: every turn `FileStore.write` writes it,
   `Game.draft()` deep-copies it, `Game.commit()` re-validates it.
2. Tools and requests receive the pack beside the draft. `MasterTool.call` and `Request.write`
   in `core` grow a parameter whose only meaning is a `Pack`: a layering smell.
3. The engine holds an in-memory `campaigns: dict[Slug, K]`, filled by the runtime when a
   session opens (as `install_pack` fills `packs.written` today), and reads
   `self.campaign_pack(draft.campaign_id)`. Saves, `Game`, and every tool signature stay as
   they are. The engine already owns mutable installed state, so this adds no new kind of thing.

Recommendation: 3. Drift check: `Campaign` gets a `check_drift(other)` like `ScenarioMeta`'s,
comparing the copy; the runtime runs it when a session opens against the campaign file. The
launcher does not compare copies; it reads each campaign file once for the catalog.

### Engine seam

- `creation_steps(pack, picks)`, `create_character(name, brief, pack, picks)`, `author(meta,
  source, pack, ...)`, `guidance(pack, *, opening)`. Replace or extend per the option 1 table,
  with the SRD still from `self.packs.srd()`.
- `admit(scenario, campaign)`: engines equal, `scenario.setting in (SRD_PACK,
  campaign.setting_id)`.
- `restore`: no pack lookup. `validate`: no pack check.
- `PackSet` shrinks to `shipped`, `written`, `installed`, `srd()`, `require(id)`.

### Runtime, library, wiring

- `Settings.campaigns_dir` (`config.py`), read by `app` and `ui` only. `qa/server.py:42`
  copies `("scenarios", "characters")` into its work dir and builds `Settings` with four dirs:
  add `campaigns`.
- `Library.campaigns: Path`; `read_campaigns(models)` through `routed()` like `read_scenario`;
  `read_campaign`, `write_campaign`; character readers take a campaign id.
- `Runtime.new_campaign(engine_id, meta, pack_id)`: copies `engine.packs.require(pack_id)`.
  *decide*: also a campaign from a premise, the worldsmith writing the setting at once (today's
  New pack flow, landing in the campaign) with a "save as template" toggle. Recommendation:
  yes; otherwise one act is two pages.
- `new_scenario(engine_id, meta, document, setting)` as option 1. *decide*: the character
  select stays on the scenario page (today `check` runs `engine.begin` with a character to
  prove the opening starts). Recommendation: keep it, listing characters of campaigns whose
  setting admits this scenario.
- `new_character(campaign_id, name, brief, picks)`.
- `LaunchTarget(campaign_id, scenario_id, character_id)`; `slug` is three parts;
  `SAVE_SLUG_PATTERN` unchanged; the comment above it in `core/io.py` ("Two content ids joined
  by `--`") changes. `GAME_ROUTE` gains a segment (`ui/app.py::_game`, `ui/widgets.py::
  game_path`). `FileStore.media_dir` unchanged. `runtime.py:472` icon roots: scenario folder
  and the campaign's character folder.
- `LauncherCatalog`: campaigns, each with its characters; scenarios top-level with their
  setting; `_save_option` resolves titles by `(campaign_id, character_id)` and checks the
  scenario's setting against the campaign's.

### UI

- Home: "Campaigns" (each with its party) beside "Scenarios"; pick a campaign, then a scenario
  it admits, then one of its characters. "New campaign" button. Settings list stays, as
  templates.
- New campaign page: rules, title, setting select (or premise / document for a written one).
- New character page: campaign select first; no setting select.
- New scenario page: as option 1.
- Pack page: unchanged. A campaign page showing the copy read-only: later, when asked.

### Content, docs, qa

- `characters/kael/*` become three shipped campaigns, one per engine, each with an `srd` copy
  and one Kael (icons move with them). `scenarios/` stays, gaining `setting`.
- `.gitignore`: `/packs/` stays. Saves: stale.
- `qa/`: `s_home.py`, `s_create.py`, `server.py`, `run_all.sh` shots that drive the home page.
- README: campaign paragraph; the characters line; `docs/24XX.md` as option 1.

### Tests

- Everything under option 1, plus: `Library` campaign reads and writes; three-level
  `LauncherCatalog`; campaign `check_drift`; three-part save slug and route; the copy is
  byte-equal to the template; a template edit after the copy does not reach the campaign (the
  test that proves the option); `admit` of a scenario against a campaign.
- `fifth.py`, `sixth.py`: a campaign fixture each.

### Feature impact

Gains:

- Editing or deleting a template never touches a game in play. The pack page becomes safe.
- The home page reads like a table: my campaigns, each with its party, and the adventures
  they can run.
- Room for a party of several characters and an order of scenarios without moving files again.

Losses:

- A character no longer plays across engines from one folder.
- One more page and one more step before play: campaign, then character, then scenario. The
  shipped campaigns hide it for a first run.
- A written pack is copied, so a fix to it does not reach old campaigns. That is the point,
  but a player who wants the fix re-creates the campaign.

### Contract for a future engine

As option 1, with "the pack the runtime installed for this campaign" in place of
`require(setting)` during play. An engine never looks a setting up by id after creation.

### Estimate

Three to four days on top of option 1's day: `Library`, `LauncherCatalog`, home page, three
create pages, route, content move, `qa/`.

## Sequencing

- Option 1 alone is one step and a full stop. 1 + 1b covers drift for half a day more.
- Option 3 contains option 1. Doing 1 first costs one round of stale saves and, if 1b was
  done, a hash field that option 3 removes again. Doing 3 straight costs one bigger phase.
- Recommendation: 1 + 1b first, ship, play a few games, then 3 if the campaign shape (a party,
  an order of adventures) is actually wanted; drift alone no longer justifies it.

## Decisions to take before a PLAN.md

1. Option 1, 1 + 1b, or 1 then 3.
2. Replace or extend per creation table (the table under option 1).
3. Admission `in (srd, setting)` for every engine, or plain equality.
4. Rename `pack` in code, or only in player-facing words.
5. Under 1b: refuse on drift, or warn.
6. Under 3: scenarios top-level (portable) or under the campaign.
7. Under 3: how the engine reaches the copy (recommendation: an in-memory map on the engine).
8. Under 3: a campaign written from a premise on the campaign page, or only from a template.
9. Under 3: the character select stays on the scenario page.
