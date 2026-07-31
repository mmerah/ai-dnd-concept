from dataclasses import dataclass, field

from .bootstrap import Composition
from .session_model import Session


@dataclass(frozen=True, slots=True)
class _RegisteredSession:
    scenario_name: str
    character_name: str
    session: Session


@dataclass(slots=True)
class SessionRegistry:
    composition: Composition
    _sessions: dict[str, _RegisteredSession] = field(default_factory=dict)

    def session(self, slug: str, scenario_name: str, character_name: str) -> Session:
        held = self._sessions.get(slug)
        if held is not None:
            if (held.scenario_name, held.character_name) != (
                scenario_name,
                character_name,
            ):
                raise ValueError(
                    f"open session {slug!r} uses "
                    f"{held.scenario_name!r}/{held.character_name!r}, not "
                    f"{scenario_name!r}/{character_name!r}"
                )
            return held.session
        application = self.composition.application(slug, scenario_name, character_name)
        created = Session(
            app=application,
            advancement=self.composition.advancement_ui(application.engine),
        )
        self._sessions[slug] = _RegisteredSession(
            scenario_name=scenario_name,
            character_name=character_name,
            session=created,
        )
        return created
