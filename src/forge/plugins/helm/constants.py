"""Constantes du domaine Helm : versions ciblees, apiVersions, plafonds.

Portage de `helm_forge.constants` (MIGRATION.md §4), ampute de ce qui appartient
au coeur : les expressions regulieres sont passees dans `names.py`, et
`SPEC_FILENAME` / `SPEC_SCHEMA_VERSION` sont remplaces par `forge_version` du
modele racine (`forge.spec.assembly`).

Ce module ne contient que des donnees immuables et ne depend d'aucun autre
module : il est la base de la pile d'imports du plugin.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Kubernetes
# --------------------------------------------------------------------------

#: Fenetre de versions de Kubernetes supportees (N-2 a N). La derniere entree
#: est la plus recente et sert de defaut. Arbitrage H12 : cette fenetre fait
#: foi ; l'exemple `1.31` de DESIGN.md §3 est corrige, pas la fenetre. Elle est
#: revalidee contre le `kubeconform` reellement installe, jamais elargie pour
#: faire passer un exemple.
KUBERNETES_VERSIONS: Final[tuple[str, ...]] = ("1.34", "1.35", "1.36")

#: Version proposee par defaut : la derniere stable de la fenetre.
DEFAULT_KUBERNETES_VERSION: Final[str] = KUBERNETES_VERSIONS[-1]

#: apiVersion employee selon la famille de ressource. Toutes les ressources
#: generees sont stables sur la fenetre supportee ; ce tableau existe pour
#: absorber sans douleur une future divergence de version.
API_VERSIONS: Final[dict[str, str]] = {
    "workload": "apps/v1",
    "batch": "batch/v1",
    "hpa": "autoscaling/v2",
    "pdb": "policy/v1",
    "ingress": "networking.k8s.io/v1",
    "networkpolicy": "networking.k8s.io/v1",
    "rbac": "rbac.authorization.k8s.io/v1",
}

# --------------------------------------------------------------------------
# Plafonds de longueur
# --------------------------------------------------------------------------
#
# Kubernetes limite un label DNS-1123 a 63 caracteres. Le generateur suffixe les
# ressources (`-headless`, `-serviceaccount`), d'ou une marge confortable sur le
# nom du service et celui des composants.
#
# Arbitrage H6 : les plafonds qui portent sur le bloc partage `service:`
# (`MAX_SERVICE_NAME_LENGTH`, `MAX_DESCRIPTION_LENGTH`,
# `MAX_ENVIRONMENT_NAME_LENGTH`) sont verifies par le **controle croise du
# plugin**, jamais par le coeur : ce sont des contraintes de `Chart.yaml` et du
# budget de 63 caracteres des noms de ressources Kubernetes, et le coeur n'a pas
# a connaitre Helm. Seul `MAX_COMPONENT_NAME_LENGTH` est applique par le modele,
# parce que les composants vivent dans la section `helm:`.

#: Plafond du nom de service (`service.name`), employe comme nom de chart.
MAX_SERVICE_NAME_LENGTH: Final[int] = 40

#: Plafond du nom d'un composant (`helm.components[].name`).
MAX_COMPONENT_NAME_LENGTH: Final[int] = 20

#: Plafond d'un nom d'environnement (`service.environments[].name`).
MAX_ENVIRONMENT_NAME_LENGTH: Final[int] = 20

#: Plafond de la description (`service.description`), reprise dans `Chart.yaml`.
MAX_DESCRIPTION_LENGTH: Final[int] = 200

# --------------------------------------------------------------------------
# Valeurs de repli du bloc partage
# --------------------------------------------------------------------------
#
# `service.owner` et `service.owner_email` alimentent la liste `maintainers` de
# `Chart.yaml`, qui n'accepte pas de valeur vide. `owner_email` etant facultatif
# dans le coeur, le plugin doit savoir quoi ecrire en son absence.

#: Mainteneur ecrit dans `Chart.yaml` quand `service.owner` est vide.
DEFAULT_MAINTAINER_NAME: Final[str] = "unknown"

#: Adresse ecrite dans `Chart.yaml` quand `service.owner_email` est absent.
DEFAULT_MAINTAINER_EMAIL: Final[str] = "unknown@example.com"
