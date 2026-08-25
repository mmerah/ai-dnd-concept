# L10: other harnesses, folded into L9's external submode

**Zero lines of Python.** This is one JSON file and a README table.

L10 is not its own phase: it is the config-level half of L9, covering code mode's `external`
submode (L9 owns that naming) — the user runs a coding CLI in their own terminal while `uv run aidm`
is the save-polling viewer (`ui/game.py:391 poll_save`). Such a harness needs two things: somewhere
to register one stdio command (`uv run python -m aidm.harness.mcp`, refused unless `HARNESS` is a code-mode value (L9 renames today's `code` to `external`)),
and somewhere it finds `SKILL.md`. Everything under that MCP boundary is already harness-agnostic —
tools, rules text, saves, viewer — and `.agents/skills/` is already the single skills source, with
`.claude/skills/*` as committed symlinks into it (also what L9's SDK driver reads via
`setting_sources`).

## Per-harness surface

| harness | config file | MCP registration | skills discovery | verified? |
|---|---|---|---|---|
| claude code | `.mcp.json`, `.claude/settings.local.json` (`enabledMcpjsonServers`) | done | `.claude/skills/*` → symlinks to `.agents/skills` | yes, in repo |
| codex | `.codex/config.toml` (`[mcp_servers.aidm]`) | done | `.agents/skills`, scanned cwd→repo root | yes (docs + repo) |
| opencode | `opencode.json` at repo root: `"mcp": {"aidm": {"type": "local", "command": [...], "enabled": true}}` | to add, ~8 lines | reads both `.agents/skills/*/SKILL.md` and `.claude/skills` | docs verified, never run here |
| pi | `.pi/settings.json`, reads `AGENTS.md`, skills from `.agents/skills` | **none — upstream: "No MCP."** | would work | verified from pi's README |

pi is out of scope, not deferred: its README states it does not and will not support MCP. Reaching
aidm from pi would mean a third-party adapter or a new CLI over `Harness`, neither of which is
config-level. Its skills and `AGENTS.md` already work here, so the day pi matters it is a README line.

## Codex images: given up

Codex can generate images, but too slowly and too unreliably to sit inside a turn. Tried and
rejected — do not re-propose it. Media stays the app's own OpenRouter path (`app/media.py`).

## Approach

- **Python: none.** The earlier draft proposed a `MediaConfig.generate` flag so the viewer could
  display art an external agent drew without buying any itself. With no agent able to draw, that
  flag has zero users: art placed by hand is already shown untouched, because `Illustrator._draw`
  skips any scene whose file exists (`media.py:_existing`). Cut.
- **Config: ~8 lines.** `opencode.json` at the repo root, `$schema` plus the four `mcp.aidm` keys.
- **Docs: ~12 lines.** The table above in README's code-mode section, and pi's exclusion.

## Steps

1. `opencode.json` — new, at the repo root, mirroring `.codex/config.toml`'s command and args.
2. `README.md` — under code mode: the harness/config-file table, and one line that pi is out.
3. Nothing in `.agents/skills/` — codex, opencode and pi all read it as it stands.

## Risk / size

An hour, all prose. Nothing here can break claude code: `opencode.json` is inert to it, and no
existing file changes except `README.md`. The one unverified claim is opencode's config shape (from
its docs; never run against this repo) — `opencode` starting and listing the `aidm` tools is the
whole check. Nothing blocks folding this into L9's phase; do it in the same pass as L9's README
paragraph so the mode table is written once.
