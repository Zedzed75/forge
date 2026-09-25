"""Model of a component: a named workload and its resources.

Port of `helm_forge.models.component` (MIGRATION.md §4).

A component corresponds to a deployable workload (`api`, `worker`, `cleanup`).
It carries its type (Deployment, StatefulSet, CronJob) and the list of ancillary
resources to generate around it (`addons`).

The sub-models are **always present**, even when the matching addon is not
selected: `values.yaml` thus exposes a complete commented block for each
feature, which is the expected Helm convention. It is the `addons` list that
decides which files are actually generated.

Two divergences from the legacy tool:

* the `servicemonitor` block is not ported (arbitration H7, out of scope);
* the normalisations used to write into `__dict__` to work around
  `validate_assignment=True`; that mode not being reintroduced (arbitration
  H11), they are written as ordinary assignments, performed during validation.
  The model stays immutable **after** validation: nothing modifies it any more.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.component_blocks import (
    ComponentSecretSpec,
    ConfigSpec,
    CronSpec,
    HpaSpec,
    IngressSpec,
    NetworkPolicySpec,
    PdbSpec,
    PersistenceSpec,
    RbacSpec,
)
from forge.plugins.helm.constants import MAX_COMPONENT_NAME_LENGTH
from forge.plugins.helm.enums import (
    AccessMode,
    AddonKind,
    ComponentKind,
    IngressController,
    ResourceProfile,
    ServiceType,
)
from forge.plugins.helm.names import (
    AbsolutePath,
    CronSchedule,
    EnvKey,
    HttpPath,
    ImageRepository,
    Percentage,
    Port,
    PortName,
    Quantity,
)
from forge.plugins.helm.profiles import RESOURCE_PROFILES, scale_quantity
from forge.spec.types import DnsLabel, ForgeModel, Subdomain

#: Addons incompatible with a CronJob: a job is neither exposed nor autoscaled.
CRONJOB_FORBIDDEN_ADDONS: frozenset[AddonKind] = frozenset(
    {AddonKind.SERVICE, AddonKind.INGRESS, AddonKind.HPA, AddonKind.PDB}
)


class ProbesSpec(ForgeModel):
    """Health probes of the main container."""

    #: Generates the liveness and readiness probes. False for a worker with no
    #: port.
    enabled: bool = True

    #: HTTP path queried by the liveness probe (restarts the container).
    liveness_path: HttpPath = "/healthz"

    #: HTTP path queried by the readiness probe (removed from the Service).
    readiness_path: HttpPath = "/ready"

    #: Startup probe: useful for slow-starting applications, it suspends liveness
    #: and readiness until it has succeeded.
    startup_enabled: bool = False

    #: Delay before the first query, in seconds (>= 0).
    initial_delay_seconds: int = Field(default=5, ge=0)

    #: Period between two queries, in seconds (>= 1).
    period_seconds: int = Field(default=10, ge=1)

    #: How long a response is waited for, in seconds (>= 1).
    timeout_seconds: int = Field(default=2, ge=1)

    #: Number of consecutive failures before declaring the probe failed (>= 1).
    failure_threshold: int = Field(default=3, ge=1)


class ResourcesSpec(ForgeModel):
    """Requests and limits of the main container.

    The `profile` field is informative: the four quantities are authoritative.
    When a known profile is given without an explicit quantity, the profile
    values are applied automatically — that is what makes a partial spec
    equivalent to a complete one.
    """

    #: Template applied: small | medium | large | custom (fills nothing in).
    profile: ResourceProfile = ResourceProfile.SMALL

    #: CPU guaranteed to the container (`50m`, `1`).
    cpu_request: Quantity = "50m"

    #: Memory guaranteed to the container (`64Mi`, `1Gi`).
    memory_request: Quantity = "64Mi"

    #: CPU ceiling of the container (`200m`, `2`).
    cpu_limit: Quantity = "200m"

    #: Memory ceiling of the container; going over it kills the container.
    memory_limit: Quantity = "128Mi"

    @model_validator(mode="before")
    @classmethod
    def _apply_profile(cls, data: Any) -> Any:
        """Fill in the missing quantities from the requested profile."""
        if not isinstance(data, dict):
            return data
        values = RESOURCE_PROFILES.get(str(data.get("profile", ResourceProfile.SMALL)))
        if values is None:  # "custom" or unknown profile: nothing to fill in.
            return data
        data = dict(data)
        data.setdefault("cpu_request", values.cpu_request)
        data.setdefault("memory_request", values.memory_request)
        data.setdefault("cpu_limit", values.cpu_limit)
        data.setdefault("memory_limit", values.memory_limit)
        return data

    def scaled(self, factor: int) -> ResourcesSpec:
        """Return a copy whose four quantities are multiplied."""
        if factor == 1:
            return self
        return ResourcesSpec(
            profile=ResourceProfile.CUSTOM,
            cpu_request=scale_quantity(self.cpu_request, factor),
            memory_request=scale_quantity(self.memory_request, factor),
            cpu_limit=scale_quantity(self.cpu_limit, factor),
            memory_limit=scale_quantity(self.memory_limit, factor),
        )


class SecuritySpec(ForgeModel):
    """Security context of the pod and of the container.

    `strict` set to true applies the recommended hardening: non-root user,
    read-only root filesystem, all capabilities dropped, default seccomp profile.
    Each field stays overridable.
    """

    #: Applies the recommended hardening; false relaxes the defaults.
    strict: bool = True

    #: Forbids the container from starting as root.
    run_as_non_root: bool = True

    #: UID of the container process (>= 1, hence never root).
    run_as_user: int = Field(default=10001, ge=1)

    #: GID of the container process (>= 1).
    run_as_group: int = Field(default=10001, ge=1)

    #: GID owning the mounted volumes (>= 1).
    fs_group: int = Field(default=10001, ge=1)

    #: Mounts the root filesystem read-only.
    read_only_root_filesystem: bool = True

    #: Forbids a process from acquiring more privileges than its parent.
    allow_privilege_escalation: bool = False

    #: Linux capabilities dropped; `["ALL"]` is the recommended hardening.
    drop_capabilities: list[str] = Field(default_factory=lambda: ["ALL"])

    #: seccomp profile: `RuntimeDefault` or `Unconfined`.
    seccomp_profile: str = "RuntimeDefault"

    @model_validator(mode="before")
    @classmethod
    def _relax_when_not_strict(cls, data: Any) -> Any:
        """Relax the default values when the hardening is declined."""
        if not isinstance(data, dict) or data.get("strict", True):
            return data
        data = dict(data)
        data.setdefault("run_as_non_root", False)
        data.setdefault("read_only_root_filesystem", False)
        data.setdefault("drop_capabilities", [])
        return data


class ComponentServiceSpec(ForgeModel):
    """Service exposing the workload.

    Named `ComponentServiceSpec` and not `ServiceSpec`: the core already uses
    that latter name for the shared `service:` block, and `derive.py` will import
    both. The name of the key in `forge.yml` stays `service`.
    """

    #: Service type: ClusterIP | NodePort | LoadBalancer.
    type: ServiceType = ServiceType.CLUSTER_IP

    #: Port exposed by the Service (1-65535); distinct from `container_port`.
    port: Port = 80

    #: A StatefulSet requires a headless Service (`clusterIP: None`) to give each
    #: pod a stable network identity. Set automatically.
    headless: bool = False

    #: Node port, with a Service of type NodePort (30000-32767 usually).
    node_port: Port | None = None

    #: Annotations placed on the Service (a load balancer, for instance).
    annotations: dict[str, str] = Field(default_factory=dict)


class ComponentSpec(ForgeModel):
    """A named workload and the whole set of its ancillary resources."""

    #: Component name: a DNS label, prefix of all its resources.
    name: DnsLabel = Field(max_length=MAX_COMPONENT_NAME_LENGTH)

    #: Type of workload: deployment | statefulset | cronjob.
    kind: ComponentKind = ComponentKind.DEPLOYMENT

    #: Ancillary resources generated around the workload: service, ingress,
    #: configmap, secret, hpa, pdb, serviceaccount, networkpolicy.
    #: The list is deduplicated and put back into the canonical order of
    #: `AddonKind`, so that two equivalent specs produce the same project.
    addons: list[AddonKind] = Field(
        default_factory=lambda: [AddonKind.SERVICE, AddonKind.CONFIGMAP]
    )

    #: Override of the image repository, when a component does not use the main
    #: project image (rare: a worker generally shares the same image).
    image_repository: ImageRepository | None = None

    #: Container command: that is how a worker differs from an API while sharing
    #: the same image. Empty = the image entrypoint.
    command: list[str] = Field(default_factory=list)

    #: Arguments passed to the container command.
    args: list[str] = Field(default_factory=list)

    #: Default replica count (>= 0); overridden per environment.
    replicas: int = Field(default=1, ge=0)

    #: Port the container listens on (1-65535). Distinct from `service.port`:
    #: the nominal Helm case exposes a Service on 80 towards a container on 8080
    #: (arbitration H5, the three port fields are kept).
    container_port: Port = 8080

    #: Name of the container port, echoed by the Service and by the probes.
    #:
    #: Kubernetes imposes the IANA_SVC_NAME format here: at most 15 characters,
    #: lowercase, digits and hyphens, at least one letter, no leading or
    #: trailing hyphen, no two consecutive hyphens. No validator catches it — a
    #: 29-character name passes `helm lint`, `helm template` **and**
    #: `kubeconform -strict`, and is only refused on apply. Hence this
    #: constraint on the model: it is the only place that can carry it.
    port_name: PortName = "http"

    #: Health probes of the main container.
    probes: ProbesSpec = Field(default_factory=ProbesSpec)

    #: Requests and limits of the main container.
    resources: ResourcesSpec = Field(default_factory=ResourcesSpec)

    #: Security context of the pod and of the container.
    security: SecuritySpec = Field(default_factory=SecuritySpec)

    #: Service exposing the workload (`service` addon).
    service: ComponentServiceSpec = Field(default_factory=ComponentServiceSpec)

    #: HTTP exposure (`ingress` addon, which requires the `service` addon).
    ingress: IngressSpec = Field(default_factory=IngressSpec)

    #: Persistent volume attached to the workload.
    persistence: PersistenceSpec = Field(default_factory=PersistenceSpec)

    #: Horizontal autoscaling (`hpa` addon).
    hpa: HpaSpec = Field(default_factory=HpaSpec)

    #: Voluntary disruption budget (`pdb` addon).
    pdb: PdbSpec = Field(default_factory=PdbSpec)

    #: Network traffic restriction (`networkpolicy` addon).
    networkpolicy: NetworkPolicySpec = Field(default_factory=NetworkPolicySpec)

    #: Rights of the component ServiceAccount within its namespace.
    rbac: RbacSpec = Field(default_factory=RbacSpec)

    #: Non-sensitive configuration (`configmap` addon).
    config: ConfigSpec = Field(default_factory=ConfigSpec)

    #: Expected secret keys (`secret` addon); never a value.
    secret: ComponentSecretSpec = Field(default_factory=ComponentSecretSpec)

    #: CronJob parameters; only meaningful for `kind: cronjob`, where it is
    #: filled in automatically when absent.
    cron: CronSpec | None = None

    # ------------------------------------------------------------------
    # Cross-validation
    # ------------------------------------------------------------------

    @field_validator("addons")
    @classmethod
    def _normalise_addons(cls, value: list[AddonKind]) -> list[AddonKind]:
        """Deduplicate the addons and put them back into the canonical order.

        The file plan thus becomes independent of the order they were typed in.
        """
        order = list(AddonKind)
        return sorted(set(value), key=order.index)

    @model_validator(mode="after")
    def _check_coherence(self) -> ComponentSpec:
        """Check the coherence of the whole and apply the forced defaults."""
        if AddonKind.INGRESS in self.addons and AddonKind.SERVICE not in self.addons:
            raise ValueError(
                f"component {self.name!r}: the ingress addon requires the service addon"
            )

        if self.kind is ComponentKind.CRONJOB:
            forbidden = sorted(
                addon.value for addon in self.addons if addon in CRONJOB_FORBIDDEN_ADDONS
            )
            if forbidden:
                raise ValueError(
                    f"component {self.name!r} of type cronjob: incompatible "
                    f"addons {forbidden}"
                )
            if self.cron is None:
                self.cron = CronSpec()
        elif self.cron is not None:
            raise ValueError(
                f"component {self.name!r}: the cron block is only meaningful for a "
                "component of type cronjob"
            )

        if self.kind is ComponentKind.STATEFULSET:
            # A StatefulSet needs a headless Service and, in almost every case,
            # a persistent volume.
            self.service.headless = True
            self.persistence.enabled = True
            if AddonKind.SERVICE not in self.addons:
                # Forcing `headless` is not enough: without the addon the
                # Service is not generated at all and `serviceName` designates a
                # resource that does not exist. The StatefulSet then loses the
                # stable network identity that is its whole point — and no
                # validator can see it, the manifest remaining valid.
                order = list(AddonKind)
                self.addons = sorted(
                    {*self.addons, AddonKind.SERVICE}, key=order.index
                )

        return self

    # ------------------------------------------------------------------
    # Convenience accessors, used by derive.py and the templates
    # ------------------------------------------------------------------

    def has(self, addon: AddonKind) -> bool:
        """Tell whether an addon is selected for this component."""
        return addon in self.addons

    @property
    def is_workload(self) -> bool:
        """True for a Deployment or a StatefulSet, false for a CronJob."""
        return self.kind in (ComponentKind.DEPLOYMENT, ComponentKind.STATEFULSET)
