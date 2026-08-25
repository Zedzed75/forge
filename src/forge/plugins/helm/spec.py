"""Section `helm:` de forge.yml.

Portage de `helm_forge.models.spec` (MIGRATION.md §4). L'identite du service —
nom, description, mainteneur, liste et ordre des environnements — est montee
dans le bloc partage `service:` du coeur ; ce qui reste ici decrit **comment le
service est empaquete pour Kubernetes** : version du chart, version cible du
cluster, disposition, namespaces, image, composants, secrets, annexes.

Trois ecarts structurels avec le legacy, tous arbitres (MIGRATION.md §4) :

* `helm.environments` est un **dict cle par nom d'environnement** (H4), sur le
  modele de `ansible.hosts.<env>` : le nom et l'ordre vivent dans
  `service.environments`. Consequence directe : le controle « cle
  d'environnement inconnue » ne peut plus etre fait ici — il appartient au
  controle croise du plugin, comme `ansible.answers.cross_check` ;
* `layout: umbrella` (H3), `extras.helmfile`, `extras.ci` et le bloc
  `servicemonitor` (H7, H8) ne sont pas portes ; `extra="forbid"` les refusera
  proprement ;
* `validate_assignment=True` n'est pas reintroduit (H11) : ce modele est
  **immuable apres validation**, et ne derive plus rien lui-meme.

Contrat de derivation — ce que `derive.py` devra assurer
========================================================

Le legacy calculait ces valeurs dans ses validateurs. Ce sont elles qui rendent
un `forge.yml` minimal equivalent a un `forge.yml` complet ; MIGRATION.md §4
demande explicitement de les conserver. Ce modele expose tout ce qu'elles
exigent, et rien de plus n'est necessaire.

1. **Namespace de chaque environnement**, si `helm.environments.<env>.namespace`
   est absent, selon `namespace_strategy` :
   `single` -> `service.name` ; `per_env` -> `<service.name>-<env>` ;
   `custom` -> erreur, un namespace explicite est exige pour chaque
   environnement de `service.environments`.

2. **Profil applique a chaque environnement** — `profiles.profile_for(nom,
   production=env.production)` (arbitrage H2) :
   `production: true` force le profil `prod` ; sinon la reconnaissance par le
   nom s'applique (`prod`, `prd`, `production`, `stage`, `stg`, `develop`...).
   Le controle croise emet un `Issue` de niveau *warning* quand les deux sources
   divergent, plutot que de trancher en silence. Le profil renseigne, pour
   chaque environnement et chaque composant, les valeurs laissees vides :
   `log_level`, `replicas` (charges de travail seulement), `hpa_enabled` (si
   l'addon `hpa` est present), `pdb_enabled` (si l'addon `pdb` est present), et
   `resources = component.resources.scaled(profile.resource_multiplier)` quand
   le multiplicateur n'est pas 1. Une entree de surcharge est creee pour
   **chaque** composant de **chaque** environnement, meme vide dans la spec.

3. **Hote d'Ingress** de chaque composant portant l'addon `ingress`, si
   `ingress_host` est absent (arbitrages H1 et H2) :
   le prefixe est `service.name` pour le **premier** composant expose dans
   l'ordre de `components`, et `<composant>-<service.name>` pour les suivants,
   afin que deux composants exposes ne se disputent pas le meme hote ;
   puis, **si `service.environments[].domain` est renseigne**, l'hote est
   `<prefixe>.<domaine-de-l-env>`, **sans** reinserer le nom d'environnement
   (le domaine le porte deja) ; **sinon**, repli legacy :
   `<prefixe>[.<env> si profile.host_includes_env].<component.ingress.base_domain>`.

4. **Tag de l'image**, selon `image.strategy` :
   `appVersion` -> tag vide dans les values, repli sur `.Chart.AppVersion`
   (soit `helm.app_version`) ; `per_env` -> le tag de
   `helm.environments.<env>.components.<nom>.image_tag`, a laisser vide quand il
   n'est pas fourni ; `fixed` -> `image.tag`, dont le modele garantit deja la
   presence.

Le controle croise du plugin (hors de ce module) doit par ailleurs verifier :
les cles de `helm.environments` absentes de `service.environments` (H4) ; les
plafonds `MAX_SERVICE_NAME_LENGTH`, `MAX_ENVIRONMENT_NAME_LENGTH` et
`MAX_DESCRIPTION_LENGTH`, ainsi que le format de `service.owner_email` (H6) ; la
completude des namespaces en strategie `custom` ; la divergence H2.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.helm.components import ComponentSpec, ResourcesSpec
from forge.plugins.helm.constants import (
    DEFAULT_KUBERNETES_VERSION,
    KUBERNETES_VERSIONS,
)
from forge.plugins.helm.enums import (
    AddonKind,
    ImagePullPolicy,
    Layout,
    NamespaceStrategy,
    SecretStrategy,
    TagStrategy,
)
from forge.plugins.helm.names import ImageRepository
from forge.spec.names import require_unique
from forge.spec.types import DnsLabel, ForgeModel, SemVer, Subdomain


class KubernetesTarget(ForgeModel):
    """Version de Kubernetes ciblee par le chart genere."""

    #: Version mineure ciblee ; doit appartenir a `KUBERNETES_VERSIONS`.
    version: str = DEFAULT_KUBERNETES_VERSION

    @field_validator("version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value not in KUBERNETES_VERSIONS:
            supported = ", ".join(KUBERNETES_VERSIONS)
            raise ValueError(f"version Kubernetes {value!r} non supportee : {supported}")
        return value

    @property
    def kube_version_constraint(self) -> str:
        """Contrainte a ecrire dans le champ `kubeVersion` de `Chart.yaml`.

        Le suffixe `-0` autorise les pre-versions, faute de quoi Helm rejette un
        cluster dont la version porte un suffixe (`v1.36.0-eks-1`).
        """
        return f">={self.version}.0-0"

    @property
    def full_version(self) -> str:
        """Version complete passee a kubeconform pour choisir ses schemas."""
        return f"{self.version}.0"


class ImageSpec(ForgeModel):
    """Image de conteneur employee par defaut par tous les composants."""

    #: Registre OCI (`docker.io`, `ghcr.io`, `registry.gitlab.com`).
    registry: Subdomain = "docker.io"

    #: Depot dans le registre, sans tag (`acme/shop`).
    repository: ImageRepository = "app"

    #: Origine du tag : appVersion (repli sur `.Chart.AppVersion`) | per_env
    #: (un tag par environnement) | fixed (le tag ci-dessous).
    strategy: TagStrategy = TagStrategy.APP_VERSION

    #: Tag fige ; obligatoire avec la strategie `fixed`, interdit sinon.
    tag: str = ""

    #: Politique de recuperation : Always | IfNotPresent | Never.
    pull_policy: ImagePullPolicy = ImagePullPolicy.IF_NOT_PRESENT

    #: Nom du Secret de type dockerconfigjson pour un registre prive ; absent =
    #: registre public.
    pull_secret_name: str | None = None

    @model_validator(mode="after")
    def _check_tag(self) -> ImageSpec:
        if self.strategy is TagStrategy.FIXED and not self.tag:
            raise ValueError(
                'image.tag est obligatoire avec la strategie de tag "fixed"'
            )
        if self.strategy is not TagStrategy.FIXED and self.tag:
            raise ValueError(
                "image.tag ne doit etre renseigne qu'avec la strategie "
                '"fixed" ; utilisez la surcharge par environnement sinon'
            )
        return self


class SecretSpec(ForgeModel):
    """Strategie de gestion des secrets du projet.

    Aucune strategie ne produit jamais de valeur secrete reelle : le generateur
    ne fabrique que des emplacements a remplir hors du depot.
    """

    #: Mode de gestion : placeholder | external-secrets | sealed-secrets | none.
    strategy: SecretStrategy = SecretStrategy.PLACEHOLDER

    #: Nom du SecretStore ou ClusterSecretStore, pour external-secrets.
    store_name: str = "default"

    #: Intervalle de rafraichissement, pour external-secrets (`1h`, `15m`).
    refresh_interval: str = "1h"


class ExtrasSpec(ForgeModel):
    """Fichiers annexes generes a cote du chart.

    `helmfile` et `ci` du legacy ne sont pas portes (arbitrages H7 et H8) :
    aucun gabarit ne les rendait, et la CI est de niveau depot (decision Q6).
    """

    #: Genere un Makefile de raccourcis (lint, template, upgrade).
    makefile: bool = True

    #: Genere les tests Helm (`templates/tests/`), lances par `helm test`.
    helm_tests: bool = True


class EnvironmentOverride(ForgeModel):
    """Ecarts d'un composant pour un environnement donne.

    Seules les valeurs non nulles sont ecrites dans `values-<env>.yaml` : un
    fichier d'environnement ne contient que des differences, jamais une copie
    complete de `values.yaml`. Une valeur absente est calculee par `derive.py` a
    partir du profil de l'environnement.
    """

    #: Nombre de replicas dans cet environnement ; absent = valeur du profil.
    replicas: int | None = Field(default=None, ge=0)

    #: Active l'autoscaling ici ; absent = valeur du profil.
    hpa_enabled: bool | None = None

    #: Active le budget d'interruption ici ; absent = valeur du profil.
    pdb_enabled: bool | None = None

    #: Hote d'Ingress force ; absent = derive (H1) du domaine de
    #: l'environnement, ou de `ingress.base_domain`.
    ingress_host: Subdomain | None = None

    #: Requests/limits forces ici ; absent = ceux du composant, multiplies par
    #: `profile.resource_multiplier`.
    resources: ResourcesSpec | None = None

    #: Tag d'image propre a l'environnement, avec la strategie `per_env`.
    image_tag: str | None = None


class EnvironmentSpec(ForgeModel):
    """Surcharges d'un environnement, indexees par son nom dans `helm.environments`.

    Le nom et l'ordre des environnements vivent dans `service.environments`
    (arbitrage H4) : ce modele ne porte donc que des surcharges, et un
    environnement absent de ce dict est parfaitement valide — il prend tout de
    son profil.
    """

    #: Namespace de deploiement ; absent = derive de `namespace_strategy`.
    namespace: DnsLabel | None = None

    #: Niveau de journalisation ; absent = valeur du profil (`debug` en dev).
    log_level: str | None = None

    #: Surcharges par nom de composant ; les noms doivent exister dans
    #: `helm.components`.
    components: dict[str, EnvironmentOverride] = Field(default_factory=dict)

    #: Valeurs libres injectees telles quelles dans `values-<env>.yaml`.
    extra_values: dict[str, Any] = Field(default_factory=dict)


class HelmSpec(ForgeModel):
    """Section `helm:` complete."""

    #: Version du chart lui-meme, au sens SemVer exige par Helm.
    chart_version: SemVer = "0.1.0"

    #: Version de l'application empaquetee, reprise dans `appVersion` et servant
    #: de tag d'image avec la strategie `appVersion`.
    app_version: str = Field(default="1.0.0", min_length=1)

    #: Version de Kubernetes ciblee : contrainte `kubeVersion` et schemas
    #: employes par kubeconform.
    kubernetes: KubernetesTarget = Field(default_factory=KubernetesTarget)

    #: Disposition du projet ; seule `single` est generee (arbitrage H3).
    layout: Layout = Layout.SINGLE

    #: Derivation du namespace : single | per_env | custom.
    namespace_strategy: NamespaceStrategy = NamespaceStrategy.PER_ENV

    #: Faux par defaut : le namespace est presque toujours gere en amont, et le
    #: creer dans le chart le rendrait supprimable par `helm uninstall`.
    create_namespace: bool = False

    #: Image de conteneur employee par defaut par tous les composants.
    image: ImageSpec = Field(default_factory=ImageSpec)

    #: Charges de travail generees ; au moins une. L'ordre est significatif :
    #: le premier composant expose porte l'hote d'Ingress nu (cf. derivation 3).
    components: list[ComponentSpec] = Field(min_length=1)

    #: Strategie de gestion des secrets ; jamais de valeur secrete generee.
    secrets: SecretSpec = Field(default_factory=SecretSpec)

    #: Fichiers annexes generes a cote du chart.
    extras: ExtrasSpec = Field(default_factory=ExtrasSpec)

    #: Surcharges par environnement, cle par nom (arbitrage H4). Les cles
    #: doivent figurer dans `service.environments` — verifie par le controle
    #: croise du plugin, seul a voir le bloc partage.
    environments: dict[str, EnvironmentSpec] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation croisee
    # ------------------------------------------------------------------

    @field_validator("components")
    @classmethod
    def _unique_component_names(cls, value: list[ComponentSpec]) -> list[ComponentSpec]:
        require_unique((composant.name for composant in value), "noms de composants")
        return value

    @model_validator(mode="after")
    def _check_environment_overrides(self) -> HelmSpec:
        """Verifie que les surcharges citent des composants declares.

        Le pendant de ce controle — les cles d'environnement inconnues — ne peut
        pas etre fait ici : `HelmSpec` ne voit pas `service.environments`.
        """
        connus = {composant.name for composant in self.components}
        for nom, env in self.environments.items():
            inconnus = sorted(set(env.components) - connus)
            if inconnus:
                raise ValueError(
                    f"environnement {nom!r} : surcharges pour des composants "
                    f"inconnus {inconnus}"
                )
        return self

    @model_validator(mode="after")
    def _check_custom_namespaces(self) -> HelmSpec:
        """Exige un namespace explicite pour chaque environnement declare.

        La strategie `custom` ne derive rien : elle attend un namespace ecrit a
        la main. Ce controle couvre les environnements presents dans
        `helm.environments` ; celui des environnements qui n'y figurent pas du
        tout appartient au controle croise, qui seul connait la liste complete.
        """
        if self.namespace_strategy is not NamespaceStrategy.CUSTOM:
            return self
        for nom, env in self.environments.items():
            if env.namespace is None:
                raise ValueError(
                    f"environnement {nom!r} : la strategie de namespace "
                    '"custom" exige un namespace explicite'
                )
        return self

    # ------------------------------------------------------------------
    # Acces pratiques
    # ------------------------------------------------------------------

    def component(self, name: str) -> ComponentSpec:
        """Retourne le composant `name`, ou leve `KeyError`."""
        for composant in self.components:
            if composant.name == name:
                return composant
        raise KeyError(f"composant inconnu : {name!r}")

    @property
    def component_names(self) -> tuple[str, ...]:
        """Noms des composants, dans l'ordre de declaration."""
        return tuple(composant.name for composant in self.components)

    def overrides(self, environment: str) -> EnvironmentSpec:
        """Surcharges de l'environnement `environment`, vides s'il n'en a pas.

        Un environnement declare dans `service.environments` mais absent de
        `helm.environments` est valide : il prend tout de son profil.
        """
        return self.environments.get(environment) or EnvironmentSpec()

    def uses_addon(self, addon: AddonKind) -> bool:
        """Indique si au moins un composant emploie l'addon donne."""
        return any(composant.has(addon) for composant in self.components)

    def exposed_components(self) -> tuple[str, ...]:
        """Noms des composants portant l'addon `ingress`, dans l'ordre declare.

        Le premier de cette liste porte l'hote nu (`<service>.<domaine>`) ; les
        suivants sont prefixes de leur propre nom (cf. derivation 3).
        """
        return tuple(
            composant.name
            for composant in self.components
            if composant.has(AddonKind.INGRESS)
        )
