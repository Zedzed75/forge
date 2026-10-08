"""Enumerations of the `helm:` section of forge.yml.

Port of `helm_forge.models.enums` (MIGRATION.md §4).

They all inherit from `StrEnum`: the value serialised into `forge.yml` is
therefore the readable string, and direct comparison with a string works — which
the resolution of the resource profiles depends on. The values that appear
verbatim in a Kubernetes manifest keep the exact casing the API expects
(`ClusterIP`, `IfNotPresent`).

Two deliberate divergences from the legacy tool, both applying the same
principle: **a value that is declared but not generated is a trap**, since it
passes the validation of an `extra="forbid"` schema and then blows generation up.

* `Layout.UMBRELLA` is removed (arbitration H3): the legacy planner raised
  `NotImplementedError` and no template existed. To be reintroduced along with
  its templates.
* `AddonKind.SERVICEMONITOR` is removed (arbitration H7): Prometheus scraping is
  out of the scope of phase 4.
* `CIProvider` is not ported (arbitration H8): CI is repository-level
  (decision Q6), and the two domains expressed it in two different ways.
"""

from __future__ import annotations

from enum import StrEnum


class Layout(StrEnum):
    """Layout of the generated project.

    `single`: a single chart holding every component — the only accepted value
    today (arbitration H3).
    """

    SINGLE = "single"


class ComponentKind(StrEnum):
    """Type of workload carried by a component.

    `deployment`: stateless workload, the usual value.
    `statefulset`: stable network identity and volume (forces a headless Service
    and persistence).
    `cronjob`: scheduled run, neither exposed nor autoscaled.
    """

    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    CRONJOB = "cronjob"


class AddonKind(StrEnum):
    """Additional resource attachable to a component.

    The presence of an entry in `ComponentSpec.addons` decides which template
    files are actually generated. Activation at runtime stays driven by an
    `enabled` flag in the values, overridable per environment.

    The declaration order below is the **canonical order**: the `addons` list is
    renormalised to it, so that two equivalent specs produce the same project
    whatever the order they were typed in.
    """

    SERVICE = "service"
    INGRESS = "ingress"
    CONFIGMAP = "configmap"
    SECRET = "secret"
    HPA = "hpa"
    PDB = "pdb"
    SERVICEACCOUNT = "serviceaccount"
    NETWORKPOLICY = "networkpolicy"


class ServiceType(StrEnum):
    """Type of Kubernetes Service exposing the workload."""

    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


class IngressController(StrEnum):
    """Target ingress controller, which determines annotations and ingressClassName."""

    NGINX = "nginx"
    TRAEFIK = "traefik"


class ImagePullPolicy(StrEnum):
    """Pull policy for the container image."""

    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


class TagStrategy(StrEnum):
    """Origin of the image tag in the generated values.

    `appVersion`: empty tag, falls back to `.Chart.AppVersion`.
    `per_env`: a distinct tag per environment (`helm.environments.<env>`).
    `fixed`: a single frozen tag, supplied by `helm.image.tag`.
    """

    APP_VERSION = "appVersion"
    PER_ENV = "per_env"
    FIXED = "fixed"


class NamespaceStrategy(StrEnum):
    """How the namespace of each environment is derived.

    `single`: the same namespace for every environment (`<service>`).
    `per_env`: `<service>-<env>`.
    `custom`: namespace typed explicitly for each environment.
    """

    SINGLE = "single"
    PER_ENV = "per_env"
    CUSTOM = "custom"


class SecretStrategy(StrEnum):
    """How the secrets of the generated project are managed.

    None of these strategies ever produces a real secret value: the generator
    only builds placeholders to be filled outside the repository.

    `placeholder`: Helm Secret with mandatory values.
    `external-secrets`: ExternalSecret resource (third-party operator).
    `sealed-secrets`: SealedSecret resource (Bitnami).
    `none`: secrets managed entirely outside the chart.
    """

    PLACEHOLDER = "placeholder"
    EXTERNAL_SECRETS = "external-secrets"
    SEALED_SECRETS = "sealed-secrets"
    NONE = "none"


class ResourceProfile(StrEnum):
    """Requests/limits template applied to the containers.

    `small`, `medium` and `large` fill in the four missing quantities; `custom`
    fills in none and lets the explicit quantities be authoritative.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    CUSTOM = "custom"


class AccessMode(StrEnum):
    """Access mode of a PersistentVolumeClaim."""

    RWO = "ReadWriteOnce"
    ROX = "ReadOnlyMany"
    RWX = "ReadWriteMany"
    RWOP = "ReadWriteOncePod"
