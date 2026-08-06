import pytest
from golden_test_support import REGENERATE


def pytest_sessionfinish(session: pytest.Session) -> None:
    """A regenerating run rewrites the golden fixtures, so it can never also check them: an
    `AIDM_GOLDEN_REGEN` left exported in a shell would turn every lock into a rubber stamp."""
    if REGENERATE:
        print("\nAIDM_GOLDEN_REGEN was set: fixtures were rewritten, nothing was checked.")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
