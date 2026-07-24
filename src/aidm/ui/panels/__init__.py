"""The panels the page composes. One module per panel; the trace is the point of the app."""

from .chat import chat
from .roles import role_badges
from .state import state_panel
from .trace import trace_panel

__all__ = ["chat", "role_badges", "state_panel", "trace_panel"]
