"""Modele d'un composant : une charge de travail nommee et ses ressources.

Portage de `helm_forge.models.component` (MIGRATION.md §4).

Un composant correspond a une charge de travail deployable (`api`, `worker`,
`cleanup`). Il porte son type (Deployment, StatefulSet, CronJob) et la liste des
ressources annexes a generer autour de lui (`addons`).

Les sous-modeles sont **toujours presents**, meme lorsque l'addon correspondant
n'est pas selectionne : `values.yaml` expose ainsi un bloc commente complet pour
chaque fonctionnalite, ce qui est la convention Helm attendue. C'est la liste
`addons` qui decide des fichiers reellement generes.

Deux ecarts avec le legacy :

* le bloc `servicemonitor` n'est pas porte (arbitrage H7, hors perimetre) ;
* les normalisations ecrivaient dans `__dict__` pour contourner
  `validate_assignment=True` ; ce mode n'etant pas reintroduit (arbitrage H11),
  elles sont ecrites en affectations ordinaires, faites pendant la validation.
  Le modele reste immuable **apres** validation : plus rien ne le modifie.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.component_blocks import (
    ComponentSecretSpec,
    ConfigSpec,
    CronSpec,
    HpaSpec,
    IngressSpec,
    NetworkPolicySpec,
    PdbSpec,
    PersistenceSpec,
    RbacSpec,
)
from forge.plugins.helm.constants import MAX_COMPONENT_NAME_LENGTH
from forge.plugins.helm.enums import (
    AccessMode,
    AddonKind,
    ComponentKind,
    IngressController,
    ResourceProfile,
    ServiceType,
)
from forge.plugins.helm.names import (
    AbsolutePath,
    CronSchedule,
    EnvKey,
    HttpPath,
    ImageRepository,
    Percentage,
    Port,
    PortName,
    Quantity,
)
from forge.plugins.helm.profiles import RESOURCE_PROFILES, scale_quantity
from forge.spec.types import DnsLabel, ForgeModel, Subdomain

#: Addons incompatibles avec un CronJob : un job n'est ni expose ni autoscale.
CRONJOB_FORBIDDEN_ADDONS: frozenset[AddonKind] = frozenset(
    {AddonKind.SERVICE, AddonKind.INGRESS, AddonKind.HPA, AddonKind.PDB}
)


class ProbesSpec(ForgeModel):
    """Sondes de sante du conteneur principal."""

    #: Genere les sondes liveness et readiness. Faux pour un worker sans port.
    enabled: bool = True

    #: Chemin HTTP interroge par la sonde liveness (redemarre le conteneur).
    liveness_path: HttpPath = "/healthz"

    #: Chemin HTTP interroge par la sonde readiness (retire du Service).
    readiness_path: HttpPath = "/ready"

    #: Sonde startup : utile aux applications au demarrage lent, elle suspend
    #: liveness et readiness tant qu'elle n'a pas reussi.
    startup_enabled: bool = False

    #: Delai avant la premiere interrogation, en secondes (>= 0).
    initial_delay_seconds: int = Field(default=5, ge=0)

    #: Periode entre deux interrogations, en secondes (>= 1).
    period_seconds: int = Field(default=10, ge=1)

    #: Delai d'attente d'une reponse, en secondes (>= 1).
    timeout_seconds: int = Field(default=2, ge=1)

    #: Nombre d'echecs consecutifs avant de declarer la sonde en echec (>= 1).
    failure_threshold: int = Field(default=3, ge=1)


class ResourcesSpec(ForgeModel):
    """Requests et limits du conteneur principal.

    Le champ `profile` est informatif : les quatre quantites font foi. Quand un
    profil connu est indique sans quantite explicite, les valeurs du profil sont
    appliquees automatiquement — c'est ce qui rend une spec partielle
    equivalente a une spec complete.
    """

    #: Gabarit applique : small | medium | large | custom (aucun completement).
    profile: ResourceProfile = ResourceProfile.SMALL

    #: CPU garanti au conteneur (`50m`, `1`).
    cpu_request: Quantity = "50m"

    #: Memoire garantie au conteneur (`64Mi`, `1Gi`).
    memory_request: Quantity = "64Mi"

    #: Plafond de CPU du conteneur (`200m`, `2`).
    cpu_limit: Quantity = "200m"

    #: Plafond de memoire du conteneur ; un depassement tue le conteneur.
    memory_limit: Quantity = "128Mi"

    @model_validator(mode="before")
    @classmethod
    def _apply_profile(cls, data: Any) -> Any:
        """Complete les quantites absentes a partir du profil demande."""
        if not isinstance(data, dict):
            return data
        values = RESOURCE_PROFILES.get(str(data.get("profile", ResourceProfile.SMALL)))
        if values is None:  # profil « custom » ou inconnu : rien a completer.
            return data
        data = dict(data)
        data.setdefault("cpu_request", values.cpu_request)
        data.setdefault("memory_request", values.memory_request)
        data.setdefault("cpu_limit", values.cpu_limit)
        data.setdefault("memory_limit", values.memory_limit)
        return data

    def scaled(self, factor: int) -> ResourcesSpec:
        """Renvoie une copie dont les quatre quantites sont multipliees."""
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
    """Contexte de securite du pod et du conteneur.

    `strict` a vrai applique le durcissement recommande : utilisateur non root,
    systeme de fichiers racine en lecture seule, toutes les capabilities
    retirees, profil seccomp par defaut. Chaque champ reste surchargeable.
    """

    #: Applique le durcissement recommande ; faux assouplit les defauts.
    strict: bool = True

    #: Interdit au conteneur de demarrer en tant que root.
    run_as_non_root: bool = True

    #: UID du processus du conteneur (>= 1, donc jamais root).
    run_as_user: int = Field(default=10001, ge=1)

    #: GID du processus du conteneur (>= 1).
    run_as_group: int = Field(default=10001, ge=1)

    #: GID proprietaire des volumes montes (>= 1).
    fs_group: int = Field(default=10001, ge=1)

    #: Monte le systeme de fichiers racine en lecture seule.
    read_only_root_filesystem: bool = True

    #: Interdit a un processus d'acquerir plus de privileges que son parent.
    allow_privilege_escalation: bool = False

    #: Capabilities Linux retirees ; `["ALL"]` est le durcissement recommande.
    drop_capabilities: list[str] = Field(default_factory=lambda: ["ALL"])

    #: Profil seccomp : `RuntimeDefault` ou `Unconfined`.
    seccomp_profile: str = "RuntimeDefault"

    @model_validator(mode="before")
    @classmethod
    def _relax_when_not_strict(cls, data: Any) -> Any:
        """Assouplit les valeurs par defaut quand le durcissement est refuse."""
        if not isinstance(data, dict) or data.get("strict", True):
            return data
        data = dict(data)
        data.setdefault("run_as_non_root", False)
        data.setdefault("read_only_root_filesystem", False)
        data.setdefault("drop_capabilities", [])
        return data


class ComponentServiceSpec(ForgeModel):
    """Service exposant la charge de travail.

    Nomme `ComponentServiceSpec` et non `ServiceSpec` : le coeur emploie deja ce
    dernier nom pour le bloc partage `service:`, et `derive.py` importera les
    deux. Le nom de la cle dans `forge.yml` reste `service`.
    """

    #: Type de Service : ClusterIP | NodePort | LoadBalancer.
    type: ServiceType = ServiceType.CLUSTER_IP

    #: Port expose par le Service (1-65535) ; distinct de `container_port`.
    port: Port = 80

    #: Un StatefulSet exige un Service headless (`clusterIP: None`) pour donner
    #: une identite reseau stable a chaque pod. Positionne automatiquement.
    headless: bool = False

    #: Port du noeud, avec un Service de type NodePort (30000-32767 usuel).
    node_port: Port | None = None

    #: Annotations posees sur le Service (equilibreur de charge, par exemple).
    annotations: dict[str, str] = Field(default_factory=dict)


class ComponentSpec(ForgeModel):
    """Une charge de travail nommee et l'ensemble de ses ressources annexes."""

    #: Nom du composant : label DNS, prefixe de toutes ses ressources.
    name: DnsLabel = Field(max_length=MAX_COMPONENT_NAME_LENGTH)

    #: Type de charge de travail : deployment | statefulset | cronjob.
    kind: ComponentKind = ComponentKind.DEPLOYMENT

    #: Ressources annexes generees autour de la charge de travail : service,
    #: ingress, configmap, secret, hpa, pdb, serviceaccount, networkpolicy.
    #: La liste est dedoublonnee et remise dans l'ordre canonique d'`AddonKind`,
    #: afin que deux specs equivalentes produisent le meme projet.
    addons: list[AddonKind] = Field(
        default_factory=lambda: [AddonKind.SERVICE, AddonKind.CONFIGMAP]
    )

    #: Surcharge du depot d'image, quand un composant n'emploie pas l'image
    #: principale du projet (rare : un worker partage en general l'image).
    image_repository: ImageRepository | None = None

    #: Commande du conteneur : c'est ainsi qu'un worker se distingue d'une API
    #: tout en partageant la meme image. Vide = entrypoint de l'image.
    command: list[str] = Field(default_factory=list)

    #: Arguments passes a la commande du conteneur.
    args: list[str] = Field(default_factory=list)

    #: Nombre de replicas par defaut (>= 0) ; surcharge par environnement.
    replicas: int = Field(default=1, ge=0)

    #: Port ecoute par le conteneur (1-65535). Distinct de `service.port` :
    #: le cas nominal Helm expose un Service sur 80 vers un conteneur sur 8080
    #: (arbitrage H5, les trois champs de port sont conserves).
    container_port: Port = 8080

    #: Nom du port du conteneur, repris par le Service et par les sondes.
    #:
    #: Kubernetes impose ici le format IANA_SVC_NAME : au plus 15 caracteres,
    #: minuscules, chiffres et tirets, au moins une lettre, ni tiret initial ou
    #: final, ni deux tirets consecutifs. Aucun validateur ne l'attrape — un nom
    #: de 29 caracteres passe `helm lint`, `helm template` **et**
    #: `kubeconform -strict`, et n'est refuse qu'a l'application. D'ou cette
    #: contrainte au modele : c'est le seul endroit qui puisse la porter.
    port_name: PortName = "http"

    #: Sondes de sante du conteneur principal.
    probes: ProbesSpec = Field(default_factory=ProbesSpec)

    #: Requests et limits du conteneur principal.
    resources: ResourcesSpec = Field(default_factory=ResourcesSpec)

    #: Contexte de securite du pod et du conteneur.
    security: SecuritySpec = Field(default_factory=SecuritySpec)

    #: Service exposant la charge de travail (addon `service`).
    service: ComponentServiceSpec = Field(default_factory=ComponentServiceSpec)

    #: Exposition HTTP (addon `ingress`, qui exige l'addon `service`).
    ingress: IngressSpec = Field(default_factory=IngressSpec)

    #: Volume persistant attache a la charge de travail.
    persistence: PersistenceSpec = Field(default_factory=PersistenceSpec)

    #: Autoscaling horizontal (addon `hpa`).
    hpa: HpaSpec = Field(default_factory=HpaSpec)

    #: Budget d'interruption volontaire (addon `pdb`).
    pdb: PdbSpec = Field(default_factory=PdbSpec)

    #: Restriction du trafic reseau (addon `networkpolicy`).
    networkpolicy: NetworkPolicySpec = Field(default_factory=NetworkPolicySpec)

    #: Droits du ServiceAccount du composant dans son namespace.
    rbac: RbacSpec = Field(default_factory=RbacSpec)

    #: Configuration non sensible (addon `configmap`).
    config: ConfigSpec = Field(default_factory=ConfigSpec)

    #: Cles de secret attendues (addon `secret`) ; jamais de valeur.
    secret: ComponentSecretSpec = Field(default_factory=ComponentSecretSpec)

    #: Parametres du CronJob ; n'a de sens que pour `kind: cronjob`, ou il est
    #: renseigne automatiquement quand il est absent.
    cron: CronSpec | None = None

    # ------------------------------------------------------------------
    # Validation croisee
    # ------------------------------------------------------------------

    @field_validator("addons")
    @classmethod
    def _normalise_addons(cls, value: list[AddonKind]) -> list[AddonKind]:
        """Dedoublonne les addons et les remet dans l'ordre canonique.

        Le plan de fichiers devient ainsi independant de l'ordre de saisie.
        """
        order = list(AddonKind)
        return sorted(set(value), key=order.index)

    @model_validator(mode="after")
    def _check_coherence(self) -> ComponentSpec:
        """Verifie la coherence de l'ensemble et applique les defauts imposes."""
        if AddonKind.INGRESS in self.addons and AddonKind.SERVICE not in self.addons:
            raise ValueError(
                f"composant {self.name!r} : l'addon ingress exige l'addon service"
            )

        if self.kind is ComponentKind.CRONJOB:
            forbidden = sorted(
                addon.value for addon in self.addons if addon in CRONJOB_FORBIDDEN_ADDONS
            )
            if forbidden:
                raise ValueError(
                    f"composant {self.name!r} de type cronjob : addons "
                    f"incompatibles {forbidden}"
                )
            if self.cron is None:
                self.cron = CronSpec()
        elif self.cron is not None:
            raise ValueError(
                f"composant {self.name!r} : le bloc cron n'a de sens que pour un "
                "composant de type cronjob"
            )

        if self.kind is ComponentKind.STATEFULSET:
            # Un StatefulSet a besoin d'un Service headless et, dans la quasi
            # totalite des cas, d'un volume persistant.
            self.service.headless = True
            self.persistence.enabled = True
            if AddonKind.SERVICE not in self.addons:
                # Forcer `headless` ne suffit pas : sans l'addon, le Service
                # n'est pas genere du tout et `serviceName` designe une
                # ressource inexistante. Le StatefulSet perd alors l'identite
                # reseau stable qui est sa seule raison d'etre — et aucun
                # validateur ne peut le voir, le manifeste restant valide.
                ordre = list(AddonKind)
                self.addons = sorted(
                    {*self.addons, AddonKind.SERVICE}, key=ordre.index
                )

        return self

    # ------------------------------------------------------------------
    # Acces pratiques, employes par derive.py et les gabarits
    # ------------------------------------------------------------------

    def has(self, addon: AddonKind) -> bool:
        """Indique si un addon est selectionne pour ce composant."""
        return addon in self.addons

    @property
    def is_workload(self) -> bool:
        """Vrai pour un Deployment ou un StatefulSet, faux pour un CronJob."""
        return self.kind in (ComponentKind.DEPLOYMENT, ComponentKind.STATEFULSET)
