"""The `service:` block — the part of the specification every domain sees.

It is the only business model in the core: it describes no technology, just the
identity of the service and its environments (cf. DESIGN.md §3).
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, Subdomain


class Environment(ForgeModel):
    """A deployment environment. Declaration order is meaningful."""

    #: Short environment name (dev, staging, prod). Used as a key everywhere.
    name: DnsLabel

    #: DNS domain of the environment, optional (e.g. `staging.example.net`).
    domain: Subdomain | None = None

    #: Marks the production environment: turns on the plugins' hardened profiles.
    production: bool = False


class ServiceSpec(ForgeModel):
    """Service identity, shared by every generated domain."""

    #: Service name: project name, chart name and resource prefix.
    name: DnsLabel

    #: One-line description, reused in the headers of generated files.
    description: str = Field(min_length=1)

    #: Team or person in charge.
    owner: str = Field(min_length=1)

    #: Contact address of the owner (optional).
    owner_email: str | None = None

    #: Business labels carried over as-is by every domain.
    labels: dict[str, str] = Field(default_factory=dict)

    #: Environments, in promotion order (dev -> staging -> prod).
    environments: list[Environment] = Field(min_length=1)

    @field_validator("environments")
    @classmethod
    def _unique_environment_names(cls, value: list[Environment]) -> list[Environment]:
        require_unique((env.name for env in value), "environment names")
        return value

    @model_validator(mode="after")
    def _at_most_one_production(self) -> ServiceSpec:
        production = [env.name for env in self.environments if env.production]
        if len(production) > 1:
            raise ValueError(
                "only one environment may carry production: true "
                f"(found: {', '.join(production)})"
            )
        return self

    @property
    def environment_names(self) -> tuple[str, ...]:
        """Environment names, in declaration order."""
        return tuple(env.name for env in self.environments)

    def environment(self, name: str) -> Environment:
        """Return the `name` environment, or raise `KeyError`."""
        for env in self.environments:
            if env.name == name:
                return env
        raise KeyError(name)
