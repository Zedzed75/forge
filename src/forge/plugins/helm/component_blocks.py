"""Sous-modeles des ressources adjointes a un composant.

Separe de `components.py` pour tenir la limite de 600 lignes du projet, et
parce que la coupure a un sens : ici vivent les blocs qui decrivent une
**ressource annexe** — ce que forge genere *autour* de la charge de travail —
tandis que `components.py` decrit la charge de travail elle-meme et l'assemble.

Chaque bloc est toujours present dans le modele, meme quand l'addon
correspondant n'est pas selectionne : `values.yaml` expose ainsi un bloc
commente complet pour chaque fonctionnalite, ce qui est la convention Helm
attendue. C'est la liste `addons` du composant qui decide des fichiers
reellement generes.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.enums import AccessMode, IngressController
from forge.plugins.helm.names import (
    AbsolutePath,
    CronSchedule,
    EnvKey,
    HttpPath,
    Percentage,
    Quantity,
)
from forge.spec.types import DnsLabel, ForgeModel, Subdomain

#: Modes d'injection admis pour un ConfigMap ou un Secret : variables
#: d'environnement via `envFrom`, ou fichier monte dans le conteneur.
MOUNT_MODES = ("env", "file")

#: Politiques de concurrence admises par un CronJob Kubernetes.
CONCURRENCY_POLICIES = ("Allow", "Forbid", "Replace")

#: Politiques de redemarrage admises par le pod d'un CronJob.
RESTART_POLICIES = ("OnFailure", "Never")


class IngressSpec(ForgeModel):
    """Exposition HTTP par un Ingress.

    L'hote n'est pas stocke ici : il est derive par environnement par
    `derive.py`, et reste surchargeable dans `values-<env>.yaml`.
    """

    #: Ingress controller cible : nginx | traefik.
    controller: IngressController = IngressController.NGINX

    #: Domaine de base employe quand l'environnement n'a pas son propre
    #: `service.environments[].domain` (arbitrage H1 : le domaine du coeur
    #: l'emporte quand il est renseigne).
    base_domain: Subdomain = "example.com"

    #: Chemin HTTP servi par cette regle d'Ingress.
    path: HttpPath = "/"

    #: Type de correspondance du chemin : Prefix | Exact | ImplementationSpecific.
    path_type: str = "Prefix"

    #: Emet un certificat TLS pour l'hote via cert-manager.
    tls: bool = True

    #: Nom du ClusterIssuer cert-manager employe pour emettre le certificat.
    issuer: str = "letsencrypt-prod"

    #: Surcharge de `ingressClassName` ; absent = derive du `controller`.
    class_name: str | None = None

    #: Annotations posees sur l'Ingress.
    annotations: dict[str, str] = Field(default_factory=dict)


class PersistenceSpec(ForgeModel):
    """Volume persistant attache a la charge de travail."""

    #: Genere un PersistentVolumeClaim ; force a vrai pour un StatefulSet.
    enabled: bool = False

    #: StorageClass demandee ; chaine vide = classe par defaut du cluster.
    storage_class: str = ""

    #: Taille demandee au volume (`10Gi`).
    size: Quantity = "10Gi"

    #: Mode d'acces : ReadWriteOnce | ReadOnlyMany | ReadWriteMany |
    #: ReadWriteOncePod.
    access_mode: AccessMode = AccessMode.RWO

    #: Chemin absolu de montage du volume dans le conteneur.
    mount_path: AbsolutePath = "/data"


class HpaSpec(ForgeModel):
    """Autoscaling horizontal base sur l'utilisation CPU, et memoire en option."""

    #: Plancher de replicas (1-100).
    min_replicas: int = Field(default=2, ge=1, le=100)

    #: Plafond de replicas (1-100), au moins egal a `min_replicas`.
    max_replicas: int = Field(default=5, ge=1, le=100)

    #: Cible d'utilisation CPU en pourcentage (1-100).
    target_cpu: Percentage = 80

    #: Cible d'utilisation memoire en pourcentage ; absente = non surveillee.
    target_memory: Percentage | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> HpaSpec:
        if self.min_replicas > self.max_replicas:
            raise ValueError("hpa.min_replicas ne peut pas depasser hpa.max_replicas")
        return self


class PdbSpec(ForgeModel):
    """Budget d'interruption volontaire."""

    #: Nombre minimal de pods disponibles : entier positif ou pourcentage
    #: sous forme de chaine (`"50%"`).
    min_available: int | str = 1

    @model_validator(mode="after")
    def _check_min_available(self) -> PdbSpec:
        value = self.min_available
        if isinstance(value, str) and not (
            value.endswith("%") and value[:-1].isdigit()
        ):
            raise ValueError(
                'pdb.min_available doit etre un entier ou un pourcentage du type "50%"'
            )
        if isinstance(value, int) and value < 0:
            raise ValueError("pdb.min_available ne peut pas etre negatif")
        return self


class NetworkPolicySpec(ForgeModel):
    """Restriction du trafic reseau entrant et sortant."""

    #: Autorise le trafic entrant venant du namespace du composant.
    allow_from_same_namespace: bool = True

    #: Namespaces supplementaires autorises en entree (labels DNS).
    allow_from_namespaces: list[DnsLabel] = Field(default_factory=list)

    #: La resolution DNS doit rester autorisee, sinon le pod ne joint plus rien.
    allow_dns: bool = True

    #: Autorise tout le trafic sortant ; faux restreint la sortie au DNS.
    allow_egress_all: bool = False


class RbacSpec(ForgeModel):
    """Droits du ServiceAccount du composant, dans son namespace.

    Genere avec l'addon `serviceaccount` : un Role n'a de sens qu'avec un
    sujet. Aucune ressource de portee cluster n'est produite — ClusterRole et
    ClusterRoleBinding sont hors perimetre, et les inventer casserait la regle
    « ne jamais inventer un kind ».
    """

    #: Cree un Role et son RoleBinding lies au ServiceAccount du composant.
    #: `roleRef` etant immuable, changer le Role vise fait echouer un upgrade.
    create: bool = False

    #: Regles du Role, au format PolicyRule de Kubernetes. Une liste vide ne
    #: produit ni Role ni RoleBinding : un Role sans regle est valide au schema,
    #: mais inutile et trompeur.
    rules: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def _regles_completes(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Chaque regle doit porter apiGroups, resources et verbs, non vides.

        L'API refuse une regle incomplete, mais `kubeconform` la laisse passer :
        le controle appartient donc au modele.
        """
        for index, regle in enumerate(value):
            manquants = [cle for cle in ("apiGroups", "resources", "verbs") if cle not in regle]
            if manquants:
                raise ValueError(
                    f"Regle RBAC n°{index + 1} incomplete : {', '.join(manquants)} "
                    "manquant(s). Pour les ressources du groupe core, apiGroups "
                    'vaut [""].'
                )
            if not regle["verbs"] or not regle["resources"]:
                raise ValueError(
                    f"Regle RBAC n°{index + 1} : `resources` et `verbs` ne peuvent "
                    "pas etre vides."
                )
        return value


class ConfigSpec(ForgeModel):
    """Configuration non sensible, exposee par un ConfigMap."""

    #: Cles de configuration attendues (MAJUSCULES_ET_SOULIGNES).
    keys: list[EnvKey] = Field(default_factory=lambda: ["LOG_LEVEL", "APP_ENV"])

    #: Injection des cles dans le conteneur : `env` (envFrom) ou `file` (monte).
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ConfigSpec:
        if self.mount_as not in MOUNT_MODES:
            raise ValueError('config.mount_as doit valoir "env" ou "file"')
        return self


class ComponentSecretSpec(ForgeModel):
    """Cles de secret attendues par le composant.

    Seules les cles sont decrites : aucune valeur n'est jamais stockee dans la
    specification ni dans les fichiers generes.
    """

    #: Cles de secret attendues (MAJUSCULES_ET_SOULIGNES).
    keys: list[EnvKey] = Field(default_factory=lambda: ["API_KEY"])

    #: Injection des cles dans le conteneur : `env` (envFrom) ou `file` (monte).
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ComponentSecretSpec:
        if self.mount_as not in MOUNT_MODES:
            raise ValueError('secret.mount_as doit valoir "env" ou "file"')
        return self


class CronSpec(ForgeModel):
    """Parametres propres a un CronJob."""

    #: Planification cron a cinq champs (`0 3 * * *`).
    schedule: CronSchedule = "0 3 * * *"

    #: Concurrence de deux executions : Allow | Forbid | Replace.
    concurrency_policy: str = "Forbid"

    #: Redemarrage du pod : OnFailure | Never.
    restart_policy: str = "OnFailure"

    #: Nombre d'executions reussies conservees dans l'historique (>= 0).
    successful_jobs_history_limit: int = Field(default=3, ge=0)

    #: Nombre d'executions echouees conservees dans l'historique (>= 0).
    failed_jobs_history_limit: int = Field(default=1, ge=0)

    #: Nombre de reprises avant d'abandonner une execution (>= 0).
    backoff_limit: int = Field(default=3, ge=0)

    #: Retard tolere avant de considerer une execution manquee ; absent = aucune
    #: limite.
    starting_deadline_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_policies(self) -> CronSpec:
        if self.concurrency_policy not in CONCURRENCY_POLICIES:
            raise ValueError(
                "cron.concurrency_policy doit valoir Allow, Forbid ou Replace"
            )
        if self.restart_policy not in RESTART_POLICIES:
            raise ValueError("cron.restart_policy doit valoir OnFailure ou Never")
        return self
