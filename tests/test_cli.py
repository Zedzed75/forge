"""Tests de bout en bout de la CLI, plugin `demo` a l'appui.

Ils verifient le cablage complet — entretien, spec, rendu copier, validation,
comparaison — et non le detail de chaque couche, deja couvert ailleurs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app, run_new
from forge.plugins_api.manager import ForgeManager
from tests.conftest import DEMO_PLUGIN, SPECS_DIR
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

#: Reponses rejouant l'entretien complet : bloc service, puis domaine demo.
ENTRETIEN = [
    "boutique",                # nom du service
    "Boutique en ligne",       # description
    "Equipe Plateforme",       # responsable
    "",                        # adresse de contact
    "dev,prod",                # environnements
    True,                      # un environnement de production ?
    "prod",                    # lequel
    "dev.example.net",         # domaine de dev
    "example.net",             # domaine de prod
    True,                      # generer le domaine demo ?
    "bonjour",                 # salutation
    "cpu,requetes",            # widgets
    "gauge",                   # type du widget cpu
    "counter",                 # type du widget requetes
]


def _invoke(args: list[str], monkeypatch: pytest.MonkeyPatch, plugins: str = DEMO_PLUGIN):
    monkeypatch.setenv("FORGE_PLUGINS", plugins)
    return runner.invoke(app, args)


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "forge" in result.stdout


def test_plugins_liste_les_domaines_enregistres(monkeypatch):
    result = _invoke(["plugins"], monkeypatch)
    assert result.exit_code == 0
    assert "demo" in result.stdout


def test_plugins_sans_plugin_le_dit_clairement(monkeypatch):
    """Branche atteignable seulement si aucun domaine n'est livre ni declare."""
    monkeypatch.setattr("forge.plugins_api.manager.BUILTIN_PLUGINS", ())
    result = runner.invoke(app, ["plugins"])
    assert result.exit_code == 0
    assert "aucun domaine" in result.stdout


def test_plugins_liste_les_domaines_livres():
    """Le domaine Ansible est disponible sans rien declarer."""
    result = runner.invoke(app, ["plugins"])
    assert result.exit_code == 0
    assert "ansible" in result.stdout


def test_catalog_liste_les_elements(monkeypatch):
    result = _invoke(["catalog", "demo"], monkeypatch)
    assert result.exit_code == 0
    assert "gauge" in result.stdout


def test_catalog_detaille_un_element(monkeypatch):
    result = _invoke(["catalog", "demo", "gauge"], monkeypatch)
    assert result.exit_code == 0
    assert "detailed" in result.stdout


def test_catalog_refuse_un_element_inconnu(monkeypatch):
    result = _invoke(["catalog", "demo", "sonar"], monkeypatch)
    assert result.exit_code == 1


def test_catalog_refuse_un_domaine_inconnu(monkeypatch):
    # Un nom qu'aucun plugin ne portera : « terraform » servait ici jusqu'a
    # ce qu'il devienne un domaine reel (phase 7).
    result = _invoke(["catalog", "inexistant"], monkeypatch)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def test_generate_produit_l_arborescence_attendue(tmp_path, monkeypatch):
    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(tmp_path)],
        monkeypatch,
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "forge.yml").is_file()
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "demo" / ".copier-answers.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()


def test_generate_en_simulation_n_ecrit_rien(tmp_path, monkeypatch):
    result = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-complet.yml"),
            "-o",
            str(tmp_path),
            "--dry-run",
        ],
        monkeypatch,
    )
    assert result.exit_code == 0
    assert list(tmp_path.iterdir()) == []


def test_generate_refuse_un_domaine_inconnu(tmp_path, monkeypatch):
    result = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-complet.yml"),
            "-o",
            str(tmp_path),
            "--only",
            "terraform",
        ],
        monkeypatch,
    )
    assert result.exit_code == 1


def test_generate_sans_spec_trouvable_le_dit(tmp_path, monkeypatch):
    result = _invoke(["generate", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# validate / diff sur un projet deja genere
# ---------------------------------------------------------------------------


def test_validate_passe_sur_un_projet_fraichement_genere(projet_demo, monkeypatch):
    target, _, _ = projet_demo
    result = _invoke(["validate", "-o", str(target)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "aucun ecart" in result.stdout


def test_diff_ne_voit_aucun_ecart_juste_apres_generation(projet_demo, monkeypatch):
    target, _, _ = projet_demo
    result = _invoke(["diff", "-o", str(target)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "a jour" in result.stdout


def test_diff_signale_un_fichier_supprime_dans_la_cible(projet_demo, tmp_path, monkeypatch):
    target, model, manager = projet_demo
    copie = tmp_path / "copie"
    copie.mkdir()
    import shutil

    shutil.copytree(target / "demo", copie / "demo")
    (copie / "demo" / "environments" / "prod" / "cpu.yml").unlink()
    shutil.copy(target / "forge.yml", copie / "forge.yml")

    result = _invoke(["diff", "-o", str(copie)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "environments/prod/cpu.yml" in result.stdout


# ---------------------------------------------------------------------------
# new (entretien scripte)
# ---------------------------------------------------------------------------


def test_new_conduit_l_entretien_puis_genere(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    prompter = ScriptedPrompter(ENTRETIEN)
    result = run_new(
        tmp_path,
        manager,
        prompter,
        spec_out=tmp_path / "forge.yml",
    )
    assert prompter.exhausted
    assert result.domains == ["demo"]
    assert (tmp_path / "forge.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "dev" / "cpu.yml").is_file()


def test_new_ecrit_une_spec_rejouable(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    run_new(
        tmp_path / "projet",
        manager,
        ScriptedPrompter(ENTRETIEN),
        spec_out=tmp_path / "forge.yml",
        dry_run=True,
    )
    data, model = pipeline.load_spec(tmp_path / "forge.yml", manager)
    assert model.service.name == "boutique"
    assert model.domain_names() == ("demo",)
    assert [w["name"] for w in data["demo"]["widgets"]] == ["cpu", "requetes"]


def test_new_permet_de_decliner_un_domaine(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    reponses = list(ENTRETIEN[:9]) + [False]
    result = run_new(
        tmp_path,
        manager,
        ScriptedPrompter(reponses),
        spec_out=tmp_path / "forge.yml",
        dry_run=True,
    )
    assert result.domains == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_update_rejoue_le_gabarit_sur_un_projet_genere(tmp_path, monkeypatch):
    """`copier update` exige un depot git cible : c'est bien ce que le coeur fait."""
    import subprocess

    from tests.conftest import build_project, template_is_dirty

    if template_is_dirty():
        pytest.skip("gabarit non committe : copier update ne peut pas comparer deux refs")

    build_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
    )
    result = _invoke(["update", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "demo" in result.stdout
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()


def test_update_ignore_un_domaine_jamais_genere(tmp_path, monkeypatch):
    result = _invoke(["update", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0
    assert "aucun" in result.stdout


def test_le_chemin_de_gabarit_du_plugin_est_celui_declare(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    hooks = manager.domain("demo")
    assert (Path(pipeline.copier_runner.template_root()) / hooks.template_subdir()).is_dir()
