"""Validation commands for the generated Ansible project.

Port of the "what to run" part of `ansible_forge.verify` (MIGRATION.md §3):
execution, timeout, missing-tool detection and reporting belong to the core
(`forge.validate.runner`). Here, only the list of commands.

CLAUDE.md requires that every generated project pass
`ansible-playbook --syntax-check` and `ansible-lint`. Neither is a dependency of
forge: generation does not need them, only verification asks for them — hence
`requires_linux`, which allows the WSL fallback on Windows (ansible-core does not
support Windows as a control node).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins_api.types import Command

#: Maximum time granted to a command, in seconds.
TIMEOUT = 600

#: Environment variable pointing at the installed Galaxy collections.
#: Without them, `--syntax-check` fails on the modules the roles quote
#: (`community.general.timezone`…): that is not a defect of the generated
#: project, it is a runtime prerequisite, which `requirements.yml` documents.
COLLECTIONS_ENV_VAR = "FORGE_ANSIBLE_COLLECTIONS"

#: Default location, taken from the convention of the legacy harness.
DEFAULT_COLLECTIONS = "/opt/forge-collections"


def tool_environment() -> tuple[tuple[str, str], ...]:
    """Environment variables passed to both tools.

    Colour is disabled so that the report stays readable and comparable; the path
    to the collections is passed on when it is configured.
    """
    variables = {"ANSIBLE_FORCE_COLOR": "0"}
    collections = os.environ.get(COLLECTIONS_ENV_VAR, DEFAULT_COLLECTIONS)
    if collections:
        variables["ANSIBLE_COLLECTIONS_PATH"] = collections
    return tuple(sorted(variables.items()))

#: Installation message common to both tools.
INSTALL_HINT = (
    "pipx install ansible-core ansible-lint (or "
    "python -m pip install ansible-core ansible-lint). On Windows, install them "
    "inside a WSL distribution: ansible-core does not support Windows as a "
    "control node."
)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commands validating the generated project, in execution order.

    One syntax check per environment — an incomplete inventory only shows on the
    environment concerned — then one pass of ansible-lint over the whole project.
    """
    commands_list: list[Command] = []
    for env in spec.service.environments:
        commands_list.append(
            Command(
                label=f"syntax-check ({env.name})",
                tool="ansible-playbook",
                argv=(
                    "-i",
                    f"inventories/{env.name}",
                    "playbooks/site.yml",
                    "--syntax-check",
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=tool_environment(),
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    commands_list.append(
        Command(
            label="ansible-lint",
            tool="ansible-lint",
            argv=("--offline", "--nocolor"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=tool_environment(),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    )
    return commands_list


def deploy_commands(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commands deploying the project onto `environment` (`forge_deploy` hook).

    The core never runs them: they are written into a pipeline.

    `--diff` is there on purpose: the pipeline log becomes the trace of what
    changed on the machines, which no other artefact keeps.
    """
    return [
        Command(
            label=f"ansible-playbook ({environment})",
            tool="ansible-playbook",
            argv=("-i", f"inventories/{environment}", "playbooks/site.yml", "--diff"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=tool_environment(),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]
