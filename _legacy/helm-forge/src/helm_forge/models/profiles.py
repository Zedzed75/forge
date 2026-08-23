"""Profils de ressources et profils par environnement.

Ce module ne contient que des données et des fonctions pures, sans dépendance
vers pydantic : il est importable depuis n'importe quel modèle sans risque de
cycle d'imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ..constants import QUANTITY

# --------------------------------------------------------------------------
# Profils de ressources
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceValues:
    """Quatre quantités Kubernetes décrivant requests et limits d'un conteneur."""

    cpu_request: str
    memory_request: str
    cpu_limit: str
    memory_limit: str


#: Gabarits proposés dans le CLI. Volontairement modestes : un chart généré doit
#: pouvoir démarrer sur un cluster de développement sans épuiser le quota.
RESOURCE_PROFILES: Final[dict[str, ResourceValues]] = {
    "small": ResourceValues("50m", "64Mi", "200m", "128Mi"),
    "medium": ResourceValues("250m", "256Mi", "1", "512Mi"),
    "large": ResourceValues("1", "1Gi", "2", "2Gi"),
}


# --------------------------------------------------------------------------
# Profils par environnement
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentProfile:
    """Valeurs dérivées automatiquement pour un environnement donné.

    Ces valeurs ne sont jamais demandées à l'utilisateur : elles alimentent
    directement ``values-<env>.yaml``, où elles restent modifiables à la main.
    """

    replicas: int
    hpa_enabled: bool
    pdb_enabled: bool
    log_level: str
    #: Multiplicateur appliqué aux requests/limits du profil choisi.
    resource_multiplier: int
    #: Si vrai, l'hôte d'Ingress inclut le nom de l'environnement.
    #: La production expose <app>.<domaine>, les autres <app>.<env>.<domaine>.
    host_includes_env: bool


#: Profils reconnus par leur nom. Un environnement au nom inattendu reçoit
#: DEFAULT_ENVIRONMENT_PROFILE, c'est-à-dire le comportement le plus prudent.
ENVIRONMENT_PROFILES: Final[dict[str, EnvironmentProfile]] = {
    "dev": EnvironmentProfile(
        replicas=1,
        hpa_enabled=False,
        pdb_enabled=False,
        log_level="debug",
        resource_multiplier=1,
        host_includes_env=True,
    ),
    "staging": EnvironmentProfile(
        replicas=2,
        hpa_enabled=False,
        pdb_enabled=True,
        log_level="info",
        resource_multiplier=1,
        host_includes_env=True,
    ),
    "prod": EnvironmentProfile(
        replicas=3,
        hpa_enabled=True,
        pdb_enabled=True,
        log_level="info",
        resource_multiplier=2,
        host_includes_env=False,
    ),
}

#: Profil appliqué à tout environnement hors de la liste ci-dessus.
DEFAULT_ENVIRONMENT_PROFILE: Final[EnvironmentProfile] = EnvironmentProfile(
    replicas=1,
    hpa_enabled=False,
    pdb_enabled=False,
    log_level="info",
    resource_multiplier=1,
    host_includes_env=True,
)


def profile_for_environment(name: str) -> EnvironmentProfile:
    """Renvoie le profil associé à un nom d'environnement.

    Les alias courants sont reconnus afin que ``production`` se comporte comme
    ``prod`` et ``stage`` comme ``staging``.
    """
    aliases = {
        "production": "prod",
        "prd": "prod",
        "stage": "staging",
        "stg": "staging",
        "develop": "dev",
        "development": "dev",
    }
    key = aliases.get(name, name)
    return ENVIRONMENT_PROFILES.get(key, DEFAULT_ENVIRONMENT_PROFILE)


# --------------------------------------------------------------------------
# Arithmétique sur les quantités Kubernetes
# --------------------------------------------------------------------------

_QUANTITY_PARTS = re.compile(r"^([0-9]+(?:\.[0-9]+)?)([a-zA-Z]*)$")


def scale_quantity(quantity: str, factor: int) -> str:
    """Multiplie une quantité Kubernetes par un entier, en gardant son suffixe.

    ``scale_quantity("50m", 2)`` renvoie ``"100m"``, ``scale_quantity("1", 2)``
    renvoie ``"2"``. Le résultat est rendu sans décimale lorsqu'il tombe juste,
    ce qui garantit un rendu identique d'une exécution à l'autre.
    """
    if factor == 1:
        return quantity
    match = _QUANTITY_PARTS.match(quantity)
    if match is None:  # pragma: no cover - protégé en amont par la validation
        raise ValueError(f"quantité Kubernetes invalide : {quantity!r}")
    number, suffix = match.groups()
    scaled = float(number) * factor
    rendered = str(int(scaled)) if scaled.is_integer() else f"{scaled:g}"
    return f"{rendered}{suffix}"


def is_valid_quantity(quantity: str) -> bool:
    """Indique si la chaîne est une quantité Kubernetes acceptable."""
    return bool(QUANTITY.match(quantity))
