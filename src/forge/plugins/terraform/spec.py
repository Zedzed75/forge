"""Section `terraform:` de forge.yml.

Premier sous-modele du projet qui ne porte aucun heritage : il n'y avait pas
d'outil legacy Terraform a convertir. Sa forme suit celle des deux autres
domaines — un bloc statique, un dict de surcharges cle par environnement, un
bloc `extras` — pour qu'un `forge.yml` reste lisible d'une section a l'autre.

Ce que ce modele decrit : **le socle sur lequel les autres domaines se
posent**. Le namespace, son budget, l'identite qui y deploie, ce qui y entre et
en sort. Pas la charge applicative : c'est le domaine Helm qui la deploie, dans
le namespace que celui-ci cree.

Ce que ce modele ne peut pas verifier, et qui appartient au controle croise
(`answers.cross_check`) : les cles de `environments` absentes de
`service.environments`, la completude des namespaces en strategie `custom`, et
les plafonds qui portent sur le bloc partage `service:`.

**Aucune valeur secrete n'a sa place ici.** Les cles de backend reconnues comme
secretes sont refusees par le modele, et le mot de passe de registre est une
variable Terraform sans defaut, absente des fichiers generes.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.terraform.catalog.registry import family_names
from forge.plugins.terraform.constants import (
    MAX_NAMESPACE_LENGTH,
    REQUIRED_BACKEND_KEYS,
    SECRET_BACKEND_KEYS,
    VERSION_CONSTRAINT_RE,
)
from forge.plugins.terraform.enums import (
    BackendKind,
    KubernetesAuth,
    NamespaceStrategy,
    ResourceFamily,
)
from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, Subdomain


class BackendSpec(ForgeModel):
    """Ou l'etat Terraform est conserve, et comment on l'y adresse."""

    #: Type de backend.
    kind: BackendKind = BackendKind.LOCAL

    #: Cles de configuration du backend, ecrites telles quelles dans
    #: `backend.tf`. Les cles secretes sont refusees : elles se fournissent par
    #: `-backend-config` ou par variable d'environnement.
    config: dict[str, str] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def _no_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        interdites = sorted(SECRET_BACKEND_KEYS & set(value))
        if interdites:
            raise ValueError(
                "cles de backend secretes refusees : "
                f"{', '.join(interdites)}. Fournissez-les a l'execution "
                "(terraform init -backend-config=...) ou par variable "
                "d'environnement ; un fichier genere ne porte jamais de secret."
            )
        return value

    @model_validator(mode="after")
    def _required_keys(self) -> BackendSpec:
        manquantes = [
            cle for cle in REQUIRED_BACKEND_KEYS[self.kind.value] if cle not in self.config
        ]
        if manquantes:
            raise ValueError(
                f"backend '{self.kind.value}' : cles obligatoires absentes de "
                f"terraform.backend.config : {', '.join(manquantes)}."
            )
        return self


class KubernetesAccessSpec(ForgeModel):
    """Comment le provider Kubernetes joint le cluster."""

    #: Mode d'authentification.
    auth: KubernetesAuth = KubernetesAuth.KUBECONFIG

    #: Chemin du kubeconfig, en mode `kubeconfig`. Devient la valeur par defaut
    #: de la variable `kube_config_path` de chaque racine d'environnement.
    config_path: str = "~/.kube/config"

    #: Nomme un contexte kubeconfig par environnement. Laisser a `true` : sans
    #: contexte explicite, le provider emploie le contexte courant de la
    #: machine, et rien ne dit vers quel cluster l'application est partie.
    context_per_environment: bool = True


class QuotaSpec(ForgeModel):
    """Budget d'un environnement. Toute cle omise garde la valeur par defaut."""

    #: Plafond de CPU demandable (ex. "4", "500m").
    cpu: str | None = None

    #: Plafond de memoire demandable, suffixe obligatoire (ex. "8Gi").
    memory: str | None = None

    #: Nombre maximal de pods simultanes.
    pods: int | None = Field(default=None, gt=0)


class TerraformEnvironmentSpec(ForgeModel):
    """Surcharges d'un environnement. Cle par nom d'environnement."""

    #: Namespace explicite. Obligatoire en strategie `custom`, facultatif sinon.
    namespace: DnsLabel | None = None

    #: Contexte kubeconfig vise par cet environnement.
    kube_context: str | None = None

    #: Budget de cet environnement.
    quota: QuotaSpec | None = None

    #: Labels ajoutes aux ressources de cet environnement seulement.
    labels: dict[str, str] = Field(default_factory=dict)

    #: Cles de backend propres a cet environnement — typiquement `key` ou
    #: `prefix`, pour que deux environnements n'ecrivent pas le meme etat.
    backend_config: dict[str, str] = Field(default_factory=dict)

    #: Noms DNS couverts par le certificat auto-signe de cet environnement.
    tls_dns_names: list[Subdomain] = Field(default_factory=list)

    @field_validator("backend_config")
    @classmethod
    def _no_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        interdites = sorted(SECRET_BACKEND_KEYS & set(value))
        if interdites:
            raise ValueError(
                f"cles de backend secretes refusees : {', '.join(interdites)}."
            )
        return value


class TerraformExtras(ForgeModel):
    """Fichiers annexes du projet genere."""

    #: Makefile de raccourcis (`make init ENV=prod`, `make plan ENV=prod`).
    makefile: bool = True

    #: Fichier `.tflint.hcl` activant le jeu de regles Terraform de tflint.
    tflint_config: bool = True


class TerraformSpec(ForgeModel):
    """Section `terraform:` : le socle d'infrastructure du service."""

    #: Contrainte `required_version`. Bornez toujours la version majeure.
    terraform_version: str = "~> 1.9"

    #: Ou l'etat est conserve.
    backend: BackendSpec = Field(default_factory=BackendSpec)

    #: Comment joindre le cluster.
    kubernetes: KubernetesAccessSpec = Field(default_factory=KubernetesAccessSpec)

    #: Comment le nom du namespace est derive de l'environnement.
    namespace_strategy: NamespaceStrategy = NamespaceStrategy.PER_ENV

    #: Familles de ressources retenues. L'ordre d'ecriture n'a pas d'importance :
    #: le catalogue les remet dans l'ordre canonique.
    resources: list[ResourceFamily] = Field(
        default_factory=lambda: [ResourceFamily.NAMESPACE], min_length=1
    )

    #: Surcharges par environnement. Un environnement absent prend les valeurs
    #: derivees ; les noms sont valides par le controle croise du plugin.
    environments: dict[str, TerraformEnvironmentSpec] = Field(default_factory=dict)

    #: Fichiers annexes.
    extras: TerraformExtras = Field(default_factory=TerraformExtras)

    @field_validator("terraform_version")
    @classmethod
    def _version_constraint(cls, value: str) -> str:
        if not VERSION_CONSTRAINT_RE.match(value):
            raise ValueError(
                f"terraform_version '{value}' n'est pas une contrainte de "
                "version Terraform (ex. '~> 1.9', '>= 1.5, < 2.0'). Une version "
                "nue figerait le projet sur un correctif precis."
            )
        return value

    @field_validator("resources")
    @classmethod
    def _unique_resources(cls, value: list[ResourceFamily]) -> list[ResourceFamily]:
        require_unique((famille.value for famille in value), "familles de ressources")
        return value

    @model_validator(mode="after")
    def _known_families(self) -> TerraformSpec:
        """Garde-fou : le catalogue et l'enumeration doivent rester d'accord."""
        connues = set(family_names())
        inconnues = sorted(f.value for f in self.resources if f.value not in connues)
        if inconnues:  # pragma: no cover - defaut de programmation du plugin
            raise ValueError(
                f"familles absentes du catalogue : {', '.join(inconnues)}."
            )
        return self

    @model_validator(mode="after")
    def _custom_namespaces_declared(self) -> TerraformSpec:
        """En strategie `custom`, toute surcharge declaree doit nommer son namespace.

        Ce controle ne voit que les environnements **presents** dans
        `terraform.environments` ; ceux qui n'y figurent pas du tout sont
        rattrapes par le controle croise, seul a connaitre
        `service.environments`.
        """
        if self.namespace_strategy is not NamespaceStrategy.CUSTOM:
            return self
        muets = sorted(
            nom for nom, surcharge in self.environments.items() if surcharge.namespace is None
        )
        if muets:
            raise ValueError(
                'la strategie de namespace "custom" exige un namespace explicite ; '
                f"absent pour : {', '.join(muets)}."
            )
        return self

    @model_validator(mode="after")
    def _namespace_lengths(self) -> TerraformSpec:
        trop_longs = sorted(
            f"{nom} ({surcharge.namespace})"
            for nom, surcharge in self.environments.items()
            if surcharge.namespace and len(surcharge.namespace) > MAX_NAMESPACE_LENGTH
        )
        if trop_longs:
            raise ValueError(
                f"un nom de namespace fait au plus {MAX_NAMESPACE_LENGTH} "
                f"caracteres ; trop long pour : {', '.join(trop_longs)}."
            )
        return self

    # -- lecture ------------------------------------------------------------

    def overrides(self, environment: str) -> TerraformEnvironmentSpec:
        """Surcharges de `environment`, vides s'il n'en a pas."""
        return self.environments.get(environment) or TerraformEnvironmentSpec()

    def uses(self, family: ResourceFamily) -> bool:
        """Indique si la famille est retenue."""
        return family in self.resources

    def family_names(self) -> tuple[str, ...]:
        """Noms des familles retenues, tels qu'ecrits dans la specification."""
        return tuple(famille.value for famille in self.resources)

    def namespace_for(self, service_name: str, environment: str) -> str:
        """Namespace de `environment`, derive selon la strategie.

        En strategie `custom`, un environnement sans surcharge retomberait ici
        sans reponse : le controle croise l'a deja refuse, et le repli sur le
        nom derive garde la fonction totale plutot que de lever depuis un
        chemin de rendu.
        """
        explicite = self.overrides(environment).namespace
        if explicite:
            return explicite
        if self.namespace_strategy is NamespaceStrategy.SAME:
            return service_name
        return f"{service_name}-{environment}"

    def model_dump_stable(self) -> dict[str, Any]:  # pragma: no cover - confort de debogage
        """Vue serialisable du modele, pour inspection manuelle."""
        return self.model_dump(mode="json")
