"""Modèle d'un composant : une charge de travail nommée et ses ressources.

Un composant correspond à une charge de travail déployable (``api``,
``worker``, ``cleanup``). Il porte son type (Deployment, StatefulSet, CronJob)
et la liste des ressources annexes à générer autour de lui (``addons``).

Les sous-modèles sont toujours présents, même lorsque l'addon correspondant
n'est pas sélectionné : cela permet à ``values.yaml`` d'exposer un bloc commenté
complet pour chaque fonctionnalité, ce qui est la convention Helm attendue.
C'est la liste ``addons`` qui décide des fichiers réellement générés.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ..constants import MAX_COMPONENT_NAME_LENGTH
from .base import ForgeModel
from .enums import (
    AccessMode,
    AddonKind,
    ComponentKind,
    IngressController,
    ResourceProfile,
    ServiceType,
)
from .profiles import RESOURCE_PROFILES, scale_quantity
from .validators import (
    AbsolutePath,
    CronSchedule,
    DnsLabel,
    EnvKey,
    HttpPath,
    ImageRepository,
    Percentage,
    Port,
    Quantity,
    Subdomain,
)


class ProbesSpec(ForgeModel):
    """Sondes de santé du conteneur principal."""

    enabled: bool = True
    liveness_path: HttpPath = "/healthz"
    readiness_path: HttpPath = "/ready"
    #: Sonde startup : utile pour les applications au démarrage lent, elle
    #: suspend liveness et readiness tant qu'elle n'a pas réussi.
    startup_enabled: bool = False
    initial_delay_seconds: int = Field(default=5, ge=0)
    period_seconds: int = Field(default=10, ge=1)
    timeout_seconds: int = Field(default=2, ge=1)
    failure_threshold: int = Field(default=3, ge=1)


class ResourcesSpec(ForgeModel):
    """Requests et limits du conteneur principal.

    Le champ ``profile`` est informatif : les quatre quantités font foi. Quand
    un profil connu est indiqué sans quantité explicite, les valeurs du profil
    sont appliquées automatiquement.
    """

    profile: ResourceProfile = ResourceProfile.SMALL
    cpu_request: Quantity = "50m"
    memory_request: Quantity = "64Mi"
    cpu_limit: Quantity = "200m"
    memory_limit: Quantity = "128Mi"

    @model_validator(mode="before")
    @classmethod
    def _apply_profile(cls, data: Any) -> Any:
        """Complète les quantités absentes à partir du profil demandé."""
        if not isinstance(data, dict):
            return data
        profile = str(data.get("profile", ResourceProfile.SMALL))
        values = RESOURCE_PROFILES.get(profile)
        if values is None:  # profil « custom » ou inconnu : rien à compléter.
            return data
        data.setdefault("cpu_request", values.cpu_request)
        data.setdefault("memory_request", values.memory_request)
        data.setdefault("cpu_limit", values.cpu_limit)
        data.setdefault("memory_limit", values.memory_limit)
        return data

    def scaled(self, factor: int) -> ResourcesSpec:
        """Renvoie une copie dont les quatre quantités sont multipliées."""
        if factor == 1:
            return self
        return ResourcesSpec(
            profile=ResourceProfile.CUSTOM,
            cpu_request=scale_quantity(self.cpu_request, factor),
            memory_request=scale_quantity(self.memory_request, factor),
            cpu_limit=scale_quantity(self.cpu_limit, factor),
            memory_limit=scale_quantity(self.memory_limit, factor),
        )


class SecuritySpec(ForgeModel):
    """Contexte de sécurité du pod et du conteneur.

    ``strict`` à vrai applique le durcissement recommandé : utilisateur non
    root, système de fichiers racine en lecture seule, toutes les capabilities
    retirées, profil seccomp par défaut. Chaque champ reste surchargeable.
    """

    strict: bool = True
    run_as_non_root: bool = True
    run_as_user: int = Field(default=10001, ge=1)
    run_as_group: int = Field(default=10001, ge=1)
    fs_group: int = Field(default=10001, ge=1)
    read_only_root_filesystem: bool = True
    allow_privilege_escalation: bool = False
    drop_capabilities: list[str] = Field(default_factory=lambda: ["ALL"])
    seccomp_profile: str = "RuntimeDefault"

    @model_validator(mode="before")
    @classmethod
    def _relax_when_not_strict(cls, data: Any) -> Any:
        """Assouplit les valeurs par défaut quand le durcissement est refusé."""
        if not isinstance(data, dict) or data.get("strict", True):
            return data
        data.setdefault("run_as_non_root", False)
        data.setdefault("read_only_root_filesystem", False)
        data.setdefault("drop_capabilities", [])
        return data


class ServiceSpec(ForgeModel):
    """Service exposant la charge de travail."""

    type: ServiceType = ServiceType.CLUSTER_IP
    port: Port = 80
    #: Un StatefulSet exige un Service headless (clusterIP: None) pour donner
    #: une identité réseau stable à chaque pod. Positionné automatiquement.
    headless: bool = False
    node_port: Port | None = None
    annotations: dict[str, str] = Field(default_factory=dict)


class IngressSpec(ForgeModel):
    """Exposition HTTP par un Ingress.

    L'hôte n'est pas stocké ici : il est dérivé par environnement à partir de
    ``base_domain`` et du profil d'environnement, et reste surchargeable dans
    ``values-<env>.yaml``.
    """

    controller: IngressController = IngressController.NGINX
    base_domain: Subdomain = "example.com"
    path: HttpPath = "/"
    path_type: str = "Prefix"
    tls: bool = True
    #: Nom du ClusterIssuer cert-manager utilisé pour émettre le certificat.
    issuer: str = "letsencrypt-prod"
    #: Surcharge éventuelle de ingressClassName, sinon dérivée du controller.
    class_name: str | None = None
    annotations: dict[str, str] = Field(default_factory=dict)


class PersistenceSpec(ForgeModel):
    """Volume persistant attaché à la charge de travail."""

    enabled: bool = False
    #: Chaîne vide : la StorageClass par défaut du cluster est utilisée.
    storage_class: str = ""
    size: Quantity = "10Gi"
    access_mode: AccessMode = AccessMode.RWO
    mount_path: AbsolutePath = "/data"


class HpaSpec(ForgeModel):
    """Autoscaling horizontal basé sur l'utilisation CPU, et mémoire en option."""

    min_replicas: int = Field(default=2, ge=1, le=100)
    max_replicas: int = Field(default=5, ge=1, le=100)
    target_cpu: Percentage = 80
    target_memory: Percentage | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> HpaSpec:
        if self.min_replicas > self.max_replicas:
            raise ValueError(
                "hpa.min_replicas ne peut pas dépasser hpa.max_replicas"
            )
        return self


class PdbSpec(ForgeModel):
    """Budget d'interruption volontaire.

    ``min_available`` accepte un entier ou un pourcentage sous forme de chaîne.
    """

    min_available: int | str = 1

    @model_validator(mode="after")
    def _check_min_available(self) -> PdbSpec:
        value = self.min_available
        if isinstance(value, str) and not (
            value.endswith("%") and value[:-1].isdigit()
        ):
            raise ValueError(
                "pdb.min_available doit être un entier ou un pourcentage "
                'du type "50%"'
            )
        if isinstance(value, int) and value < 0:
            raise ValueError("pdb.min_available ne peut pas être négatif")
        return self


class NetworkPolicySpec(ForgeModel):
    """Restriction du trafic réseau entrant et sortant."""

    allow_from_same_namespace: bool = True
    allow_from_namespaces: list[DnsLabel] = Field(default_factory=list)
    #: La résolution DNS doit rester autorisée, sinon le pod ne joint plus rien.
    allow_dns: bool = True
    allow_egress_all: bool = False


class ServiceMonitorSpec(ForgeModel):
    """Collecte Prometheus via la CRD ServiceMonitor de Prometheus Operator."""

    path: HttpPath = "/metrics"
    port_name: str = "http"
    interval: str = "30s"
    scrape_timeout: str = "10s"


class ConfigSpec(ForgeModel):
    """Configuration non sensible, exposée par un ConfigMap."""

    keys: list[EnvKey] = Field(default_factory=lambda: ["LOG_LEVEL", "APP_ENV"])
    #: Injection des clés dans le conteneur : variables d'environnement via
    #: envFrom, ou fichier monté dans le conteneur.
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ConfigSpec:
        if self.mount_as not in {"env", "file"}:
            raise ValueError('config.mount_as doit valoir "env" ou "file"')
        return self


class ComponentSecretSpec(ForgeModel):
    """Clés de secret attendues par le composant.

    Seules les clés sont décrites : aucune valeur n'est jamais stockée dans la
    spécification ni dans les fichiers générés.
    """

    keys: list[EnvKey] = Field(default_factory=lambda: ["API_KEY"])
    mount_as: str = "env"

    @model_validator(mode="after")
    def _check_mount_as(self) -> ComponentSecretSpec:
        if self.mount_as not in {"env", "file"}:
            raise ValueError('secret.mount_as doit valoir "env" ou "file"')
        return self


class CronSpec(ForgeModel):
    """Paramètres propres à un CronJob."""

    schedule: CronSchedule = "0 3 * * *"
    concurrency_policy: str = "Forbid"
    restart_policy: str = "OnFailure"
    successful_jobs_history_limit: int = Field(default=3, ge=0)
    failed_jobs_history_limit: int = Field(default=1, ge=0)
    backoff_limit: int = Field(default=3, ge=0)
    starting_deadline_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_policies(self) -> CronSpec:
        if self.concurrency_policy not in {"Allow", "Forbid", "Replace"}:
            raise ValueError(
                "cron.concurrency_policy doit valoir Allow, Forbid ou Replace"
            )
        if self.restart_policy not in {"OnFailure", "Never"}:
            raise ValueError("cron.restart_policy doit valoir OnFailure ou Never")
        return self


#: Addons incompatibles avec un CronJob : un job n'est ni exposé ni autoscalé.
_CRONJOB_FORBIDDEN_ADDONS: frozenset[AddonKind] = frozenset(
    {AddonKind.SERVICE, AddonKind.INGRESS, AddonKind.HPA, AddonKind.PDB,
     AddonKind.SERVICEMONITOR}
)


class ComponentSpec(ForgeModel):
    """Une charge de travail nommée et l'ensemble de ses ressources annexes."""

    name: DnsLabel = Field(max_length=MAX_COMPONENT_NAME_LENGTH)
    kind: ComponentKind = ComponentKind.DEPLOYMENT
    #: Ressources annexes générées autour de la charge de travail. L'ordre est
    #: normalisé afin que deux specs équivalentes produisent le même projet.
    addons: list[AddonKind] = Field(
        default_factory=lambda: [AddonKind.SERVICE, AddonKind.CONFIGMAP]
    )

    #: Surcharge du dépôt d'image, quand un composant n'utilise pas l'image
    #: principale du projet (rare : un worker partage en général l'image).
    image_repository: ImageRepository | None = None
    #: Commande et arguments : c'est ainsi qu'un worker se distingue d'une API
    #: tout en partageant la même image.
    command: list[str] = Field(default_factory=list)
    args: list[str] = Field(default_factory=list)

    replicas: int = Field(default=1, ge=0)
    container_port: Port = 8080
    port_name: str = "http"

    probes: ProbesSpec = Field(default_factory=ProbesSpec)
    resources: ResourcesSpec = Field(default_factory=ResourcesSpec)
    security: SecuritySpec = Field(default_factory=SecuritySpec)
    service: ServiceSpec = Field(default_factory=ServiceSpec)
    ingress: IngressSpec = Field(default_factory=IngressSpec)
    persistence: PersistenceSpec = Field(default_factory=PersistenceSpec)
    hpa: HpaSpec = Field(default_factory=HpaSpec)
    pdb: PdbSpec = Field(default_factory=PdbSpec)
    networkpolicy: NetworkPolicySpec = Field(default_factory=NetworkPolicySpec)
    servicemonitor: ServiceMonitorSpec = Field(default_factory=ServiceMonitorSpec)
    config: ConfigSpec = Field(default_factory=ConfigSpec)
    secret: ComponentSecretSpec = Field(default_factory=ComponentSecretSpec)
    cron: CronSpec | None = None

    # ------------------------------------------------------------------
    # Validation croisée
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _normalise_and_check(self) -> ComponentSpec:
        """Normalise les addons puis vérifie la cohérence de l'ensemble."""
        # Déduplication en conservant l'ordre canonique de déclaration de
        # AddonKind : le plan de fichiers devient ainsi indépendant de l'ordre
        # de saisie de l'utilisateur.
        order = list(AddonKind)
        unique = sorted(set(self.addons), key=order.index)
        if unique != self.addons:
            # validate_assignment est actif : écrire directement dans __dict__
            # évite de relancer ce validateur en boucle.
            self.__dict__["addons"] = unique

        if AddonKind.INGRESS in unique and AddonKind.SERVICE not in unique:
            raise ValueError(
                f"composant {self.name!r} : l'addon ingress exige l'addon service"
            )
        if AddonKind.SERVICEMONITOR in unique and AddonKind.SERVICE not in unique:
            raise ValueError(
                f"composant {self.name!r} : l'addon servicemonitor exige "
                "l'addon service"
            )

        if self.kind is ComponentKind.CRONJOB:
            forbidden = sorted(a.value for a in unique if a in _CRONJOB_FORBIDDEN_ADDONS)
            if forbidden:
                raise ValueError(
                    f"composant {self.name!r} de type cronjob : addons "
                    f"incompatibles {forbidden}"
                )
            if self.cron is None:
                self.__dict__["cron"] = CronSpec()
        elif self.cron is not None:
            raise ValueError(
                f"composant {self.name!r} : le bloc cron n'a de sens que pour "
                "un composant de type cronjob"
            )

        if self.kind is ComponentKind.STATEFULSET:
            # Un StatefulSet a besoin d'un Service headless et, dans la quasi
            # totalité des cas, d'un volume persistant.
            if not self.service.headless:
                self.service.__dict__["headless"] = True
            if not self.persistence.enabled:
                self.persistence.__dict__["enabled"] = True

        return self

    # ------------------------------------------------------------------
    # Accès pratiques, utilisés par le planificateur et les gabarits
    # ------------------------------------------------------------------

    def has(self, addon: AddonKind) -> bool:
        """Indique si un addon est sélectionné pour ce composant."""
        return addon in self.addons

    @property
    def is_workload(self) -> bool:
        """Vrai pour un Deployment ou un StatefulSet, faux pour un CronJob."""
        return self.kind in (ComponentKind.DEPLOYMENT, ComponentKind.STATEFULSET)
