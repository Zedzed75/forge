"""Sub-models of the resources attached to a component.

Split out of `components.py` to keep within the project's 600-line limit, and
because the cut means something: here live the blocks describing an **ancillary
resource** — what forge generates *around* the workload — whereas
`components.py` describes the workload itself and assembles it.

Every block is always present in the model, even when the matching addon is not
selected: `values.yaml` thus exposes a complete commented block for each
feature, which is the expected Helm convention. It is the component's `addons`
list that decides which files are actually generated.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.enums import AccessMode, IngressController
from forge.plugins.helm.names import (
    AbsolutePath,
    CronSchedule,
    EnvKey,
    HttpPath,
    Percentage,
    Quantity,
)
from forge.spec.types import DnsLabel, ForgeModel, Subdomain

#: Injection modes accepted for a ConfigMap or a Secret: environment variables
#: through `envFrom`, or a file mounted inside the container.
MOUNT_MODES = ("env", "file")

#: Concurrency policies accepted by a Kubernetes CronJob.
CONCURRENCY_POLICIES = ("Allow", "Forbid", "Replace")

#: Restart policies accepted by the pod of a CronJob.
RESTART_POLICIES = ("OnFailure", "Never")


class IngressSpec(ForgeModel):
    """HTTP exposure through an Ingress.

    The host is not stored here: it is derived per environment by `derive.py`,
    and stays overridable in `values-<env>.yaml`.
    """

    #: Target ingress controller: nginx | traefik.
    controller: IngressController = IngressController.NGINX

    #: Base domain used when the environment has no `service.environments[]
    #: .domain` of its own (arbitration H1: the core domain wins when it is set).
    base_domain: Subdomain = "example.com"

    #: HTTP path served by this Ingress rule.
    path: HttpPath = "/"

    #: How the path is matched: Prefix | Exact | ImplementationSpecific.
    path_type: str = "Prefix"

    #: Issues a TLS certificate for the host through cert-manager.
    tls: bool = True

    #: Name of the cert-manager ClusterIssuer used to issue the certificate.
    issuer: str = "letsencrypt-prod"

    #: Override of `ingressClassName`; absent = derived from the `controller`.
    class_name: str | None = None

    #: Annotations placed on the Ingress.
    annotations: dict[str, str] = Field(default_factory=dict)


class PersistenceSpec(ForgeModel):
    """Persistent volume attached to the workload."""

    #: Generates a PersistentVolumeClaim; forced to true for a StatefulSet.
    enabled: bool = False

    #: StorageClass requested; an empty string = the cluster default class.
    storage_class: str = ""

    #: Size requested for the volume (`10Gi`).
    size: Quantity = "10Gi"

    #: Access mode: ReadWriteOnce | ReadOnlyMany | ReadWriteMany |
    #: ReadWriteOncePod.
    access_mode: AccessMode = AccessMode.RWO

    #: Absolute mount path of the volume inside the container.
    mount_path: AbsolutePath = "/data"


class HpaSpec(ForgeModel):
    """Horizontal autoscaling based on CPU usage, and optionally on memory."""

    #: Replica floor (1-100).
    min_replicas: int = Field(default=2, ge=1, le=100)

    #: Replica ceiling (1-100), at least equal to `min_replicas`.
    max_replicas: int = Field(default=5, ge=1, le=100)

    #: Target CPU usage as a percentage (1-100).
    target_cpu: Percentage = 80

    #: Target memory usage as a percentage; absent = not watched.
    target_memory: Percentage | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> HpaSpec:
        if self.min_replicas > self.max_replicas:
            raise ValueError("hpa.min_replicas cannot exceed hpa.max_replicas")
        return self


class PdbSpec(ForgeModel):
    """Voluntary disruption budget."""

    #: Minimum number of available pods: a positive integer, or a percentage as
    #: a string (`"50%"`).
    min_available: int | str = 1

    @model_validator(mode="after")
    def _check_min_available(self) -> PdbSpec:
        value = self.min_available
        if isinstance(value, str) and not (
            value.endswith("%") and value[:-1].isdigit()
        ):
            raise ValueError(
                'pdb.min_available must be an integer or a percentage like "50%"'
            )
        if isinstance(value, int) and value < 0:
            raise ValueError("pdb.min_available cannot be negative")
        return self


class NetworkPolicySpec(ForgeModel):
    """Restriction of the ingress and egress network traffic."""

    #: Allows incoming traffic coming from the component namespace.
    allow_from_same_namespace: bool = True

    #: Additional namespaces allowed as a source (DNS labels).
    allow_from_namespaces: list[DnsLabel] = Field(default_factory=list)

    #: DNS resolution must stay allowed, otherwise the pod reaches nothing.
    allow_dns: bool = True

    #: Allows all outgoing traffic; false restricts egress to DNS.
    allow_egress_all: bool = False


class RbacSpec(ForgeModel):
    """Rights of the component ServiceAccount, within its namespace.

    Generated together with the `serviceaccount` addon: a Role only makes sense
    with a subject. No cluster-scoped resource is produced — ClusterRole and
    ClusterRoleBinding are out of scope, and inventing them would break the
    "never invent a kind" rule.
    """

    #: Creates a Role and its RoleBinding bound to the component ServiceAccount.
    #: `roleRef` being immutable, changing the Role it points at fails an upgrade.
    create: bool = False

    #: Rules of the Role, in the Kubernetes PolicyRule format. An empty list
    #: produces neither Role nor RoleBinding: a Role with no rule is
    #: schema-valid, but useless and misleading.
    rules: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def _complete_rules(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Every rule must carry apiGroups, resources and verbs, all non-empty.

        The API refuses an incomplete rule, but `kubeconform` lets it through:
        the check therefore belongs to the model.
        """
        for index, rule in enumerate(value):
            missing = [key for key in ("apiGroups", "resources", "verbs") if key not in rule]
            if missing:
                raise ValueError(
                    f"RBAC rule #{index + 1} is incomplete: {', '.join(missing)} "
                    'missing. For the resources of the core group, apiGroups is [""].'
                )
            if not rule["verbs"] or not rule["resources"]:
                raise ValueError(
                    f"RBAC rule #{index + 1}: `resources` and `verbs` cannot be empty."
                )
        return value


class ConfigSpec(ForgeModel):
    """Non-sensitive configuration, exposed through a ConfigMap."""

    #: Expected configuration keys (UPPERCASE_WITH_UNDERSCORES).
    keys: list[EnvKey] = Field(default_factory=lambda: ["LOG_LEVEL", "APP_ENV"])

    #: Injection of the keys into the container: `env` (envFrom) or `file`
    #: (mounted).
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ConfigSpec:
        if self.mount_as not in MOUNT_MODES:
            raise ValueError('config.mount_as must be "env" or "file"')
        return self


class ComponentSecretSpec(ForgeModel):
    """Secret keys expected by the component.

    Only the keys are described: no value is ever stored in the specification
    nor in the generated files.
    """

    #: Expected secret keys (UPPERCASE_WITH_UNDERSCORES).
    keys: list[EnvKey] = Field(default_factory=lambda: ["API_KEY"])

    #: Injection of the keys into the container: `env` (envFrom) or `file`
    #: (mounted).
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ComponentSecretSpec:
        if self.mount_as not in MOUNT_MODES:
            raise ValueError('secret.mount_as must be "env" or "file"')
        return self


class CronSpec(ForgeModel):
    """Parameters specific to a CronJob."""

    #: Five-field cron schedule (`0 3 * * *`).
    schedule: CronSchedule = "0 3 * * *"

    #: Concurrency of two runs: Allow | Forbid | Replace.
    concurrency_policy: str = "Forbid"

    #: Pod restart: OnFailure | Never.
    restart_policy: str = "OnFailure"

    #: Number of successful runs kept in the history (>= 0).
    successful_jobs_history_limit: int = Field(default=3, ge=0)

    #: Number of failed runs kept in the history (>= 0).
    failed_jobs_history_limit: int = Field(default=1, ge=0)

    #: Number of retries before giving a run up (>= 0).
    backoff_limit: int = Field(default=3, ge=0)

    #: Delay tolerated before considering a run missed; absent = no limit.
    starting_deadline_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_policies(self) -> CronSpec:
        if self.concurrency_policy not in CONCURRENCY_POLICIES:
            raise ValueError(
                "cron.concurrency_policy must be Allow, Forbid or Replace"
            )
        if self.restart_policy not in RESTART_POLICIES:
            raise ValueError("cron.restart_policy must be OnFailure or Never")
        return self
