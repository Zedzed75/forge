"""ASCII tree of the generated project — **the only relic of the legacy planner**.

The README of the generated project displays the complete tree of that project.
copier cannot supply it: at the moment it renders a file, it does not yet know
which other files it will write. The list of paths must therefore be rebuilt
without rendering anything.

:func:`expected_paths` is `ansible_forge.engine.planner.plan` reduced to its paths
alone: the same split into sections, the same conditions, but no content. It is
the **only** place in forge that duplicates the knowledge of the template tree: if
a template is added, removed or renamed, it has to be reflected here, otherwise
the README lies. The parity test catches it, because it compares `README.md` byte
for byte.

:func:`build_tree` is the literal port of `ansible_forge.engine.writer.build_tree`
— the same branch characters, the same sort (directories first, then files, each
alphabetically), the same deduplication.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

#: Characters drawing the tree (port of `writer`).
_BRANCH = "├── "
_LAST_BRANCH = "└── "
_VERTICAL = "│   "
_SPACE = "    "

#: Files written for **every** role, under `roles/<role>/`.
SHARED_ROLE_FILES: tuple[str, ...] = (
    "defaults/main.yml",
    "meta/main.yml",
    "README.md",
)

#: Files specific to each role, under `roles/<role>/`.
#: Port of the destinations of `role_planner.ROLE_FILES` (the template sources
#: are of no use any more: copier finds them on its own in `template/roles/`).
ROLE_FILES: dict[str, tuple[str, ...]] = {
    "common": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/motd.j2",
    ),
    "users": (
        "tasks/main.yml",
        "vars/main.yml",
        "templates/sudoers.j2",
    ),
    "ssh_hardening": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/hardening.conf.j2",
    ),
    "firewall": (
        "tasks/main.yml",
        "tasks/ufw.yml",
        "tasks/firewalld.yml",
        "handlers/main.yml",
        "vars/main.yml",
    ),
    "nginx": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/nginx.conf.j2",
        "templates/vhost.conf.j2",
    ),
    "docker": (
        "tasks/main.yml",
        "tasks/repository_debian.yml",
        "tasks/repository_redhat.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/daemon.json.j2",
    ),
    "postgresql": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
    ),
}

#: Paths displayed in the tree without being written by forge.
#:
#: The legacy planner wrote a copy of the specification into the project (the
#: `embed_spec` option). forge no longer does: the unified specification lives at
#: the root of the target repository, above `ansible/` (MIGRATION.md §7,
#: divergence 3). The entry is kept in the tree so that `README.md` stays
#: identical to the parity snapshot; it is a deliberate choice, to be lifted at
#: the same time as the other legacy mentions of the README
#: (`ansible-forge generate`).
LEGACY_TREE_ENTRIES: tuple[str, ...] = ("forge.yml",)

#: Files written by copier but deliberately absent from the tree:
#: `.copier-answers.yml` is generation plumbing, not part of the Ansible project
#: (MIGRATION.md §7, divergence 1).
HIDDEN_ENTRIES: tuple[str, ...] = (".copier-answers.yml",)


def expected_paths(spec: Any) -> list[str]:
    """Paths forge is going to write, sorted — the planner reduced to its paths.

    Follows the order of `planner.plan` section by section: project files, root
    variables, inventories, playbooks, roles, README.
    """
    ansible = spec.ansible
    options = ansible.options
    paths: list[str] = ["ansible.cfg", "requirements.yml"]

    if options.write_lint_config:
        paths += [".gitignore", ".yamllint", ".ansible-lint"]
    if options.write_ci:
        paths.append(".github/workflows/ansible-lint.yml")
    paths.extend(LEGACY_TREE_ENTRIES)

    paths.append("group_vars/all.yml")
    paths += [f"group_vars/{group.name}.yml" for group in ansible.groups]

    for env in spec.service.environments:
        base = f"inventories/{env.name}"
        paths.append(f"{base}/hosts.yml")
        paths.append(f"{base}/group_vars/all/main.yml")
        if options.use_vault:
            paths.append(f"{base}/group_vars/all/vault.yml.example")
        paths += [f"{base}/group_vars/{group.name}.yml" for group in ansible.groups]
        by_group = ansible.hosts.get(env.name, {})
        names = sorted(host.name for hosts in by_group.values() for host in hosts)
        paths += [f"{base}/host_vars/{name}.yml" for name in names]

    paths += ["playbooks/site.yml", "playbooks/ping.yml"]
    paths += [f"playbooks/{group.name}.yml" for group in ansible.groups]

    for role_name in ansible.ordered_used_roles():
        paths += [f"roles/{role_name}/{file}" for file in SHARED_ROLE_FILES]
        paths += [f"roles/{role_name}/{file}" for file in ROLE_FILES[role_name]]

    paths.append("README.md")
    return sorted(paths)


def build_tree(paths: list[str], root: str) -> str:
    """Render a readable tree from a list of relative paths.

    Literal port of `writer.build_tree`: `sorted(set(...))` on the way in, then a
    recursive rendering.
    """
    tree = _nest(sorted(set(paths)))
    lines = [f"{root}/"]
    lines.extend(_render(tree, prefix=""))
    return "\n".join(lines)


def _nest(paths: list[str]) -> dict[str, dict]:
    """Turn a list of flat paths into a nested dictionary."""
    root: dict[str, dict] = {}
    for path in paths:
        node = root
        for part in PurePosixPath(path).parts:
            node = node.setdefault(part, {})
    return root


def _render(node: dict[str, dict], prefix: str) -> list[str]:
    """Recursively render one level of the tree.

    Directories (nodes that have children) are listed before files, then sorted by
    name: the display is stable from one run to the next.
    """
    entries = sorted(node.items(), key=lambda item: (not item[1], item[0]))
    lines: list[str] = []
    for index, (name, children) in enumerate(entries):
        last = index == len(entries) - 1
        connector = _LAST_BRANCH if last else _BRANCH
        suffix = "/" if children else ""
        lines.append(f"{prefix}{connector}{name}{suffix}")
        if children:
            lines.extend(_render(children, prefix + (_SPACE if last else _VERTICAL)))
    return lines
