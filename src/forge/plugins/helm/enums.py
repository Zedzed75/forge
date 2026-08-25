"""Enumerations de la section `helm:` de forge.yml.

Portage de `helm_forge.models.enums` (MIGRATION.md §4).

Toutes heritent de `StrEnum` : la valeur serialisee dans `forge.yml` est donc la
chaine lisible, et la comparaison directe avec une chaine fonctionne — ce dont
depend la resolution des profils de ressources. Les valeurs qui apparaissent
telles quelles dans un manifeste Kubernetes conservent la casse exacte attendue
par l'API (`ClusterIP`, `IfNotPresent`).

Deux ecarts assumes avec le legacy, tous deux par application du meme principe :
**une valeur declaree mais non generee est un piege**, puisqu'elle passe la
validation d'un schema `extra="forbid"` et fait exploser la generation.

* `Layout.UMBRELLA` est retire (arbitrage H3) : le planner legacy levait
  `NotImplementedError` et aucun gabarit n'existait. A reintroduire avec ses
  gabarits.
* `AddonKind.SERVICEMONITOR` est retire (arbitrage H7) : la collecte Prometheus
  est hors perimetre de la phase 4.
* `CIProvider` n'est pas porte (arbitrage H8) : la CI est de niveau depot
  (decision Q6), et les deux domaines l'exprimaient de deux facons.
"""

from __future__ import annotations

from enum import StrEnum


class Layout(StrEnum):
    """Disposition du projet genere.

    `single` : un chart unique contenant tous les composants — seule valeur
    admise aujourd'hui (arbitrage H3).
    """

    SINGLE = "single"


class ComponentKind(StrEnum):
    """Type de charge de travail porte par un composant.

    `deployment` : charge sans etat, la valeur usuelle.
    `statefulset` : identite reseau et volume stables (impose un Service
    headless et la persistance).
    `cronjob` : execution planifiee, ni exposee ni autoscalee.
    """

    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    CRONJOB = "cronjob"


class AddonKind(StrEnum):
    """Ressource additionnelle attachable a un composant.

    La presence d'une entree dans `ComponentSpec.addons` decide des fichiers de
    gabarit reellement generes. L'activation a l'execution reste pilotee par un
    drapeau `enabled` dans les values, surchargeable par environnement.

    L'ordre de declaration ci-dessous est l'**ordre canonique** : la liste
    `addons` y est renormalisee, afin que deux specs equivalentes produisent le
    meme projet quel que soit l'ordre de saisie.
    """

    SERVICE = "service"
    INGRESS = "ingress"
    CONFIGMAP = "configmap"
    SECRET = "secret"
    HPA = "hpa"
    PDB = "pdb"
    SERVICEACCOUNT = "serviceaccount"
    NETWORKPOLICY = "networkpolicy"


class ServiceType(StrEnum):
    """Type de Service Kubernetes exposant la charge de travail."""

    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


class IngressController(StrEnum):
    """Ingress controller cible, qui determine annotations et ingressClassName."""

    NGINX = "nginx"
    TRAEFIK = "traefik"


class ImagePullPolicy(StrEnum):
    """Politique de recuperation de l'image du conteneur."""

    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


class TagStrategy(StrEnum):
    """Origine du tag de l'image dans les values generees.

    `appVersion` : tag vide, repli sur `.Chart.AppVersion`.
    `per_env` : un tag distinct par environnement (`helm.environments.<env>`).
    `fixed` : un tag unique et fige, fourni par `helm.image.tag`.
    """

    APP_VERSION = "appVersion"
    PER_ENV = "per_env"
    FIXED = "fixed"


class NamespaceStrategy(StrEnum):
    """Mode de derivation du namespace de chaque environnement.

    `single` : le meme namespace pour tous les environnements (`<service>`).
    `per_env` : `<service>-<env>`.
    `custom` : namespace saisi explicitement pour chaque environnement.
    """

    SINGLE = "single"
    PER_ENV = "per_env"
    CUSTOM = "custom"


class SecretStrategy(StrEnum):
    """Mode de gestion des secrets du projet genere.

    Aucune de ces strategies ne produit jamais de valeur secrete reelle : le
    generateur ne fabrique que des emplacements a remplir hors du depot.

    `placeholder` : Secret Helm a valeurs obligatoires.
    `external-secrets` : ressource ExternalSecret (operateur tiers).
    `sealed-secrets` : ressource SealedSecret (Bitnami).
    `none` : secrets geres entierement hors du chart.
    """

    PLACEHOLDER = "placeholder"
    EXTERNAL_SECRETS = "external-secrets"
    SEALED_SECRETS = "sealed-secrets"
    NONE = "none"


class ResourceProfile(StrEnum):
    """Gabarit de requests/limits applique aux conteneurs.

    `small`, `medium`, `large` completent les quatre quantites absentes ;
    `custom` n'en complete aucune et laisse les quantites explicites faire foi.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    CUSTOM = "custom"


class AccessMode(StrEnum):
    """Mode d'acces d'un PersistentVolumeClaim."""

    RWO = "ReadWriteOnce"
    ROX = "ReadOnlyMany"
    RWX = "ReadWriteMany"
    RWOP = "ReadWriteOncePod"
