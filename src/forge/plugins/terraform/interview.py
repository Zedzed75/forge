"""Interview for the Terraform domain.

Written against the core `Prompter` protocol, never against questionary: that is
what makes the interview replayable by `tests/scripted_prompter.py`.

The order of the questions follows the order of the real decision: first **what
Terraform lays down** (the families), because everything else depends on it;
then **where the state lives**, which is the security choice; finally **how the
cluster is joined**. Questions without an object are not asked: a `local`
backend asks for no key, in-cluster authentication asks for no kubeconfig.

Per arbitration R7 (PLAN.md), returning `None` does not mean that the user
declines the domain — the core has already asked that — but that there is
nothing to generate: here, no family retained.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.terraform.catalog.registry import all_families
from forge.plugins.terraform.constants import REQUIRED_BACKEND_KEYS
from forge.plugins.terraform.enums import (
    BackendKind,
    KubernetesAuth,
    NamespaceStrategy,
    ResourceFamily,
)
from forge.spec.names import DNS_LABEL_RE
from forge.spec.service import ServiceSpec

#: Terraform version offered by default. Bounded on the major: a constraint
#: without an upper bound lets a future version 2 break the project.
DEFAULT_VERSION = "~> 1.9"

#: Labels of the namespace strategies, in the order offered.
NAMESPACE_CHOICES: list[tuple[str, str]] = [
    (
        NamespaceStrategy.PER_ENV.value,
        "one namespace per environment (<service>-<env>) — recommended",
    ),
    (NamespaceStrategy.SAME.value, "a single namespace for every environment"),
    (NamespaceStrategy.CUSTOM.value, "I name each namespace myself"),
]

#: Labels of the backends, in the order offered.
BACKEND_CHOICES: list[tuple[str, str]] = [
    (BackendKind.LOCAL.value, "local — file in the working directory (discovery)"),
    (BackendKind.S3.value, "s3 — S3 or S3-compatible bucket"),
    (BackendKind.GCS.value, "gcs — Google Cloud Storage bucket"),
    (BackendKind.AZURERM.value, "azurerm — Azure storage account"),
    (BackendKind.HTTP.value, "http — service implementing the state API (GitLab, Atlantis)"),
]

#: Labels of the authentication modes.
AUTH_CHOICES: list[tuple[str, str]] = [
    (KubernetesAuth.KUBECONFIG.value, "kubeconfig — a file and a named context"),
    (KubernetesAuth.IN_CLUSTER.value, "in_cluster — Terraform runs inside the target cluster"),
]


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduct the interview and return the `terraform:` section of forge.yml."""
    prompter.note(
        "Terraform lays the foundation: the namespace, its budget, the identity "
        "that deploys into it. The application workload belongs to the Helm domain."
    )

    families = _ask_families(prompter)
    if not families:
        prompter.note("No family retained: the terraform domain is not generated.")
        return None

    section: dict[str, Any] = {
        "terraform_version": prompter.text(
            "Terraform version constraint", default=DEFAULT_VERSION
        ),
        "resources": families,
    }

    strategy = prompter.select(
        "How should the namespaces be named?", NAMESPACE_CHOICES, NamespaceStrategy.PER_ENV.value
    )
    section["namespace_strategy"] = strategy

    backend = _ask_backend(prompter)
    if backend:
        section["backend"] = backend

    access = _ask_kubernetes(prompter)
    if access:
        section["kubernetes"] = access

    environments = _ask_environments(prompter, service, strategy)
    if environments:
        section["environments"] = environments

    section["extras"] = {
        "makefile": prompter.confirm(
            "Add a Makefile of shortcuts (make plan ENV=prod)?", default=True
        ),
        "tflint_config": prompter.confirm(
            "Add a .tflint.hcl file?", default=True
        ),
    }
    return section


def _ask_families(prompter: Prompter) -> list[str]:
    """Resource families retained."""
    choices = [(family.name, f"{family.name} — {family.summary}") for family in all_families()]
    return prompter.checkbox(
        "What should Terraform lay down?", choices, [ResourceFamily.NAMESPACE.value]
    )


def _ask_backend(prompter: Prompter) -> dict[str, Any]:
    """State backend and its mandatory keys.

    No secret key is asked for: the model would refuse them, and a generated
    file never carries a secret.
    """
    kind = prompter.select("Where should the Terraform state be kept?", BACKEND_CHOICES, BackendKind.LOCAL.value)
    if kind == BackendKind.LOCAL.value:
        prompter.note(
            "Local state: neither lock nor encryption. Not to be kept for a "
            "shared environment."
        )
        return {}

    config: dict[str, str] = {}
    for key in REQUIRED_BACKEND_KEYS[kind]:
        if key in ("key", "prefix"):
            # Derived per environment: asking for them would produce a state
            # shared between environments, exactly what must be avoided.
            continue
        config[key] = prompter.text(f"backend {kind}: {key}", validate=_non_empty)
    return {"kind": kind, "config": config}


def _ask_kubernetes(prompter: Prompter) -> dict[str, Any]:
    """Cluster access."""
    auth = prompter.select(
        "How does Terraform join the cluster?", AUTH_CHOICES, KubernetesAuth.KUBECONFIG.value
    )
    if auth == KubernetesAuth.IN_CLUSTER.value:
        return {"auth": auth}

    path = prompter.text("Path of the kubeconfig", default="~/.kube/config")
    per_env = prompter.confirm(
        "A different kubeconfig context per environment?", default=True
    )
    access: dict[str, Any] = {}
    if path != "~/.kube/config":
        access["config_path"] = path
    if not per_env:
        access["context_per_environment"] = False
    return access


def _ask_environments(
    prompter: Prompter, service: ServiceSpec, strategy: str
) -> dict[str, Any]:
    """Per-environment overrides. Only the `custom` strategy requires them."""
    if strategy != NamespaceStrategy.CUSTOM.value:
        return {}
    return {
        env.name: {
            "namespace": prompter.text(
                f"Namespace of environment '{env.name}'",
                default=f"{service.name}-{env.name}",
                validate=_dns_label,
            )
        }
        for env in service.environments
    }


def _non_empty(value: str) -> str | None:
    return None if value.strip() else "A value is required."


def _dns_label(value: str) -> str | None:
    if not DNS_LABEL_RE.match(value):
        return "A DNS label: lowercase letters, digits and hyphens."
    return None
