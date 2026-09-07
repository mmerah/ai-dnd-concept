# QA harness: the real app, driven by scripted roles

`qa/` runs the real NiceGUI app with the three AI roles replaced by scripts, then drives it in
Chromium with Playwright. Nothing here is a test: it starts processes, takes screenshots, and
writes a soft-assert report per scenario. Findings from the last sweep are in `FINDINGS.md`.

## The scripted roles (`agents.py`)

The master reads PLAYER ACTION from its prompt like the real one. Lines that start with `!` are
scripts, everything else is prose:

| Script | What the master does |
| --- | --- |
| `!roll what="Try the door" actor_id=player question="Does it give?"` | calls the tool `roll` with those arguments (values parse as JSON, else strings; quote lists: `items='["torch"]'`) |
| `!change verb=reveal entity_id=vault-map` | wraps the arguments in a `change_world` call |
| `!next_scene`, `!move to_id=cellar`, `!hire entity_id=grix terms="..."`, ... | any engine tool by name |
| `!none` | no tool call at all |
| `!crash` / `!refuse` | the master's spawn fails with `OSError` / `Refusal` |
| `!fail narrator`, `!bad worldsmith`, `!slow narrator` | arms a one-shot fault in another role: a refusal, one garbage answer, or a 6 s stall |

Plain words with no script get one engine-appropriate roll. The narrator echoes what it was
given (`[narration] ...` and `[happened] ...` lines), so a screenshot shows what the page was
told; `[say <id> "words"]` in the action adds a spoken line by that id. The worldsmith answers
each request shape (scene, map, sheet, abilities) with a small valid draft.

## Run it

```bash
uv venv /tmp/pw --python 3.13 && uv pip install --python /tmp/pw/bin/python playwright
export QA_PW=/tmp/pw/bin/python QA_WORK=/tmp/aidm-qa-work
qa/run_all.sh                      # every scenario, a fresh server each
qa/run_all.sh loner mobile         # some of them
qa/serve.sh --transport mcp        # just the server: http://localhost:8123, /qa/log lists spawns
```

`drive.py` pins Chromium at `/opt/pw-browsers/chromium-1194`; change `CHROMIUM` for another
machine. Screenshots and `report.json` land in `qa/shots/<scenario>/` (ignored by git).

Scenarios: `home`, `loner` (the whole life of a game page), `goons` (map, hire, interjection,
level-up, more map), `breathless` (loot decisions, breath, stress, hire), `24xx` (jobs, hire,
succession), `settings`, `create` (every engine's character, two scenarios, the launcher),
`mobile` (a phone and a tablet), `mcp` (the master's tools over HTTP), `probe` (odds and ends).
