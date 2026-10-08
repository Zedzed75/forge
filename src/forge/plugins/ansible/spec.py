"""The `ansible:` section of forge.yml.

Port of `ansible_forge.models.spec` (MIGRATION.md §3). The identity of the
project — name, description, author, list of environments — moved up into the
core's shared `service:` block; what remains here describes **how Ansible talks
to the machines**: OS family, remote account, groups, hosts, roles.

Two normalisations of the legacy tool are kept as they are, because they make a
partial specification equivalent to a complete one — and therefore the rendering
reproducible:

* missing role options take the catalogue default, and the dict is reordered
  according to the declaration order of the options;
* a role applied by a group but absent from `roles:` is added with its defaults,
  then the whole list is sorted into the frozen order of the catalogue.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.ansible.catalog.registry import (
    role_names,
    sort_roles,
    validate_options,
)
from forge.plugins.ansible.names import (
    GROUP_NAME_RE,
    HOST_NAME_RE,
    MAX_PORT,
    MIN_PORT,
    RESERVED_GROUP_NAMES,
    check_var_names,
)
from forge.spec.names import find_duplicates
from forge.spec.types import ForgeModel


class OSFamily(str, Enum):
    """Operating system family targeted by the project.

    It conditions the packages, the services and the configuration paths the
    generated roles use.
    """

    DEBIAN = "debian"
    REDHAT = "redhat"


class HostSpec(ForgeModel):
    """One inventory machine."""

    #: Inventory name of the machine; serves as the host_vars file name.
    name: str

    #: Address or resolvable name used for the SSH connection.
    ansible_host: str

    #: SSH port specific to this machine; absent = the project-wide value.
    ansible_port: int | None = None

    #: SSH account specific to this machine; absent = the project-wide value.
    ansible_user: str | None = None

    #: Free-form variables written into host_vars/<machine>.yml.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not HOST_NAME_RE.match(value):
            raise ValueError(
                f"Invalid host name: '{value}'. Expected: lowercase letters, digits, "
                "dots, hyphens and underscores."
            )
        return value

    @field_validator("ansible_port")
    @classmethod
    def _valid_port(cls, value: int | None) -> int | None:
        if value is not None and not MIN_PORT <= value <= MAX_PORT:
            raise ValueError(f"SSH port out of bounds: {value} (expected {MIN_PORT}-{MAX_PORT}).")
        return value

    @field_validator("vars")
    @classmethod
    def _valid_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return check_var_names(value, "host_vars")


class GroupSpec(ForgeModel):
    """A host group and the roles applied to it."""

    #: Name of the Ansible group.
    name: str

    #: Description echoed in the generated inventory and playbooks.
    description: str = ""

    #: Roles applied to the group; reordered into catalogue order.
    roles: list[str] = Field(default_factory=lambda: ["common"])

    #: Free-form variables written into group_vars/<group>.yml.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not GROUP_NAME_RE.match(value):
            raise ValueError(
                f"Invalid group name: '{value}'. Expected: lowercase letters, digits "
                "and underscores (hyphens are forbidden by Ansible)."
            )
        if value in RESERVED_GROUP_NAMES:
            reserved = ", ".join(sorted(RESERVED_GROUP_NAMES))
            raise ValueError(
                f"The group name '{value}' is reserved by Ansible ({reserved})."
            )
        return value

    @field_validator("roles")
    @classmethod
    def _valid_roles(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("A group must apply at least one role.")
        duplicates = find_duplicates(value)
        if duplicates:
            raise ValueError(
                f"Duplicate role(s) in the group: {', '.join(sorted(duplicates))}."
            )
        known = role_names()
        unknown = [name for name in value if name not in known]
        if unknown:
            raise ValueError(
                f"Unknown role: '{unknown[0]}'. Available roles: {', '.join(known)}."
            )
        return sort_roles(value)

    @field_validator("vars")
    @classmethod
    def _valid_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return check_var_names(value, "group_vars")


class RoleConfig(ForgeModel):
    """The options chosen for a role of the catalogue."""

    #: Name of the role, as it appears in the catalogue.
    name: str

    #: Options of the role; completed with the catalogue defaults at validation.
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: Any) -> Any:
        """Complete and reorder the options from the catalogue.

        This is what makes a partial forge.yml equivalent to a complete one: both
        produce the same object, hence the same output.
        """
        if not isinstance(data, dict):
            return data
        name = data.get("name")
        if not isinstance(name, str) or name not in role_names():
            return data  # invalid name: the field validator will say why
        data = dict(data)
        data["options"] = validate_options(name, data.get("options") or {})
        return data

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if value not in role_names():
            raise ValueError(
                f"Unknown role: '{value}'. Available roles: {', '.join(role_names())}."
            )
        return value


class GenerationOptions(ForgeModel):
    """What the generated project ships, beyond the roles and the inventory."""

    #: Writes one example vault file per environment.
    use_vault: bool = True

    #: Writes .ansible-lint, .yamllint and .gitignore at the project root.
    write_lint_config: bool = True

    #: Writes a GitHub Actions workflow running ansible-lint.
    write_ci: bool = False


class AnsibleSpec(ForgeModel):
    """The complete `ansible:` section."""

    #: Targeted OS family: conditions packages, services and paths.
    os_family: OSFamily = OSFamily.DEBIAN

    #: SSH account used by default to reach the machines.
    remote_user: str = "ansible"

    #: Goes through `become` (sudo) for the privileged tasks.
    become: bool = True

    #: SSH port used by default.
    ssh_port: int = 22

    #: Python interpreter of the target machines (`auto_silent` or an absolute path).
    python_interpreter: str = "auto_silent"

    #: What the generated project ships beyond the roles.
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    #: Host groups; the order is that of the inventory and of site.yml.
    groups: list[GroupSpec] = Field(min_length=1)

    #: Machines per environment then per group: hosts[env][group].
    hosts: dict[str, dict[str, list[HostSpec]]] = Field(default_factory=dict)

    #: Inventory variables per environment then per scope (`all` or a group).
    group_vars: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)

    #: Role options; completed at validation with the applied roles.
    roles: list[RoleConfig] = Field(default_factory=list)

    # -- validation ---------------------------------------------------------

    @field_validator("ssh_port")
    @classmethod
    def _valid_port(cls, value: int) -> int:
        if not MIN_PORT <= value <= MAX_PORT:
            raise ValueError(f"SSH port out of bounds: {value} (expected {MIN_PORT}-{MAX_PORT}).")
        return value

    @field_validator("groups")
    @classmethod
    def _unique_groups(cls, value: list[GroupSpec]) -> list[GroupSpec]:
        duplicates = find_duplicates(group.name for group in value)
        if duplicates:
            raise ValueError(f"Duplicate group(s): {', '.join(sorted(duplicates))}.")
        return value

    @model_validator(mode="after")
    def _check_references(self) -> AnsibleSpec:
        """Check that hosts and group_vars only quote declared groups."""
        known = {group.name for group in self.groups}
        for env, by_group in self.hosts.items():
            unknown = sorted(set(by_group) - known)
            if unknown:
                raise ValueError(
                    f"The environment '{env}' references unknown groups: "
                    f"{', '.join(unknown)}."
                )
            names = [host.name for group in by_group.values() for host in group]
            duplicates = find_duplicates(names)
            if duplicates:
                raise ValueError(
                    f"Host(s) declared more than once in the environment '{env}': "
                    f"{', '.join(sorted(duplicates))}."
                )
        for env, by_scope in self.group_vars.items():
            unknown = sorted(set(by_scope) - known - {"all"})
            if unknown:
                raise ValueError(
                    f"The environment '{env}' defines variables for unknown groups: "
                    f"{', '.join(unknown)}."
                )
            for scope, variables in by_scope.items():
                check_var_names(variables, f"inventories/{env}/group_vars/{scope}")
        return self

    @model_validator(mode="after")
    def _fill_missing_roles(self) -> AnsibleSpec:
        """Add the roles that are applied but not configured, then sort by catalogue."""
        configured = {config.name for config in self.roles}
        for name in sorted(self.used_roles() - configured):
            self.roles.append(RoleConfig(name=name))
        order = role_names()
        self.roles.sort(key=lambda config: order.index(config.name))
        return self

    # -- lookups ------------------------------------------------------------

    def used_roles(self) -> set[str]:
        """Roles actually applied by at least one group."""
        return {name for group in self.groups for name in group.roles}

    def ordered_used_roles(self) -> list[str]:
        """Applied roles, in the frozen order of the catalogue."""
        return sort_roles(self.used_roles())

    def group(self, name: str) -> GroupSpec:
        """Return the `name` group, or raise `KeyError`."""
        for group in self.groups:
            if group.name == name:
                return group
        raise KeyError(name)

    def role_options(self, name: str) -> dict[str, Any]:
        """Options retained for the `name` role, catalogue defaults included."""
        for config in self.roles:
            if config.name == name:
                return config.options
        return validate_options(name, {})
