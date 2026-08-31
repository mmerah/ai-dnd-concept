import logging
from asyncio import Lock
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256

from pydantic import Field, ValidationError

from aidm.config import Role, RoleConfig, Settings
from aidm.core.entities import Frozen
from aidm.core.io import ENCODING, FileStore, write_text

from .spawn import RunResult, Spawner

LOGGER = logging.getLogger(__name__)


class SessionEntry(Frozen):
    fingerprint: str
    session: str


class SessionFile(Frozen):
    roles: dict[Role, SessionEntry] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Conversations:
    """A conversation is disposable memory beside the save, never state."""

    spawner: Spawner
    store: FileStore
    settings: Settings
    _locks: dict[tuple[str, Role], Lock] = field(default_factory=dict, repr=False)

    async def ask(
        self,
        slug: str,
        role: Role,
        instructions: str,
        prompt: str,
        session: str | None = None,
        cold_retry: Callable[[], bool] = lambda: True,
    ) -> RunResult:
        """Once the role has applied anything, a cold retry would apply it twice."""
        stamp = fingerprint(self.settings.roles.for_name(role), instructions)
        async with self._locks.setdefault((slug, role), Lock()):
            held = session if session is not None else self._held(slug, role, stamp)
            while True:
                try:
                    spoken = await self.spawner.run(role, prompt, held)
                except (OSError, ValueError) as failed:
                    self._write(slug, role, stamp, None)
                    # A named session means the prompt is a continuation, which says nothing cold.
                    if held is None or session is not None or not cold_retry():
                        raise
                    LOGGER.warning("the resumed %s failed, starting cold: %s", role, failed)
                    held = None
                    continue
                self._write(slug, role, stamp, spoken.session)
                return spoken

    def forget(self, slug: str) -> None:
        self.store.sessions_path(slug).unlink(missing_ok=True)

    def _held(self, slug: str, role: Role, stamp: str) -> str | None:
        entry = self._read(slug).roles.get(role)
        return entry.session if entry is not None and entry.fingerprint == stamp else None

    def _read(self, slug: str) -> SessionFile:
        path = self.store.sessions_path(slug)
        if not path.is_file():
            return SessionFile()
        try:
            return SessionFile.model_validate_json(path.read_text(encoding=ENCODING))
        except (OSError, ValidationError) as unreadable:
            # Memory, not state: an unreadable sidecar is thrown away rather than repaired.
            LOGGER.warning("discarding the session file for %r: %s", slug, unreadable)
            path.unlink(missing_ok=True)
            return SessionFile()

    def _write(self, slug: str, role: Role, stamp: str, session: str | None) -> None:
        roles = dict(self._read(slug).roles)
        if session is None:
            _ = roles.pop(role, None)
        else:
            roles[role] = SessionEntry(fingerprint=stamp, session=session)
        try:
            write_text(self.store.sessions_path(slug), SessionFile(roles=roles).model_dump_json())
        except OSError as unwritable:
            # A sidecar that will not write costs a cold start, never the turn that just played.
            LOGGER.warning("the session file for %r went unwritten: %s", slug, unwritable)


def fingerprint(config: RoleConfig, instructions: str) -> str:
    """A change to any of it makes the conversation it started wrong."""
    told = f"{config.provider}|{config.model}|{config.effort}|{instructions}"
    return sha256(told.encode(ENCODING)).hexdigest()
