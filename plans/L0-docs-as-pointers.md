# L0 — docs become pointers, not copies

`docs/24XX.md`, `docs/LONER-3E.md`, `docs/CAIRN-BAREBONES.md` and `docs/FATE-CONDENSED.md` are
near-verbatim SRD extractions (367 / 946 / 1476 / 1408 lines). Each becomes a ~50–70 line pointer
file. Duplicating a source of truth is the problem: a pack transcribed out of our extraction inherits
whatever drifted during extraction, so an implementer must build from the official page instead.

Verified safe: nothing reads `docs/*.md` at runtime, build time, in prompts or in tests
(`grep` over `src`, `tests`, `evals`, `pyproject.toml`, the packs), and `pyproject.toml:26` packages
only `src/aidm`, so they never ship in the wheel. The only references are prose:
`README.md:14-17,129-131`, `IDEAS.md:7-8`, and two docstrings (`loner3e/rules.py:25`,
`twentyfourxx/rules.py:27`).

## Steps

1. **Do this before deleting anything.** Fate Condensed is CC BY 3.0 Unported, which requires its
   attribution paragraph wherever our copyright appears, in the same size as our copyright text. Its
   only copy in the repo is `docs/FATE-CONDENSED.md:22` — the Fate *Condensed* wording naming PK
   Sullivan et al., **not** the generic Fate Core paragraph on fate-srd.com. Copy it verbatim into
   `README.md`, and into `src/aidm/engines/fate/packs/srd.json` and its `director.md` when L5 creates
   them. Losing this paragraph is a licence breach; nothing else in this phase is.
2. Rewrite each of the four files to the section list below. Delete the `Planned engine package` and
   `Engine package sketch` sections outright — they are superseded by `plans/L5-*` and `plans/L6-*`.
3. Update the prose references: `README.md:14-17,129-131` and the two rules.py docstrings now point
   at a pointer file rather than an extraction, so reword anything implying the rules text is here.

## Sections of the slim file

(a) Title and one line on the game. (b) **Official sources** — canonical rules URLs, the archive or
commit the old extraction was taken from, one or two explanatory guides. (c) **Licence and
attribution** — licence, link, author, and the exact required attribution string, quoted. (d) **Pack
sources, per pack, with URLs** (below). (e) **Deviations in this repo** — the current list carried
over whole, prose preamble included; this is the file's only normative content. (f) One line saying
mechanics live in `src/aidm/engines/<id>/`, and that `packs/srd.json` — not this file — is the
transcription of record.

## Licence per game — link plus attribution suffices in all four

- **Loner 3e** (`lonersrd.zotiquestgames.com`) — CC BY-SA 4.0, Roberto Bisceglie / Zotiquest Games.
  ShareAlike binds the *adaptations* (our packs and `director.md`), which already carry it.
- **Cairn Barebones** (`cairnrpg.com`) — CC BY-SA 4.0, Yochai Gal. Same reasoning.
- **24XX** — CC BY 4.0, Jason Tocci; required credit "24XX rules are CC BY Jason Tocci" is already
  verbatim at `twentyfourxx/director.md:3`.
- **Fate Condensed** — CC BY 3.0 Unported, Evil Hat. The one blocking case; see step 1.

No licence here requires shipping rules text.

## Pack sources

- **Loner 3e** — core rules `https://lonersrd.zotiquestgames.com/core/loner-3e.html`; twelve adventure
  packs at `https://lonersrd.zotiquestgames.com/adventure_packs/APnn_<name>.html`, `AP01_fantasy`
  through `AP12_cyberpunk` (2e copies under `adventure_packs/legacy/`). Our `packs/ap01-fantasy.json`
  comes from the first; its `© Roberto Bisceglie` footer against the site's CC BY-SA declaration is
  the open question `README.md:133` already records — carry that question into the new file.
- **Cairn Barebones** — eight pages under `https://cairnrpg.com/barebones/rules/`, of which
  `barebones-character-creation`, `barebones-gear-packages` and `barebones-marketplace` carry every
  table L6's pack needs. Later packs may draw on `/resources/monsters/` and
  `/resources/third-party-content/`; Barebones itself ships no bestiary.
- **24XX** — no separate pack sources. Specialties, origins, the 17 skills and the gear lists are all
  in the SRD at `https://24xx-srd.carrd.co/`. The 200+ hacks at `https://itch.io/c/1204990/24xx` are
  separately licensed and are not drop-in packs.
- **Fate Condensed** — no separate pack sources. The 19 skills and the ladder are in the SRD itself
  (`https://fate-srd.com/downloads/CC-BY-SRDs.zip`); alternate skill lists are its own optional rule,
  § "Changing the Skill List".

## Deviations that live only in prose — these must survive the port

Both existing Deviations sections open with an **unnumbered preamble** of settled rulings that a
careless port drops:

- **24XX** — help is one die at most; "more than one bulky item *may* hinder you" is Director
  adjudication; an ally who helps "shares the risk" in fiction only; the d20 detail tables and the d6
  job-finding roll are the SRD's own "invent" branch.
- **Loner 3e** — the Adventure Maker, the 5W+H frame, the open-ended tables and the next-scene mood
  roll stay authoring-time or in the Director's seat; Appendix A is a different game.

**One reverse case.** Loner deviation 2 claims "a non-living character gets a sheet the first time an
engine needs one". It never does: `SheetEngine.seed` returns early unless `entity.kind == "actor"`
(`engines/core.py:330`) and `resolve_question` routes through `require_actor_here`. Reword it to say
non-living characters are refused, or take L4 step 10 and make the claim true.

New deviations that L4 and L6 will add to these files: 24XX starships, 24XX "make a new character if
killed", Loner's invented starter tables, Cairn's ungated Training, and Cairn's own death rule. Leave
room for them; do not try to write them now.
