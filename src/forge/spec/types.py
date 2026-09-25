"""Field types shared by the core and the plugins.

Port of `helm_forge.models.validators` (MIGRATION.md §4): `DnsLabel`,
`Subdomain` and `SemVer` also serve the shared `service:` block, hence the core.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from forge.spec.names import (
    DNS_LABEL_RE,
    SEMVER_RE,
    SUBDOMAIN_RE,
    check_pattern,
)


def _dns_label(value: str) -> str:
    return check_pattern(value, DNS_LABEL_RE, "a valid DNS label (a-z, 0-9, hyphens)")


def _subdomain(value: str) -> str:
    return check_pattern(value, SUBDOMAIN_RE, "a valid DNS domain name")


def _semver(value: str) -> str:
    return check_pattern(value, SEMVER_RE, "a semantic version (MAJOR.MINOR.PATCH)")


#: DNS label: service, chart or namespace name.
DnsLabel = Annotated[str, AfterValidator(_dns_label)]

#: Fully qualified domain name: environment domain, Ingress host.
Subdomain = Annotated[str, AfterValidator(_subdomain)]

#: Semantic version.
SemVer = Annotated[str, AfterValidator(_semver)]


class ForgeModel(BaseModel):
    """Common base of every specification model.

    `extra="forbid"`: an unknown key in `forge.yml` is a typo, never a silence.
    Exact duplicate of the two legacy `ForgeModel` classes, merged here once and
    for all (MIGRATION.md §5.1).
    """

    model_config = ConfigDict(extra="forbid", frozen=False, validate_default=True)
