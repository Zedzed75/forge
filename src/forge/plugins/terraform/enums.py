"""Enumerations du domaine Terraform.

Toutes heritent de `str` : le dict `domain` passe a copier doit rester
JSON-serialisable, et `.value` s'ecrit tel quel dans `.copier-answers.yml`.

`NamespaceStrategy` reprend les trois memes strategies que le domaine Helm.
C'est une duplication **assumee** : la partager exigerait de placer la notion de
namespace dans le coeur, qui doit rester agnostique (DESIGN.md §2). Les deux
domaines se rejoignent la ou il faut — sur la **facette** `namespaces`, comparee
par `forge validate`.
"""

from __future__ import annotations

from enum import Enum


class BackendKind(str, Enum):
    """Ou l'etat Terraform est conserve.

    L'etat contient en clair tout ce que les ressources exposent, y compris les
    mots de passe generes : le choix du backend est un choix de securite avant
    d'etre un choix de confort.
    """

    #: Fichier local. Utile en decouverte, jamais en equipe : ni verrou ni
    #: chiffrement, et rien n'empeche deux personnes d'appliquer en meme temps.
    LOCAL = "local"

    #: Bucket S3 (ou compatible). Le verrouillage demande `use_lockfile` ou une
    #: table DynamoDB, sans quoi deux applications concurrentes se recouvrent.
    S3 = "s3"

    #: Bucket Google Cloud Storage. Verrouillage natif, chiffrement au repos.
    GCS = "gcs"

    #: Compte de stockage Azure. Verrouillage natif par bail de blob.
    AZURERM = "azurerm"

    #: Service HTTP implementant l'API d'etat (GitLab managed state, Atlantis).
    HTTP = "http"


class NamespaceStrategy(str, Enum):
    """Comment le nom du namespace est derive de l'environnement."""

    #: Un seul namespace pour tous les environnements : `<service>`.
    SAME = "same"

    #: Un namespace par environnement : `<service>-<env>`.
    PER_ENV = "per_env"

    #: Chaque environnement fournit son namespace explicitement.
    CUSTOM = "custom"


class KubernetesAuth(str, Enum):
    """Comment le provider Kubernetes s'authentifie."""

    #: Fichier kubeconfig, avec un contexte nomme. Mode des postes et de la CI
    #: classique. Sans contexte explicite, le provider emploie le contexte
    #: *courant* du poste : c'est l'accident de production le plus banal.
    KUBECONFIG = "kubeconfig"

    #: Terraform s'execute dans un pod du cluster vise et lit son jeton monte.
    IN_CLUSTER = "in_cluster"


class ResourceFamily(str, Enum):
    """Familles de ressources que le module peut declarer.

    L'ordre de declaration est l'ordre canonique : il fixe l'ordre des fichiers
    `.tf` du module, celui des lignes du README et celui des cles de
    `domain.resource_slots`.
    """

    #: Le namespace lui-meme. Selectionnee, Terraform le **cree** ; absente, le
    #: module se rattache a un namespace existant fourni en variable.
    NAMESPACE = "namespace"

    #: ResourceQuota + LimitRange : le budget du namespace.
    QUOTA = "quota"

    #: Secret de tirage d'image (`kubernetes.io/dockerconfigjson`).
    REGISTRY_SECRET = "registry_secret"

    #: ServiceAccount + Role + RoleBinding pour les deploiements automatises.
    SERVICE_ACCOUNT = "service_account"

    #: NetworkPolicy fermant le namespace par defaut.
    NETWORK_POLICY = "network_policy"

    #: Mot de passe genere (`random_password`) depose en Secret.
    RANDOM_SECRET = "random_secret"

    #: Certificat auto-signe (`tls_*`) depose en Secret `kubernetes.io/tls`.
    TLS_CERTIFICATE = "tls_certificate"
