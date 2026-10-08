"""Projection of the unified specification into copier's `domain` dict.

This is the implementation of the `forge_answers` hook (DESIGN.md §2.2) for the
Ansible domain, and the central piece of the port: every template reads what this
module produces.

The contract, upheld by :func:`build`:

* **the same names as in the legacy planner** — converting a template comes down
  to changing the delimiters and prefixing `domain.` (or using the loop variable
  of a `yield`);
* **JSON-serialisable** — no pydantic object, no `Enum`, no `set`: the dict is
  written as-is into `.copier-answers.yml` and replayed by `copier update`;
* **frozen order** — keys inserted in a stable order, lists sorted explicitly,
  never by accident.

The computation itself lives in :mod:`forge.plugins.ansible.derive` (derived
values) and :mod:`forge.plugins.ansible.tree` (the README tree); this module only
assembles it.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.ansible import derive, tree
from forge.plugins.ansible.names import ENV_NAME_RE
from forge.plugins_api import checks
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Build the `domain` dict passed to copier for the Ansible domain.

    `spec` is the assembled root model: `spec.service` (shared block) and
    `spec.ansible` (an `AnsibleSpec` instance).
    """
    service = spec.service
    ansible = spec.ansible

    # Author of the generated roles: the owner of the service, failing that its
    # name. Port of `planner._roles` (`spec.author or spec.project_name`).
    author = service.owner or service.name

    contexts = derive.role_contexts(ansible, author=author)
    environments = derive.environments(spec, contexts)

    return {
        # -- identity and connection settings -------------------------------
        "author": author,
        "default_env": service.environments[0].name,
        "env_names": [env.name for env in service.environments],
        "os_family": ansible.os_family.value,
        "remote_user": ansible.remote_user,
        "become": ansible.become,
        "ssh_port": ansible.ssh_port,
        "python_interpreter": ansible.python_interpreter,
        "options": {
            "use_vault": ansible.options.use_vault,
            "write_lint_config": ansible.options.write_lint_config,
            "write_ci": ansible.options.write_ci,
        },
        # -- Galaxy dependencies --------------------------------------------
        "collections": derive.collections(ansible),
        "collection_users": derive.collection_users(ansible),
        # -- roles ------------------------------------------------------------
        "roles": contexts,
        "role_slots": derive.role_slots(contexts),
        "role_overrides": derive.role_overrides(ansible),
        # -- groups and environments ------------------------------------------
        "groups": derive.project_groups(ansible, contexts),
        "environments": environments,
        # -- documentation ---------------------------------------------------
        "tree": tree.build_tree(tree.expected_paths(spec), service.name),
    }


def cross_check(spec: Any) -> list[Issue]:
    """Check that `ansible.hosts` and `ansible.group_vars` quote known environments.

    `AnsibleSpec` only sees its own section: it can check that the groups quoted
    exist, never that the environments exist, since those are declared in the
    shared `service:` block. This cross-check fills that hole (cf.
    `plugin.forge_consistency`).

    Returns one `error` level `Issue` per unknown environment, in alphabetical
    order — the list is displayed to the user as-is.
    """
    ansible = getattr(spec, "ansible", None)
    if ansible is None:
        return []

    # An environment can be quoted by both sections: the shared check reports it
    # only once, naming the sections at fault.
    issues = checks.unknown_environments(
        spec,
        "ansible",
        {"ansible.hosts": ansible.hosts, "ansible.group_vars": ansible.group_vars},
    )
    issues.extend(_check_env_names(spec))
    return issues


def _check_env_names(spec: Any) -> list[Issue]:
    """Refuse the environment names Ansible cannot carry.

    `service.environments[].name` is a **DNS label**: the core accepts the hyphen
    in it, because Kubernetes needs it. Ansible, on the other hand, uses that name
    as an inventory group name, and its group names forbid the hyphen. An
    environment named `pre-prod` would therefore pass the core validation and
    produce an invalid Ansible project.

    The check belongs to the plugin, not to the core: it is an Ansible rule, and
    the core has no business knowing it.
    """
    offenders = [
        env.name
        for env in spec.service.environments
        if not ENV_NAME_RE.match(env.name)
    ]
    if not offenders:
        return []
    return [
        Issue(
            level="error",
            message=(
                f"environment name(s) incompatible with Ansible: "
                f"{', '.join(offenders)}. The name is used as an inventory group "
                "name, and Ansible forbids the hyphen there."
            ),
            hint="Use underscores: 'pre_prod' rather than 'pre-prod'.",
            domains=("ansible",),
        )
    ]
