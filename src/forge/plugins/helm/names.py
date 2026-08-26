"""Regles de nommage propres a Helm et Kubernetes.

Portage de `helm_forge.models.validators` et de la partie « expressions
regulieres » de `helm_forge.constants` (MIGRATION.md §4).

`DnsLabel`, `Subdomain` et `SemVer` sont montes dans le coeur
(`forge.spec.types`) parce qu'ils servent aussi au bloc partage `service:`.
Ce qui reste ici decrit ce que **Kubernetes et OCI** acceptent, pas ce que forge
accepte : le coeur n'a pas a connaitre la grammaire d'un depot d'image ni celle
d'une quantite de ressource.
"""

from __future__ import annotations

import re
from typing import Annotated, Final

from pydantic import AfterValidator, Field

from forge.spec.names import check_pattern

# --------------------------------------------------------------------------
# Expressions regulieres
# --------------------------------------------------------------------------

#: Cle de variable d'environnement, telle qu'attendue dans un ConfigMap ou un
#: Secret consomme via `envFrom`.
ENV_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z_][A-Z0-9_]*$")

#: Quantite Kubernetes : 100m, 1, 1.5, 512Mi, 10Gi...
QUANTITY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$"
)

#: Depot d'image OCI : minuscules, chiffres, separateurs, chemins imbriques.
IMAGE_REPOSITORY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*$"
)

#: Planification cron a cinq champs, telle qu'attendue par un CronJob.
CRON_SCHEDULE_RE: Final[re.Pattern[str]] = re.compile(r"^(\S+\s+){4}\S+$")

#: Adresse electronique du mainteneur du chart. Verification volontairement
#: simple : on refuse les saisies manifestement fausses sans ajouter la
#: dependance `email-validator`. Employee par le controle croise du plugin,
#: jamais par le coeur (arbitrage H6) : c'est une contrainte de `Chart.yaml`.
EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# Validateurs
# --------------------------------------------------------------------------


def _env_key(value: str) -> str:
    """Valide une cle de variable d'environnement (majuscules et soulignes)."""
    return check_pattern(
        value,
        ENV_KEY_RE,
        "une cle valide : majuscules, chiffres et soulignes, ne commencant pas "
        "par un chiffre",
    )


def _quantity(value: str) -> str:
    """Valide une quantite Kubernetes (100m, 512Mi, 2, 10Gi...)."""
    return check_pattern(value, QUANTITY_RE, "une quantite Kubernetes valide")


def _image_repository(value: str) -> str:
    """Valide un chemin de depot d'image OCI."""
    return check_pattern(value, IMAGE_REPOSITORY_RE, "un depot d'image valide")


def _http_path(value: str) -> str:
    """Valide un chemin HTTP absolu."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} doit commencer par une barre oblique")
    return value


def _absolute_path(value: str) -> str:
    """Valide un chemin absolu de montage dans le conteneur."""
    if not value.startswith("/"):
        raise ValueError(f"{value!r} doit etre un chemin absolu")
    return value


def _cron_schedule(value: str) -> str:
    """Valide une planification cron a cinq champs, espaces de bord retires."""
    return check_pattern(
        value.strip(),
        CRON_SCHEDULE_RE,
        'une planification cron a cinq champs (exemple : "0 3 * * *")',
    )


def is_valid_email(value: str) -> bool:
    """Indique si `value` est une adresse electronique acceptable."""
    return bool(EMAIL_RE.match(value))


# --------------------------------------------------------------------------
# Types annotes exportes
# --------------------------------------------------------------------------

#: Cle de ConfigMap ou de Secret consommee via `envFrom` (MAJUSCULES_ET_SOULIGNES).
EnvKey = Annotated[str, AfterValidator(_env_key)]

#: Quantite de ressource Kubernetes (`50m`, `64Mi`, `1`, `10Gi`).
Quantity = Annotated[str, AfterValidator(_quantity)]

#: Depot d'image OCI, sans registre ni tag (`acme/shop`).
ImageRepository = Annotated[str, AfterValidator(_image_repository)]

#: Chemin HTTP absolu (`/healthz`).
HttpPath = Annotated[str, AfterValidator(_http_path)]

#: Chemin absolu de montage dans le conteneur (`/data`).
AbsolutePath = Annotated[str, AfterValidator(_absolute_path)]

#: Planification cron a cinq champs (`0 3 * * *`).
CronSchedule = Annotated[str, AfterValidator(_cron_schedule)]

#: Port reseau valide au sens de Kubernetes (1-65535).
Port = Annotated[int, Field(ge=1, le=65535)]

#: Pourcentage entier (1-100), employe par les cibles d'autoscaling.
Percentage = Annotated[int, Field(ge=1, le=100)]

#: Nom de port Kubernetes (format IANA_SVC_NAME) : au plus 15 caracteres,
#: minuscules, chiffres et tirets, au moins une lettre, ni tiret en tete ou en
#: queue, ni deux tirets consecutifs.
PORT_NAME_RE = re.compile(r"^(?!-)(?!.*--)(?=.*[a-z])[a-z0-9-]{1,15}(?<!-)$")


def _port_name(value: str) -> str:
    if not PORT_NAME_RE.match(value):
        raise ValueError(
            f"Nom de port invalide : '{value}'. Kubernetes impose le format "
            "IANA_SVC_NAME : au plus 15 caracteres, minuscules, chiffres et "
            "tirets, au moins une lettre, sans tiret en tete ni en queue."
        )
    return value


#: Nom de port du conteneur, repris par le Service et par les sondes.
PortName = Annotated[str, AfterValidator(_port_name)]
