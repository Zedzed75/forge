"""Modèle de données de helm-forge.

Ce paquet expose la spécification complète d'un projet à générer. Les modules
sont découpés par responsabilité : ``enums`` pour les valeurs closes,
``validators`` pour les règles Kubernetes, ``profiles`` pour les valeurs
dérivées, ``component`` pour une charge de travail, ``spec`` pour la racine.
"""

from __future__ import annotations

from .base import ForgeModel
from .component import (
    ComponentSecretSpec,
    ComponentSpec,
    ConfigSpec,
    CronSpec,
    HpaSpec,
    IngressSpec,
    NetworkPolicySpec,
    PdbSpec,
    PersistenceSpec,
    ProbesSpec,
    ResourcesSpec,
    SecuritySpec,
    ServiceMonitorSpec,
    ServiceSpec,
)
from .enums import (
    AccessMode,
    AddonKind,
    CIProvider,
    ComponentKind,
    ImagePullPolicy,
    IngressController,
    Layout,
    NamespaceStrategy,
    ResourceProfile,
    SecretStrategy,
    ServiceType,
    TagStrategy,
)
from .profiles import (
    DEFAULT_ENVIRONMENT_PROFILE,
    ENVIRONMENT_PROFILES,
    RESOURCE_PROFILES,
    EnvironmentProfile,
    ResourceValues,
    profile_for_environment,
    scale_quantity,
)
from .spec import (
    AppMeta,
    EnvironmentOverride,
    EnvironmentSpec,
    ExtrasSpec,
    ImageSpec,
    KubernetesTarget,
    ProjectSpec,
    SecretSpec,
)

__all__ = [
    "AccessMode",
    "AddonKind",
    "AppMeta",
    "CIProvider",
    "ComponentKind",
    "ComponentSecretSpec",
    "ComponentSpec",
    "ConfigSpec",
    "CronSpec",
    "DEFAULT_ENVIRONMENT_PROFILE",
    "ENVIRONMENT_PROFILES",
    "EnvironmentOverride",
    "EnvironmentProfile",
    "EnvironmentSpec",
    "ExtrasSpec",
    "ForgeModel",
    "HpaSpec",
    "ImagePullPolicy",
    "ImageSpec",
    "IngressController",
    "IngressSpec",
    "KubernetesTarget",
    "Layout",
    "NamespaceStrategy",
    "NetworkPolicySpec",
    "PdbSpec",
    "PersistenceSpec",
    "ProbesSpec",
    "ProjectSpec",
    "RESOURCE_PROFILES",
    "ResourceProfile",
    "ResourceValues",
    "ResourcesSpec",
    "SecretSpec",
    "SecretStrategy",
    "SecuritySpec",
    "ServiceMonitorSpec",
    "ServiceSpec",
    "ServiceType",
    "TagStrategy",
    "profile_for_environment",
    "scale_quantity",
]
