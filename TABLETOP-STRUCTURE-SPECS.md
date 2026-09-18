# Tabletop content structure: options

Input for a future PLAN.md phase. Not scheduled. Facts about today's code were checked
against the tree and by two adversarial reviews. Every decision is taken; the chosen design is
option 1, one pack per character and per scenario.

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

## Option 1: one pack per character and per scenario

One id, not a list. The word is "pack" everywhere: the field, the dropdown, the home page,
the class, the folder. The SRD pack stays as the engine's rules kit and is offered as the
"no pack" choice, so the field is never empty and Tunnel Goons and 24XX change nothing
visible.

### Rule

- A character is made with one pack. A scenario is written with one pack. A game plays the
  scenario's pack.
- The SRD pack is always read for rules-level tables. The chosen pack is read for setting
  prose, names, rules, locations, seeds and cast. Every creation table is the SRD's entries
  followed by the chosen pack's; nothing pools two chosen packs. `pack="srd"` means no setting
  prose and no seeds, exactly as today.
- Admission: `character.pack in (SRD_PACK, pack)`. A character made with the SRD alone plays
  any scenario; a character made with a pack plays that pack's scenarios. This keeps today's
  subset behaviour for the one case anyone uses.

### Creation tables per engine (SRD then pack, everywhere)

| Engine | Table | SRD holds | A chosen pack holds | Read as |
| --- | --- | --- | --- | --- |
| Loner | concepts, skills, frailties, gear | 5 / 6 / 5 / 6, this repo's | 36 each (AP) or 6 to 36 (written) | SRD + pack |
| 24XX | skills | 17 | none (`()` by shape) | rules-level, SRD always |
| 24XX | specialties, origins | 6 / 3 | 1 to n (written; `min_length=1`) | SRD + pack |
| 24XX | starting_kit | 1 | none | rules-level |
| Tunnel Goons | items (hint text) | 18 | 0 to n | SRD + pack |
| Loner | twists | 6 + 6 | `None` | rules-level |

`spends_luck`, `rules`: the chosen pack's alone.

### Model (`core/model.py`)

```python
class Scenario[P: BaseModel](Frozen):
    meta: ScenarioMeta
    engine: EngineId
    pack: Slug  # "srd" is the engine's rules kit, no setting prose
    source: str = ""
    payload: P

class Character[P: BaseModel](Frozen):
    id: Slug
    engine: EngineId
    pack: Slug
    payload: P

class Game[P: BaseModel](Mutable):
    ...
    pack: Slug
```

Delete `Packs`, `_distinct_packs`. `CharacterHeader.packs` → `pack`; `CatalogEntry.packs`
→ `pack`.

### Pack set (`engines/packs.py`)

```python
@dataclass(frozen=True, slots=True)
class PackSet[K: Pack]:
    engine: EngineId
    shipped: Mapping[Slug, K]
    written: Mapping[Slug, K]
    installed: Mapping[Slug, K]

    def srd(self) -> K: ...

    def require(self, pack_id: Slug) -> K:
        found = self.installed.get(pack_id)
        if found is None:
            raise Refusal(f"pack {pack_id!r} is not installed for {self.engine!r}")
        return found

    def options(self) -> tuple[DecisionOption, ...]:
        return tuple(DecisionOption(id=key, label=pack.name) for key, pack in self.installed.items())

    def guidance(self, pack_id: Slug, *, opening: bool) -> str: ...
    def rules_section(self, pack_id: Slug) -> Sections: ...
    def seeds(self, pack_id: Slug) -> tuple[str, ...]: ...
```

Delete `MAX_SUPPLEMENTS`, `select`, `chosen`, `supplements`, `Pack.defined_ids` and its two
overrides, `check_addable` (a written pack must only not shadow a shipped id and must parse).

### Seam (`engines/seam.py`)

```python
def admit(self, pack_id: Slug, character: AnyCharacter) -> None:
    self.packs.require(pack_id)
    if character.pack not in (SRD_PACK, pack_id):
        raise Refusal(
            f"{character.id!r} was made with {character.pack!r}; "
            f"this scenario plays {pack_id!r}"
        )
```

- `select_packs`, `supplement_options` go; the create pages read `engine.packs.options()`.
  `guidance(pack_id, *, opening)`.
- `creation_steps(pack_id, picks)`, `create_character(name, brief, pack_id, picks)`,
  `build_character(...)`, `sheet_character(name, sheet, pack_id)`, `build_scenario(meta,
  pack_id, ...)`, `author(meta, source, pack_id, ...)`.
- `validate`: drop the `SRD_PACK in state.packs` check. `restore`: `self.packs.require
  (state.pack)`.
- `edited`, `author_pack`: unchanged.

### Engines

- Loner: `chosen = self.packs.require(pack_id)`; `skills = (*srd.skills, *chosen.skills)`
  and the same for concepts, frailties, gear; `spends_luck = chosen.spends_luck`;
  `master_sections` glossary reads the SRD and the chosen pack. Twists stay `srd()`.
- 24XX: `_offered(pack_id)` = SRD + chosen; `write_sheet` and `SheetDraft.check` take that
  pair; `skills` and `starting_kit` stay `srd()`.
- Tunnel Goons: `items` hint = SRD + chosen.
- Choosing `srd` reads the SRD once, not twice.
- `SceneEngine`, `RoomEngine`: `rules_sections` → `rules_section`; `guidance(draft.pack, ...)`.
- Test engines `tests/support/fifth.py`, `sixth.py` (their `packs=` fixtures at lines 54 to 59
  and 91 to 96): same contract.

### UI

- `create.py`: one `ui.select` (not `multiple`), label "Pack", default `"srd"` shown as the
  SRD pack's name. `CharacterForm.choose_pack` resets picks; `ScenarioForm.
  follow_character_id` sets the select to the character's pack. Delete `_packs_select`,
  `_selected_packs`, `_offered`, `choose_packs`, `follow_supplements`; keep `_drop_stale`.
  `roll_seed` reads one pack.
- Home: `_packs` unchanged; `PackEntry` unchanged. Pack page: unchanged.
- The word "setting" is never shown to the player for a pack: it is the app's Settings page.

### Content, docs, qa

- `scenarios/*/world.json` (3), `characters/kael/*.json` (3): `"packs": ["srd"]` →
  `"pack": "srd"`.
- Saves: stale, skipped with a warning (accepted rule).
- Shipped pack JSON and `scripts/srd_packs.py`: unchanged.
- Goldens (three `worldsmith.txt`): unchanged text expected; regenerate and diff.
- `qa/s_create.py`: the `loner-supplements` block picks AP01 on a single "Pack" select;
  its SRD picks ("Quiet Hands", "Pry Bar") still exist under extend; the shot is retaken.
- README: the pack paragraph and "Pick it on a character and on a scenario"; `docs/24XX.md`
  lines 36 to 38 ("selected on the character and on the scenario").

### Tests

- `tests/engines/test_packs.py`: drop overlap, cap and `select` cases; add `require` refusal.
- `tests/engines/test_integrity_boundaries.py` (lines 126, 159, 167) and
  `tests/engines/test_scene_bar.py` (338, 345: `..._no_packs_is_refused...`): the duplicate,
  missing and uninstalled cases become one uninstalled-pack case.
- `tests/engines/test_seam.py`, `test_rooms.py`: `admit` with `srd`, the same pack, and
  another pack.
- `tests/loner3e/test_create.py`, `tests/twentyfourxx/test_create.py`, `tests/tunnelgoons/
  test_engine.py`: one pack; the options are the SRD's then the chosen pack's.
- `tests/loner3e/test_tools.py` (163, 174): `draft.pack = "ap01-fantasy"` for `spend_luck`.
- `tests/loner3e/test_prompt_budget.py`: worst case is the single largest AP file; the
  `MAX_SUPPLEMENTS` import goes.
- `tests/scripts/test_srd_packs.py` (13, 156): drop the `defined_ids` collision assertion.
- `tests/ui/test_create.py`: single select; the character's pack follows into the scenario form.
- `tests/app/test_launcher.py`, `test_pack_authoring.py`, `test_pack_editing.py`,
  `test_master_tools.py` (257), `tests/twentyfourxx/test_worldsmith.py` (11), `tests/support/
  tunnelgoons.py` (119), `twentyfourxx.py` (53): field rename.

### Feature impact

Gains:

- One select on both create pages. No cap, no overlap refusal, no subset refusal to explain.
- The worldsmith prompt carries one `PACK:` block. Smaller, on point.
- `PackSet` loses half its methods; `create.py` loses five helpers.

Losses:

- Stacking two adventure packs (fantasy + horror). No shipped content does it; a written pack
  is the way to "dark fantasy".
- The allowed-sources list as a concept. Two written 24XX packs can no longer both feed one
  character.

Unchanged problems:

- Editing a written pack still changes scenarios and characters that name it. Deleting one
  still breaks their saves. As today; see "Considered and rejected".

### Contract for a future engine

1. Ship `packs/srd.json`: rules-level tables and, where the game has one, a starter creation
   set. No setting prose. A hack is a new engine, not a pack.
2. Rules-level fields come from `self.packs.srd()`. Setting prose, names, rules, locations,
   seeds and cast come from `self.packs.require(pack_id)`. A creation table is the SRD's
   entries followed by the chosen pack's. A written pack leaves rules-level fields
   empty or `None` (today: Loner twists `None`, 24XX `skills` `()`).
3. Never pool two chosen packs.

Shapes checked against this contract: a D&D-like (classes in the SRD, a pack adds
subclasses, races and backgrounds), PbtA (playbooks
in the SRD, a pack adds more), a game with no creation tables (SRD ships tables `()`,
`creation_steps` ignores the pack), a game whose setting is its rules (Mothership: the SRD
pack carries the setting prose too, and the engine ships no other pack).

### Estimate

One day. 20 source files, 25 test files, one qa script, two docs.

## Considered and rejected

- **Option 2, rename `packs` and keep the list.** No simplification.
- **Option 3, a campaign folder that embeds a copy of the pack, with its own characters.**
  Its one unique gain is the copy, which only protects a running game from an edit or a delete
  of a written pack. A party of several characters or an ordered series of adventures would
  need it, and neither is a feature. A scenario already embeds its cast, arc and opening, so a
  well-written scenario is self-contained without it. Three to four days for a home page
  shaped like a table. The full write-up is in git history (commit cb5bcbc).
- **A drift pin** (a hash of the pack on scenario, character and save, refused on mismatch).
  Half a day. Not taken: editing a written pack under a running game is the player's own act,
  and today's behaviour (the tables change in play) is accepted.

## Decided

- Option 1 alone. No drift pin, no campaign layer, now or later.
- The word is "pack" everywhere; "setting" is the app's Settings page and a pack's prose field.
- Every creation table is the SRD's entries followed by the chosen pack's, in every engine.
- Admission: a character made with `srd` plays any scenario; one made with a pack plays that
  pack's scenarios.
