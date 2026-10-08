"""Projection of the specification into copier's `domain` dict, and cross-checks.

The same contract as the two other domains (`forge_answers`, DESIGN.md §2.2):
JSON-serialisable output, frozen order, no pydantic object. The computation lives
in :mod:`derive`, :mod:`derive_env` and :mod:`tree`; this module assembles, and
carries the checks the sub-model cannot do because it does not see `service:`.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import derive, derive_env, tree
from forge.plugins.terraform.constants import MAX_NAMESPACE_LENGTH
from forge.plugins.terraform.enums import BackendKind, NamespaceStrategy, ResourceFamily
from forge.plugins_api import checks
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Build the `domain` dict passed to copier for the Terraform domain."""
    service = spec.service
    terraform = spec.terraform

    return {
        # -- identity of the module ------------------------------------------
        "module_dir": tree.module_dir(service.name),
        "module_name": service.name,
        "terraform_version": terraform.terraform_version,
        "providers": derive.providers(spec),
        # -- what the module receives and returns -----------------------------
        "variables": derive.variables(spec),
        "root_variables": derive.root_variables(spec),
        "outputs": derive.outputs(spec),
        # -- base layer -------------------------------------------------------
        "backend": derive.backend(spec),
        "kubernetes": derive.kubernetes(spec),
        "namespace_strategy": terraform.namespace_strategy.value,
        "creates_namespace": derive.creates_namespace(spec),
        "labels": derive.base_labels(spec),
        # -- retained families -------------------------------------------------
        "resources": [family["name"] for family in derive.families(spec)],
        "families": derive.families(spec),
        "resource_slots": tree.resource_slots(spec),
        # -- environments -------------------------------------------------------
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        "environments": derive_env.environments(spec),
        # -- extras and documentation ---------------------------------------------
        "extras": derive.extras(spec),
        "root_files": tree.root_files(spec),
        "module_files": tree.module_files(spec),
        "environment_files": tree.environment_files(),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Checks `TerraformSpec` cannot do: it does not see `service:`.

    Deterministic order: the list is displayed as-is.
    """
    terraform = getattr(spec, "terraform", None)
    if terraform is None:
        return []

    issues: list[Issue] = []
    issues.extend(
        checks.unknown_environments(
            spec, "terraform", {"terraform.environments": terraform.environments}
        )
    )
    issues.extend(_check_custom_namespaces(spec, terraform))
    issues.extend(_check_namespace_lengths(spec, terraform))
    issues.extend(_check_orphan_overrides(spec, terraform))
    issues.extend(_check_state_safety(spec, terraform))
    issues.extend(_check_cluster_context(spec, terraform))
    return issues


def _check_custom_namespaces(spec: Any, terraform: Any) -> list[Issue]:
    """Require an explicit namespace for every environment, `custom` strategy.

    The sub-model only checks the environments **present** in
    `terraform.environments`; the one that does not appear there at all is only
    visible from here.
    """
    if terraform.namespace_strategy is not NamespaceStrategy.CUSTOM:
        return []
    return [
        Issue(
            level="error",
            message=(
                f"environment '{env.name}': the \"custom\" namespace strategy "
                "requires an explicit namespace, and none is declared."
            ),
            hint=(
                f"Set terraform.environments.{env.name}.namespace, or switch "
                "terraform.namespace_strategy to per_env to derive "
                f"'{spec.service.name}-{env.name}'."
            ),
            domains=("terraform",),
        )
        for env in spec.service.environments
        if terraform.overrides(env.name).namespace is None
    ]


def _check_namespace_lengths(spec: Any, terraform: Any) -> list[Issue]:
    """Check the **derived** namespaces, which the sub-model never saw.

    `<service>-<env>` can exceed 63 characters while neither the service name nor
    the environment name exceeds its own cap: the product only exists here.
    """
    issues: list[Issue] = []
    for env in spec.service.environments:
        namespace = terraform.namespace_for(spec.service.name, env.name)
        if len(namespace) <= MAX_NAMESPACE_LENGTH:
            continue
        issues.append(
            Issue(
                level="error",
                message=(
                    f"the namespace derived for '{env.name}' is "
                    f"'{namespace}' ({len(namespace)} characters); Kubernetes "
                    f"accepts at most {MAX_NAMESPACE_LENGTH}."
                ),
                hint=(
                    "Shorten service.name or the environment name, or set "
                    f"terraform.environments.{env.name}.namespace."
                ),
                domains=("terraform",),
            )
        )
    return issues


def _check_orphan_overrides(spec: Any, terraform: Any) -> list[Issue]:
    """Report an override with no effect because its family is not retained.

    A carefully tuned and silently ignored value is worse than an error: nothing
    distinguishes it from a value that is applied.
    """
    issues: list[Issue] = []
    checks_to_run = (
        (ResourceFamily.QUOTA, "quota", "quota", "a namespace budget"),
        (
            ResourceFamily.TLS_CERTIFICATE,
            "tls_dns_names",
            "tls_certificate",
            "certificate DNS names",
        ),
    )
    for family, attribute, family_name, label in checks_to_run:
        if terraform.uses(family):
            continue
        for name in sorted(terraform.environments):
            if not getattr(terraform.environments[name], attribute, None):
                continue
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"terraform.environments.{name}.{attribute} declares "
                        f"{label}, but the '{family_name}' family is not in "
                        "terraform.resources: that value will not be applied."
                    ),
                    hint=(
                        f"Add '{family_name}' to terraform.resources, or remove "
                        f"terraform.environments.{name}.{attribute}."
                    ),
                    domains=("terraform",),
                )
            )
    return issues


def _check_state_safety(spec: Any, terraform: Any) -> list[Issue]:
    """Report a local state on a production environment.

    The Terraform state carries in plain text everything the resources expose —
    including the passwords generated by the `random_secret` family. On the
    `local` backend, it lives in the working directory, with neither lock nor
    encryption.
    """
    if terraform.backend.kind is not BackendKind.LOCAL:
        return []
    production = [env.name for env in spec.service.environments if env.production]
    if not production:
        return []
    secrets = terraform.uses(ResourceFamily.RANDOM_SECRET) or terraform.uses(
        ResourceFamily.TLS_CERTIFICATE
    )
    detail = (
        "; it will carry in plain text the values generated by the "
        "random_secret / tls_certificate families"
        if secrets
        else ""
    )
    return [
        Issue(
            level="warning",
            message=(
                f"the production environment '{production[0]}' uses the 'local' "
                f"state backend: the state is neither shared, nor locked, nor "
                f"encrypted{detail}."
            ),
            hint=(
                "Switch terraform.backend.kind to s3, gcs, azurerm or http for "
                "production."
            ),
            domains=("terraform",),
        )
    ]


def _check_cluster_context(spec: Any, terraform: Any) -> list[Issue]:
    """Report the environments that will apply on the current context.

    It is the most banal accident of the Kubernetes provider: with no named
    context, `terraform apply` goes to the cluster the kubeconfig of the machine
    designates at the moment the command is launched.
    """
    access = terraform.kubernetes
    if access.auth.value != "kubeconfig" or access.context_per_environment:
        return []
    silent = [
        env.name
        for env in spec.service.environments
        if not terraform.overrides(env.name).kube_context
    ]
    if not silent:
        return []
    return [
        Issue(
            level="warning",
            message=(
                "terraform.kubernetes.context_per_environment is false and no "
                f"context is named for: {', '.join(silent)}. Terraform will apply "
                "on the current context of the machine."
            ),
            hint=(
                "Switch context_per_environment back to true, or set "
                "terraform.environments.<env>.kube_context."
            ),
            domains=("terraform",),
        )
    ]
