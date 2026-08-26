"""Les domaines sont un **choix**, jamais un lot.

C'est la promesse centrale de l'outil : une seule description du service, et
l'utilisateur decide ce qu'il en tire. Trois facons de choisir, toutes couvertes
ici :

* une section absente de `forge.yml` ne genere rien ;
* `--only` restreint une execution a certains domaines ;
* l'entretien de `forge new` demande lesquels produire.

Le mecanisme existait depuis la phase 2 ; ce module le verrouille, et verifie
que la CLI le **dit** — un projet vide sans explication n'est pas une reponse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app, run_new
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data, save_spec
from tests.conftest import REPO_ROOT
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

SPEC_DEUX = REPO_ROOT / "tests" / "specs" / "deux-domaines.yml"
SPEC_ANSIBLE_SEUL = REPO_ROOT / "tests" / "specs" / "ansible-ci.yml"
SPEC_HELM_SEUL = REPO_ROOT / "tests" / "specs" / "helm-complet.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    for module in BUILTIN_PLUGINS:
        instance.register_module(module)
    return instance


def _generer(spec_path: Path, cible: Path, **kwargs) -> pipeline.GenerationResult:
    manager = _manager()
    data = load_spec_data(spec_path)
    return pipeline.generate(data, validate_spec(data, manager), manager, cible, **kwargs)


def _domaines_produits(cible: Path) -> set[str]:
    """Sous-repertoires de domaine reellement ecrits dans la cible."""
    return {
        chemin.name
        for chemin in cible.iterdir()
        if chemin.is_dir() and chemin.name in {"ansible", "helm"}
    }


# ---------------------------------------------------------------------------
# 1. Une section absente ne genere rien
# ---------------------------------------------------------------------------


def test_une_specification_ansible_seule_ne_produit_pas_de_chart(tmp_path):
    resultat = _generer(SPEC_ANSIBLE_SEUL, tmp_path)
    assert resultat.domains == ["ansible"]
    assert _domaines_produits(tmp_path) == {"ansible"}


def test_une_specification_helm_seule_ne_produit_pas_de_projet_ansible(tmp_path):
    resultat = _generer(SPEC_HELM_SEUL, tmp_path)
    assert resultat.domains == ["helm"]
    assert _domaines_produits(tmp_path) == {"helm"}


def test_une_specification_sans_aucun_domaine_le_dit_clairement(tmp_path):
    """Un projet vide sans explication n'est pas une reponse acceptable."""
    spec = tmp_path / "forge.yml"
    save_spec(
        {
            "forge_version": 1,
            "service": {
                "name": "nu",
                "description": "Service sans domaine",
                "owner": "Equipe",
                "environments": [{"name": "prod"}],
            },
        },
        spec,
        sections=[],
    )
    cible = tmp_path / "projet"
    resultat = runner.invoke(app, ["generate", "-s", str(spec), "-o", str(cible)])

    assert resultat.exit_code == 0
    assert "aucun domaine" in resultat.stdout
    assert "domaines disponibles" in resultat.stdout
    assert "ansible" in resultat.stdout and "helm" in resultat.stdout
    assert _domaines_produits(cible) == set()


# ---------------------------------------------------------------------------
# 2. `--only` restreint une execution
# ---------------------------------------------------------------------------


def test_only_restreint_la_generation_a_un_domaine(tmp_path):
    resultat = _generer(SPEC_DEUX, tmp_path, only=["helm"])
    assert resultat.domains == ["helm"]
    assert _domaines_produits(tmp_path) == {"helm"}


def test_only_accepte_plusieurs_domaines(tmp_path):
    resultat = _generer(SPEC_DEUX, tmp_path, only=["ansible", "helm"])
    assert resultat.domains == ["ansible", "helm"]


# ---------------------------------------------------------------------------
# 3. L'entretien demande lesquels produire
# ---------------------------------------------------------------------------


def test_l_entretien_permet_de_ne_retenir_qu_un_domaine(tmp_path):
    """L'utilisateur coche `helm` seul : aucun projet Ansible ne doit sortir."""
    manager = _manager()
    reponses = [
        "boutique",              # nom du service
        "Boutique en ligne",     # description
        "Equipe Plateforme",     # responsable
        "",                      # contact
        "prod",                  # environnements
        True,                    # un environnement de production ?
        "prod",                  # lequel
        "",                      # domaine DNS de prod
        ["helm"],                # <- LE CHOIX : helm seul
        # entretien du domaine helm
        "1.36", "0.1.0", "1.0.0",
        "docker.io", "boutique", "appVersion",
        "per_env",
        "api", "deployment", ["service"], "8080",
        False,                   # ajouter un autre composant ?
        True, True,              # makefile, tests helm
    ]
    prompter = ScriptedPrompter(reponses)
    resultat = run_new(tmp_path, manager, prompter, spec_out=tmp_path / "forge.yml")

    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    assert resultat.domains == ["helm"]
    assert _domaines_produits(tmp_path) == {"helm"}
    # La specification ecrite ne porte que la section retenue.
    ecrite = load_spec_data(tmp_path / "forge.yml")
    assert "helm" in ecrite and "ansible" not in ecrite


# ---------------------------------------------------------------------------
# La CLI doit dire ce qu'elle fait
# ---------------------------------------------------------------------------


def test_generate_annonce_ce_qu_il_va_produire(tmp_path):
    resultat = runner.invoke(
        app,
        ["generate", "-s", str(SPEC_DEUX), "-o", str(tmp_path), "--only", "helm", "--dry-run"],
    )
    assert resultat.exit_code == 0, resultat.stdout
    assert "helm/" in resultat.stdout
    assert "ansible/" not in resultat.stdout


def test_plugins_distingue_les_domaines_demandes_des_autres():
    resultat = runner.invoke(app, ["plugins", "-s", str(SPEC_HELM_SEUL)])
    assert resultat.exit_code == 0, resultat.stdout
    lignes = resultat.stdout.splitlines()
    ligne_helm = next(ligne for ligne in lignes if ligne.startswith("helm"))
    ligne_ansible = next(ligne for ligne in lignes if ligne.startswith("ansible"))

    assert "demande par la specification" in ligne_helm
    assert "non demande" in ligne_ansible
    assert "1 domaine(s) demande(s) sur 3" in resultat.stdout


@pytest.mark.parametrize(
    "spec", [SPEC_ANSIBLE_SEUL, SPEC_HELM_SEUL, SPEC_DEUX], ids=["ansible", "helm", "deux"]
)
def test_validate_accepte_un_projet_mono_comme_multi_domaine(spec, tmp_path):
    """Aucun controle inter-domaines ne doit penaliser un projet a un domaine."""
    _generer(spec, tmp_path)
    resultat = runner.invoke(app, ["validate", "-o", str(tmp_path), "--skip-missing"])
    assert resultat.exit_code == 0, resultat.stdout
    assert "aucun ecart" in resultat.stdout
