import json
import os
from difflib import unified_diff
from itertools import islice
from pathlib import Path

ENCODING = "utf-8"
FIXTURES = Path(__file__).parent / "fixtures"
REGENERATE = os.environ.get("AIDM_GOLDEN_REGEN") == "1"
DIFF_LINES = 40


def golden(path: Path, actual: str) -> None:
    """Regenerate fixtures only when explicitly enabled, and never report that run as passing."""
    if REGENERATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding=ENCODING)
        return
    if not path.is_file():
        raise AssertionError(f"no fixture at {path}: regenerate with AIDM_GOLDEN_REGEN=1")
    expected = path.read_text(encoding=ENCODING)
    if actual != expected:
        raise AssertionError(f"{path} drifted from its fixture:\n{_diff(expected, actual)}")


def golden_json(path: Path, actual: object) -> None:
    golden(path, json.dumps(actual, indent=2, ensure_ascii=False) + "\n")


def _diff(expected: str, actual: str) -> str:
    lines = unified_diff(
        expected.splitlines(), actual.splitlines(), "fixture", "actual", lineterm="", n=1
    )
    return "\n".join(islice(lines, DIFF_LINES))
