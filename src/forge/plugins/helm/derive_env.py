"""Per-environment derivation: namespaces, profiles, hosts, overrides.

The **variable** part of the `domain` dict, split from
:mod:`forge.plugins.helm.derive` which only computes its static part. This is
where what the legacy tool did in `ProjectSpec._derive_namespaces`,
`_derive_environment_defaults` and `_hostname` lives — three validators that wrote
into `__dict__` to work around `validate_assignment=True`. That mode is not
reintroduced (arbitration H11): the spec stays immutable after validation, and the
derivation produces dicts directly.

What makes a minimal `forge.yml` equivalent to a complete one fits in one
sentence: **an override entry is created for every component of every
environment**, even when absent from the specification, and the environment
profile fills in every value left empty there. The templates therefore never have
to wonder whether an override exists.

Values stay at `None` exactly where the legacy tool left them at `None`: the
values templates test `is not none` so as to write real divergences only.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm.derive import resources as resources_context
from forge.plugins.helm.enums import AddonKind, NamespaceStrategy
from forge.plugins.helm.profiles import EnvironmentProfile, profile_for

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------


def namespace(helm: Any, service_name: str, env_name: str, override: Any) -> str:
    """Deployment namespace of an environment.

    Port of `ProjectSpec._derive_namespaces`: an explicit namespace always wins;
    otherwise `single` gives `<service>`, `per_env` gives `<service>-<env>`, and
    `custom` derives nothing at all — that is the very principle of that strategy.

    The model already refuses a missing namespace for an environment **present**
    in `helm.environments`; what remains here is the case of an environment that
    does not appear there at all, which only the cross-check sees coming
    (`answers.cross_check`). The error is raised rather than guessed: a chart
    deployed into an invented namespace would be worse than a generation failure.
    """
    if override.namespace is not None:
        return override.namespace
    if helm.namespace_strategy is NamespaceStrategy.SINGLE:
        return service_name
    if helm.namespace_strategy is NamespaceStrategy.PER_ENV:
        return f"{service_name}-{env_name}"
    raise ValueError(
        f"environment '{env_name}': the \"custom\" namespace strategy requires an "
        f"explicit namespace in helm.environments.{env_name}.namespace"
    )


# ---------------------------------------------------------------------------
# Ingress host
# ---------------------------------------------------------------------------


def host_prefix(helm: Any, service_name: str, component_name: str) -> str:
    """Host prefix of an exposed component.

    Port of `ProjectSpec._hostname`: the **first** exposed component, in the order
    of `components`, carries the service name alone; the following ones are
    prefixed with their own name, so that two exposed components do not fight over
    the same host.
    """
    exposed = helm.exposed_components()
    if exposed and exposed[0] == component_name:
        return service_name
    return f"{component_name}-{service_name}"


def ingress_host(
    helm: Any,
    service_name: str,
    component: Any,
    env: Any,
    profile: EnvironmentProfile,
) -> str:
    """Ingress host of a component for an environment (arbitrations H1, H2).

    `service.environments[].domain` **wins** when it is set: the host becomes
    `<prefix>.<env-domain>`, **without** reinserting the environment name, since
    the domain already carries it. Otherwise, a literal fallback on the legacy
    behaviour: `<prefix>[.<env> when profile.host_includes_env].<ingress.base_domain>`.

    `host_includes_env` comes from the **resolved** profile (H2), hence from
    `production: true` when it is present, and from the environment name
    otherwise.
    """
    prefix = host_prefix(helm, service_name, component.name)
    if env.domain:
        return f"{prefix}.{env.domain}"
    parts = [prefix]
    if profile.host_includes_env:
        parts.append(env.name)
    parts.append(component.ingress.base_domain)
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Per-component overrides
# ---------------------------------------------------------------------------


def component_override(
    helm: Any,
    service_name: str,
    component: Any,
    env: Any,
    profile: EnvironmentProfile,
    override: Any,
) -> dict[str, Any]:
    """Divergences of a component for an environment, profile applied.

    Port of `ProjectSpec._derive_environment_defaults`, condition by condition. A
    value stays at `None` exactly where the legacy tool left it at `None`:

    * `replicas`: the profile only fills in the **workloads**; a CronJob has no
      replicas, so the key stays null;
    * `hpa_enabled` / `pdb_enabled`: null when the component does not carry the
      matching addon, otherwise the values would announce an autoscaling no
      resource implements;
    * `ingress_host`: null when the component is not exposed;
    * `resources`: null when the profile multiplier is 1 — there is then no
      divergence to write into `values-<env>.yaml`;
    * `image_tag`: never derived. It is worth only what the specification
      contains; the project's tag strategy lives in `domain.image.strategy`, and
      it is the values template that draws the consequences.
    """
    replicas = override.replicas
    if replicas is None and component.is_workload:
        replicas = profile.replicas

    hpa_enabled = override.hpa_enabled
    if hpa_enabled is None and component.has(AddonKind.HPA):
        hpa_enabled = profile.hpa_enabled

    pdb_enabled = override.pdb_enabled
    if pdb_enabled is None and component.has(AddonKind.PDB):
        pdb_enabled = profile.pdb_enabled

    host = override.ingress_host
    if host is None and component.has(AddonKind.INGRESS):
        host = ingress_host(helm, service_name, component, env, profile)

    scaled_resources = override.resources
    if scaled_resources is None and profile.resource_multiplier != 1:
        scaled_resources = component.resources.scaled(profile.resource_multiplier)

    return {
        "name": component.name,
        "replicas": replicas,
        "hpa_enabled": hpa_enabled,
        "pdb_enabled": pdb_enabled,
        "ingress_host": host,
        "resources": (
            None if scaled_resources is None else resources_context(scaled_resources)
        ),
        "image_tag": override.image_tag,
    }


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------


def profile_context(profile: EnvironmentProfile) -> dict[str, Any]:
    """Resolved profile of an environment, in JSON-serialisable form.

    Exposed as-is so that the templates can document *why* a value is what it is
    ("prod profile: 3 replicas") without reimplementing recognition by name.
    """
    return {
        "replicas": profile.replicas,
        "hpa_enabled": profile.hpa_enabled,
        "pdb_enabled": profile.pdb_enabled,
        "log_level": profile.log_level,
        "resource_multiplier": profile.resource_multiplier,
        "host_includes_env": profile.host_includes_env,
    }


def environments(spec: Any) -> list[dict[str, Any]]:
    """One environment per `service.environments` entry, in its order.

    The promotion order (dev -> staging -> prod) is that of the shared block: the
    `helm.environments` dict carries overrides only (arbitration H4).

    `components` is a dict **keyed by component name**, in the order of
    `helm.components`: that is the shape the legacy templates read
    (`env.components[component.name]`). An entry exists for every component, even
    when absent from the specification.
    """
    helm = spec.helm
    service_name = spec.service.name
    result: list[dict[str, Any]] = []

    for env in spec.service.environments:
        overrides = helm.overrides(env.name)
        profile = profile_for(env.name, production=env.production)
        by_component: dict[str, dict[str, Any]] = {}
        for component in helm.components:
            own = overrides.components.get(component.name)
            by_component[component.name] = component_override(
                helm,
                service_name,
                component,
                env,
                profile,
                own if own is not None else _EMPTY_OVERRIDE,
            )
        result.append(
            {
                "name": env.name,
                "namespace": namespace(helm, service_name, env.name, overrides),
                "domain": env.domain or "",
                "production": env.production,
                "log_level": overrides.log_level or profile.log_level,
                "profile": profile_context(profile),
                "components": by_component,
                "extra_values": dict(overrides.extra_values),
            }
        )
    return result


def _empty_override() -> Any:
    """Empty override, used for a component absent from `helm.environments`.

    Built only once: the model being immutable, sharing it is risk-free and avoids
    instantiating one pydantic model per component and per environment.
    """
    from forge.plugins.helm.spec import EnvironmentOverride

    return EnvironmentOverride()


#: Shared neutral override (cf. :func:`_empty_override`).
_EMPTY_OVERRIDE = _empty_override()
