"""Types de champs partages par le coeur et les plugins.

Portage de `helm_forge.models.validators` (MIGRATION.md §4) : `DnsLabel`,
`Subdomain` et `SemVer` servent aussi au bloc `service:` partage, donc au coeur.
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
    return check_pattern(value, DNS_LABEL_RE, "un label DNS valide (a-z, 0-9, tirets)")


def _subdomain(value: str) -> str:
    return check_pattern(value, SUBDOMAIN_RE, "un nom de domaine DNS valide")


def _semver(value: str) -> str:
    return check_pattern(value, SEMVER_RE, "une version semantique (MAJEUR.MINEUR.CORRECTIF)")


#: Label DNS : nom de service, de chart, de namespace.
DnsLabel = Annotated[str, AfterValidator(_dns_label)]

#: Nom de domaine complet : domaine d'environnement, hote d'Ingress.
Subdomain = Annotated[str, AfterValidator(_subdomain)]

#: Version semantique.
SemVer = Annotated[str, AfterValidator(_semver)]


class ForgeModel(BaseModel):
    """Base commune a tous les modeles de specification.

    `extra="forbid"` : une cle inconnue dans `forge.yml` est une faute de frappe,
    jamais un silence. Doublon exact des deux `ForgeModel` legacy, fusionne ici
    une bonne fois (MIGRATION.md §5.1).
    """

    model_config = ConfigDict(extra="forbid", frozen=False, validate_default=True)
