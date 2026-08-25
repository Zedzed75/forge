"""Profils de ressources et profils par environnement.

Portage de `helm_forge.models.profiles` (MIGRATION.md §4). Ce module ne contient
que des donnees et des fonctions pures, sans dependance vers pydantic : il est
importable depuis n'importe quel modele sans risque de cycle d'imports, et
`derive.py` s'en sert pour calculer les valeurs implicites.

**Pourquoi la reconnaissance par le nom survit** (arbitrage H2) : c'est elle qui
rend un `forge.yml` minimal equivalent a un `forge.yml` complet — un
environnement nomme `prod` recoit trois replicas, un HPA et un hote sans
infixe, sans que l'utilisateur ait rien a ecrire. MIGRATION.md §4 demande
explicitement de la conserver. Le drapeau explicite `service.environments[]
.production` du coeur la **surcharge** quand il est present : voir
:func:`profile_for`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from forge.plugins.helm.names import QUANTITY_RE

# --------------------------------------------------------------------------
# Profils de ressources
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceValues:
    """Quatre quantites Kubernetes decrivant requests et limits d'un conteneur."""

    cpu_request: str
    memory_request: str
    cpu_limit: str
    memory_limit: str


#: Gabarits proposes par le questionnaire. Volontairement modestes : un chart
#: genere doit pouvoir demarrer sur un cluster de developpement sans epuiser le
#: quota. Le profil `custom` est absent : il ne complete rien.
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
    """Valeurs derivees automatiquement pour un environnement donne.

    Ces valeurs ne sont jamais demandees a l'utilisateur : elles alimentent
    directement `values-<env>.yaml`, ou elles restent modifiables a la main.
    """

    #: Nombre de replicas des charges de travail (Deployment, StatefulSet).
    replicas: int

    #: Autoscaling horizontal actif pour les composants portant l'addon `hpa`.
    hpa_enabled: bool

    #: Budget d'interruption actif pour les composants portant l'addon `pdb`.
    pdb_enabled: bool

    #: Niveau de journalisation ecrit dans la configuration du composant.
    log_level: str

    #: Multiplicateur applique aux requests/limits du profil de ressources.
    resource_multiplier: int

    #: Si vrai, l'hote d'Ingress inclut le nom de l'environnement : la
    #: production expose `<service>.<domaine>`, les autres
    #: `<service>.<env>.<domaine>`.
    host_includes_env: bool


#: Profils reconnus par leur nom. Un environnement au nom inattendu recoit
#: `DEFAULT_ENVIRONMENT_PROFILE`, c'est-a-dire le comportement le plus prudent.
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

#: Profil applique a tout environnement hors de la liste ci-dessus.
DEFAULT_ENVIRONMENT_PROFILE: Final[EnvironmentProfile] = EnvironmentProfile(
    replicas=1,
    hpa_enabled=False,
    pdb_enabled=False,
    log_level="info",
    resource_multiplier=1,
    host_includes_env=True,
)

#: Cle du profil de production, seule cible du drapeau `production: true`.
PRODUCTION_PROFILE_KEY: Final[str] = "prod"

#: Alias courants, pour que `production` se comporte comme `prod` et `stage`
#: comme `staging`. La reconnaissance est litterale : elle ne devine rien.
ENVIRONMENT_ALIASES: Final[dict[str, str]] = {
    "production": "prod",
    "prd": "prod",
    "stage": "staging",
    "stg": "staging",
    "develop": "dev",
    "development": "dev",
}


def profile_key(name: str) -> str:
    """Cle de profil correspondant a `name`, alias resolus."""
    return ENVIRONMENT_ALIASES.get(name, name)


def profile_for_environment(name: str) -> EnvironmentProfile:
    """Profil associe a un nom d'environnement, par reconnaissance du nom.

    Portage a l'identique du legacy. `derive.py` doit passer par
    :func:`profile_for`, qui tient compte du drapeau explicite du coeur.
    """
    return ENVIRONMENT_PROFILES.get(profile_key(name), DEFAULT_ENVIRONMENT_PROFILE)


def is_production_name(name: str) -> bool:
    """Indique si `name` est reconnu comme un environnement de production.

    Sert au controle croise du plugin : quand cette reconnaissance et le drapeau
    `service.environments[].production` divergent, un `Issue` de niveau
    *warning* est emis plutot que de trancher en silence (arbitrage H2).
    """
    return profile_key(name) == PRODUCTION_PROFILE_KEY


def profile_for(name: str, *, production: bool = False) -> EnvironmentProfile:
    """Profil retenu pour un environnement, arbitrage H2 applique.

    `production=True` (soit `service.environments[].production` du coeur) force
    le profil de production, et donc `host_includes_env=False`. Sinon, la
    reconnaissance par le nom s'applique : c'est elle qui rend une spec minimale
    equivalente a une spec complete.
    """
    if production:
        return ENVIRONMENT_PROFILES[PRODUCTION_PROFILE_KEY]
    return profile_for_environment(name)


# --------------------------------------------------------------------------
# Arithmetique sur les quantites Kubernetes
# --------------------------------------------------------------------------

_QUANTITY_PARTS: Final[re.Pattern[str]] = re.compile(
    r"^([0-9]+(?:\.[0-9]+)?)([a-zA-Z]*)$"
)


def scale_quantity(quantity: str, factor: int) -> str:
    """Multiplie une quantite Kubernetes par un entier, en gardant son suffixe.

    `scale_quantity("50m", 2)` renvoie `"100m"`, `scale_quantity("1", 2)`
    renvoie `"2"`. Le resultat est rendu sans decimale lorsqu'il tombe juste, ce
    qui garantit un rendu identique d'une execution a l'autre.
    """
    if factor == 1:
        return quantity
    match = _QUANTITY_PARTS.match(quantity)
    if match is None:  # pragma: no cover - protege en amont par la validation
        raise ValueError(f"quantite Kubernetes invalide : {quantity!r}")
    number, suffix = match.groups()
    scaled = float(number) * factor
    rendered = str(int(scaled)) if scaled.is_integer() else f"{scaled:g}"
    return f"{rendered}{suffix}"


def is_valid_quantity(quantity: str) -> bool:
    """Indique si la chaine est une quantite Kubernetes acceptable."""
    return bool(QUANTITY_RE.match(quantity))
