"""Tests du plugin Helm : modele, controles croises, validateurs, catalogue.

La parite avec le generateur d'origine a servi pendant tout le portage, puis a
ete retiree en phase 10 avec `_legacy/`. Elle avait deja cesse de couvrir
l'essentiel : les neuf familles de ressources creees en phase 4 n'existaient pas
dans l'outil d'origine, et ce sont `tests/golden/helm-complet/` et les
validateurs reels qui les tiennent.

Ce module couvre ce que ni l'un ni l'autre ne dit : les refus, les
normalisations imposees, et les garde-fous que seuls le modele ou le controle
croise peuvent porter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.errors import SpecValidationError
from forge.plugins.helm import answers as answers_module
from forge.plugins.helm import validators
from forge.plugins.helm.catalog.registry import all_families, family_names, get_family
from forge.plugins.helm.components import ComponentSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import REPO_ROOT

HELM_PLUGIN = "forge.plugins.helm.plugin"

#: Specification golden exercant les treize familles.
SPEC_COMPLETE = REPO_ROOT / "tests" / "specs" / "helm-complet.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(HELM_PLUGIN)
    return instance


def _spec_data(**surcharges) -> dict:
    """Specification Helm minimale valide."""
    data = {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "prod", "production": True}],
        },
        "helm": {"components": [{"name": "api", "addons": ["service"]}]},
    }
    for chemin, valeur in surcharges.items():
        cible = data
        *parents, feuille = chemin.split(".")
        for parent in parents:
            cible = cible[parent]
        cible[feuille] = valeur
    return data


# ---------------------------------------------------------------------------
# Normalisations imposees par Kubernetes
# ---------------------------------------------------------------------------


def test_un_statefulset_recoit_toujours_son_service_headless():
    """Sans l'addon, `serviceName` designerait une ressource inexistante.

    Forcer `headless` ne suffit pas : le Service ne serait pas genere du tout,
    et le StatefulSet perdrait l'identite reseau stable qui est sa raison
    d'etre. Aucun validateur ne peut le voir, le manifeste restant valide.
    """
    composant = ComponentSpec(name="store", kind="statefulset", addons=["configmap"])
    assert [addon.value for addon in composant.addons] == ["service", "configmap"]
    assert composant.service.headless is True
    assert composant.persistence.enabled is True


def test_un_deployment_ne_recoit_pas_de_service_impose():
    composant = ComponentSpec(name="api", kind="deployment", addons=["configmap"])
    assert [addon.value for addon in composant.addons] == ["configmap"]


def test_un_nom_de_port_trop_long_est_refuse():
    """Kubernetes impose le format IANA_SVC_NAME : au plus 15 caracteres.

    Aucun validateur externe ne l'attrape — un nom de 29 caracteres passe
    `helm lint`, `helm template` et `kubeconform -strict`, et n'est refuse
    qu'a l'application.
    """
    with pytest.raises(Exception, match="IANA_SVC_NAME|Nom de port invalide"):
        ComponentSpec(name="api", port_name="un-nom-de-port-beaucoup-trop-long")


@pytest.mark.parametrize("nom", ["-http", "http-", "http--2", "80"])
def test_les_noms_de_port_mal_formes_sont_refuses(nom):
    with pytest.raises(Exception):
        ComponentSpec(name="api", port_name=nom)


def test_les_addons_sont_remis_dans_l_ordre_canonique():
    """Le plan de fichiers devient independant de l'ordre de saisie."""
    composant = ComponentSpec(name="api", addons=["hpa", "service", "configmap"])
    assert [addon.value for addon in composant.addons] == ["service", "configmap", "hpa"]


def test_un_ingress_sans_service_est_refuse():
    with pytest.raises(Exception, match="service"):
        ComponentSpec(name="api", addons=["ingress"])


# ---------------------------------------------------------------------------
# RBAC : declarable depuis forge.yml, pas seulement dans values.yaml
# ---------------------------------------------------------------------------


def test_les_regles_rbac_viennent_de_la_specification():
    """Sans cela, elles seraient ecrites en dur dans values.yaml et perdues
    a chaque regeneration."""
    composant = ComponentSpec(
        name="api",
        addons=["service", "serviceaccount"],
        rbac={
            "create": True,
            "rules": [
                {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "list"]}
            ],
        },
    )
    assert composant.rbac.create is True
    assert composant.rbac.rules[0]["resources"] == ["configmaps"]


def test_une_regle_rbac_incomplete_est_refusee():
    """L'API refuse une regle sans verbs ; kubeconform la laisse passer."""
    with pytest.raises(Exception, match="incomplete|verbs"):
        ComponentSpec(
            name="api",
            rbac={"create": True, "rules": [{"apiGroups": [""], "resources": ["pods"]}]},
        )


# ---------------------------------------------------------------------------
# Controles croises — ce que le sous-modele ne peut pas voir
# ---------------------------------------------------------------------------


def test_un_environnement_inconnu_dans_helm_environments_est_signale():
    data = _spec_data()
    data["helm"]["environments"] = {"recette": {"log_level": "debug"}}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert any("recette" in issue.message for issue in issues)
    assert all(issue.hint for issue in issues if issue.level == "error")


def test_une_specification_saine_ne_produit_aucune_erreur():
    spec = validate_spec(_spec_data(), _manager())
    assert [i for i in answers_module.cross_check(spec) if i.level == "error"] == []


# ---------------------------------------------------------------------------
# Validateurs
# ---------------------------------------------------------------------------


def test_trois_commandes_par_environnement_et_le_chainage_du_rendu():
    """`kubeconform` lit le rendu de `helm template` : c'est un `stdin_from`."""
    data = _spec_data()
    data["service"]["environments"] = [{"name": "dev"}, {"name": "prod", "production": True}]
    spec = validate_spec(data, _manager())
    commandes = validators.commands(spec, Path("helm"))

    assert [c.label for c in commandes] == [
        "helm lint (dev)",
        "helm template (dev)",
        "kubeconform -strict (dev)",
        "helm lint (prod)",
        "helm template (prod)",
        "kubeconform -strict (prod)",
    ]
    conform = commandes[2]
    assert conform.stdin_from == "helm template (dev)"
    assert "-strict" in conform.argv
    assert all(c.requires_linux for c in commandes)


def test_le_rendu_est_demande_dans_le_namespace_derive():
    spec = validate_spec(_spec_data(), _manager())
    template = validators.commands(spec, Path("helm"))[1]
    index = template.argv.index("--namespace")
    assert template.argv[index + 1] == "boutique-prod"


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def test_le_catalogue_couvre_les_familles_demandees():
    """PLAN.md fixe la liste attendue au terme de la phase 4."""
    attendues = {
        "deployment", "service", "ingress", "configmap", "statefulset",
        "cronjob", "secret", "hpa", "pdb", "serviceaccount", "rbac",
        "networkpolicy",
    }
    assert attendues <= set(family_names())


def test_chaque_famille_documente_ses_pieges():
    """Les pieges expliquent des choix du chart qui paraitraient arbitraires."""
    sans_piege = [f.name for f in all_families() if not f.traps]
    assert not sans_piege, f"familles sans point de vigilance : {sans_piege}"


def test_aucune_version_d_api_supprimee_n_est_employee():
    """Une apiVersion retiree rend le chart ininstallable sur un cluster recent."""
    supprimees = (
        "extensions/v1beta1",
        "networking.k8s.io/v1beta1",
        "autoscaling/v2beta1",
        "autoscaling/v2beta2",
        "policy/v1beta1",
        "batch/v1beta1",
    )
    for famille in all_families():
        assert famille.api_version not in supprimees, (
            f"{famille.name} emploie {famille.api_version}, supprimee de Kubernetes"
        )


def test_le_catalogue_est_expose_par_le_hook():
    entrees = _manager().domain("helm").catalog()
    assert [e.name for e in entrees] == family_names()
    ingress = next(e for e in entrees if e.name == "ingress")
    assert "pathType" in ingress.details
    assert "ingress.className" in ingress.options


# ---------------------------------------------------------------------------
# Rendu complet
# ---------------------------------------------------------------------------


def test_les_treize_familles_produisent_leurs_ressources(tmp_path):
    """Rendu du cas golden : chaque famille active doit sortir un fichier."""
    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    gabarits = tmp_path / "helm" / "charts" / "boutique" / "templates"
    produits = {chemin.name for chemin in gabarits.glob("*.yaml")}
    for attendu in (
        "deployment-api.yaml",
        "statefulset-db-proxy.yaml",
        "cronjob-cleanup.yaml",
        "service-api.yaml",
        "service-db-proxy.yaml",
        "ingress-api.yaml",
        "configmap-api.yaml",
        "secret-api.yaml",
        "hpa-api.yaml",
        "pdb-api.yaml",
        "serviceaccount-api.yaml",
        "rbac-api.yaml",
        "networkpolicy-api.yaml",
    ):
        assert attendu in produits, f"{attendu} n'a pas ete genere"


def test_un_nom_de_composant_a_tiret_passe_par_values_ref(tmp_path):
    """`.Values.db-proxy` casserait le chart ; `(index .Values "db-proxy")` non."""
    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    rendu = (
        tmp_path / "helm" / "charts" / "boutique" / "templates" / "statefulset-db-proxy.yaml"
    ).read_text(encoding="utf-8")
    assert '(index .Values "db-proxy")' in rendu
    assert ".Values.db-proxy" not in rendu


def test_les_valeurs_libres_d_environnement_sont_rendues(tmp_path):
    """Le generateur d'origine les perdait en silence."""
    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    values = (
        tmp_path / "helm" / "charts" / "boutique" / "values-prod.yaml"
    ).read_text(encoding="utf-8")
    assert "monitoring" in values


# ---------------------------------------------------------------------------
# Validation reelle du chart genere
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_le_chart_genere_passe_ses_propres_validateurs(tmp_path):
    """Regle dure de CLAUDE.md, sur le cas qui active les treize familles.

    `helm lint`, `helm template` sur chaque environnement, puis
    `kubeconform -strict` sur le rendu — nativement, ou via le pont WSL.
    """
    from forge.validate import tools

    for outil in ("helm", "kubeconform"):
        if not tools.probe(outil, True).available:
            pytest.skip(f"{outil} introuvable, nativement comme dans WSL")

    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    resultat = pipeline.validate(spec, manager, tmp_path)
    echecs = [check for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(c.label for c in echecs)}\n"
        + "\n".join(c.detail for c in echecs)[:2000]
    )
    # Le chainage doit avoir reellement tourne, pas avoir ete saute.
    lances = [c.label for rapport in resultat.reports for c in rapport.checks]
    assert any("kubeconform" in label for label in lances)


def test_l_arborescence_annoncee_correspond_aux_fichiers_generes(tmp_path):
    """Arbitrage R3 : `tree.py` reste au plugin, mais un test le tient a jour.

    copier ne peut pas dire a l'avance ce qu'il va ecrire, et le README du chart
    l'affiche. Un gabarit ajoute, retire ou renomme sans mise a jour de
    `tree.py` rendrait donc le README faux — en silence, sans ce test.
    """
    from forge.plugins.helm import tree

    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    base = tmp_path / "helm"
    produits = {
        chemin.relative_to(base).as_posix()
        for chemin in base.rglob("*")
        if chemin.is_file()
    }
    annonces = set(tree.expected_paths(spec))
    # Ecarts assumes : la plomberie de copier n'est pas annoncee, et forge.yml
    # vit desormais a la racine du depot cible (ecart de parite 3).
    assert produits - annonces <= {".copier-answers.yml"}
    assert annonces - produits <= {"forge.yml"}


def test_helm_est_toujours_appele_avec_la_version_de_kubernetes_visee(tmp_path):
    """Sans `--kube-version`, helm evalue le chart contre le defaut de son binaire.

    Ce defaut change a chaque version de helm : un chart declarant
    `kubeVersion: >=1.34.0-0` passait sur un poste dont le helm etait recent et
    echouait en CI, ou il etait epingle. Plus grave que l'echec lui-meme :
    `.Capabilities.KubeVersion` etait renseigne avec une version qui n'est pas
    celle que la specification vise.

    Trouve par la premiere execution reelle de la CI.
    """
    from forge.plugins.helm import validators

    manager = _manager()
    data = load_spec_data(SPEC_COMPLETE)
    spec = validate_spec(data, manager)
    attendue = spec.helm.kubernetes.full_version

    concernees = [
        commande
        for commande in validators.commands(spec, tmp_path)
        if commande.tool == "helm"
    ]
    assert concernees, "le domaine doit declarer des commandes helm"
    for commande in concernees:
        assert "--kube-version" in commande.argv, commande.label
        position = commande.argv.index("--kube-version")
        assert commande.argv[position + 1] == attendue, commande.label
