"""Validation commands for the generated Helm chart.

Port of the "what to run" part of `helm_forge.validation.runner`
(MIGRATION.md §4): execution, timeout, missing-tool detection, stdin chaining and
reporting belong to the core (`forge.validate.runner`). Here, only the list of
commands.

Three checks per environment, in this order:

1. `helm lint` — coherence of the chart and of its values;
2. `helm template` — the chart actually renders;
3. `kubeconform -strict` — the rendered manifests conform to the schemas of the
   targeted Kubernetes API version.

The third reads the **rendering** of the second: that is the `stdin_from` of the
`Command` contract. When `helm template` fails, the core skips `kubeconform`
rather than running it on an empty input — it would have nothing to validate.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins_api.types import Command

#: Maximum time granted to a command, in seconds.
TIMEOUT = 300

#: Installation message common to both tools.
INSTALL_HINT = (
    "install helm (https://helm.sh/docs/intro/install/) and kubeconform "
    "(https://github.com/yannh/kubeconform). On Windows, the WSL bridge looks for "
    "them in /opt/forge-tools/bin; a symbolic link is enough."
)

#: Environment variable pointing at a local kubeconform schema cache.
#: `kubeconform` otherwise downloads the schemas on every run: in CI without
#: network access, or on an offline workstation, validation would fail for a reason
#: unrelated to the chart.
SCHEMAS_ENV_VAR = "FORGE_KUBECONFORM_SCHEMAS"


def _values(chart: str, env_name: str) -> tuple[str, ...]:
    """`--values` options, in Helm's order of precedence.

    The common values first, the environment override next: Helm applies the files
    left to right, and the last one wins.
    """
    return (
        "--values",
        f"{chart}/values.yaml",
        "--values",
        f"{chart}/values-{env_name}.yaml",
    )


def _environment() -> tuple[tuple[str, str], ...]:
    """Environment variables passed to the tools."""
    variables: dict[str, str] = {"NO_COLOR": "1"}
    schemas = os.environ.get(SCHEMAS_ENV_VAR, "")
    if schemas:
        variables["KUBECONFORM_SCHEMA_LOCATION"] = schemas
    return tuple(sorted(variables.items()))


def _namespaces(spec: Any) -> dict[str, str]:
    """Derived namespace of each environment, indexed by name.

    The derivation belongs to `derive.py`; we read it back here rather than redo
    it, so that `helm template` runs in the namespace the chart announces itself.
    Computed once, not once per environment.
    """
    from forge.plugins.helm import answers

    return {
        env.get("name"): env.get("namespace") or spec.service.name
        for env in answers.build(spec).get("environments", [])
    }


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commands validating the generated chart, in execution order."""
    helm = spec.helm
    chart = f"charts/{spec.service.name}"
    version = getattr(helm.kubernetes, "full_version", None) or f"{helm.kubernetes.version}.0"
    shared_env = _environment()
    namespaces = _namespaces(spec)

    commands_list: list[Command] = []
    for env in spec.service.environments:
        values = _values(chart, env.name)
        render = f"helm template ({env.name})"
        commands_list.append(
            Command(
                label=f"helm lint ({env.name})",
                tool="helm",
                # `--kube-version` is not a detail: without it, helm evaluates the
                # chart against the Kubernetes version **its binary** defaults to,
                # which changes with every helm release. A chart declaring
                # `kubeVersion: >=1.34.0-0` passed on a workstation and failed in
                # CI for that reason alone — and, more seriously, `.Capabilities`
                # was filled in with the wrong version.
                argv=("lint", chart, "--kube-version", version, *values),
                cwd=outdir,
                timeout=TIMEOUT,
                env=shared_env,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        commands_list.append(
            Command(
                label=render,
                tool="helm",
                argv=(
                    "template",
                    spec.service.name,
                    chart,
                    "--namespace",
                    namespaces.get(env.name, spec.service.name),
                    # Same reason as for `helm lint`, with a more direct
                    # consequence: it is this version that feeds
                    # `.Capabilities.KubeVersion` in the rendered templates.
                    "--kube-version",
                    version,
                    *values,
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=shared_env,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        commands_list.append(
            Command(
                label=f"kubeconform -strict ({env.name})",
                tool="kubeconform",
                argv=(
                    "-strict",
                    "-summary",
                    "-kubernetes-version",
                    version,
                    "-schema-location",
                    "default",
                    "-",
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=shared_env,
                stdin_from=render,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    return commands_list


#: Time left to `helm upgrade --wait` before the deployment is considered failed.
#: Helm waits for every resource to become ready; without a bound, a pipeline stays
#: stuck on a pod that will never start.
DEPLOY_TIMEOUT = "10m"


def deploy_commands(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commands deploying the chart into `environment` (`forge_deploy` hook).

    The core never runs them: they are written into a pipeline.

    `--atomic` implies `--wait` and **rolls the release back** when the deployment
    fails: without it, a failed `upgrade` leaves the release in an intermediate
    state, and the next deployment fails for an unrelated reason.
    """
    helm = spec.helm
    chart = f"charts/{spec.service.name}"
    namespace = _namespaces(spec).get(environment, spec.service.name)
    argv = [
        "upgrade",
        "--install",
        spec.service.name,
        chart,
        "--namespace",
        namespace,
    ]
    if helm.create_namespace:
        argv.append("--create-namespace")
    argv += [
        *_values(chart, environment),
        "--atomic",
        "--timeout",
        DEPLOY_TIMEOUT,
    ]
    return [
        Command(
            label=f"helm upgrade --install ({environment})",
            tool="helm",
            argv=tuple(argv),
            cwd=outdir,
            timeout=TIMEOUT,
            env=_environment(),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]
