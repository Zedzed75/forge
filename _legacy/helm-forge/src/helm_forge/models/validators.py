"""Types annotés réutilisables, porteurs des règles de validation Kubernetes.

Regrouper ces règles ici évite de les répéter dans chaque modèle et garantit
qu'un nom de composant est validé exactement comme un nom de namespace.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

from ..constants import (
    CRON_SCHEDULE,
    DNS1123_LABEL,
    DNS1123_SUBDOMAIN,
    ENV_KEY,
    IMAGE_REPOSITORY,
    QUANTITY,
    SEMVER,
)


def _dns_label(value: str) -> str:
    """Valide un label DNS-1123 : minuscules, chiffres et tirets internes."""
    if not DNS1123_LABEL.match(value):
        raise ValueError(
            f"{value!r} n'est pas un label DNS-1123 valide : minuscules, "
            "chiffres et tirets uniquement, sans tiret en début ni en fin"
        )
    return value


def _subdomain(value: str) -> str:
    """Valide un sous-domaine DNS-1123 (hôte d'Ingress, domaine de base)."""
    if not DNS1123_SUBDOMAIN.match(value):
        raise ValueError(f"{value!r} n'est pas un nom de domaine DNS-1123 valide")
    return value


def _env_key(value: str) -> str:
    """Valide une clé de variable d'environnement (majuscules et underscores)."""
    if not ENV_KEY.match(value):
        raise ValueError(
            f"{value!r} n'est pas une clé valide : majuscules, chiffres et "
            "underscores, ne commençant pas par un chiffre"
        )
    return value


def _quantity(value: str) -> str:
    """Valide une quantité Kubernetes (100m, 512Mi, 2, 10Gi...)."""
    if not QUANTITY.match(value):
        raise ValueError(f"{value!r} n'est pas une quantité Kubernetes valide")
    return value


def _http_path(value: str) -> str:
    """Valide un chemin HTTP absolu."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} doit commencer par une barre oblique")
    return value


def _semver(value: str) -> str:
    """Valide une version SemVer stricte, exigée par Helm pour Chart.yaml."""
    if not SEMVER.match(value):
        raise ValueError(f"{value!r} n'est pas une version SemVer valide")
    return value


def _image_repository(value: str) -> str:
    """Valide un chemin de dépôt d'image OCI."""
    if not IMAGE_REPOSITORY.match(value):
        raise ValueError(f"{value!r} n'est pas un dépôt d'image valide")
    return value


def _cron_schedule(value: str) -> str:
    """Valide une planification cron à cinq champs."""
    if not CRON_SCHEDULE.match(value.strip()):
        raise ValueError(
            f"{value!r} n'est pas une planification cron à cinq champs "
            '(exemple : "0 3 * * *")'
        )
    return value.strip()


def _absolute_path(value: str) -> str:
    """Valide un chemin absolu de montage dans le conteneur."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} doit être un chemin absolu")
    return value


# --------------------------------------------------------------------------
# Types annotés exportés
# --------------------------------------------------------------------------

DnsLabel = Annotated[str, AfterValidator(_dns_label)]
Subdomain = Annotated[str, AfterValidator(_subdomain)]
EnvKey = Annotated[str, AfterValidator(_env_key)]
Quantity = Annotated[str, AfterValidator(_quantity)]
HttpPath = Annotated[str, AfterValidator(_http_path)]
SemVer = Annotated[str, AfterValidator(_semver)]
ImageRepository = Annotated[str, AfterValidator(_image_repository)]
CronSchedule = Annotated[str, AfterValidator(_cron_schedule)]
AbsolutePath = Annotated[str, AfterValidator(_absolute_path)]

#: Port réseau valide au sens de Kubernetes.
Port = Annotated[int, Field(ge=1, le=65535)]

#: Pourcentage entier, utilisé par les cibles d'autoscaling.
Percentage = Annotated[int, Field(ge=1, le=100)]
