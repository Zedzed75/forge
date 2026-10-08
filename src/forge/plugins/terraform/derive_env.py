"""The part of the projection that varies from one environment to the next.

One Terraform root per environment, and for each of them: its namespace, its
cluster context, its state location, its values. The module itself is written
only once — that is the whole point of the layout.

Two invariants hold this module together:

* **two environments never write the same state.** The state key is derived from
  the service and the environment when the specification does not give it; two
  roots sharing a state would destroy each other at the first apply, and nothing
  in Terraform reports it in advance.
* **no secret value goes into `terraform.tfvars`.** The file only takes up
  non-secret variables, and only those the module — or the root — declares:
  Terraform refuses a tfvars quoting an unknown variable.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import derive, hcl
from forge.plugins.terraform.constants import DEFAULT_STATE_FILE
from forge.plugins.terraform.enums import ResourceFamily


def environments(spec: Any) -> list[dict[str, Any]]:
    """One entry per `service.environments` environment, in order."""
    variables = derive.root_variables(spec)
    declared = {variable["name"]: variable for variable in variables}
    arguments = [
        {"name": variable["name"], "value": f"var.{variable['name']}"}
        for variable in derive.variables(spec)
    ]
    return [
        _environment(spec, env, declared, variables, arguments)
        for env in spec.service.environments
    ]


def _environment(
    spec: Any,
    env: Any,
    declared: dict[str, dict[str, Any]],
    variables: list[dict[str, Any]],
    arguments: list[dict[str, str]],
) -> dict[str, Any]:
    """Projection of one environment."""
    terraform = spec.terraform
    override = terraform.overrides(env.name)
    namespace = terraform.namespace_for(spec.service.name, env.name)
    values = _values(spec, env, override, namespace, declared)

    return {
        "name": env.name,
        "production": env.production,
        "domain": env.domain or "",
        "namespace": namespace,
        "kube_context": values.get("kube_context", ""),
        "backend_config": _backend_config(spec, env, override),
        "tfvars": [
            {"name": name, "value": hcl.hcl_value(value)}
            for name, value in values.items()
            if name in declared and not declared[name]["sensitive"]
        ],
        "module_arguments": arguments,
        "variable_names": [variable["name"] for variable in variables],
    }


def _values(
    spec: Any,
    env: Any,
    override: Any,
    namespace: str,
    declared: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Pre-filled values of the environment, in the order of the `tfvars`.

    The order is the reading order: first what identifies the environment, then
    the cluster access, then the settings of the retained families.
    """
    terraform = spec.terraform
    values: dict[str, Any] = {
        "service_name": spec.service.name,
        "environment": env.name,
        "namespace": namespace,
        "labels": {**spec.service.labels, **override.labels},
    }

    if "kube_context" in declared:
        values["kube_context"] = override.kube_context or (
            env.name if terraform.kubernetes.context_per_environment else ""
        )

    if terraform.uses(ResourceFamily.QUOTA):
        quota = override.quota
        for name, attribute in (
            ("quota_cpu", "cpu"),
            ("quota_memory", "memory"),
            ("quota_pods", "pods"),
        ):
            explicit = getattr(quota, attribute, None) if quota else None
            values[name] = explicit if explicit is not None else _default(declared, name)

    if terraform.uses(ResourceFamily.TLS_CERTIFICATE):
        names = list(override.tls_dns_names)
        if not names and env.domain:
            names = [f"{spec.service.name}.{env.domain}"]
        values["tls_dns_names"] = names
        values["tls_common_name"] = names[0] if names else ""

    return values


def _default(declared: dict[str, dict[str, Any]], name: str) -> Any:
    """Default value declared for `name`, as the catalogue gives it.

    It is read back from the catalogue rather than copied here: a default value
    changed in a family must show up in the `terraform.tfvars` without anyone
    having to think about it.
    """
    return _CATALOG_DEFAULTS[name]


def _catalog_defaults() -> dict[str, Any]:
    """Default values of every family variable, indexed by name."""
    from forge.plugins.terraform.catalog.registry import all_families

    return {
        variable.name: variable.default
        for family in all_families()
        for variable in family.variables
    }


#: Computed once: the catalogue is frozen at module load.
_CATALOG_DEFAULTS: dict[str, Any] = _catalog_defaults()


def _backend_config(spec: Any, env: Any, override: Any) -> list[dict[str, str]]:
    """Backend keys of this environment: common, then specific, then derived.

    The state key is **always** present in the output: it is what guarantees that
    two environments do not write to the same place.
    """
    configuration: dict[str, str] = {
        **spec.terraform.backend.config,
        **override.backend_config,
    }
    kind = spec.terraform.backend.kind.value
    derived = _state_key(spec.service.name, env.name, kind)
    for key, value in derived.items():
        configuration.setdefault(key, value)
    return [
        {"name": key, "value": hcl.hcl_value(value)}
        for key, value in sorted(configuration.items())
    ]


def _state_key(service_name: str, environment: str, kind: str) -> dict[str, str]:
    """Derived state location, specific to the environment, per backend."""
    if kind == "local":
        return {"path": DEFAULT_STATE_FILE}
    if kind == "s3":
        return {"key": f"{service_name}/{environment}/{DEFAULT_STATE_FILE}"}
    if kind == "gcs":
        return {"prefix": f"{service_name}/{environment}"}
    if kind == "azurerm":
        return {"key": f"{service_name}-{environment}.tfstate"}
    return {}
