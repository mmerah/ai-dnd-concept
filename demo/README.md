# The demo recording

Records `docs/demo.gif`: one game of Loner 3e, played through the real app with the three AI
roles answering from an authored script, filmed with a camera that pushes in on whatever the
turn changed.

## Record it

```bash
uv run python demo/server.py &          # the real app, scripted roles, seeded dice
uv run --group qa python demo/record.py --out docs/demo.gif --webp
```

The server must be up before the recorder starts. One pass takes about four minutes and writes
the same file every time: the dice are seeded, the roles answer from `script.py`, and the camera
moves are computed from the page's own element boxes.

## The pieces

- `script.py` — the beats: what the player types, what the master plays, what the narrator writes.
  The narration is authored to match the seeded dice, so the prose and the oracle card agree.
- `roles.py` — the three roles, answering those beats. It extends the QA harness's scripted roles.
- `server.py` — the real app with those roles and a seeded `Random`, on port 8124.
- `record.py` — drives the page, captures master frames at 2x, then crops, eases, styles and
  encodes offline. `ZOOM`, `OUT_WIDTH`, `COLORS` and the beats' `hold` are the tuning knobs.

## Filming against the real AI roles

Nothing in `record.py` knows about the scripted roles. Point it at a real server and it films a
real game, one the models write as it goes:

```bash
uv run aidm &
uv run --group qa python demo/record.py --base http://localhost:8080 --out docs/demo.gif
```

The beats' player lines are typed as written; the roles answer for themselves, so the camera's
`focus` per beat is a guess at what that turn will change, and the run costs whatever the roles
cost. The recording is no longer reproducible.
