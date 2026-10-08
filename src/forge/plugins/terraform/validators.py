"""Validation commands for the generated Terraform project.

The first domain with no legacy generator: there is no parity snapshot to say
whether the output is right. It is these four commands that hold that role, and
they check different things:

1. `terraform fmt -check` — the canonical formatting. Requires neither network nor
   `init`, and catches the defect templates produce most easily: a misaligned `=`.
   It is also a determinism check, since the canonical form is unique.
2. `terraform init -backend=false` — the providers resolve. Without it, `validate`
   refuses to run. `-backend=false` avoids reaching the state storage: code is
   validated, no infrastructure is touched.
3. `terraform validate` — the configuration holds up: types, references, mandatory
   arguments, unknown blocks. It is the central validator.
4. `tflint` — what `validate` lets through: an unbounded provider version, a
   variable declared and never used, a non-conforming resource name.

The first three run **per environment root**: each root is an independent
Terraform configuration, and nothing guarantees that the validity of one entails
that of the other. `tflint` walks the tree in one go.

None of these commands reaches the cluster nor reads a state: `forge validate`
checks code, never an infrastructure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins.terraform import tree
from forge.plugins_api.types import Command

#: Maximum time granted to a command, in seconds. `init` downloads providers on
#: the first pass: the timeout is wider than that of the other domains.
TIMEOUT = 600

#: Installation message common to both tools.
INSTALL_HINT = (
    "install terraform (https://developer.hashicorp.com/terraform/install) and "
    "tflint (https://github.com/terraform-linters/tflint). On Windows, the WSL "
    "bridge looks for them in /opt/forge-tools/bin; a symbolic link is enough."
)

#: Environment variable pointing at a local provider cache. Without it,
#: `terraform init` re-downloads every provider for **each** environment root:
#: three environments, three times the same download.
CACHE_ENV_VAR = "FORGE_TF_PLUGIN_CACHE"


def _environment() -> tuple[tuple[str, str], ...]:
    """Environment variables passed to terraform and tflint.

    `TF_IN_AUTOMATION` removes messages inviting the user to run other commands —
    pointless here. `CHECKPOINT_DISABLE` suppresses the call to HashiCorp that
    checks whether a newer version exists: it is the only network access these
    commands make without being obliged to.
    """
    variables: dict[str, str] = {
        "NO_COLOR": "1",
        "TF_IN_AUTOMATION": "1",
        "CHECKPOINT_DISABLE": "1",
    }
    cache = os.environ.get(CACHE_ENV_VAR, "")
    # Terraform fails when the cache directory does not exist: better to do
    # without it than to fail validation over a badly set path.
    if cache and Path(cache).is_dir():
        variables["TF_PLUGIN_CACHE_DIR"] = cache
    return tuple(sorted(variables.items()))


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commands validating the generated project, in execution order."""
    shared_env = _environment()
    commands_list: list[Command] = [
        Command(
            label="terraform fmt",
            tool="terraform",
            argv=("fmt", "-check", "-recursive", "-diff", "-no-color"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=shared_env,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]

    for env in spec.service.environments:
        root = outdir / tree.environment_dir(env.name)
        commands_list.append(
            Command(
                label=f"terraform init ({env.name})",
                tool="terraform",
                argv=("init", "-backend=false", "-input=false", "-no-color"),
                cwd=root,
                timeout=TIMEOUT,
                env=shared_env,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        commands_list.append(
            Command(
                label=f"terraform validate ({env.name})",
                tool="terraform",
                argv=("validate", "-no-color"),
                cwd=root,
                timeout=TIMEOUT,
                env=shared_env,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )

    commands_list.append(
        Command(
            label="tflint",
            tool="tflint",
            argv=("--recursive", "--no-color"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=shared_env,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    )
    return commands_list


def deploy_commands(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commands applying the base layer onto `environment` (`forge_deploy` hook).

    The core never runs them: they are written into a pipeline.

    Two commands, and the first is not the same as at validation time: here `init`
    **reaches** the state storage, since the point is to apply. That is the only
    difference, and it is the one that counts.

    `-auto-approve` is there because a pipeline has nobody to confirm. The
    confirmation therefore belongs to the pipeline itself — a manual approval
    before the production job, which the `pipeline` domain generates.
    """
    root = outdir / tree.environment_dir(environment)
    shared_env = _environment()
    return [
        Command(
            label=f"terraform init ({environment})",
            tool="terraform",
            argv=("init", "-input=false", "-no-color"),
            cwd=root,
            timeout=TIMEOUT,
            env=shared_env,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        ),
        Command(
            label=f"terraform apply ({environment})",
            tool="terraform",
            argv=("apply", "-auto-approve", "-input=false", "-no-color"),
            cwd=root,
            timeout=TIMEOUT,
            env=shared_env,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        ),
    ]
