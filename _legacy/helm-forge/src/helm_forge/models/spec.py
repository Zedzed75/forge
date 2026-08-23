"""Modèle racine : ``ProjectSpec`` décrit intégralement un projet à générer.

Une spécification est la seule entrée du générateur. Deux spécifications
identiques produisent deux projets identiques, octet pour octet ; c'est
l'exigence centrale posée par ``CLAUDE.md``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..constants import (
    DEFAULT_KUBERNETES_VERSION,
    KUBERNETES_VERSIONS,
    MAX_APP_NAME_LENGTH,
    MAX_ENVIRONMENT_NAME_LENGTH,
    SPEC_SCHEMA_VERSION,
)
from .base import ForgeModel
from .component import ComponentSpec, ResourcesSpec
from .enums import (
    AddonKind,
    CIProvider,
    ImagePullPolicy,
    Layout,
    NamespaceStrategy,
    SecretStrategy,
    TagStrategy,
)
from .profiles import profile_for_environment
from .validators import DnsLabel, ImageRepository, SemVer, Subdomain

#: Validation d'adresse électronique volontairement simple : on refuse les
#: saisies manifestement fausses sans ajouter la dépendance email-validator.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AppMeta(ForgeModel):
    """Identité de l'application et métadonnées du chart."""

    name: DnsLabel = Field(max_length=MAX_APP_NAME_LENGTH)
    description: str = Field(min_length=1, max_length=200)
    #: Version du chart lui-même, au sens SemVer exigé par Helm.
    chart_version: SemVer = "0.1.0"
    #: Version de l'application empaquetée, reprise dans appVersion.
    app_version: str = Field(default="1.0.0", min_length=1)
    maintainer_name: str = Field(default="unknown", min_length=1)
    maintainer_email: str = "unknown@example.com"

    @field_validator("maintainer_email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        if not _EMAIL.match(value):
            raise ValueError(f"{value!r} n'est pas une adresse électronique valide")
        return value


class KubernetesTarget(ForgeModel):
    """Version de Kubernetes ciblée par le chart généré."""

    version: str = DEFAULT_KUBERNETES_VERSION

    @field_validator("version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value not in KUBERNETES_VERSIONS:
            supported = ", ".join(KUBERNETES_VERSIONS)
            raise ValueError(
                f"version Kubernetes {value!r} non supportée : {supported}"
            )
        return value

    @property
    def kube_version_constraint(self) -> str:
        """Contrainte à écrire dans le champ kubeVersion de Chart.yaml.

        Le suffixe ``-0`` autorise les pré-versions, faute de quoi Helm rejette
        un cluster dont la version porte un suffixe (``v1.36.0-eks-1``).
        """
        return f">={self.version}.0-0"

    @property
    def full_version(self) -> str:
        """Version complète passée à kubeconform pour choisir ses schémas."""
        return f"{self.version}.0"


class ImageSpec(ForgeModel):
    """Image de conteneur utilisée par défaut par tous les composants."""

    registry: Subdomain = "docker.io"
    repository: ImageRepository = "app"
    strategy: TagStrategy = TagStrategy.APP_VERSION
    #: Tag figé, obligatoire uniquement avec la stratégie ``fixed``.
    tag: str = ""
    pull_policy: ImagePullPolicy = ImagePullPolicy.IF_NOT_PRESENT
    pull_secret_name: str | None = None

    @model_validator(mode="after")
    def _check_tag(self) -> ImageSpec:
        if self.strategy is TagStrategy.FIXED and not self.tag:
            raise ValueError(
                'image.tag est obligatoire avec la stratégie de tag "fixed"'
            )
        if self.strategy is not TagStrategy.FIXED and self.tag:
            raise ValueError(
                "image.tag ne doit être renseigné qu'avec la stratégie "
                '"fixed" ; utilisez la surcharge par environnement sinon'
            )
        return self


class SecretSpec(ForgeModel):
    """Stratégie de gestion des secrets du projet.

    Aucune stratégie ne produit jamais de valeur secrète réelle : le générateur
    ne fabrique que des emplacements à remplir hors du dépôt.
    """

    strategy: SecretStrategy = SecretStrategy.PLACEHOLDER
    #: Nom du SecretStore ou ClusterSecretStore, pour external-secrets.
    store_name: str = "default"
    #: Intervalle de rafraîchissement, pour external-secrets.
    refresh_interval: str = "1h"


class ExtrasSpec(ForgeModel):
    """Fichiers annexes générés à côté du chart."""

    makefile: bool = True
    helmfile: bool = False
    helm_tests: bool = True
    ci: CIProvider = CIProvider.NONE


class EnvironmentOverride(ForgeModel):
    """Écarts d'un composant pour un environnement donné.

    Seules les valeurs non nulles sont écrites dans ``values-<env>.yaml`` : un
    fichier d'environnement ne contient que des différences, jamais une copie
    complète de ``values.yaml``.
    """

    replicas: int | None = Field(default=None, ge=0)
    hpa_enabled: bool | None = None
    pdb_enabled: bool | None = None
    ingress_host: Subdomain | None = None
    resources: ResourcesSpec | None = None
    #: Tag d'image propre à l'environnement, avec la stratégie ``per_env``.
    image_tag: str | None = None


class EnvironmentSpec(ForgeModel):
    """Un environnement de déploiement et ses surcharges."""

    name: DnsLabel = Field(max_length=MAX_ENVIRONMENT_NAME_LENGTH)
    #: Rempli automatiquement par ProjectSpec selon la stratégie de namespace.
    namespace: DnsLabel | None = None
    #: Rempli automatiquement à partir du profil d'environnement.
    log_level: str | None = None
    #: Surcharges par nom de composant.
    components: dict[str, EnvironmentOverride] = Field(default_factory=dict)
    #: Valeurs libres injectées telles quelles dans values-<env>.yaml.
    extra_values: dict[str, Any] = Field(default_factory=dict)


class ProjectSpec(BaseModel):
    """Description complète et rejouable d'un projet Kubernetes/Helm."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    #: Version du schéma de forge.yml, pour les migrations futures.
    schema_version: Literal[1] = SPEC_SCHEMA_VERSION

    app: AppMeta
    kubernetes: KubernetesTarget = Field(default_factory=KubernetesTarget)
    layout: Layout = Layout.SINGLE
    namespace_strategy: NamespaceStrategy = NamespaceStrategy.PER_ENV
    #: Faux par défaut : le namespace est presque toujours géré en amont, et le
    #: créer dans le chart le rendrait supprimable par helm uninstall.
    create_namespace: bool = False
    environments: list[EnvironmentSpec] = Field(min_length=1)
    image: ImageSpec = Field(default_factory=ImageSpec)
    components: list[ComponentSpec] = Field(min_length=1)
    secrets: SecretSpec = Field(default_factory=SecretSpec)
    extras: ExtrasSpec = Field(default_factory=ExtrasSpec)

    # ------------------------------------------------------------------
    # Validation croisée et dérivation des valeurs implicites
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _check_and_derive(self) -> ProjectSpec:
        self._check_unique_names()
        self._derive_namespaces()
        self._derive_environment_defaults()
        return self

    def _check_unique_names(self) -> None:
        """Refuse deux composants ou deux environnements de même nom."""
        for label, names in (
            ("composants", [c.name for c in self.components]),
            ("environnements", [e.name for e in self.environments]),
        ):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            if duplicates:
                raise ValueError(f"noms de {label} en double : {duplicates}")

        known = {c.name for c in self.components}
        for env in self.environments:
            unknown = sorted(set(env.components) - known)
            if unknown:
                raise ValueError(
                    f"environnement {env.name!r} : surcharges pour des "
                    f"composants inconnus {unknown}"
                )

    def _derive_namespaces(self) -> None:
        """Renseigne le namespace de chaque environnement s'il est absent."""
        for env in self.environments:
            if env.namespace is not None:
                continue
            if self.namespace_strategy is NamespaceStrategy.SINGLE:
                env.__dict__["namespace"] = self.app.name
            elif self.namespace_strategy is NamespaceStrategy.PER_ENV:
                env.__dict__["namespace"] = f"{self.app.name}-{env.name}"
            else:
                raise ValueError(
                    f"environnement {env.name!r} : la stratégie de namespace "
                    '"custom" exige un namespace explicite'
                )

    def _derive_environment_defaults(self) -> None:
        """Applique le profil d'environnement aux valeurs laissées vides."""
        for env in self.environments:
            profile = profile_for_environment(env.name)
            if env.log_level is None:
                env.__dict__["log_level"] = profile.log_level

            for component in self.components:
                override = env.components.get(component.name)
                if override is None:
                    override = EnvironmentOverride()
                    env.components[component.name] = override

                if override.replicas is None and component.is_workload:
                    override.__dict__["replicas"] = profile.replicas
                if override.hpa_enabled is None and component.has(AddonKind.HPA):
                    override.__dict__["hpa_enabled"] = profile.hpa_enabled
                if override.pdb_enabled is None and component.has(AddonKind.PDB):
                    override.__dict__["pdb_enabled"] = profile.pdb_enabled
                if override.ingress_host is None and component.has(AddonKind.INGRESS):
                    override.__dict__["ingress_host"] = self._hostname(component, env)
                if override.resources is None and profile.resource_multiplier != 1:
                    override.__dict__["resources"] = component.resources.scaled(
                        profile.resource_multiplier
                    )

    def _hostname(self, component: ComponentSpec, env: EnvironmentSpec) -> str:
        """Calcule l'hôte d'Ingress d'un composant pour un environnement.

        Le premier composant exposé porte le nom de l'application ; les
        suivants sont préfixés par leur propre nom, afin que deux composants
        exposés ne se disputent pas le même hôte. Le nom de l'environnement est
        inséré partout sauf en production.
        """
        exposed = [c.name for c in self.components if c.has(AddonKind.INGRESS)]
        prefix = (
            self.app.name
            if exposed and exposed[0] == component.name
            else f"{component.name}-{self.app.name}"
        )
        parts = [prefix]
        if profile_for_environment(env.name).host_includes_env:
            parts.append(env.name)
        parts.append(component.ingress.base_domain)
        return ".".join(parts)

    # ------------------------------------------------------------------
    # Accès pratiques
    # ------------------------------------------------------------------

    @property
    def chart_name(self) -> str:
        """Nom du chart principal, aligné sur le nom de l'application."""
        return self.app.name

    def component(self, name: str) -> ComponentSpec:
        """Renvoie un composant par son nom, ou lève une KeyError explicite."""
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(f"composant inconnu : {name!r}")

    def environment(self, name: str) -> EnvironmentSpec:
        """Renvoie un environnement par son nom, ou lève une KeyError explicite."""
        for env in self.environments:
            if env.name == name:
                return env
        raise KeyError(f"environnement inconnu : {name!r}")

    @property
    def environment_names(self) -> list[str]:
        """Noms des environnements, dans l'ordre de la spécification."""
        return [e.name for e in self.environments]

    def uses_addon(self, addon: AddonKind) -> bool:
        """Indique si au moins un composant utilise l'addon donné."""
        return any(c.has(addon) for c in self.components)
