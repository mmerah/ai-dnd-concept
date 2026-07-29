"""The one thing that pins `Roles`' field names to the `Role` literal: every role must resolve."""

from aidm.config import RoleConfig, settings
from aidm.domain.models.base import ROLES


def test_every_role_resolves_to_a_config() -> None:
    for role in ROLES:
        assert isinstance(settings().roles.for_role(role), RoleConfig)
