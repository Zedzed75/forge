"""Interview for the Ansible domain (`forge_interview` hook).

Port of `ansible_forge.prompts.flow` (MIGRATION.md §3). Two substantive
differences from the original tool, both caused by the shared `service:` block:

* the project identity and the list of environments are no longer asked for
  here — the core has already obtained them (`forge.interview.service_flow`)
  and passes them in `service`;
* the output is not a model but **the `ansible:` section of forge.yml**, that
  is, a dict of simple types, directly serialisable to YAML and validatable by
  `AnsibleSpec`.

What is left here is what Ansible alone knows: OS family, SSH connection, host
groups, per-environment inventory, role options.

The validators in this module return `None | str` (the prompter's `Validator`
contract), where those in `names.py` raise `ValueError` for pydantic: both say
the same thing, but one is displayed under a field and the other stops the
validation of the model. An answer accepted here can never be refused later.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.ansible.catalog.registry import get_role, role_names
from forge.plugins.ansible.interview_roles import ask_role_options
from forge.plugins.ansible.names import (
    GROUP_NAME_RE,
    HOST_NAME_RE,
    MAX_PORT,
    MIN_PORT,
    RESERVED_GROUP_NAMES,
    USER_NAME_RE,
)
from forge.plugins.ansible.spec import OSFamily
from forge.spec.service import Environment, ServiceSpec

#: Group offered by default for the first question of the loop.
DEFAULT_GROUP = "webservers"

#: Beyond that, declaring the machines by hand in forge.yml is faster.
MAX_HOSTS_PER_GROUP = 100

#: Label of a domain name, used to validate a host address.
_FQDN_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Run the Ansible interview and return the `ansible:` section of forge.yml.

    Returns `None` when the user declares zero groups: without a group there is
    neither inventory nor playbook, so nothing to generate. The core has
    already asked *which* domains to generate; this interview does not ask
    again.
    """
    connection = _ask_connection(prompter)
    groups = _ask_groups(prompter)
    if not groups:
        prompter.note("No group declared: the Ansible domain is not generated.")
        return None

    hosts = _ask_hosts(prompter, service.environments, groups)
    roles = _ask_roles(prompter, groups)
    options = _ask_generation_options(prompter)

    # The key order is that of the AnsibleSpec fields: forge.yml then reads in
    # the same order as the model that validates it.
    return {
        **connection,
        "options": options,
        "groups": groups,
        "hosts": hosts,
        "roles": roles,
    }


def _ask_connection(prompter: Prompter) -> dict[str, Any]:
    """OS family and SSH connection settings shared by every machine."""
    prompter.note("── Target machines and connection ──")
    os_family = prompter.select(
        "Target operating system family",
        [
            (OSFamily.DEBIAN.value, "Debian / Ubuntu"),
            (OSFamily.REDHAT.value, "RHEL / Rocky / Fedora"),
        ],
        default=OSFamily.DEBIAN.value,
    )
    remote_user = prompter.text(
        "SSH account used by Ansible",
        default="ansible",
        validate=lambda value: _check_pattern(
            value, USER_NAME_RE, "SSH user name", "Expected: a POSIX account name."
        ),
    )
    ssh_port = prompter.text(
        "SSH port of the target machines",
        default="22",
        validate=_validate_port,
    )
    become = prompter.confirm("Use sudo (privilege escalation)?", default=True)
    python_interpreter = prompter.text("Remote Python interpreter", default="auto_silent")

    return {
        "os_family": os_family,
        "remote_user": remote_user.strip(),
        "become": become,
        "ssh_port": int(ssh_port),
        "python_interpreter": python_interpreter.strip(),
    }


def _ask_groups(prompter: Prompter) -> list[dict[str, Any]]:
    """Host groups and the roles applied to each of them.

    An empty list means "no Ansible project": it is the only way to decline the
    domain once the interview has started, hence the first name being optional.
    """
    prompter.note("── Machine groups ──")
    prompter.note(
        "An Ansible project describes at least one machine group; "
        "leaving the first name empty gives up the Ansible domain."
    )
    catalog = [(name, f"{name} — {get_role(name).summary}") for name in role_names()]
    groups: list[dict[str, Any]] = []
    taken: set[str] = set()

    while True:
        first = not groups
        name = prompter.text(
            f"Name of group #{len(groups) + 1}",
            default=DEFAULT_GROUP if first else "",
            validate=lambda value, taken=taken, first=first: _validate_group_name(
                value, taken, allow_empty=first
            ),
        ).strip()
        if not name:
            return groups

        description = prompter.text(f"Description of group '{name}'", default="").strip()
        roles = prompter.checkbox(
            f"Roles applied to group '{name}'", catalog, default=["common"]
        )
        if not roles:
            prompter.note("No role chosen: the 'common' role is applied by default.")
            roles = ["common"]

        group: dict[str, Any] = {"name": name}
        if description:
            group["description"] = description
        group["roles"] = list(roles)
        groups.append(group)
        taken.add(name)

        if not prompter.confirm("Add another group?", default=False):
            return groups


def _ask_hosts(
    prompter: Prompter, environments: list[Environment], groups: list[dict[str, Any]]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Machines of each group, environment by environment.

    The environments come from the `service:` block: the interview does not ask
    for them again, it merely walks them in promotion order.
    """
    prompter.note("── Machines ──")
    detailed = prompter.confirm(
        "Specify a per-machine SSH port or account?", default=False
    )
    hosts: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for environment in environments:
        hosts[environment.name] = {}
        for group in groups:
            entries = _ask_hosts_of_group(prompter, environment, group["name"], detailed)
            if entries:
                hosts[environment.name][group["name"]] = entries
    return hosts


def _ask_hosts_of_group(
    prompter: Prompter, environment: Environment, group: str, detailed: bool
) -> list[dict[str, Any]]:
    """Machines of one group in a given environment."""
    env = environment.name
    count = prompter.text(
        f"Number of machines in '{group}' for environment '{env}'",
        default="1",
        validate=_validate_count,
    )
    entries: list[dict[str, Any]] = []
    taken: set[str] = set()

    for index in range(1, int(count) + 1):
        name = prompter.text(
            f"  Name of machine {index}/{count} ({group}/{env})",
            default=f"{group}-{env}-{index:02d}",
            validate=lambda value, taken=taken: _validate_host_name(value, taken),
        ).strip()
        taken.add(name)
        entry: dict[str, Any] = {
            "name": name,
            # New compared to the legacy tool: when the environment declares a
            # domain in the `service:` block, the default address follows from it.
            "ansible_host": prompter.text(
                f"  IP address or domain name of '{name}'",
                default=f"{name}.{environment.domain}" if environment.domain else "",
                validate=_validate_host_address,
            ).strip(),
        }
        if detailed:
            port = prompter.text(
                f"  SSH port of '{name}' (empty = project value)",
                default="",
                validate=lambda value: None if not value.strip() else _validate_port(value),
            )
            user = prompter.text(
                f"  SSH account of '{name}' (empty = project value)", default=""
            )
            if port.strip():
                entry["ansible_port"] = int(port)
            if user.strip():
                entry["ansible_user"] = user.strip()
        entries.append(entry)
    return entries


def _ask_roles(prompter: Prompter, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Options of the roles actually applied, in catalog order."""
    used = {role for group in groups for role in group["roles"]}
    ordered = [name for name in role_names() if name in used]
    if not ordered:
        return []

    prompter.note("── Role settings ──")
    if not prompter.confirm(
        "Customise the role settings? (no = documented default values)",
        default=False,
    ):
        # `AnsibleSpec` fills the missing options with the catalog defaults:
        # naming the roles is enough, the output stays complete.
        return [{"name": name} for name in ordered]

    return [
        {"name": name, "options": ask_role_options(prompter, get_role(name))} for name in ordered
    ]


def _ask_generation_options(prompter: Prompter) -> dict[str, Any]:
    """Side files to produce in addition to the roles and the inventory."""
    prompter.note("── Generation options ──")
    return {
        "use_vault": prompter.confirm(
            "Generate the vault file templates (secrets)?", default=True
        ),
        "write_lint_config": prompter.confirm(
            "Generate .gitignore, .yamllint and .ansible-lint?", default=True
        ),
        "write_ci": prompter.confirm(
            "Generate a GitHub Actions workflow running ansible-lint?", default=False
        ),
    }


# -- input validators -------------------------------------------------------


def _check_pattern(value: str, pattern: re.Pattern[str], label: str, hint: str) -> str | None:
    """Validate a string against a regular expression."""
    if pattern.match(value.strip()):
        return None
    return f"Invalid {label}: '{value}'. {hint}"


def _validate_port(value: str) -> str | None:
    """Validate a TCP port entry."""
    try:
        parsed = int(value.strip())
    except ValueError:
        return f"An integer is expected, got: '{value}'."
    if not MIN_PORT <= parsed <= MAX_PORT:
        return f"The port must be between {MIN_PORT} and {MAX_PORT}, got: {parsed}."
    return None


def _validate_count(value: str) -> str | None:
    """Validate a machine count."""
    if not value.strip().isdigit():
        return f"A zero or positive integer is expected, got: '{value}'."
    if int(value) > MAX_HOSTS_PER_GROUP:
        return (
            f"Beyond {MAX_HOSTS_PER_GROUP} machines, declare them directly "
            "in forge.yml."
        )
    return None


def _validate_group_name(value: str, taken: set[str], *, allow_empty: bool = False) -> str | None:
    """Validate a group name, uniqueness and reserved names included."""
    value = value.strip()
    if allow_empty and not value:
        return None
    error = _check_pattern(
        value,
        GROUP_NAME_RE,
        "group name",
        "Expected: lowercase letters, digits and '_' (the hyphen is forbidden).",
    )
    if error:
        return error
    if value in RESERVED_GROUP_NAMES:
        return f"The name '{value}' is reserved by Ansible."
    if value in taken:
        return f"The group '{value}' is already declared."
    return None


def _validate_host_name(value: str, taken: set[str]) -> str | None:
    """Validate a machine name, uniqueness included."""
    value = value.strip()
    error = _check_pattern(
        value,
        HOST_NAME_RE,
        "host name",
        "Expected: lowercase letters, digits, '.', '-' and '_'.",
    )
    if error:
        return error
    if value in taken:
        return f"The machine '{value}' is already declared in this environment."
    return None


def _validate_host_address(value: str) -> str | None:
    """Validate a host address: IP address or domain name."""
    value = value.strip()
    if not value:
        return "The host address is mandatory (IP address or domain name)."
    if _is_ip(value) or _is_fqdn(value):
        return None
    return f"'{value}' is neither an IP address nor a valid domain name."


def _is_ip(value: str) -> bool:
    """Tell whether the string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_fqdn(value: str) -> bool:
    """Tell whether the string is a syntactically valid domain name."""
    if not value or len(value) > 253:
        return False
    labels = value.rstrip(".").split(".")
    return all(_FQDN_LABEL_RE.match(label) for label in labels)
