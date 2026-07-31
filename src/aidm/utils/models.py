from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def __hash__(self) -> int:
        raise TypeError(f"unhashable type: {type(self).__name__!r}")


class Mutable(BaseModel):
    """State a resolution mutates in place; `commit` revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")
