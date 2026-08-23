"""Constantes partagées : versions supportées, expressions de validation, limites.

Ce module ne contient que des données immuables. Il ne dépend d'aucun autre
module du projet, ce qui en fait la base de la pile d'imports.
"""

from __future__ import annotations

import re
from typing import Final

# --------------------------------------------------------------------------
# Kubernetes
# --------------------------------------------------------------------------

#: Fenêtre de versions supportées (N-2 à N), décision D7 du document de
#: conception. La dernière entrée est la plus récente et sert de défaut.
KUBERNETES_VERSIONS: Final[tuple[str, ...]] = ("1.34", "1.35", "1.36")

#: Version proposée par défaut dans le CLI : la dernière stable.
DEFAULT_KUBERNETES_VERSION: Final[str] = KUBERNETES_VERSIONS[-1]

#: apiVersion à utiliser selon la version de Kubernetes ciblée. Toutes les
#: ressources générées sont stables sur la fenêtre supportée ; ce tableau
#: existe pour absorber sans douleur une future divergence de version.
API_VERSIONS: Final[dict[str, str]] = {
    "workload": "apps/v1",
    "batch": "batch/v1",
    "hpa": "autoscaling/v2",
    "pdb": "policy/v1",
    "ingress": "networking.k8s.io/v1",
    "networkpolicy": "networking.k8s.io/v1",
    "rbac": "rbac.authorization.k8s.io/v1",
    "servicemonitor": "monitoring.coreos.com/v1",
}

# --------------------------------------------------------------------------
# Expressions régulières de validation
# --------------------------------------------------------------------------

#: Label DNS-1123 : noms de ressources Kubernetes, de namespaces, de composants.
DNS1123_LABEL: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
)

#: Sous-domaine DNS-1123 : hôtes d'Ingress, domaines de base, registries.
DNS1123_SUBDOMAIN: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)

#: Clé de variable d'environnement, telle qu'attendue dans un ConfigMap ou un
#: Secret consommé via envFrom.
ENV_KEY: Final[re.Pattern[str]] = re.compile(r"^[A-Z_][A-Z0-9_]*$")

#: Quantité Kubernetes : 100m, 1, 1.5, 512Mi, 10Gi, 1e3...
QUANTITY: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$"
)

#: SemVer strict, exigé par Helm pour le champ version de Chart.yaml.
SEMVER: Final[re.Pattern[str]] = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

#: Dépôt d'image OCI : minuscules, chiffres, séparateurs, chemins imbriqués.
IMAGE_REPOSITORY: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*$"
)

#: Planification cron à cinq champs, telle qu'attendue par un CronJob.
CRON_SCHEDULE: Final[re.Pattern[str]] = re.compile(
    r"^(\S+\s+){4}\S+$"
)

# --------------------------------------------------------------------------
# Limites
# --------------------------------------------------------------------------

#: Kubernetes limite un label DNS-1123 à 63 caractères. Le générateur suffixe
#: les ressources (-headless, -serviceaccount, -metrics), on garde donc une
#: marge confortable sur le nom de l'application et des composants.
MAX_APP_NAME_LENGTH: Final[int] = 40
MAX_COMPONENT_NAME_LENGTH: Final[int] = 20
MAX_ENVIRONMENT_NAME_LENGTH: Final[int] = 20

#: Nom du fichier de spécification rejouable déposé à la racine du projet généré.
SPEC_FILENAME: Final[str] = "forge.yml"

#: Version du schéma de forge.yml. À incrémenter à chaque changement cassant du
#: modèle, avec une migration dans spec_io.
SPEC_SCHEMA_VERSION: Final[int] = 1
