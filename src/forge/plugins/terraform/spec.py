"""The `terraform:` section of forge.yml.

The first sub-model of the project that carries no inheritance: there was no
legacy Terraform tool to convert. Its shape follows that of the two other
domains — a static block, a dict of overrides keyed by environment name, an
`extras` block — so that a `forge.yml` stays readable from one section to the
next.

What this model describes: **the base layer the other domains rest on**. The
namespace, its budget, the identity that deploys into it, what goes in and comes
out. Not the application payload: it is the Helm domain that deploys it, into the
namespace this one creates.

What this model cannot check, and which belongs to the cross-check
(`answers.cross_check`): the keys of `environments` absent from
`service.environments`, the completeness of the namespaces under the `custom`
strategy, and the caps that bear on the shared `service:` block.

**No secret value has its place here.** The backend keys recognised as secret are
refused by the model, and the registry password is a Terraform variable with no
default, absent from the generated files.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.terraform.catalog.registry import family_names
from forge.plugins.terraform.constants import (
    MAX_NAMESPACE_LENGTH,
    REQUIRED_BACKEND_KEYS,
    SECRET_BACKEND_KEYS,
    VERSION_CONSTRAINT_RE,
)
from forge.plugins.terraform.enums import (
    BackendKind,
    KubernetesAuth,
    NamespaceStrategy,
    ResourceFamily,
)
from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, Subdomain


class BackendSpec(ForgeModel):
    """Where the Terraform state is kept, and how it is addressed."""

    #: Type of backend.
    kind: BackendKind = BackendKind.LOCAL

    #: Configuration keys of the backend, written as-is into `backend.tf`. Secret
    #: keys are refused: they are supplied through `-backend-config` or through
    #: an environment variable.
    config: dict[str, str] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def _no_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = sorted(SECRET_BACKEND_KEYS & set(value))
        if forbidden:
            raise ValueError(
                "secret backend keys refused: "
                f"{', '.join(forbidden)}. Supply them at run time "
                "(terraform init -backend-config=...) or through an environment "
                "variable; a generated file never carries a secret."
            )
        return value

    @model_validator(mode="after")
    def _required_keys(self) -> BackendSpec:
        missing = [
            key for key in REQUIRED_BACKEND_KEYS[self.kind.value] if key not in self.config
        ]
        if missing:
            raise ValueError(
                f"backend '{self.kind.value}': mandatory keys absent from "
                f"terraform.backend.config: {', '.join(missing)}."
            )
        return self


class KubernetesAccessSpec(ForgeModel):
    """How the Kubernetes provider reaches the cluster."""

    #: Authentication mode.
    auth: KubernetesAuth = KubernetesAuth.KUBECONFIG

    #: Path of the kubeconfig, in `kubeconfig` mode. Becomes the default value of
    #: the `kube_config_path` variable of each environment root.
    config_path: str = "~/.kube/config"

    #: Names one kubeconfig context per environment. Leave it at `true`: with no
    #: explicit context, the provider uses the current context of the machine, and
    #: nothing says which cluster the application went to.
    context_per_environment: bool = True


class QuotaSpec(ForgeModel):
    """Budget of an environment. Any omitted key keeps the default value."""

    #: Cap on requestable CPU (e.g. "4", "500m").
    cpu: str | None = None

    #: Cap on requestable memory, suffix mandatory (e.g. "8Gi").
    memory: str | None = None

    #: Maximum number of simultaneous pods.
    pods: int | None = Field(default=None, gt=0)


class TerraformEnvironmentSpec(ForgeModel):
    """Overrides of an environment. Keyed by environment name."""

    #: Explicit namespace. Mandatory under the `custom` strategy, optional
    #: otherwise.
    namespace: DnsLabel | None = None

    #: kubeconfig context this environment targets.
    kube_context: str | None = None

    #: Budget of this environment.
    quota: QuotaSpec | None = None

    #: Labels added to the resources of this environment only.
    labels: dict[str, str] = Field(default_factory=dict)

    #: Backend keys specific to this environment — typically `key` or `prefix`,
    #: so that two environments do not write the same state.
    backend_config: dict[str, str] = Field(default_factory=dict)

    #: DNS names covered by the self-signed certificate of this environment.
    tls_dns_names: list[Subdomain] = Field(default_factory=list)

    @field_validator("backend_config")
    @classmethod
    def _no_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = sorted(SECRET_BACKEND_KEYS & set(value))
        if forbidden:
            raise ValueError(
                f"secret backend keys refused: {', '.join(forbidden)}."
            )
        return value


class TerraformExtras(ForgeModel):
    """Extra files of the generated project."""

    #: Makefile of shortcuts (`make init ENV=prod`, `make plan ENV=prod`).
    makefile: bool = True

    #: A `.tflint.hcl` file enabling the Terraform rule set of tflint.
    tflint_config: bool = True


class TerraformSpec(ForgeModel):
    """The `terraform:` section: the infrastructure base layer of the service."""

    #: `required_version` constraint. Always bound the major version.
    terraform_version: str = "~> 1.9"

    #: Where the state is kept.
    backend: BackendSpec = Field(default_factory=BackendSpec)

    #: How the cluster is reached.
    kubernetes: KubernetesAccessSpec = Field(default_factory=KubernetesAccessSpec)

    #: How the namespace name is derived from the environment.
    namespace_strategy: NamespaceStrategy = NamespaceStrategy.PER_ENV

    #: Retained resource families. The order they are written in does not matter:
    #: the catalogue puts them back into canonical order.
    resources: list[ResourceFamily] = Field(
        default_factory=lambda: [ResourceFamily.NAMESPACE], min_length=1
    )

    #: Overrides per environment. An absent environment takes the derived values;
    #: the names are validated by the plugin cross-check.
    environments: dict[str, TerraformEnvironmentSpec] = Field(default_factory=dict)

    #: Extra files.
    extras: TerraformExtras = Field(default_factory=TerraformExtras)

    @field_validator("terraform_version")
    @classmethod
    def _version_constraint(cls, value: str) -> str:
        if not VERSION_CONSTRAINT_RE.match(value):
            raise ValueError(
                f"terraform_version '{value}' is not a Terraform version "
                "constraint (e.g. '~> 1.9', '>= 1.5, < 2.0'). A bare version would "
                "freeze the project on one precise patch."
            )
        return value

    @field_validator("resources")
    @classmethod
    def _unique_resources(cls, value: list[ResourceFamily]) -> list[ResourceFamily]:
        require_unique((family.value for family in value), "resource families")
        return value

    @model_validator(mode="after")
    def _known_families(self) -> TerraformSpec:
        """Guard rail: the catalogue and the enumeration must stay in agreement."""
        known = set(family_names())
        unknown = sorted(f.value for f in self.resources if f.value not in known)
        if unknown:  # pragma: no cover - a programming defect of the plugin
            raise ValueError(
                f"families absent from the catalogue: {', '.join(unknown)}."
            )
        return self

    @model_validator(mode="after")
    def _custom_namespaces_declared(self) -> TerraformSpec:
        """Under the `custom` strategy, every declared override must name its namespace.

        This check only sees the environments **present** in
        `terraform.environments`; the ones that do not appear there at all are
        caught by the cross-check, the only place that knows
        `service.environments`.
        """
        if self.namespace_strategy is not NamespaceStrategy.CUSTOM:
            return self
        silent = sorted(
            name for name, override in self.environments.items() if override.namespace is None
        )
        if silent:
            raise ValueError(
                'the "custom" namespace strategy requires an explicit namespace; '
                f"absent for: {', '.join(silent)}."
            )
        return self

    @model_validator(mode="after")
    def _namespace_lengths(self) -> TerraformSpec:
        too_long = sorted(
            f"{name} ({override.namespace})"
            for name, override in self.environments.items()
            if override.namespace and len(override.namespace) > MAX_NAMESPACE_LENGTH
        )
        if too_long:
            raise ValueError(
                f"a namespace name is at most {MAX_NAMESPACE_LENGTH} characters; "
                f"too long for: {', '.join(too_long)}."
            )
        return self

    # -- lookups ------------------------------------------------------------

    def overrides(self, environment: str) -> TerraformEnvironmentSpec:
        """Overrides of `environment`, empty when it has none."""
        return self.environments.get(environment) or TerraformEnvironmentSpec()

    def uses(self, family: ResourceFamily) -> bool:
        """Tell whether the family is retained."""
        return family in self.resources

    def family_names(self) -> tuple[str, ...]:
        """Names of the retained families, as written in the specification."""
        return tuple(family.value for family in self.resources)

    def namespace_for(self, service_name: str, environment: str) -> str:
        """Namespace of `environment`, derived according to the strategy.

        Under the `custom` strategy, an environment with no override would land
        here with no answer: the cross-check has already refused it, and falling
        back on the derived name keeps the function total rather than raising from
        a rendering path.
        """
        explicit = self.overrides(environment).namespace
        if explicit:
            return explicit
        if self.namespace_strategy is NamespaceStrategy.SAME:
            return service_name
        return f"{service_name}-{environment}"

    def model_dump_stable(self) -> dict[str, Any]:  # pragma: no cover - debugging comfort
        """Serialisable view of the model, for manual inspection."""
        return self.model_dump(mode="json")
