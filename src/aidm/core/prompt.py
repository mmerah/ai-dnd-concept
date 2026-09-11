from collections.abc import Iterable, Sequence

from aidm.core.play import Exchange, SceneRecord
from aidm.core.views import Pairs

SCENE_EXCHANGES = 20
WHOLE_SCENES = 2
TAIL_EXCHANGES = 3
INTERJECTED = "(a party member speaks, unprompted)"


def sections(parts: Pairs) -> str:
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def lines_of(parts: Iterable[str]) -> str:
    return "\n".join(parts) or "- (none)"


def sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def render_history(records: Sequence[SceneRecord]) -> str:
    if not any(record.exchanges for record in records):
        return "(the game has not started yet)"
    total = len(records)
    return "\n\n".join(_block(record, index, total) for index, record in enumerate(records))


def told_history(records: Sequence[SceneRecord]) -> str:
    """The recent blocks the master reads, without recaps: those are the worldsmith's."""
    recent = [record for record in records[-WHOLE_SCENES:] if record.exchanges]
    if not recent:
        return "(nothing yet)"
    return "\n\n".join(
        f"{_header(record)}\n\n{_told(record.exchanges[-SCENE_EXCHANGES:])}" for record in recent
    )


def _block(record: SceneRecord, index: int, total: int) -> str:
    header = _header(record)
    if index >= total - WHOLE_SCENES:
        body = _told(record.exchanges[-SCENE_EXCHANGES:])
    elif record.recap:
        body = f"what happened: {record.recap}"
    else:
        body = _told(record.exchanges[-TAIL_EXCHANGES:])
    return f"{header}\n\n{body}"


def _header(scene: SceneRecord) -> str:
    return f"SCENE: {scene.title}" + (f"\n{scene.focus}" if scene.focus else "")


def _told(exchanges: Sequence[Exchange]) -> str:
    return "\n\n".join(_entry(exchange) for exchange in exchanges) or "(nothing yet)"


def _entry(exchange: Exchange) -> str:
    if exchange.mark == "interjection":
        return f"{INTERJECTED}\n{exchange.transcript}"
    if exchange.mark:
        return exchange.transcript
    return f"> {exchange.prompt}\n{exchange.transcript}"
