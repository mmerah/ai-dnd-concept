# Tabletop content structure: two options

Input for a future PLAN.md. Not scheduled. Facts about today's code are checked against the
tree at the time of writing; anything marked *decide* is open.

## How real tables layer content

| Layer | Real name | Holds | This repo today |
| --- | --- | --- | --- |
| 1 | Core rules | Dice, oracle, the sheet, rules tables (Loner twists, 24XX's 17 skills) | `rules.md` + the rules-level fields of `packs/srd.json` |
| 2 | Setting book (supplement, sourcebook, genre pack, hack) | Lore, creation tables, names, one special rule, factions, NPCs, monsters, places, hooks | A pack (`Pack` subclass). Loner's "Adventure Packs" are this layer, not layer 3 |
| 3 | Adventure (module, scenario) | One story: hook, opening, its own cast, secrets, rough end | `scenarios/<id>/world.json`: `meta` + opening `payload` (scene, cast, arc) |
| 4 | Campaign | One setting, one party, several adventures in order | Not a thing. Saves are `<scenario>--<character>` |
| 5 | Play | What happened at the table | Saves |

What real tables do that this repo does:

- Keep the module (3) apart from the setting (2). A module is written for a setting.
- Make a character from the setting's tables, not from a generic list plus the setting's.

What real tables do not do, and this repo does:

- Pick a *list* of supplements on the character, another list on the adventure, and check one
  is inside the other. A table plays "Loner + Fantasy"; the setting is one choice.
- Pool the core book's generic starter tables with the setting's tables. In Loner the AP replaces
  the generic list.
- Let a sourcebook edit change an adventure already in play. A printed module holds its own
  NPCs and tables.

## Today's shape (facts)

- `packs: tuple[Slug, ...]` on `Scenario`, `Character`, `Game`, `CharacterHeader`
  (`core/model.py`), validated unique by `Packs`. `"srd"` must be in the list (`Engine.validate`).
- `PackSet` (`engines/packs.py`): `shipped`, `written`, `installed`; `select` checks unique,
  installed, `MAX_SUPPLEMENTS = 2`, and `defined_ids` overlap between packs; `chosen` returns the
  packs in order; `guidance`, `rules_sections`, `seeds` concatenate over the selection;
  `check_addable` = "selectable beside the SRD".
- `Engine` (`engines/seam.py`): `select_packs` prepends `"srd"`; `admit(packs, character)` runs
  `select` and refuses unless `character.packs ⊆ packs`; `begin` calls `admit`; `restore` calls
  `select(state.packs)`; `guidance(selection)` prepends `authoring`; `sheet_character` and
  `build_scenario` carry `packs` into the files.
- Rules-level tables already read the SRD pack alone: Loner twists (`Loner3eEngine.__init__`),
  24XX `skills` and `starting_kit` (`self.packs.srd()`). Setting-level tables pool across the
  selection: Loner `concepts/skills/frailties/gear` (`creation_steps`, `master_sections`), 24XX
  `specialties/origins` (`_offered`, `write_sheet`), Tunnel Goons `items` hint. Loner
  `spends_luck` is any-of over the selection.
- UI (`ui/create.py`): `_packs_select` (`multiple=True`), `_selected_packs`, `_drop_stale`;
  `CharacterForm.choose_packs`; `ScenarioForm.follow_character_id`, `_offered`,
  `choose_packs`, `follow_supplements`, `roll_seed`. Home page lists packs (`app.py::_packs`);
  the pack page (`ui/packs.py`) edits a written pack's fields as JSON boxes; `rewrite_pack`
  re-installs it live.
- Files: shipped packs `src/aidm/engines/<engine>/packs/*.json`; written packs
  `packs/<engine>/<id>.json` (`PackStore`, gitignored `/packs/`); scenarios
  `scenarios/<id>/world.json`; characters `characters/<id>/<engine>.json`; saves
  `<scenario>--<character>.json`.
- Editing or deleting a written pack changes or breaks every scenario, character and save that
  names it: `restore` refuses a missing pack; a rewritten pack changes the tables in play.
- 27 test files mention `packs`; the two worldsmith prompt goldens carry a `PACK:` block.

## Option 1: one setting per character and per scenario

One id, not a list. The SRD pack stays and is the engine's generic setting, so the field is
never empty and every engine that ships only an SRD changes nothing visible.

### Rule

- A character is made for one setting. A scenario is written for one setting. A game plays the
  scenario's setting, and the character's setting must be the same id.
- The SRD pack is always read for rules-level tables. The chosen setting is read for
  setting-level tables. The SRD chosen as the setting supplies both. Nothing pools.

### Model (`core/model.py`)

```python
class Scenario[P: BaseModel](Frozen):
    meta: ScenarioMeta
    engine: EngineId
    setting: Slug  # a pack id; "srd" is the engine's generic setting
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

Delete `Packs`, `_distinct_packs`. `CharacterHeader.packs` → `setting: Slug`.

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
        return tuple(self.installed.items())  # the SRD is offered too, as "generic"

    def guidance(self, setting: Slug, *, opening: bool) -> str: ...
    def rules_section(self, setting: Slug) -> Sections: ...
    def seeds(self, setting: Slug) -> tuple[str, ...]: ...
```

Delete `MAX_SUPPLEMENTS`, `select`, `chosen`, `supplements`, `Pack.defined_ids` and every
override, `check_addable` (a written pack must only not shadow a shipped id and must parse).

### Seam (`engines/seam.py`)

```python
def setting_options(self) -> tuple[DecisionOption, ...]:
    return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.packs.settings())

def admit(self, setting: Slug, character: AnyCharacter) -> None:
    self.packs.require(setting)
    if character.setting != setting:
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
- `edited` / `author_pack`: unchanged.

### Engines

- Loner: `pack = self.packs.require(setting)`; tables are `pack.concepts` etc., no pooling;
  `spends_luck = pack.spends_luck`; `master_sections` glossary reads one pack. Twists stay
  `srd()`.
- 24XX: `_offered(setting)` reads one pack; `write_sheet` and `SheetDraft.check` take one
  pack; `skills` and `starting_kit` stay `srd()`.
- Tunnel Goons: `items` hint from one pack.
- `SceneEngine`, `RoomEngine`: `rules_sections` → `rules_section`; `guidance(draft.setting, ...)`.
- Test engines `tests/support/fifth.py`, `sixth.py`: follow the same contract.

### UI

- `create.py`: one `ui.select` (not `multiple`), label "Setting", default `"srd"` shown as the
  SRD pack's name. `CharacterForm.choose_setting` resets picks; `ScenarioForm.
  follow_character_id` sets the select to the character's setting. Delete `_packs_select`,
  `_selected_packs`, `_offered`, `choose_packs`, `follow_supplements`; keep `_drop_stale`
  (a setting change still leaves stale picks). `roll_seed` reads one pack.
- Home: `_packs` lists "Settings"; `PackEntry` unchanged but for the name. Pack page: unchanged.
- Words shown to the player: "setting" replaces "pack" everywhere the player reads it. *decide*:
  keep `pack` as the code and file name (`packs/`, `Pack`, `PackSet`) or rename to `setting`.
  Recommendation: rename the field and the player-facing words only; the module and class
  names stay `Pack` (a setting book is a pack of tables; the rename buys nothing in code).

### Content and files

- `scenarios/*/world.json` (3), `characters/kael/*.json` (3): `"packs": ["srd"]` →
  `"setting": "srd"`.
- Saves: stale, skipped with a warning (accepted rule).
- Shipped pack JSON: unchanged. `scripts/srd_packs.py`: unchanged.
- Prompt goldens (`tests/core/fixtures/prompts/*/worldsmith.txt`): unchanged text unless a pack
  block was pooled; regenerate and diff.

### Tests

- `tests/engines/test_packs.py`: drop the overlap, the cap and the `select` cases; add
  `require` refusal.
- `tests/engines/test_seam.py`, `test_rooms.py`, `test_integrity_boundaries.py`: `admit`
  equality; `restore` refuses an uninstalled setting.
- `tests/loner3e/test_create.py`, `tests/twentyfourxx/test_create.py`, `tests/tunnelgoons/
  test_engine.py`: one setting, no pooling (a Loner character made with `ap01-fantasy` picks from
  the fantasy tables only).
- `tests/ui/test_create.py`: single select; character setting follows into the scenario form.
- `tests/app/test_launcher.py`, `test_pack_authoring.py`, `test_pack_editing.py`: field rename.
- `tests/core/test_entities.py`: `Packs` cases go.

### Feature impact

Gains:

- A fantasy character picks from the fantasy tables, not from generic + fantasy. Matches the
  printed game.
- One select on both create pages. No cap, no overlap refusal, no subset refusal to explain.
- The worldsmith prompt carries one `PACK:` block, never two or three. Smaller, more on point.
- `PackSet` loses about half its methods; `create.py` loses five helpers.

Losses:

- Stacking two adventure packs (fantasy + horror). No shipped content does this. A written
  pack is the way to "dark fantasy".
- The SRD's generic starter tables are no longer offered beside a setting's. Only visible for
  Loner; 24XX already reads `skills` from the SRD alone and Tunnel Goons has no picks.

Unchanged problems:

- Editing a written setting still changes scenarios and characters that name it. Deleting one
  still breaks their saves. Option 3 is the fix.
- A character still cannot move from one setting to another. (Loner tags are freeform, so
  the equality check is stricter than the game needs. *decide*: keep equality for every
  engine, or let an engine relax it. Recommendation: equality; a character is made for a
  setting in every printed game.)

### Contract for a future engine

1. Ship `packs/srd.json`: rules-level tables and a generic setting in one file.
2. Read rules-level fields from `self.packs.srd()`, setting-level fields from
   `self.packs.require(setting)`. A written pack leaves rules-level fields empty or `None`
   (today: Loner twists `None`, 24XX `skills` `()`).
3. Never pool two packs.

### Estimate

One day. About 15 source files and 27 test files.

## Option 3: a campaign embeds its setting

The real-life shape: a table starts a campaign in one setting with one party, then plays
adventures inside it. The campaign holds a *copy* of the setting, so a sourcebook edit or
deletion never reaches a game in play. Includes option 1 (one setting) and adds layer 4.

### Rule

- A campaign is made once from an installed pack: the campaign folder holds the copy.
- A character is made inside a campaign, from the copy's tables.
- A scenario is written inside a campaign, from the copy's guidance.
- A game is one campaign, one scenario, one character. All three share the copy by
  construction; there is nothing to admit.
- The installed packs (shipped and written) are templates. The pack page edits templates only.

### Files

```
campaigns/<campaign>/
  campaign.json          # meta, engine, the setting copy (a full Pack)
  characters/<id>.json   # Character: id, engine, payload; no setting field
  scenarios/<id>/
    world.json           # Scenario: meta, engine, source, payload; no setting field
    icons/
saves/<campaign>--<scenario>--<character>.json
```

*decide*: `characters/<id>/<engine>.json` today lets one person play three engines from one
folder. Under a campaign a character is one engine's by construction, so the engine suffix goes.
Kael becomes three characters in three campaigns. Recommendation: accept; the cross-engine
folder was a filing trick, not a rule of play.

### Model (`core/model.py`)

```python
class CampaignMeta(Frozen):
    title: str
    brief: str = ""

class Campaign[K: BaseModel](Frozen):
    """`campaigns/<id>/campaign.json`: the setting this table plays, copied at creation."""
    meta: CampaignMeta
    engine: EngineId
    setting: K  # the engine's Pack model; core sees a BaseModel

class Scenario[P: BaseModel](Frozen):
    meta: ScenarioMeta
    engine: EngineId
    source: str = ""
    payload: P

class Character[P: BaseModel](Frozen):
    id: Slug
    engine: EngineId
    payload: P

class Game[P: BaseModel](Mutable):
    campaign_id: Slug
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    ...
```

`Game` carries no setting: the session reads the campaign file once and hands the engine the
copy. *decide*: embed the copy in the save too, so a save is playable when the campaign file is
edited by hand. Recommendation: no; `check_drift` already refuses a scenario that moved, do the
same for the campaign (a hash or a full compare of the copy).

### Engine seam

- `Engine` methods that take `setting: Slug` under option 1 take `pack: K` here:
  `creation_steps(pack, picks)`, `create_character(name, brief, pack, picks)`,
  `author(meta, source, pack, ...)`, `guidance(pack, *, opening)`, `master_sections` and
  `render_request` read the pack the session holds, not `state.setting`.
- Where the engine reads `self.packs.chosen(draft.packs)` inside a tool or a request today
  (24XX `write_sheet`, Loner `spend_luck`, `master_sections`, scene and room `guidance`), the
  pack must reach it. Two ways, *decide*:
  1. `Game` gets `setting: K` (engine-typed, saved in every save file). Every save carries the
     whole pack; `Game[P]` becomes `Game[P, K]`. Simple, fat saves.
  2. The session holds the pack and the engine's tools receive it beside the draft. Every
     `MasterTool` signature and `Request.write` grows a parameter. Thin saves, wide change.
  Recommendation: 1. A pack is a few KB; a save already holds the whole world. It keeps
  "rules code changes only the draft it is handed" true without a new parameter.
- `admit` goes. `begin(scenario_id, scenario, character)` checks engines only.
- `restore`: no pack lookup. `validate`: no pack check.
- `PackSet` shrinks to `shipped`, `written`, `installed`, `srd()`, `require(id)`. Guidance,
  rules and seeds become `Pack` methods over one pack (they mostly are already: `sections`).
- Rules-level tables: still `self.packs.srd()` at engine init (twists, 24XX skills). A campaign
  copy of a written pack has them empty, as today. *decide*: copy the SRD's rules-level fields
  into the campaign copy at creation so one object holds everything the engine reads.
  Recommendation: no; the engine already owns its rules tables, the copy is the setting.

### Runtime and library

- `Library` gains `campaigns: Path`; `read_campaigns(models)`, `read_campaign(id, model)`,
  `write_campaign`. Scenario and character readers take a campaign id. `scenario_folder
  (campaign_id, scenario_id)`.
- `Runtime.new_campaign(engine_id, meta, pack_id) -> Slug`: copies `engine.packs.require
  (pack_id)` into the file. No worldsmith call. *decide*: a campaign from a premise, the
  worldsmith writing the setting at once (today's "New pack" flow, landing in the campaign
  instead of the library). Recommendation: yes, as the same form with a "save as template"
  toggle; otherwise the player writes a pack, then a campaign from it, two pages for one act.
- `new_scenario(campaign_id, meta, document)`: no character parameter unless `begin`'s check
  needs one. Today `check` runs `engine.begin` with a character to prove the opening can start
  a game. *decide*: keep a character at scenario creation (the form already asks for one) or
  check with any character of the campaign. Recommendation: keep the form's character select,
  limited to the campaign's characters.
- `new_character(campaign_id, name, brief, picks)`.
- `LaunchTarget` gains `campaign_id`; `slug` is `<campaign>--<scenario>--<character>`.
  `SAVE_SLUG_PATTERN` unchanged.
- `LauncherCatalog`: campaigns, each with its scenarios and characters. Home page: choose a
  campaign, then a scenario, then a character of that campaign.
- `PackStore` unchanged. `rewrite_pack` unchanged; it never reaches a campaign.

### UI

- Home: a "Campaigns" section replaces the scenario + character pair; "New campaign" button.
  Settings list (installed packs) stays, as templates.
- New campaign page: rules, title, setting select (or premise / document for a written one).
- New character and new scenario pages: a campaign select first (or opened from the campaign
  card with the campaign fixed); no setting select at all.
- Pack page: unchanged. *decide*: a campaign page showing the copy read-only. Recommendation:
  later, when someone asks.

### Content and files

- `scenarios/` and `characters/` move under `campaigns/<id>/`. Three shipped scenarios become
  three shipped campaigns (one per engine, each with its `srd` copy, one scenario, one Kael).
  `whispering-vault/icons/` and `characters/kael/icons/` move with them.
- `.gitignore`: `/packs/` stays.
- Saves: stale.
- `qa/` scripts drive the home page by scenario and character selects: update.
- README: campaign paragraph; "Scenarios live under `scenarios/<id>/world.json`" changes.

### Tests

- Everything under option 1, plus: `Library` campaign reads and writes; `LauncherCatalog`
  three-level catalog; drift check on the campaign copy; save slug with three parts; the
  `new_campaign` copy is byte-equal to the template; a template edit after the copy does not
  reach the campaign (the one test that proves the option's point).
- Test engines `fifth.py`, `sixth.py`: a campaign fixture each.

### Feature impact

Gains:

- Editing or deleting a template never touches a game in play. The pack page becomes safe.
- No admit check at all: a scenario and a character cannot disagree.
- The home page reads like a table: my campaigns, each with its adventures and its party.
- Room to grow into layer 4 later (a party of several characters, an order of scenarios)
  without moving files again.

Losses:

- A character no longer plays across engines from one folder.
- One more page and one more step before play: campaign, then character, then scenario.
  The shipped campaigns hide it for a first run.
- Saves grow by one pack (option 1 of the seam *decide*).
- A written pack is copied, so a fix to it does not reach old campaigns. That is the point,
  but a player who wants the fix re-creates the campaign.

### Contract for a future engine

Same three lines as option 1, with `require(setting)` replaced by "the pack the session hands
you". An engine never looks a setting up by id after creation.

### Estimate

Three to four days on top of option 1's day: `Library`, `LauncherCatalog`, home page, two
create pages, content move, `qa/`.

## Sequencing

- Option 1 alone is one step and a full stop.
- Option 3 contains option 1. Doing 1 first costs one extra content change (`setting` id
  appears, then disappears) and two rounds of stale saves. Doing 3 straight costs one bigger
  phase.
- Recommendation: 1 first, ship, play a few games, then 3 if template drift or the admit
  refusal actually bites.

## Decisions to take before a PLAN.md

1. Option 1, 3, or 1 then 3.
2. Rename `pack` → `setting` in code, or only in player-facing words.
3. Setting equality on `admit` for every engine (option 1 only).
4. Under 3: the pack copied into `Game` (fat save) or handed to tools (wide signature).
5. Under 3: a campaign written from a premise on the campaign page, or only from a template.
6. Under 3: the character select stays on the scenario page.
