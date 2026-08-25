# PLAN

Five phases, ordered. Each phase is a report in `docs/plans/`; the report is the detail, this file is
the stack and the reasons for the order. Ship a phase, tick it, move down. Nothing here is started.

Scope: IDEAS.md L1, L2, L5, L9, L10, I4 — L10 folds into L9's phase, so six items make five phases.
Everything else in IDEAS.md is untouched and unordered by this plan; see "Not in this plan".

> Line numbers in the reports are as of `2ce9dfa`. The working tree had staged changes to `engines/`,
> `ui/`, `state/` and `harness/` while the reports were being written, so re-grep a symbol before
> trusting a line number. Symbols are stable; line numbers are not.
>
> An over-engineering pass landed before this plan started: it deleted `prompt_id`,
> `PendingDecision.free_text`, `_can_type`, the input-token estimator with `RoleConfig.max_input_tokens`
> and `TurnConfig.chars_per_token`, and `ServerTool.published`, and it finished **Phase 2 step 2** early
> (`rule()`/`action()` in `engines/core.py`, all 16 command wrappers gone). The reports below are
> corrected for it.

---

## Phase 0 — L1: make a pending decision unmistakable

[docs/plans/L1-pending-decisions.md](docs/plans/L1-pending-decisions.md)

A paused game reads as one faint bold line. `decision_panel` (`ui/game.py:344`) draws `pending.prompt`
in a card with an empty options row, and `chat` already printed the same string as `Paused: …` — and
loner's conflict hands back zero options, so that card is the whole signal.

Renderer-side only. `PendingDecision.kind` is already the engine's mark of the mode, so the card header
reflects it instead of a kind→label table. Drop the duplicate `Paused:` echo, point the composer at the
open question, reword loner's `conflict_prompt` to name the moves.

- ~35 added / ~12 removed, 4 files. No model, save or engine-API change.
- **Exit check:** `uv run aidm`, take a loner fight to a surviving exchange — one accent card reading
  `CONFLICT / the game is waiting on you`, no `Paused:` echo above it, composer prompting for an answer.
- **First, because:** cheapest, pure UI, and both L2 and L9 land on that same panel.

## Phase 1 — L2: death is a reserved trait plus one `kill` command

[docs/plans/L2-death-handling.md](docs/plans/L2-death-handling.md)

Nothing can remove or retire an entity — `world.entities` is append-only and no command has a
counterpart. Death is prose, so a killed rat keeps its sheet, its luck pool and its slot in the scene
forever.

Death is the reserved core trait `dead`, written by one core command `kill`, mirroring the reserved
`broken` trait 24XX already ships. A trait keeps the corpse referenceable, which deletion cannot.
`kill` does the whole cleanup in one call; one guard in `require_actor_here` covers every caller in both
engines. PC death reuses `consume_answer` and the existing restart button — no end-state type.

**The state-keeper agent is cut, not vaguely deferred.** The eval never reaches a death, so "the
director forgets" is unmeasured, and `world.pending_notes` is already a zero-token resolver→director
channel. Revive trigger, written into the report: the new `loner3e/finish-the-rat` eval case scoring
under ~70% over 9 repeats *after* `kill` ships and is named in the prompt.

- ~60 lines added, 8 files, nothing deleted. Saves survive; golden fixtures need `AIDM_GOLDEN_REGEN=1`.
- **Exit check:** `kill` the rat, then `roll_question` with it as `opponent_id` — the refusal names it as
  dead, its dagger is loose at the cloister, and the same call succeeded before the kill.
- **After L1, because:** a dead-player composer lockout is the same panel — one UI pass, not two.
  **Before L5, because:** L5 moves `describe`/`sheet_view`, and a corpse printing a full luck pool is a
  wart L5 should inherit already-decided.

## Phase 2 — L5: cut the ceremony an engine pays before it writes a rule

[docs/plans/L5-engine-shape-refactor.md](docs/plans/L5-engine-shape-refactor.md)

~85 lines of ceremony per engine before one mechanic exists: pack plumbing, the sheet's field list
written three times, two dispatch methods per decision kind. Fate
Condensed additionally cannot represent its own dice (`DiceEvent` forbids negative faces and demands
`kept in rolled`), cannot pause where it must (the pause point sits *between* commands, invoke happens
*inside* one), and shadows aspects in its own mechanics. Cairn's one hard stop is different:
`Engine.advancement` is mandatory and Cairn has no XP.

Three changes land, each judged by one criterion — does the Fate engine file get shorter: a `Decision`
base class, `rows()` on the sheet, a pack-creation base. A fourth, the `rule()` command constructor,
already landed in the pass noted above. Two more are
designed in the report but ship with their first user, because each adds branches nothing today
exercises: the signed/summed `DiceEvent` goes with L7 (Fate), optional `Engine.advancement` with L8
(Cairn). Plus 7 hard-coded lists killed by colocating or reflecting: the manual
`ENGINES` tuple, the outcome-name-keyed `HARM`/`HURT`, the thrice-written sheet fields, `_preview_lines`
shape-sniffing, `TAKE_THE_HIT`, `_BRIEF_LABELS`.

Explicitly not abstracted: no aspect system in core, no dice DSL, no advancement tiering, no plugin
protocol beyond discovery. The ledger counter stays per-engine, which is also why no `Sheet` field moves
and no save breaks.

- ~+90 / −240 remaining, net ≈ −150, across 9 files. Golden prompts move; turn-eval baseline needs one re-run.
- **Exit check:** `uv run pytest` green with fixtures regenerated, plus one live loner3e turn with the
  dice card unchanged.
- **Here, because:** it is the largest refactor and everything downstream is cheaper on the new shape.
  With its two deferred steps it touches no harness file, so it is independent of Phase 3 — but it still
  precedes L6/L7/L8, which are what it exists to make cheap.

## Phase 3 — L9 + L10: code mode learns to launch its own agent

[docs/plans/L9-ui-drives-claude-sdk.md](docs/plans/L9-ui-drives-claude-sdk.md) ·
[docs/plans/L10-other-harnesses.md](docs/plans/L10-other-harnesses.md)

Code mode has exactly one submode today: you run `claude` or `codex` yourself and `uv run aidm` polls
the save, because the agent's MCP server is a second process holding a second `Runtime`. That second
writer is also why the code-mode UI is read-only — `_offered_only` and `decision_panel` are disabled so
nothing races it. This phase adds the submode where the app launches the agent.

**Naming — one field, not two.** `harness: Literal["builtin", "external", "claude"]` is *who plays the
turn*: the app's own Director/Narrator roles, an agent you run yourself, or one the app launches.
`codex` and `opencode` are the next values. `code_mode` becomes `self.harness != "builtin"`, so all five
current readers keep working. Two fields would make `harness="builtin", agent="claude"` representable
and meaningless, needing a validator to reject it; one field makes it unrepresentable. Transport follows
the value in one place — the driver factory — and `GameView.viewing` becomes `harness == "external"`,
the one submode where a second process writes the save.

**The SDK earns its place on one reason.** The alternative — one subprocess driver reading JSONL
(`claude -p --output-format stream-json`, `codex exec --json`) — covers every agent with no new
dependency, and was weighed seriously. But out-of-process keeps the second writer, which is exactly what
forces `poll_save` and keeps the UI read-only. Only an in-process server shares the app's `Runtime` and
collapses to one writer under one `Harness.lock`. Secondary: the four CLIs share no JSONL vocabulary, so
"one driver" is one spawner plus a parser each, and for Claude the exec route hand-rolls the transport
and its control channel — more code than the dep it avoids. **Tripwire:** a live in-process failure
sends this phase back to exec.

The enabling find: `build_server()` (`harness/mcp.py:177`) already returns a real `mcp.server.Server`,
which is exactly what the SDK's `McpSdkServerConfig.instance` takes — the existing tool surface runs
in-process verbatim, no second schema. SDK API verified against `claude-agent-sdk` 0.2.144 via context7
and upstream source. The chat bubble needs no new code: `end_turn` commits, `chat()` draws it. The dev
tab gets one native `ui.log` fed from the message stream, with cost and tokens off `ResultMessage`.

**L10 is the config half of this phase, zero Python:** `opencode.json` at the repo root and a harness
table in the README, both under `harness=external`. pi is out of scope — its README states it does not
and will not support MCP; reaching aidm from pi needs an adapter, which is not config-level.

**Codex image generation is cut.** It works but is too slow and unreliable to sit inside a turn. Tried
and rejected — do not re-propose. This also removed the `MediaConfig.generate` flag the earlier draft
wanted: with no agent able to draw, it has zero users, and hand-placed art already displays untouched
because `Illustrator._draw` skips any scene whose file exists. Art is whatever the app draws, in every
submode.

- ~140 added / ~15 changed, one new file `harness/claude.py`, one new dep `claude-agent-sdk==0.2.144`,
  plus ~20 lines of config and README. One boundary flip: `FORBIDDEN["ui"]` currently bans
  `aidm.harness`; the flow becomes `app <- harness <- ui`.
- **Exit check:** under `HARNESS=claude`, open a game and type one action — `get_mcp_status()` lists
  exactly one connected `aidm` server and `saves/<slug>.json` advances one turn.
- **Watch:** whether `strict_mcp_config` really stops `.mcp.json` spawning a *second* aidm writer.
  Unverified until run live, and a duplicate writer is the one way this corrupts a save.
- **Do L9 and L10 in one pass** so the README mode table is written once.

## Phase 4 — I4: settings from the UI

[docs/plans/I4-settings-from-ui.md](docs/plans/I4-settings-from-ui.md)

`Settings` is a pydantic-settings `BaseSettings` (`config.py:108`) built once at the composition root
(`ui/app.py:213`). 50 leaves: 44 editable, 2 secret (write-only), 4 read-only paths. The mark is decided
by type — `SecretStr` → secret, `Path` → never — not by a name list.

Generated form, not hand-written: 44 leaves across 6 model classes, one recursive `model_fields` walk,
env key = `"__".join(path).upper()` which is pydantic-settings' own convention, so no mapping table. Six
widget branches by annotation. `.env` written with `dotenv.set_key` (python-dotenv already installed
transitively; verified it preserves comments, quoting and untouched keys). Nothing is written until
`Settings.model_validate` passes on the merged dump.

Restart is a banner, honestly. Skipped `os.execv` and NiceGUI reload — add execv when the manual step
annoys someone. An open game costs at most a turn in flight; every turn is committed in
`GameSession.commit`.

- ~140 added, 3 changed, one new file `ui/settings.py`, `python-dotenv` promoted to a direct dependency.
- **Secrets never reach the DOM:** the API-key input is created with `value=""` and `password=True` and
  is never populated from `get_secret_value()`. Blank means "leave the stored key alone", not "clear it".
- **Exit check:** `/settings`, switch `MEDIA__ENABLED` on, Save — `.env` gained the key with the existing
  API-key line and both comments intact; restart; scenes illustrate.
- **Last, because:** Phase 3 rewrites the `harness` literal, which this form renders as a select. The
  generated form absorbs that for free, but running it last means the field list is final.

---

## Cross-cutting

- **Edit collisions, in order:** `config.py` (Phase 3, Phase 4) and `ui/game.py` (Phases 0, 1, 3). With
  L5's two deferred steps, no two phases share a harness file.
- **Golden fixtures move twice** — Phase 1 (new command + prompt line) and Phase 2 (the `state:` block).
  Both need `AIDM_GOLDEN_REGEN=1`; Phase 2 additionally needs one turn-eval re-run to re-baseline.
- **Saves survive every phase.** Phase 1 adds an ordinary `Trait`, Phase 2 moves no `Sheet` field. Stale
  saves stay intentionally invalid — no version field, no conversion path.
- **Nothing here needs a new LLM role.** Phase 1 considered one and cut it on absent evidence.
- **Tests are not a deliverable.** Each phase corrects the minimum needed to stay green; no phase adds a
  suite. The exit checks above are the real proof.

## Not in this plan

L3 (eval consistency), L4 (few-shot, gated on L3), L6 (loner/24XX SRD compliance), L7 (Fate), L8
(Cairn), L11 (sound), L12 (RAG, leaning never), I1, I2, I3, I5.

L6 belongs immediately after Phase 2: the compliance pass should land on the new engine shape, and
before a third engine, so the drastic change hits the base shape once. L7 and L8 follow it — Phase 2
exists to make them cheap.
