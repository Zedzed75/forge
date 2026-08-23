"""Énumérations du modèle de spécification.

Toutes héritent de ``StrEnum`` : leur valeur sérialisée dans ``forge.yml`` est
donc la chaîne lisible, et la comparaison directe avec une chaîne fonctionne.
Les valeurs qui apparaissent telles quelles dans un manifeste Kubernetes
conservent la casse exacte attendue par l'API (``ClusterIP``, ``IfNotPresent``).
"""

from __future__ import annotations

from enum import StrEnum


class Layout(StrEnum):
    """Disposition du projet généré."""

    SINGLE = "single"        # Un chart unique contenant tous les composants.
    UMBRELLA = "umbrella"    # Un chart par composant, plus un chart parapluie.


class ComponentKind(StrEnum):
    """Type de charge de travail porté par un composant."""

    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    CRONJOB = "cronjob"


class AddonKind(StrEnum):
    """Ressource additionnelle attachable à un composant.

    La présence d'une entrée dans ``ComponentSpec.addons`` détermine quels
    fichiers de gabarit sont générés. L'activation à l'exécution reste pilotée
    par un drapeau ``enabled`` dans les values, surchargeable par environnement.
    """

    SERVICE = "service"
    INGRESS = "ingress"
    CONFIGMAP = "configmap"
    SECRET = "secret"
    HPA = "hpa"
    PDB = "pdb"
    SERVICEACCOUNT = "serviceaccount"
    NETWORKPOLICY = "networkpolicy"
    SERVICEMONITOR = "servicemonitor"


class ServiceType(StrEnum):
    """Type de Service Kubernetes."""

    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


class IngressController(StrEnum):
    """Ingress controller ciblé, qui détermine annotations et ingressClassName."""

    NGINX = "nginx"
    TRAEFIK = "traefik"


class ImagePullPolicy(StrEnum):
    """Politique de récupération de l'image."""

    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


class TagStrategy(StrEnum):
    """Origine du tag de l'image dans les values générées."""

    APP_VERSION = "appVersion"  # tag vide, repli sur .Chart.AppVersion.
    PER_ENV = "per_env"         # un tag distinct par environnement.
    FIXED = "fixed"             # un tag unique et figé, fourni par la spec.


class NamespaceStrategy(StrEnum):
    """Mode de dérivation du namespace de chaque environnement."""

    SINGLE = "single"      # Le même namespace pour tous les environnements.
    PER_ENV = "per_env"    # <app>-<env>.
    CUSTOM = "custom"      # Namespace saisi explicitement pour chaque env.


class SecretStrategy(StrEnum):
    """Mode de gestion des secrets du projet généré.

    Aucune de ces stratégies ne produit jamais de valeur secrète réelle.
    """

    PLACEHOLDER = "placeholder"            # Secret Helm à valeurs obligatoires.
    EXTERNAL_SECRETS = "external-secrets"  # CR ExternalSecret (operator tiers).
    SEALED_SECRETS = "sealed-secrets"      # CR SealedSecret (Bitnami).
    NONE = "none"                          # Secrets gérés hors du chart.


class ResourceProfile(StrEnum):
    """Gabarit de requests/limits appliqué aux conteneurs."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    CUSTOM = "custom"


class AccessMode(StrEnum):
    """Mode d'accès d'un PersistentVolumeClaim."""

    RWO = "ReadWriteOnce"
    ROX = "ReadOnlyMany"
    RWX = "ReadWriteMany"
    RWOP = "ReadWriteOncePod"


class CIProvider(StrEnum):
    """Pipeline d'intégration continue générée avec le projet."""

    NONE = "none"
    GITHUB = "github"
    GITLAB = "gitlab"
