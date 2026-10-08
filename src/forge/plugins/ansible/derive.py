"""Values derived from the Ansible specification, ready for the templates.

This module is the port of the **data computation** that
`ansible_forge.engine.planner` and `ansible_forge.engine.role_planner` performed
before rendering anything: sorts, deduplications, deduced values, variable
documentation. Rendering and writing are copier's business now.

Absolute rule: **every output is JSON-serialisable and of frozen order**. Never a
pydantic object, never an `Enum`, never a `set`: this dict is written as-is into
`.copier-answers.yml` and replayed by `copier update`.

Every function carries, as a comment, the name of the legacy function whose
behaviour it reproduces — that is what makes parity checkable.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.ansible.catalog.definition import RoleDefinition
from forge.plugins.ansible.catalog.collections import requirements_for
from forge.plugins.ansible.catalog.registry import (
    collection_requirements_for,
    get_role,
    role_names,
)

#: Comment placed on the free-form variables the user typed in.
#: The text used to be copied **word for word** from the legacy
#: (`planner.UNDOCUMENTED`), which forbade touching it: the parity snapshots
#: compared the two outputs. Those snapshots went away with `_legacy/` in
#: phase 10, and the constraint with them.
UNDOCUMENTED = "TODO: describe what this variable does and its allowed values."

#: Galaxy platforms declared in `meta/main.yml`, per OS family.
#: Port of `role_planner.PLATFORMS` (keys converted to strings: the `domain` dict
#: must contain no `Enum`).
PLATFORMS: dict[str, tuple[str, ...]] = {
    "debian": ("Debian", "Ubuntu"),
    "redhat": ("EL", "Fedora"),
}

#: Internal variables documented in the README of each role.
#: Port of `role_planner.INTERNAL_VARS`: these texts are written into the
#: generated files, so they follow the language of the output.
INTERNAL_VARS: dict[str, tuple[dict[str, str], ...]] = {
    "users": (
        {
            "name": "users_sudoers_file",
            "description": "name of the file written to /etc/sudoers.d",
        },
        {
            "name": "users_secondary_groups",
            "description": "secondary groups derived from users_accounts",
        },
        {
            "name": "users_sudo_accounts",
            "description": "present accounts that have sudo access",
        },
    ),
    "ssh_hardening": (
        {
            "name": "ssh_hardening_dropin_dir",
            "description": "directory of the additional configuration files of sshd",
        },
        {
            "name": "ssh_hardening_service",
            "description": "name of the SSH service, resolved per OS family",
        },
    ),
    "firewall": (
        {
            "name": "firewall_effective_backend",
            "description": "backend actually used, once \"auto\" is resolved",
        },
        {
            "name": "firewall_zone",
            "description": "firewalld zone the rules are set in",
        },
        {
            "name": "firewall_zone_target",
            "description": "firewalld zone target derived from the default policy",
        },
    ),
    "nginx": (
        {
            "name": "nginx_user",
            "description": "system account of the workers, resolved per OS family",
        },
        {
            "name": "nginx_config_dir",
            "description": "configuration directory of nginx",
        },
        {
            "name": "nginx_default_site_path",
            "description": "default site of the distribution, empty if there is none",
        },
    ),
    "docker": (
        {
            "name": "docker_apt_arch",
            "description": "APT architecture derived from the architecture of the machine",
        },
        {
            "name": "docker_packages",
            "description": "final list of the packages, Compose plugin included if requested",
        },
    ),
    "postgresql": (
        {
            "name": "postgresql_config_dir",
            "description": "directory of postgresql.conf and pg_hba.conf, per OS family",
        },
        {
            "name": "postgresql_settings",
            "description": "parameters applied to the server, built from the options",
        },
        {
            "name": "postgresql_users_with_password",
            "description": "roles that have a password variable filled in",
        },
    ),
    "common": (
        {
            "name": "common_ntp_package",
            "description": "time synchronisation package resolved per OS family",
        },
        {
            "name": "common_ntp_service",
            "description": "time synchronisation service resolved per OS family",
        },
    ),
}


# ---------------------------------------------------------------------------
# Free-form variables
# ---------------------------------------------------------------------------


def free_vars(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a dictionary of free-form variables into documented entries.

    Port of `planner._free_vars`. Sorting by name is what makes the `group_vars`
    and `host_vars` files reproducible whatever the order they were typed in.
    """
    return [
        {"name": name, "description": UNDOCUMENTED, "value": values[name]}
        for name in sorted(values)
    ]


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def option_context(role: RoleDefinition) -> list[dict[str, Any]]:
    """Describe the options of a role for the templates (prefixed variable name).

    Port of `role_planner.option_context`. `default` is the **catalogue** value,
    not the one chosen in the spec: `roles/<r>/defaults/main.yml` documents the
    role as it is reusable, and the project choices go into `group_vars/all.yml`
    (cf. :func:`role_overrides`).
    """
    return [
        {
            "name": option.name,
            "var_name": f"{role.name}_{option.name}",
            "description": option.description,
            "allowed": option.allowed,
            "default": option.default,
        }
        for option in role.options
    ]


def role_context(
    role_name: str,
    *,
    author: str,
    os_family: str,
    example_group: str,
) -> dict[str, Any]:
    """Complete context of a role: catalogue plus values deduced from the project.

    Port of the `shared_context` of `role_planner.plan_role`, augmented with the
    `RoleDefinition` fields the templates read directly off the object (`name`,
    `summary`, `tags`, `handlers`, `collections`).
    """
    role = get_role(role_name)
    return {
        "name": role.name,
        "summary": role.summary,
        "tags": list(role.tags),
        "handlers": list(role.handlers),
        "collections": _role_collections(role.collections),
        "os_families": list(role.os_families),
        "options": option_context(role),
        "platforms": list(PLATFORMS[os_family]),
        "author": author,
        "example_group": example_group,
        "internal_vars": [dict(item) for item in INTERNAL_VARS.get(role.name, ())],
    }


def first_group_using(groups: list[Any]) -> dict[str, str]:
    """Map each role to the first group that applies it (the README example).

    Port of `planner._first_group_using`: the order of `groups` is not sorted, it
    is that of the specification.
    """
    mapping: dict[str, str] = {}
    for group in groups:
        for name in group.roles:
            mapping.setdefault(name, group.name)
    return mapping


def role_contexts(ansible: Any, *, author: str) -> list[dict[str, Any]]:
    """Contexts of the roles actually applied, in catalogue order.

    Port of `planner._roles`: the order comes from the catalogue, never from the
    alphabet, and the example group falls back to the first declared group.
    """
    examples = first_group_using(ansible.groups)
    fallback = ansible.groups[0].name
    return [
        role_context(
            name,
            author=author,
            os_family=ansible.os_family.value,
            example_group=examples.get(name, fallback),
        )
        for name in ansible.ordered_used_roles()
    ]


def role_slots(contexts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """One slot per catalogue role, empty when the role is not applied.

    Serves the templates specific to a role:
    `roles/[% yield r from domain.role_slots.firewall %][[ r.name ]][% endyield %]/...`
    An empty list makes the file disappear; the seven keys are **always** present,
    so that a template can never reference a missing key.
    """
    by_name = {context["name"]: context for context in contexts}
    return {
        name: ([by_name[name]] if name in by_name else [])
        for name in role_names()
    }


def collection_users(ansible: Any) -> dict[str, list[str]]:
    """Map each Galaxy collection to the roles that require it.

    Port of `planner._collection_users`: collections sorted by name, roles sorted
    by name within each collection.
    """
    users: dict[str, list[str]] = {}
    for role_name in ansible.ordered_used_roles():
        for collection in get_role(role_name).collections:
            users.setdefault(collection, []).append(role_name)
    return {name: sorted(roles) for name, roles in sorted(users.items())}


def collections(ansible: Any) -> list[dict[str, str]]:
    """Galaxy collections the applied roles require, with their version constraint.

    Sorted by name and deduplicated. Each entry carries what it takes to write a
    complete dependency: the name, the accepted range, the version forge
    validates against, and the reason for the floor, echoed as a comment.
    """
    return [
        {
            "name": requirement.name,
            "version": requirement.version,
            "validated": requirement.validated,
            "reason": requirement.reason,
        }
        for requirement in collection_requirements_for(ansible.ordered_used_roles())
    ]


def _role_collections(names: tuple[str, ...]) -> list[dict[str, str]]:
    """Collections of a role: the name and the range, nothing more.

    The justification of the floor is carried only once, by `collections`:
    repeating it per role would copy it into `.copier-answers.yml` as many times
    as there are roles, in a file meant to stay readable.
    """
    return [
        {"name": requirement.name, "version": requirement.version}
        for requirement in requirements_for(names)
    ]


def role_overrides(ansible: Any) -> list[dict[str, Any]]:
    """Role options whose chosen value differs from the catalogue default.

    Port of `planner._role_overrides`. Only these values are written into
    `group_vars/all.yml`: the others stay documented in a single place,
    `roles/<role>/defaults/main.yml`. The order is that of the catalogue (roles),
    then that of the declaration of the options.
    """
    overrides: list[dict[str, Any]] = []
    for role_name in ansible.ordered_used_roles():
        role = get_role(role_name)
        chosen = ansible.role_options(role_name)
        for option in role.options:
            value = chosen.get(option.name, option.default)
            if value != option.default:
                overrides.append(
                    {
                        "name": f"{role.name}_{option.name}",
                        "description": option.description,
                        "allowed": option.allowed,
                        "value": value,
                    }
                )
    return overrides


# ---------------------------------------------------------------------------
# Groups, hosts and environments
# ---------------------------------------------------------------------------


def _group_base(group: Any, contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Part shared by the project groups and the inventory groups.

    Both levels expose the same shape — `role_names` for the plain names (the
    inventory and the README join them with commas), `roles` for the complete
    definitions — so that a template never has to wonder which level it is at.
    The definitions are therefore repeated in the answers file; that is the
    accepted price of this uniformity.
    """
    return {
        "name": group.name,
        "description": group.description,
        "role_names": list(group.roles),
        "roles": [contexts[name] for name in group.roles],
    }


def project_groups(
    ansible: Any, contexts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Project groups, in the **unsorted** order of the specification.

    Port of the contexts of `planner._root_vars` and `planner._playbooks`:
    `group_vars/<group>.yml` and `playbooks/<group>.yml` receive the complete
    definitions of the group roles, plus its free-form variables.
    """
    by_name = {context["name"]: context for context in contexts}
    return [
        {**_group_base(group, by_name), "variables": free_vars(group.vars)}
        for group in ansible.groups
    ]


def host_context(host: Any) -> dict[str, Any]:
    """One inventory machine, as `hosts.yml` and `host_vars` see it."""
    return {
        "name": host.name,
        "ansible_host": host.ansible_host,
        "ansible_port": host.ansible_port,
        "ansible_user": host.ansible_user,
        "vars": dict(host.vars),
        "variables": free_vars(host.vars),
    }


def vault_secrets(ansible: Any, env_name: str) -> list[dict[str, str]]:
    """Secrets the selected roles expect, for one environment.

    Port of `planner._vault_secrets`: today only `postgresql` declares passwords;
    failing that, an example secret is written so that the template file is never
    empty.
    """
    secrets: list[dict[str, str]] = []
    if "postgresql" in ansible.used_roles():
        for user in ansible.role_options("postgresql").get("db_users", []):
            variable = user.get("password_var")
            if variable:
                secrets.append(
                    {
                        "name": variable,
                        "description": (
                            f"Password of the \"{user.get('name', '?')}\" PostgreSQL "
                            f"role in the \"{env_name}\" environment."
                        ),
                        "placeholder": "CHANGE-ME",
                    }
                )
    if not secrets:
        secrets.append(
            {
                "name": "vault_example_secret",
                "description": (
                    "Example secret. Replace it with your own, one per line, each one "
                    "preceded by a comment."
                ),
                "placeholder": "CHANGE-ME",
            }
        )
    return secrets


def environments(spec: Any, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One environment per `service.environments` entry, in promotion order.

    Gathers what `planner._inventories` computed per environment: inventory
    groups (hosts sorted by name), the **flat** list of hosts, `all`-scoped
    variables, per-group variables and vault secrets.
    """
    ansible = spec.ansible
    by_name = {context["name"]: context for context in contexts}
    result: list[dict[str, Any]] = []
    for env in spec.service.environments:
        by_group = ansible.hosts.get(env.name, {})
        scopes = ansible.group_vars.get(env.name, {})
        groups = []
        for group in ansible.groups:
            hosts = sorted(by_group.get(group.name, []), key=lambda h: h.name)
            groups.append(
                {
                    **_group_base(group, by_name),
                    "hosts": [host_context(host) for host in hosts],
                    "variables": free_vars(scopes.get(group.name, {})),
                }
            )
        flat = sorted(
            (host for hosts in by_group.values() for host in hosts),
            key=lambda h: h.name,
        )
        result.append(
            {
                "name": env.name,
                "domain": env.domain or "",
                "production": env.production,
                "host_count": len(flat),
                "groups": groups,
                "hosts": [host_context(host) for host in flat],
                "vars_all": free_vars(scopes.get("all", {})),
                "group_vars": {
                    group.name: free_vars(scopes.get(group.name, {}))
                    for group in ansible.groups
                },
                "vault_secrets": vault_secrets(ansible, env.name),
            }
        )
    return result
