from pydantic import Field

from ..utils.models import Frozen


class AdvancementStatus(Frozen):
    headline: str
    detail: tuple[str, ...] = ()
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
