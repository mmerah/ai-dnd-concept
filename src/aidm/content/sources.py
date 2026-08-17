from dataclasses import dataclass
from typing import Literal, Protocol

type ExpansionPolicy = Literal["closed", "grounded", "generative"]


class CanonSource(Protocol):
    """What may exist beyond the state already materialized."""

    def context(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PremiseSource:
    """A scenario's own words: its `source.md` when it ships one, else the premise it was authored
    from."""

    text: str

    def context(self) -> str:
        return self.text
