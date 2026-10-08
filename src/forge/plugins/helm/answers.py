"""Projection of the unified specification into copier's `domain` dict.

Implementation of the `forge_answers` hook (DESIGN.md §2.2) for the Helm domain,
and the central piece of the port: every template reads what this module
produces.

The contract, upheld by :func:`build`:

* **the same names as in the legacy generator** — converting a template comes down
  to prefixing `domain.` (or to using the loop variable of a `yield`);
* **JSON-serialisable** — no pydantic object, no `Enum`, no `set`: the dict is
  written as-is into `.copier-answers.yml` and replayed by `copier update`;
* **frozen order** — keys inserted in a stable order, lists in the order of the
  specification, never by accident.

The computation lives in :mod:`forge.plugins.helm.derive` (static part),
:mod:`forge.plugins.helm.derive_env` (per-environment part) and
:mod:`forge.plugins.helm.tree` (generated paths); this module only assembles, and
carries the cross-checks the sub-model cannot do by itself.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm import derive, derive_env, tree
from forge.plugins.helm.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_ENVIRONMENT_NAME_LENGTH,
    MAX_SERVICE_NAME_LENGTH,
)
from forge.plugins.helm.enums import NamespaceStrategy
from forge.plugins.helm.names import is_valid_email
from forge.plugins.helm.profiles import is_production_name
from forge.plugins_api import checks
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Build the `domain` dict passed to copier for the Helm domain.

    `spec` is the assembled root model: `spec.service` (shared block) and
    `spec.helm` (a `HelmSpec` instance).
    """
    service = spec.service
    helm = spec.helm

    contexts = derive.components(helm, service_name=service.name)

    return {
        # -- chart identity ---------------------------------------------------
        "chart_dir": tree.chart_dir(service.name),
        # Prefix of every generated Helm helper: `<chart>.<suffix>`.
        # Port of the `helper` key of the legacy rendering context.
        "helper": service.name,
        "chart_version": helm.chart_version,
        "app_version": helm.app_version,
        **derive.maintainer(service),
        "kubernetes": derive.kubernetes(helm),
        # -- layout and namespaces -------------------------------------------
        "layout": helm.layout.value,
        "namespace_strategy": helm.namespace_strategy.value,
        "create_namespace": helm.create_namespace,
        # -- image, secrets, extras -------------------------------------------
        "image": derive.image(helm),
        "secrets": derive.secrets(helm),
        "extras": derive.extras(helm),
        # -- components --------------------------------------------------------
        "components": contexts,
        "component_names": [context["name"] for context in contexts],
        "component_slots": derive.component_slots(helm, contexts),
        # -- environments -------------------------------------------------------
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        "environments": derive_env.environments(spec),
        # -- documentation -------------------------------------------------------
        "chart_files": tree.chart_files(spec),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Checks `HelmSpec` cannot do: it does not see `service:`.

    Four families, all justified by an arbitration of MIGRATION.md:

    * **H4** — the keys of `helm.environments` must appear in
      `service.environments`, which now carries the name and the order;
    * **H6** — length caps and address format: these are constraints of
      `Chart.yaml` and of the 63-character budget of Kubernetes resource names,
      which the core has no business knowing;
    * **`custom` namespaces** — an environment absent from `helm.environments`
      escapes the model check;
    * **H2** — divergence between the `production` flag and recognition by name,
      reported as a *warning* rather than decided silently.

    The order of the list is deterministic: it is displayed as-is.
    """
    helm = getattr(spec, "helm", None)
    if helm is None:
        return []

    issues: list[Issue] = []
    issues.extend(
        checks.unknown_environments(
            spec, "helm", {"helm.environments": helm.environments}
        )
    )
    issues.extend(_check_limits(spec))
    issues.extend(_check_custom_namespaces(spec, helm))
    issues.extend(_check_production_divergence(spec))
    return issues


def _check_limits(spec: Any) -> list[Issue]:
    """Apply the length caps and the address format (H6).

    These checks bear on the shared `service:` block, but they are Helm
    constraints: the service name becomes the chart name and the prefix of every
    resource, the description is echoed in `Chart.yaml`, and the address feeds its
    `maintainers` list.
    """
    service = spec.service
    issues: list[Issue] = []

    if len(service.name) > MAX_SERVICE_NAME_LENGTH:
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.name is {len(service.name)} characters long; Helm "
                    f"accepts at most {MAX_SERVICE_NAME_LENGTH}, the name serving "
                    "as chart name and as prefix of every resource."
                ),
                hint=(
                    "Shorten service.name: Kubernetes caps a resource name at 63 "
                    "characters, suffixes included."
                ),
                domains=("helm",),
            )
        )

    if len(service.description) > MAX_DESCRIPTION_LENGTH:
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.description is {len(service.description)} "
                    f"characters long; the description field of Chart.yaml accepts "
                    f"at most {MAX_DESCRIPTION_LENGTH}."
                ),
                hint=(
                    "Sum service.description up in one line; the detail belongs in "
                    "the project README."
                ),
                domains=("helm",),
            )
        )

    for env in service.environments:
        if len(env.name) > MAX_ENVIRONMENT_NAME_LENGTH:
            issues.append(
                Issue(
                    level="error",
                    message=(
                        f"the environment name '{env.name}' is "
                        f"{len(env.name)} characters long; Helm accepts at most "
                        f"{MAX_ENVIRONMENT_NAME_LENGTH}."
                    ),
                    hint=(
                        f"Shorten '{env.name}': that name goes into the derived "
                        "namespace and into the Ingress host."
                    ),
                    domains=("helm",),
                )
            )

    if service.owner_email and not is_valid_email(service.owner_email):
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.owner_email '{service.owner_email}' is not a valid "
                    "email address; it feeds the maintainers list of Chart.yaml."
                ),
                hint="Use the 'team@example.com' form.",
                domains=("helm",),
            )
        )
    return issues


def _check_custom_namespaces(spec: Any, helm: Any) -> list[Issue]:
    """Require an explicit namespace for every environment, `custom` strategy.

    `HelmSpec` already checks the environments present in `helm.environments`;
    this check adds the ones that do not appear there at all, and that only the
    complete list of `service.environments` reveals.
    """
    if helm.namespace_strategy is not NamespaceStrategy.CUSTOM:
        return []
    return [
        Issue(
            level="error",
            message=(
                f"environment '{env.name}': the \"custom\" namespace strategy "
                "requires an explicit namespace, and none is declared."
            ),
            hint=(
                f"Set helm.environments.{env.name}.namespace, or switch "
                "helm.namespace_strategy to per_env to derive "
                f"'{spec.service.name}-{env.name}'."
            ),
            domains=("helm",),
        )
        for env in spec.service.environments
        if helm.overrides(env.name).namespace is None
    ]


def _check_production_divergence(spec: Any) -> list[Issue]:
    """Report a disagreement between `production:` and the environment name (H2).

    Two sources describe the same thing: the core's explicit flag and the
    recognition by name inherited from the legacy tool. The flag wins, but silence
    would be a trap — an environment named `prod` without `production: true` does
    get the production profile through its name, whereas an environment named
    `live` with `production: true` gets it through the flag: in both cases the user
    believes they wrote something else.
    """
    issues: list[Issue] = []
    for env in spec.service.environments:
        by_name = is_production_name(env.name)
        if env.production == by_name:
            continue
        if env.production:
            message = (
                f"the environment '{env.name}' carries production: true while its "
                "name is not recognised as a production name; the flag wins and "
                "the prod profile is applied."
            )
            hint = (
                f"Rename '{env.name}' to 'prod' to lift the ambiguity, or keep "
                "that name if your convention wants it that way."
            )
        else:
            message = (
                f"the environment '{env.name}' carries a production name but not "
                "production: true; the prod profile is applied to it through "
                "recognition of the name."
            )
            hint = (
                f"Add production: true to the environment '{env.name}' to make the "
                "intent explicit."
            )
        issues.append(
            Issue(level="warning", message=message, hint=hint, domains=("helm",))
        )
    return issues
