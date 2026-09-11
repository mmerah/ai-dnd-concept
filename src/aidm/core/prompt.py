from collections.abc import Iterable, Sequence

from aidm.core.play import Chapter, Exchange

type Pairs = tuple[tuple[str, str], ...]

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


def render_history(log: Sequence[Chapter]) -> str:
    if not any(chapter.exchanges for chapter in log):
        return "(the game has not started yet)"
    total = len(log)
    return "\n\n".join(_block(chapter, index, total) for index, chapter in enumerate(log))


def told_history(log: Sequence[Chapter]) -> str:
    """The recent blocks the master reads, without recaps: those are the worldsmith's."""
    recent = [chapter for chapter in log[-WHOLE_SCENES:] if chapter.exchanges]
    if not recent:
        return "(nothing yet)"
    return "\n\n".join(
        f"{_header(chapter)}\n\n{_told(chapter.exchanges[-SCENE_EXCHANGES:])}" for chapter in recent
    )


def _block(chapter: Chapter, index: int, total: int) -> str:
    header = _header(chapter)
    if index >= total - WHOLE_SCENES:
        body = _told(chapter.exchanges[-SCENE_EXCHANGES:])
    elif chapter.recap:
        body = f"what happened: {chapter.recap}"
    else:
        body = _told(chapter.exchanges[-TAIL_EXCHANGES:])
    return f"{header}\n\n{body}"


def _header(chapter: Chapter) -> str:
    return f"SCENE: {chapter.title}" + (f"\n{chapter.focus}" if chapter.focus else "")


def _told(exchanges: Sequence[Exchange]) -> str:
    return "\n\n".join(_entry(exchange) for exchange in exchanges) or "(nothing yet)"


def _entry(exchange: Exchange) -> str:
    if exchange.mark == "interjection":
        return f"{INTERJECTED}\n{exchange.transcript}"
    if exchange.mark:
        return exchange.transcript
    return f"> {exchange.words}\n{exchange.transcript}"
