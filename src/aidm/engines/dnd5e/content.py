from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated

from pydantic import Field, TypeAdapter
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from aidm.engines.loader import engine_text
from aidm.state.packs import (
    CollectionName,
    Content,
    ContentMiss,
    ContentRef,
    FactSchema,
    Record,
    fact_line,
    load,
    parse_ref,
)

ENGINE_DIR = Path(__file__).parent
# Collections whose int facts land on the sheet of any entity that refs a record in them.
PROJECTING: tuple[CollectionName, ...] = ("classes", "races", "monsters")


# `spec.json`: collection name -> the facts every record in it must carry (empty: no requirement).
_SPEC: TypeAdapter[dict[CollectionName, FactSchema]] = TypeAdapter(dict[CollectionName, FactSchema])


def pack_format() -> Mapping[CollectionName, FactSchema]:
    return _SPEC.validate_json(engine_text(ENGINE_DIR / "spec.json"))


def load_content(pack_paths: Sequence[Path] | None = None) -> Content:
    known = pack_format()
    if unknown := sorted(set(PROJECTING) - set(known)):
        raise ValueError(f"projecting names no such collection: {unknown}")
    own = (ENGINE_DIR / "packs").iterdir()  # no guard: this engine ships its packs
    packs = pack_paths or sorted(path for path in own if path.is_dir())
    return load(tuple(packs), known)


def lookup(content: Content, ref: ContentRef) -> Record | None:
    found = content.record(ref)
    return None if isinstance(found, ContentMiss) else found


def director_toolset(content: Content) -> FunctionToolset[object]:
    def read_content(
        ref: Annotated[
            str, Field(description="A content ref written `pack/collection/index`, as shown.")
        ],
    ) -> str:
        """Read the rules text of one content record.

        Use before planning from a spell, feature, or monster action whose wording you cannot
        quote. It reads canon and changes nothing.
        """
        try:
            reference = parse_ref(ref)
        except ValueError as malformed:
            raise ModelRetry(str(malformed)) from malformed
        found = content.record(reference)
        if isinstance(found, ContentMiss):
            raise ModelRetry(found.summary)
        return _record_text(found, ref)

    return FunctionToolset[object]([read_content])


def _record_text(record: Record, ref: str) -> str:
    rendered = (fact_line(k, v, ladder_full=True) for k, v in sorted(record.facts.items()))
    # Values carry commas of their own ("1d4+2 piercing"), so only a semicolon separates facts.
    facts = "; ".join(line for line in rendered if line is not None)
    options = ", ".join(str(option) for option in record.options)
    lines = [
        f"{record.name} [{ref}]",
        *([f"facts: {facts}"] if facts else []),
        *([f"tags: {', '.join(record.tags)}"] if record.tags else []),
        *([f"choose {record.choose} of: {options}"] if options else []),
        *([record.text] if record.text else []),
    ]
    return "\n".join(lines)
