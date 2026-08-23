"""Tests unitaires du modèle de spécification.

Chaque règle de validation décrite dans le document de conception dispose ici
d'un test qui prouve qu'elle est appliquée, et d'un test qui prouve qu'elle
rejette bien le cas invalide.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from helm_forge.models import (
    AddonKind,
    AppMeta,
    ComponentKind,
    ComponentSpec,
    CronSpec,
    EnvironmentOverride,
    EnvironmentSpec,
    ImageSpec,
    KubernetesTarget,
    NamespaceStrategy,
    ProjectSpec,
    ResourceProfile,
    ResourcesSpec,
    SecuritySpec,
    ServiceType,
    TagStrategy,
    profile_for_environment,
    scale_quantity,
)


# ---------------------------------------------------------------------------
# Identité de l'application
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["shop", "shop-api", "s", "a1-b2"])
def test_app_name_accepte_les_labels_dns(name: str) -> None:
    assert AppMeta(name=name, description="x").name == name


@pytest.mark.parametrize(
    "name",
    ["Shop", "shop_api", "-shop", "shop-", "shop.api", "", "a" * 41],
)
def test_app_name_refuse_les_labels_invalides(name: str) -> None:
    with pytest.raises(ValidationError):
        AppMeta(name=name, description="x")


@pytest.mark.parametrize("version", ["1.0.0", "0.1.0", "2.3.4-rc.1"])
def test_chart_version_accepte_le_semver(version: str) -> None:
    assert AppMeta(name="a", description="x", chart_version=version)


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1", "latest"])
def test_chart_version_refuse_le_non_semver(version: str) -> None:
    with pytest.raises(ValidationError):
        AppMeta(name="a", description="x", chart_version=version)


def test_email_du_mainteneur_est_valide() -> None:
    with pytest.raises(ValidationError):
        AppMeta(name="a", description="x", maintainer_email="pas-un-email")


def test_cle_inconnue_refusee() -> None:
    """Une faute de frappe dans forge.yml doit échouer, pas être ignorée."""
    with pytest.raises(ValidationError):
        AppMeta(name="a", description="x", maintaner_name="typo")


# ---------------------------------------------------------------------------
# Cible Kubernetes
# ---------------------------------------------------------------------------


def test_version_kubernetes_par_defaut_est_la_plus_recente() -> None:
    assert KubernetesTarget().version == "1.36"


def test_version_kubernetes_hors_fenetre_refusee() -> None:
    with pytest.raises(ValidationError) as exc:
        KubernetesTarget(version="1.20")
    assert "non supportée" in str(exc.value)


def test_contrainte_kube_version_autorise_les_preversions() -> None:
    """Le suffixe -0 est indispensable pour les distributions type EKS."""
    assert KubernetesTarget(version="1.36").kube_version_constraint == ">=1.36.0-0"


# ---------------------------------------------------------------------------
# Ressources et sécurité
# ---------------------------------------------------------------------------


def test_profil_de_ressources_remplit_les_quantites() -> None:
    resources = ResourcesSpec(profile=ResourceProfile.LARGE)
    assert resources.cpu_request == "1"
    assert resources.memory_limit == "2Gi"


def test_quantite_explicite_prime_sur_le_profil() -> None:
    resources = ResourcesSpec(profile=ResourceProfile.SMALL, cpu_limit="500m")
    assert resources.cpu_limit == "500m"
    assert resources.memory_limit == "128Mi"  # le reste vient du profil


def test_quantite_invalide_refusee() -> None:
    with pytest.raises(ValidationError):
        ResourcesSpec(cpu_request="beaucoup")


@pytest.mark.parametrize(
    ("quantity", "factor", "expected"),
    [("50m", 2, "100m"), ("64Mi", 2, "128Mi"), ("1", 2, "2"), ("1", 1, "1")],
)
def test_mise_a_echelle_des_quantites(quantity: str, factor: int, expected: str) -> None:
    assert scale_quantity(quantity, factor) == expected


def test_ressources_mises_a_echelle_passent_en_profil_custom() -> None:
    scaled = ResourcesSpec(profile=ResourceProfile.SMALL).scaled(2)
    assert scaled.profile is ResourceProfile.CUSTOM
    assert (scaled.cpu_request, scaled.memory_limit) == ("100m", "256Mi")


def test_securite_stricte_par_defaut() -> None:
    security = SecuritySpec()
    assert security.run_as_non_root is True
    assert security.read_only_root_filesystem is True
    assert security.drop_capabilities == ["ALL"]


def test_securite_non_stricte_assouplit_les_defauts() -> None:
    security = SecuritySpec(strict=False)
    assert security.run_as_non_root is False
    assert security.read_only_root_filesystem is False
    assert security.drop_capabilities == []


# ---------------------------------------------------------------------------
# Composants
# ---------------------------------------------------------------------------


def test_addons_dedupliques_et_ordonnes_canoniquement() -> None:
    """L'ordre de saisie ne doit pas influer sur le projet généré."""
    component = ComponentSpec(
        name="api",
        addons=[AddonKind.INGRESS, AddonKind.SERVICE, AddonKind.INGRESS],
    )
    assert component.addons == [AddonKind.SERVICE, AddonKind.INGRESS]


def test_ingress_exige_un_service() -> None:
    with pytest.raises(ValidationError) as exc:
        ComponentSpec(name="api", addons=[AddonKind.INGRESS])
    assert "ingress exige l'addon service" in str(exc.value)


def test_servicemonitor_exige_un_service() -> None:
    with pytest.raises(ValidationError):
        ComponentSpec(name="api", addons=[AddonKind.SERVICEMONITOR])


def test_cronjob_refuse_les_addons_incompatibles() -> None:
    with pytest.raises(ValidationError) as exc:
        ComponentSpec(
            name="cleanup",
            kind=ComponentKind.CRONJOB,
            addons=[AddonKind.SERVICE],
        )
    assert "incompatibles" in str(exc.value)


def test_cronjob_recoit_un_bloc_cron_par_defaut() -> None:
    component = ComponentSpec(
        name="cleanup", kind=ComponentKind.CRONJOB, addons=[AddonKind.CONFIGMAP]
    )
    assert component.cron is not None
    assert component.cron.schedule == "0 3 * * *"


def test_bloc_cron_refuse_hors_cronjob() -> None:
    with pytest.raises(ValidationError):
        ComponentSpec(name="api", cron=CronSpec())


def test_planification_cron_invalide_refusee() -> None:
    with pytest.raises(ValidationError):
        CronSpec(schedule="tous les jours")


def test_statefulset_force_service_headless_et_persistance() -> None:
    component = ComponentSpec(
        name="cache",
        kind=ComponentKind.STATEFULSET,
        addons=[AddonKind.SERVICE],
    )
    assert component.service.headless is True
    assert component.persistence.enabled is True


def test_hpa_min_superieur_au_max_refuse() -> None:
    with pytest.raises(ValidationError):
        ComponentSpec(name="api", hpa={"min_replicas": 5, "max_replicas": 2})


def test_pdb_accepte_un_pourcentage_et_refuse_une_chaine_libre() -> None:
    assert ComponentSpec(name="api", pdb={"min_available": "50%"})
    with pytest.raises(ValidationError):
        ComponentSpec(name="api", pdb={"min_available": "moitie"})


def test_port_hors_bornes_refuse() -> None:
    with pytest.raises(ValidationError):
        ComponentSpec(name="api", container_port=70000)


def test_service_type_est_une_valeur_kubernetes() -> None:
    component = ComponentSpec(name="api", service={"type": "LoadBalancer"})
    assert component.service.type is ServiceType.LOAD_BALANCER


def test_is_workload_distingue_le_cronjob() -> None:
    assert ComponentSpec(name="api").is_workload is True
    cron = ComponentSpec(
        name="cleanup", kind=ComponentKind.CRONJOB, addons=[AddonKind.CONFIGMAP]
    )
    assert cron.is_workload is False


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


def test_strategie_fixed_exige_un_tag() -> None:
    with pytest.raises(ValidationError):
        ImageSpec(strategy=TagStrategy.FIXED)


def test_tag_interdit_hors_strategie_fixed() -> None:
    with pytest.raises(ValidationError):
        ImageSpec(strategy=TagStrategy.APP_VERSION, tag="1.0.0")


def test_depot_image_invalide_refuse() -> None:
    with pytest.raises(ValidationError):
        ImageSpec(repository="Acme/Shop")


# ---------------------------------------------------------------------------
# Projet : unicité, namespaces, dérivations
# ---------------------------------------------------------------------------


def _spec(**kwargs) -> ProjectSpec:
    """Construit une spécification minimale, surchargeable par mot-clé."""
    base = dict(
        app=AppMeta(name="shop", description="Boutique"),
        environments=[EnvironmentSpec(name="dev"), EnvironmentSpec(name="prod")],
        components=[ComponentSpec(name="api")],
    )
    base.update(kwargs)
    return ProjectSpec(**base)


def test_noms_de_composants_en_double_refuses() -> None:
    with pytest.raises(ValidationError) as exc:
        _spec(components=[ComponentSpec(name="api"), ComponentSpec(name="api")])
    assert "double" in str(exc.value)


def test_noms_d_environnements_en_double_refuses() -> None:
    with pytest.raises(ValidationError):
        _spec(environments=[EnvironmentSpec(name="dev"), EnvironmentSpec(name="dev")])


def test_surcharge_pour_composant_inconnu_refusee() -> None:
    with pytest.raises(ValidationError) as exc:
        _spec(
            environments=[
                EnvironmentSpec(name="dev", components={"fantome": EnvironmentOverride()})
            ]
        )
    assert "inconnus" in str(exc.value)


def test_au_moins_un_composant_et_un_environnement() -> None:
    with pytest.raises(ValidationError):
        _spec(components=[])
    with pytest.raises(ValidationError):
        _spec(environments=[])


def test_namespace_derive_par_environnement() -> None:
    spec = _spec()
    assert spec.environment("dev").namespace == "shop-dev"
    assert spec.environment("prod").namespace == "shop-prod"


def test_namespace_unique_pour_la_strategie_single() -> None:
    spec = _spec(namespace_strategy=NamespaceStrategy.SINGLE)
    assert {e.namespace for e in spec.environments} == {"shop"}


def test_strategie_custom_exige_un_namespace_explicite() -> None:
    with pytest.raises(ValidationError) as exc:
        _spec(namespace_strategy=NamespaceStrategy.CUSTOM)
    assert "custom" in str(exc.value)

    spec = _spec(
        namespace_strategy=NamespaceStrategy.CUSTOM,
        environments=[
            EnvironmentSpec(name="dev", namespace="equipe-a-dev"),
            EnvironmentSpec(name="prod", namespace="equipe-a-prod"),
        ],
    )
    assert spec.environment("dev").namespace == "equipe-a-dev"


def test_profil_d_environnement_reconnait_les_alias() -> None:
    assert profile_for_environment("production").replicas == 3
    assert profile_for_environment("stage").pdb_enabled is True
    assert profile_for_environment("preprod").replicas == 1  # profil prudent


def test_replicas_derives_du_profil_d_environnement() -> None:
    spec = _spec()
    assert spec.environment("dev").components["api"].replicas == 1
    assert spec.environment("prod").components["api"].replicas == 3


def test_log_level_derive_du_profil() -> None:
    spec = _spec()
    assert spec.environment("dev").log_level == "debug"
    assert spec.environment("prod").log_level == "info"


def test_hpa_active_uniquement_en_production() -> None:
    spec = _spec(
        components=[ComponentSpec(name="api", addons=[AddonKind.SERVICE, AddonKind.HPA])]
    )
    assert spec.environment("dev").components["api"].hpa_enabled is False
    assert spec.environment("prod").components["api"].hpa_enabled is True


def test_ressources_doublees_en_production_seulement() -> None:
    spec = _spec()
    assert spec.environment("dev").components["api"].resources is None
    prod = spec.environment("prod").components["api"].resources
    assert prod is not None
    assert prod.cpu_request == "100m"


def test_surcharge_explicite_non_ecrasee_par_le_profil() -> None:
    spec = _spec(
        environments=[
            EnvironmentSpec(name="prod", components={"api": EnvironmentOverride(replicas=7)})
        ]
    )
    assert spec.environment("prod").components["api"].replicas == 7


# ---------------------------------------------------------------------------
# Dérivation des hôtes d'Ingress
# ---------------------------------------------------------------------------


def test_hote_ingress_omet_l_environnement_en_production() -> None:
    spec = _spec(
        components=[ComponentSpec(name="api", addons=[AddonKind.SERVICE, AddonKind.INGRESS])]
    )
    assert spec.environment("dev").components["api"].ingress_host == "shop.dev.example.com"
    assert spec.environment("prod").components["api"].ingress_host == "shop.example.com"


def test_second_composant_expose_recoit_un_hote_distinct() -> None:
    spec = _spec(
        components=[
            ComponentSpec(name="api", addons=[AddonKind.SERVICE, AddonKind.INGRESS]),
            ComponentSpec(name="admin", addons=[AddonKind.SERVICE, AddonKind.INGRESS]),
        ]
    )
    prod = spec.environment("prod").components
    assert prod["api"].ingress_host == "shop.example.com"
    assert prod["admin"].ingress_host == "admin-shop.example.com"


def test_hote_ingress_explicite_conserve() -> None:
    spec = _spec(
        components=[ComponentSpec(name="api", addons=[AddonKind.SERVICE, AddonKind.INGRESS])],
        environments=[
            EnvironmentSpec(
                name="prod",
                components={"api": EnvironmentOverride(ingress_host="boutique.acme.fr")},
            )
        ],
    )
    assert spec.environment("prod").components["api"].ingress_host == "boutique.acme.fr"


# ---------------------------------------------------------------------------
# Accès pratiques
# ---------------------------------------------------------------------------


def test_acces_par_nom(minimal_spec: ProjectSpec) -> None:
    assert minimal_spec.component("api").name == "api"
    assert minimal_spec.environment("prod").name == "prod"
    with pytest.raises(KeyError):
        minimal_spec.component("fantome")
    with pytest.raises(KeyError):
        minimal_spec.environment("fantome")


def test_uses_addon(full_spec: ProjectSpec) -> None:
    assert full_spec.uses_addon(AddonKind.INGRESS) is True
    assert full_spec.uses_addon(AddonKind.NETWORKPOLICY) is False


def test_noms_d_environnements_dans_l_ordre(full_spec: ProjectSpec) -> None:
    assert full_spec.environment_names == ["dev", "staging", "prod"]
