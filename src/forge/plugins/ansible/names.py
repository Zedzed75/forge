"""Naming rules specific to Ansible.

Port of the **domain** part of `ansible_forge.validation` (MIGRATION.md §3):
`find_duplicates` and the pattern check moved up into the core
(`forge.spec.names`); these regexes stay here because they describe what Ansible
accepts, not what forge accepts.
"""

from __future__ import annotations

import re

#: Environment name: no hyphen, it serves as a directory name and a group name.
ENV_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

#: Ansible group name: hyphens are forbidden in it.
GROUP_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")

#: Inventory host name: hyphens and dots allowed.
HOST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

#: POSIX system account name.
USER_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

#: Ansible variable name.
VAR_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Group names reserved by Ansible, forbidden as a user group.
RESERVED_GROUP_NAMES = frozenset({"all", "ungrouped", "local"})

#: Bounds of a TCP port.
MIN_PORT = 1
MAX_PORT = 65535


def check_var_names(variables: dict[str, object], context: str) -> dict[str, object]:
    """Validate the names of the free-form variables, or raise `ValueError`.

    `context` locates the error for the user: "group_vars", "host_vars" or
    `inventories/<env>/group_vars/<scope>`.
    """
    for name in variables:
        if not VAR_NAME_RE.match(name):
            raise ValueError(
                f"Invalid variable name in {context}: '{name}'. Expected: lowercase "
                "letters, digits and underscores, starting with a letter or an "
                "underscore."
            )
    return variables
