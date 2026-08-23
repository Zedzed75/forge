"""Bloc `service:` — la part de la specification que tous les domaines voient.

C'est le seul modele metier du coeur : il ne decrit aucune technologie, juste
l'identite du service et ses environnements (cf. DESIGN.md §3).
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, Subdomain


class Environment(ForgeModel):
    """Un environnement de deploiement. L'ordre de declaration est significatif."""

    #: Nom court de l'environnement (dev, staging, prod). Sert de cle partout.
    name: DnsLabel

    #: Domaine DNS de l'environnement, facultatif (ex. `staging.example.net`).
    domain: Subdomain | None = None

    #: Marque l'environnement de production : active les profils durcis des plugins.
    production: bool = False


class ServiceSpec(ForgeModel):
    """Identite du service, partagee par tous les domaines generes."""

    #: Nom du service : nom de projet, de chart et prefixe de ressource.
    name: DnsLabel

    #: Description d'une ligne, reprise dans les en-tetes de fichiers generes.
    description: str = Field(min_length=1)

    #: Equipe ou personne responsable.
    owner: str = Field(min_length=1)

    #: Adresse de contact du responsable (facultative).
    owner_email: str | None = None

    #: Labels metier repris a l'identique par tous les domaines.
    labels: dict[str, str] = Field(default_factory=dict)

    #: Environnements, dans l'ordre de promotion (dev -> staging -> prod).
    environments: list[Environment] = Field(min_length=1)

    @field_validator("environments")
    @classmethod
    def _unique_environment_names(cls, value: list[Environment]) -> list[Environment]:
        require_unique((env.name for env in value), "noms d'environnement")
        return value

    @model_validator(mode="after")
    def _at_most_one_production(self) -> ServiceSpec:
        production = [env.name for env in self.environments if env.production]
        if len(production) > 1:
            raise ValueError(
                "un seul environnement peut porter production: true "
                f"(trouves : {', '.join(production)})"
            )
        return self

    @property
    def environment_names(self) -> tuple[str, ...]:
        """Noms des environnements, dans l'ordre de declaration."""
        return tuple(env.name for env in self.environments)

    def environment(self, name: str) -> Environment:
        """Retourne l'environnement `name`, ou leve `KeyError`."""
        for env in self.environments:
            if env.name == name:
                return env
        raise KeyError(name)
