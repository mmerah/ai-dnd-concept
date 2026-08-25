# I4: Settings from the UI — write .env, restart

`Settings` is a pydantic-settings `BaseSettings` (`src/aidm/config.py:108`, `env_file=".env"`, `env_nested_delimiter="__"`).
Built once by `load_settings()` (`src/aidm/config.py:152`) at the composition root `Runtime(load_settings())` (`src/aidm/ui/app.py:213`); `harness/mcp.py:220` builds its own in a separate process.
Readers: `llm.py:107` (`settings.role`), `app/runtime.py`, `turn/run.py`, `authoring/run.py`, `ui/`.

## Editable fields

52 leaves. The mark is decided by type, not by a name list: `SecretStr` -> secret, `Path` -> never, everything else -> editable.

| Group (config.py) | Leaves | Mark |
| --- | --- | --- |
| `Providers.openrouter/local.base_url` (:18) | 2 | editable |
| `Providers.openrouter/local.api_key` (:19) | 2 | **secret** — write-only, never read back into the DOM |
| `Roles.{director,narrator,advisor,scenario_creator}` x `RoleConfig` (:22): `provider, model, retries, max_tokens, reasoning_effort, temperature, max_input_tokens` | 28 | editable |
| `MediaConfig` (:34): `enabled, provider, model, scene_ratio, icon_ratio, timeout, max_references, style` | 8 | editable |
| `TurnConfig` (:49): `director_request_limit, chars_per_token` | 2 | editable |
| `AuthoringConfig` (:56): `request_limit, starter_character, worked_example, growth_frontier, source_max_chars` | 5 | editable |
| `Settings.harness` (:122) | 1 | editable |
| `Settings.{saves,scenarios,characters,packs}_dir` (:123) | 4 | **never** — not rendered at all; repointing hides the save library from a running app |

No field carries a `description`, so labels come from the field name; `Ge`/`Le` constraints are not mirrored into widgets — re-validation on Save reports them.

## Approach

**Generated, not hand-written.** 46 editable leaves across 6 model classes: a hand-written form is the maintenance nightmare, and a name-keyed whitelist is the table the maintainer rejects.
One recursive walk over `type(model).model_fields` yields `(path, FieldInfo, value)`; the env key is `"__".join(path).upper()`, which is exactly pydantic-settings' own convention — no mapping table.
Widget per annotation (strip `| None` first): `SecretStr`->`ui.input(password=True)` with a "set"/"not set" placeholder and empty value, `bool`->`ui.switch`, `Literal`->`ui.select(get_args)`, `int|float`->`ui.number`, `str` (incl. `Slug`)->`ui.input`. The four `Path` leaves are **skipped, not
rendered read-only** — a widget for a value this plan forbids changing is ceremony.
Nested `BaseModel` recurses inside a `ui.expansion` named for the field. Five branches, ~100 lines.

**.env writer:** `dotenv.set_key(".env", key, value)`. python-dotenv 1.2.3 is already installed as a pydantic-settings dependency; verified it preserves comments and untouched keys, quotes correctly, handles multi-line (`media.style`), and creates the file if absent. Do not hand-roll a parser.

**Validate before writing:** merge changed values (raw strings) into `settings.model_dump()` and call `Settings.model_validate(merged)` — verified it round-trips (SecretStr and Path survive python-mode dump) and rejects `max_tokens=0` and a missing API key via `_keys_present`. Nothing is written unless it validates.

**Restart:** a banner. Save writes only changed keys, then shows "Saved N keys to .env — restart `uv run aidm` to apply".
Skipped: `os.execv` self-restart and NiceGUI `reload=True`. Add execv (`os.execv(sys.executable, [sys.executable, "-m", "aidm.ui"])`; `src/aidm/ui/__main__.py` already exists) when the manual step actually annoys someone.
Open sessions: `Runtime._sessions` is in-process only and every turn is committed to disk in `GameSession.commit`, so a restart costs at most a turn in flight; resuming is re-navigating from the launcher. The code-mode MCP server re-reads `.env` on its next start.

## Steps

1. `pyproject.toml`: add `"python-dotenv==1.2.3"` to `dependencies` — currently transitive.
2. New `src/aidm/ui/settings.py` (~110 lines):
   - `_leaves(model, path=()) -> Iterator[tuple[tuple[str,...], FieldInfo, object]]` — recurse on `BaseModel` values.
   - `_widget(key, field, value) -> ui.element` — the five-branch match above; `_leaves` skips `Path`.
   - `settings_page(settings: Settings)` — `page_header("Settings")`, one `ui.expansion` per nested model, `boxes: dict[str, ui.element]`, then `ui.button("Save", on_click=_save)`.
   - `_save` — collect `{key: str(value)}` where the widget differs from the loaded value (secret: only if non-empty), merge into `settings.model_dump()`, `Settings.model_validate`, then `set_key` per key; `ui.notify` the ValidationError on failure.
3. `src/aidm/ui/app.py`: register `@ui.page("/settings")` in `_register_pages` beside `/create-scenario`, calling `settings_page(runtime.settings)`.
4. `src/aidm/ui/app.py:28` header: `ui.button(icon="settings", on_click=lambda: ui.navigate.to("/settings")).props("flat color=white round")` before the existing `ui.space()`.
5. `README.md:52`: one line — the `.env` keys are editable at `/settings`, applied on restart.
6. One check in `tests/core/test_config.py`: assert `("ROLES","DIRECTOR","MAX_TOKENS")` appears in the upper-cased paths from `_leaves(Settings.model_validate({}))`, and that no widget value stringifies a `SecretStr`.

## Risk / size

~130 lines added, 3 changed, 0 deleted.
Clobbering `.env`: `set_key` rewrites one key in place and leaves comments and untouched keys alone, and nothing is written until `Settings.model_validate` passes.
Secrets in the DOM: the API-key input is created with `value=""` and `password=True` and is never populated from `api_key.get_secret_value()`; a blank box means "leave the stored key alone", not "clear it", and the placeholder only says whether a key is set.
`.env` resolves relative to CWD exactly as pydantic-settings resolves it, so a UI launched elsewhere writes where it reads.
Check: `uv run aidm`, open `/settings`, switch `MEDIA__ENABLED` on, Save, confirm `.env` gained the key with the existing API-key line and both comments intact, restart, scenes illustrate.
