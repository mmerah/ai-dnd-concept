# QA harness

Runs the real app with the three AI roles replaced by scripts, then drives it in Chromium
with Playwright. It is not a test suite: it starts processes, takes screenshots, and writes a
report per scenario to `qa/shots/<scenario>/` (ignored by git).

## Run it

```bash
export QA_WORK=/tmp/aidm-qa-work
qa/run_all.sh                 # every scenario, a fresh server each
qa/run_all.sh loner mobile    # some of them
qa/serve.sh                   # only the server, at http://localhost:8123 (/qa/log lists spawns)
qa/serve.sh --art             # the same, with placeholder 16:9 scene art drawn offline
```

`--art` turns media on and swaps the provider call for a gradient keyed off the prompt, so the
scene header can be looked at with a picture in it without a key or a network.

Playwright comes from the project venv (the `qa` dependency group), but the browsers do not:
Chromium is pinned in `drive.py` (`CHROMIUM`); change it for another machine.

Scenarios: `home`, `loner`, `goons`, `breathless`, `24xx`, `settings`, `create`, `mobile`,
`mcp` (tools over HTTP), `visual` (every page under each theme), `probe`.

## The scripted roles

The master reads PLAYER ACTION from its prompt. Lines starting with `!` are scripts:

| Script | Effect |
| --- | --- |
| `!roll what="Try the door" actor_id=player question="Does it give?"` | calls that tool (values parse as JSON, else strings; quote lists: `items='["torch"]'`) |
| `!change verb=reveal entity_id=vault-map` | a `change_world` call |
| `!none` | no tool call |
| `!crash` / `!refuse` | the master fails with `OSError` / `Refusal` |
| `!fail narrator`, `!bad worldsmith`, `!slow narrator` | the next spawn of that role fails, answers garbage once, or stalls 6 s |

Plain words with no script get one roll. The narrator echoes its prompt as `[narration]` and
`[happened]` lines, so a screenshot shows what the page was told; `[say <id> "words"]` adds a
spoken line. The worldsmith answers every request with a small valid draft.
