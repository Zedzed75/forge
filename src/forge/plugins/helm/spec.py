"""The `helm:` section of forge.yml.

Port of `helm_forge.models.spec` (MIGRATION.md §4). The identity of the service —
name, description, maintainer, list and order of the environments — moved up into
the core's shared `service:` block; what remains here describes **how the service
is packaged for Kubernetes**: chart version, target cluster version, layout,
namespaces, image, components, secrets, extras.

Three structural divergences from the legacy tool, all arbitrated
(MIGRATION.md §4):

* `helm.environments` is a **dict keyed by environment name** (H4), on the model
  of `ansible.hosts.<env>`: the name and the order live in
  `service.environments`. Direct consequence: the "unknown environment key" check
  can no longer be done here — it belongs to the plugin cross-check, like
  `ansible.answers.cross_check`;
* `layout: umbrella` (H3), `extras.helmfile`, `extras.ci` and the
  `servicemonitor` block (H7, H8) are not ported; `extra="forbid"` will refuse
  them cleanly;
* `validate_assignment=True` is not reintroduced (H11): this model is
  **immutable after validation**, and no longer derives anything itself.

Derivation contract — what `derive.py` has to guarantee
======================================================

The legacy tool computed these values in its validators. They are what makes a
minimal `forge.yml` equivalent to a complete one; MIGRATION.md §4 explicitly asks
that they be kept. This model exposes everything they require, and nothing more
is needed.

1. **Namespace of each environment**, when `helm.environments.<env>.namespace` is
   absent, according to `namespace_strategy`:
   `single` -> `service.name`; `per_env` -> `<service.name>-<env>`;
   `custom` -> an error, an explicit namespace is required for every environment
   of `service.environments`.

2. **Profile applied to each environment** — `profiles.profile_for(name,
   production=env.production)` (arbitration H2):
   `production: true` forces the `prod` profile; otherwise recognition by name
   applies (`prod`, `prd`, `production`, `stage`, `stg`, `develop`...).
   The cross-check emits a *warning* level `Issue` when the two sources diverge,
   rather than deciding silently. For each environment and each component, the
   profile fills in the values left empty: `log_level`, `replicas` (workloads
   only), `hpa_enabled` (when the `hpa` addon is present), `pdb_enabled` (when
   the `pdb` addon is present), and
   `resources = component.resources.scaled(profile.resource_multiplier)` when the
   multiplier is not 1. An override entry is created for **every** component of
   **every** environment, even when empty in the spec.

3. **Ingress host** of each component carrying the `ingress` addon, when
   `ingress_host` is absent (arbitrations H1 and H2):
   the prefix is `service.name` for the **first** exposed component in the order
   of `components`, and `<component>-<service.name>` for the following ones, so
   that two exposed components do not fight over the same host;
   then, **when `service.environments[].domain` is set**, the host is
   `<prefix>.<env-domain>`, **without** reinserting the environment name (the
   domain already carries it); **otherwise**, legacy fallback:
   `<prefix>[.<env> when profile.host_includes_env].<component.ingress.base_domain>`.

4. **Image tag**, according to `image.strategy`:
   `appVersion` -> an empty tag in the values, falling back to
   `.Chart.AppVersion` (that is, `helm.app_version`); `per_env` -> the tag of
   `helm.environments.<env>.components.<name>.image_tag`, to be left empty when
   it is not supplied; `fixed` -> `image.tag`, whose presence the model already
   guarantees.

The plugin cross-check (outside this module) must in addition verify: the keys of
`helm.environments` that are absent from `service.environments` (H4); the
`MAX_SERVICE_NAME_LENGTH`, `MAX_ENVIRONMENT_NAME_LENGTH` and
`MAX_DESCRIPTION_LENGTH` caps, as well as the format of `service.owner_email`
(H6); the completeness of the namespaces under the `custom` strategy; the H2
divergence.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.components import ComponentSpec, ResourcesSpec
from forge.plugins.helm.constants import (
    DEFAULT_KUBERNETES_VERSION,
    KUBERNETES_VERSIONS,
)
from forge.plugins.helm.enums import (
    AddonKind,
    ImagePullPolicy,
    Layout,
    NamespaceStrategy,
    SecretStrategy,
    TagStrategy,
)
from forge.plugins.helm.names import ImageRepository
from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, SemVer, Subdomain


class KubernetesTarget(ForgeModel):
    """Version of Kubernetes targeted by the generated chart."""

    #: Targeted minor version; must belong to `KUBERNETES_VERSIONS`.
    version: str = DEFAULT_KUBERNETES_VERSION

    @field_validator("version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value not in KUBERNETES_VERSIONS:
            supported = ", ".join(KUBERNETES_VERSIONS)
            raise ValueError(f"Kubernetes version {value!r} is not supported: {supported}")
        return value

    @property
    def kube_version_constraint(self) -> str:
        """Constraint to write into the `kubeVersion` field of `Chart.yaml`.

        The `-0` suffix allows pre-releases, without which Helm rejects a cluster
        whose version carries a suffix (`v1.36.0-eks-1`).
        """
        return f">={self.version}.0-0"

    @property
    def full_version(self) -> str:
        """Full version passed to kubeconform so it picks its schemas."""
        return f"{self.version}.0"


class ImageSpec(ForgeModel):
    """Container image used by default by every component."""

    #: OCI registry (`docker.io`, `ghcr.io`, `registry.gitlab.com`).
    registry: Subdomain = "docker.io"

    #: Repository within the registry, without a tag (`acme/shop`).
    repository: ImageRepository = "app"

    #: Origin of the tag: appVersion (falls back to `.Chart.AppVersion`) |
    #: per_env (one tag per environment) | fixed (the tag below).
    strategy: TagStrategy = TagStrategy.APP_VERSION

    #: Frozen tag; mandatory with the `fixed` strategy, forbidden otherwise.
    tag: str = ""

    #: Pull policy: Always | IfNotPresent | Never.
    pull_policy: ImagePullPolicy = ImagePullPolicy.IF_NOT_PRESENT

    #: Name of the dockerconfigjson Secret for a private registry; absent = a
    #: public registry.
    pull_secret_name: str | None = None

    @model_validator(mode="after")
    def _check_tag(self) -> ImageSpec:
        if self.strategy is TagStrategy.FIXED and not self.tag:
            raise ValueError(
                'image.tag is mandatory with the "fixed" tag strategy'
            )
        if self.strategy is not TagStrategy.FIXED and self.tag:
            raise ValueError(
                'image.tag must only be set with the "fixed" strategy; '
                "use the per-environment override otherwise"
            )
        return self


class SecretSpec(ForgeModel):
    """How the secrets of the project are managed.

    No strategy ever produces a real secret value: the generator only builds
    placeholders to be filled outside the repository.
    """

    #: Management mode: placeholder | external-secrets | sealed-secrets | none.
    strategy: SecretStrategy = SecretStrategy.PLACEHOLDER

    #: Name of the SecretStore or ClusterSecretStore, for external-secrets.
    store_name: str = "default"

    #: Refresh interval, for external-secrets (`1h`, `15m`).
    refresh_interval: str = "1h"


class ExtrasSpec(ForgeModel):
    """Extra files generated next to the chart.

    The legacy `helmfile` and `ci` are not ported (arbitrations H7 and H8): no
    template rendered them, and CI is repository-level (decision Q6).
    """

    #: Generates a Makefile of shortcuts (lint, template, upgrade).
    makefile: bool = True

    #: Generates the Helm tests (`templates/tests/`), launched by `helm test`.
    helm_tests: bool = True


class EnvironmentOverride(ForgeModel):
    """Divergences of a component for a given environment.

    Only the non-null values are written into `values-<env>.yaml`: an environment
    file contains differences only, never a complete copy of `values.yaml`. A
    missing value is computed by `derive.py` from the environment profile.
    """

    #: Replica count in this environment; absent = the profile value.
    replicas: int | None = Field(default=None, ge=0)

    #: Enables autoscaling here; absent = the profile value.
    hpa_enabled: bool | None = None

    #: Enables the disruption budget here; absent = the profile value.
    pdb_enabled: bool | None = None

    #: Forced Ingress host; absent = derived (H1) from the environment domain, or
    #: from `ingress.base_domain`.
    ingress_host: Subdomain | None = None

    #: Requests/limits forced here; absent = those of the component, multiplied
    #: by `profile.resource_multiplier`.
    resources: ResourcesSpec | None = None

    #: Image tag specific to the environment, with the `per_env` strategy.
    image_tag: str | None = None


class EnvironmentSpec(ForgeModel):
    """Overrides of an environment, keyed by its name in `helm.environments`.

    The name and the order of the environments live in `service.environments`
    (arbitration H4): this model therefore carries overrides only, and an
    environment absent from that dict is perfectly valid — it takes everything
    from its profile.
    """

    #: Deployment namespace; absent = derived from `namespace_strategy`.
    namespace: DnsLabel | None = None

    #: Log level; absent = the profile value (`debug` in dev).
    log_level: str | None = None

    #: Overrides per component name; the names must exist in `helm.components`.
    components: dict[str, EnvironmentOverride] = Field(default_factory=dict)

    #: Free values injected as-is into `values-<env>.yaml`.
    extra_values: dict[str, Any] = Field(default_factory=dict)


class HelmSpec(ForgeModel):
    """The complete `helm:` section."""

    #: Version of the chart itself, in the SemVer sense Helm requires.
    chart_version: SemVer = "0.1.0"

    #: Version of the packaged application, echoed in `appVersion` and serving as
    #: the image tag with the `appVersion` strategy.
    app_version: str = Field(default="1.0.0", min_length=1)

    #: Version of Kubernetes targeted: the `kubeVersion` constraint and the
    #: schemas kubeconform uses.
    kubernetes: KubernetesTarget = Field(default_factory=KubernetesTarget)

    #: Layout of the project; only `single` is generated (arbitration H3).
    layout: Layout = Layout.SINGLE

    #: Namespace derivation: single | per_env | custom.
    namespace_strategy: NamespaceStrategy = NamespaceStrategy.PER_ENV

    #: False by default: the namespace is almost always managed upstream, and
    #: creating it in the chart would make it deletable by `helm uninstall`.
    create_namespace: bool = False

    #: Container image used by default by every component.
    image: ImageSpec = Field(default_factory=ImageSpec)

    #: Generated workloads; at least one. The order is significant: the first
    #: exposed component carries the bare Ingress host (cf. derivation 3).
    components: list[ComponentSpec] = Field(min_length=1)

    #: How the secrets are managed; never a generated secret value.
    secrets: SecretSpec = Field(default_factory=SecretSpec)

    #: Extra files generated next to the chart.
    extras: ExtrasSpec = Field(default_factory=ExtrasSpec)

    #: Overrides per environment, keyed by name (arbitration H4). The keys must
    #: appear in `service.environments` — checked by the plugin cross-check, the
    #: only one that sees the shared block.
    environments: dict[str, EnvironmentSpec] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Cross-validation
    # ------------------------------------------------------------------

    @field_validator("components")
    @classmethod
    def _unique_component_names(cls, value: list[ComponentSpec]) -> list[ComponentSpec]:
        require_unique((component.name for component in value), "component names")
        return value

    @model_validator(mode="after")
    def _check_environment_overrides(self) -> HelmSpec:
        """Check that the overrides quote declared components.

        The counterpart of this check — the unknown environment keys — cannot be
        done here: `HelmSpec` does not see `service.environments`.
        """
        known = {component.name for component in self.components}
        for name, env in self.environments.items():
            unknown = sorted(set(env.components) - known)
            if unknown:
                raise ValueError(
                    f"environment {name!r}: overrides for unknown components {unknown}"
                )
        return self

    @model_validator(mode="after")
    def _check_custom_namespaces(self) -> HelmSpec:
        """Require an explicit namespace for every declared environment.

        The `custom` strategy derives nothing: it expects a namespace written by
        hand. This check covers the environments present in `helm.environments`;
        the one for the environments that do not appear there at all belongs to
        the cross-check, the only place that knows the complete list.
        """
        if self.namespace_strategy is not NamespaceStrategy.CUSTOM:
            return self
        for name, env in self.environments.items():
            if env.namespace is None:
                raise ValueError(
                    f'environment {name!r}: the "custom" namespace strategy '
                    "requires an explicit namespace"
                )
        return self

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def component(self, name: str) -> ComponentSpec:
        """Return the `name` component, or raise `KeyError`."""
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(f"unknown component: {name!r}")

    @property
    def component_names(self) -> tuple[str, ...]:
        """Component names, in declaration order."""
        return tuple(component.name for component in self.components)

    def overrides(self, environment: str) -> EnvironmentSpec:
        """Overrides of the `environment` environment, empty when it has none.

        An environment declared in `service.environments` but absent from
        `helm.environments` is valid: it takes everything from its profile.
        """
        return self.environments.get(environment) or EnvironmentSpec()

    def uses_addon(self, addon: AddonKind) -> bool:
        """Tell whether at least one component uses the given addon."""
        return any(component.has(addon) for component in self.components)

    def exposed_components(self) -> tuple[str, ...]:
        """Names of the components carrying the `ingress` addon, in declared order.

        The first of this list carries the bare host (`<service>.<domain>`); the
        following ones are prefixed with their own name (cf. derivation 3).
        """
        return tuple(
            component.name
            for component in self.components
            if component.has(AddonKind.INGRESS)
        )
