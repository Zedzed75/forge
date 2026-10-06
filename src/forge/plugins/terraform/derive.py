"""Static part of the projection: what does not depend on an environment.

Providers, variables, outputs, backend, labels: everything the module declares
once and for all. The part that varies from one environment to the next lives in
:mod:`forge.plugins.terraform.derive_env`.

One rule governs this module: **a single source for each name**. The list of
variables serves the module's `variables.tf`, each root's `variables.tf`, the
parameter passing in `main.tf` and the `terraform.tfvars`, all at once. A variable
passed to a module that does not declare it is a loud error; a variable declared
and never passed is not — it simply takes its default value, and the discrepancy
never shows.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import hcl
from forge.plugins.terraform.catalog.registry import (
    providers_for,
    selected,
    variables_for,
)
from forge.plugins.terraform.constants import DEFAULT_STATE_FILE
from forge.plugins.terraform.enums import KubernetesAuth, ResourceFamily
from forge.plugins.terraform.variables import Variable

#: HCL expression rendered by each output of the module. The addresses quoted here
#: have to match the resources of the family templates: it is the only coupling
#: between this module and the hand-written `.tf` files.
OUTPUT_VALUES: dict[str, str] = {
    "namespace": "local.namespace",
    "resource_quota_name": "kubernetes_resource_quota.this.metadata[0].name",
    "image_pull_secret_name": "kubernetes_secret.registry.metadata[0].name",
    "service_account_name": "kubernetes_service_account.deployer.metadata[0].name",
    "generated_secret_name": "kubernetes_secret.generated.metadata[0].name",
    "tls_secret_name": "kubernetes_secret.tls.metadata[0].name",
}

#: Output present whatever the retained families: it is through it that the rest
#: of the chain -- a Helm chart, a pipeline -- learns where to deploy.
BASE_OUTPUTS: dict[str, str] = {
    "namespace": "Namespace the service is deployed in.",
}

#: Variables specific to the environment root: they configure the provider, not
#: the module. The module does not know how the cluster is reached -- it is that
#: separation that makes the module reusable.
ROOT_ONLY_VARIABLES: tuple[Variable, ...] = (
    Variable(
        name="kube_config_path",
        type="string",
        description=(
            "Path of the kubeconfig file used to reach the cluster. Specific "
            "to the machine: leave the default value and override it through "
            "TF_VAR_kube_config_path if needed."
        ),
        default="~/.kube/config",
    ),
    Variable(
        name="kube_context",
        type="string",
        description=(
            "Targeted kubeconfig context. Never leave it empty: with no "
            "explicit context, Terraform applies on the current context of the "
            "machine, whatever it is."
        ),
        default="",
        per_environment=True,
    ),
)


def variables(spec: Any) -> list[dict[str, Any]]:
    """Variables of the module, common ones then those of the retained families."""
    families = selected(spec.terraform.family_names())
    return [_variable(variable) for variable in variables_for(families)]


def root_variables(spec: Any) -> list[dict[str, Any]]:
    """Variables of an environment root: those of the module, plus the access.

    The cluster access variables are only added under kubeconfig authentication:
    in `in_cluster` mode, the provider reads the token mounted in the pod and a
    kubeconfig path would make no sense.
    """
    result = variables(spec)
    if spec.terraform.kubernetes.auth is KubernetesAuth.KUBECONFIG:
        access = [_variable(variable) for variable in ROOT_ONLY_VARIABLES]
        access[0]["default"] = hcl.hcl_value(spec.terraform.kubernetes.config_path)
        result = access + result
    return result


def _variable(variable: Variable) -> dict[str, Any]:
    """Render a variable as a JSON-serialisable dict, the default already in HCL."""
    return {
        "name": variable.name,
        "type": variable.type,
        "description": variable.description,
        "has_default": variable.has_default,
        "default": hcl.hcl_value(variable.default) if variable.has_default else "",
        "sensitive": variable.sensitive,
        "per_environment": variable.per_environment,
    }


def providers(spec: Any) -> list[dict[str, str]]:
    """Required providers, sorted by local name."""
    families = selected(spec.terraform.family_names())
    return [
        {
            "name": provider.name,
            "source": provider.source,
            "version": provider.version,
            "reason": provider.reason,
        }
        for provider in providers_for(families)
    ]


def outputs(spec: Any) -> list[dict[str, str]]:
    """Outputs of the module: the base output, then those of the families.

    Deduplicated by name: the `namespace` family declares the same output as the
    base, and it really is the same one.
    """
    descriptions = dict(BASE_OUTPUTS)
    for family in selected(spec.terraform.family_names()):
        for name, description in family.outputs.items():
            descriptions.setdefault(name, description)
    return [
        {"name": name, "description": description, "value": OUTPUT_VALUES[name]}
        for name, description in descriptions.items()
    ]


def backend(spec: Any) -> dict[str, Any]:
    """State backend: its type, and the keys common to every environment.

    The keys specific to an environment — `key`, `prefix` — are added by
    `derive_env`, so that two environments never write the same state.
    """
    configuration = spec.terraform.backend
    return {
        "kind": configuration.kind.value,
        "config": dict(configuration.config),
        "is_local": configuration.kind.value == "local",
        "state_file": DEFAULT_STATE_FILE,
    }


def kubernetes(spec: Any) -> dict[str, Any]:
    """How the provider reaches the cluster."""
    access = spec.terraform.kubernetes
    return {
        "auth": access.auth.value,
        "config_path": access.config_path,
        "context_per_environment": access.context_per_environment,
        "uses_kubeconfig": access.auth is KubernetesAuth.KUBECONFIG,
    }


def base_labels(spec: Any) -> dict[str, str]:
    """Business labels of the service, taken up identically by every domain.

    The `app.kubernetes.io/*` labels do not appear here: they are computed in
    `locals.tf`, from variables, so that the module stays correct when it is
    called with values other than the generated ones.
    """
    return dict(spec.service.labels)


def extras(spec: Any) -> dict[str, bool]:
    """Extra files requested."""
    requested = spec.terraform.extras
    return {"makefile": requested.makefile, "tflint_config": requested.tflint_config}


def families(spec: Any) -> list[dict[str, Any]]:
    """Retained families, with what the module README must say about them."""
    return [
        {
            "name": family.name,
            "summary": family.summary,
            "details": family.details,
            "resources": list(family.resources),
            "providers": list(family.providers),
            "traps": list(family.traps),
            "variables": [variable.name for variable in family.variables],
            "outputs": sorted(family.outputs),
        }
        for family in selected(spec.terraform.family_names())
    ]


def creates_namespace(spec: Any) -> bool:
    """True when Terraform creates the namespace instead of attaching to it."""
    return spec.terraform.uses(ResourceFamily.NAMESPACE)
