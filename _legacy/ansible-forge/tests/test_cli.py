"""Tests des commandes de la CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_forge import __version__
from ansible_forge.cli import app
from ansible_forge.engine.role_planner import ROLE_FILES

runner = CliRunner()

MINIMAL_SPEC = Path(__file__).parent / "specs" / "minimal.yml"


class TestGeneralites:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_aide_sans_argument(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "generate" in result.stdout


class TestCommandeGenerate:
    def test_genere_le_projet(self, tmp_path: Path):
        target = tmp_path / "projet"
        result = runner.invoke(
            app, ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(target)]
        )
        assert result.exit_code == 0, result.stdout
        assert (target / "ansible.cfg").is_file()
        assert (target / "roles" / "common" / "tasks" / "main.yml").is_file()

    def test_repertoire_par_defaut_derive_du_nom_du_projet(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["generate", "--spec", str(MINIMAL_SPEC)])
        assert result.exit_code == 0, result.stdout
        assert (tmp_path / "minimal-infra" / "ansible.cfg").is_file()

    def test_dry_run_n_ecrit_rien(self, tmp_path: Path):
        target = tmp_path / "projet"
        result = runner.invoke(
            app, ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(target), "--dry-run"]
        )
        assert result.exit_code == 0, result.stdout
        assert not target.exists()
        assert "ansible.cfg" in result.stdout
        assert "aucun fichier n'a été écrit" in result.stdout

    def test_refuse_un_repertoire_non_vide(self, tmp_path: Path):
        target = tmp_path / "projet"
        target.mkdir()
        (target / "existant.txt").write_text("x", encoding="utf-8")
        result = runner.invoke(
            app, ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(target)]
        )
        assert result.exit_code == 1
        assert "n'est pas vide" in result.stdout + str(result.stderr)

    def test_force_ecrase_un_repertoire_non_vide(self, tmp_path: Path):
        target = tmp_path / "projet"
        target.mkdir()
        (target / "existant.txt").write_text("x", encoding="utf-8")
        result = runner.invoke(
            app,
            ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(target), "--force"],
        )
        assert result.exit_code == 0, result.stdout
        assert (target / "ansible.cfg").is_file()

    def test_spec_absente(self, tmp_path: Path):
        result = runner.invoke(app, ["generate", "--spec", str(tmp_path / "absent.yml")])
        assert result.exit_code == 1
        assert "introuvable" in result.stdout + str(result.stderr)

    def test_spec_invalide(self, tmp_path: Path):
        bad = tmp_path / "bad.yml"
        bad.write_text("project_name: Mauvais Nom\n", encoding="utf-8")
        result = runner.invoke(app, ["generate", "--spec", str(bad)])
        assert result.exit_code == 1
        assert "Nom de projet invalide" in result.stdout + str(result.stderr)

    def test_role_non_implemente_est_signale(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Le catalogue peut proposer un rôle dont les templates manquent encore."""
        monkeypatch.delitem(ROLE_FILES, "common")
        result = runner.invoke(
            app, ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(tmp_path / "out")]
        )
        assert result.exit_code == 1
        assert "pas encore disponibles" in result.stdout + str(result.stderr)


class TestCommandeValidate:
    def test_resume_une_spec_valide(self, tmp_path: Path):
        result = runner.invoke(app, ["validate", "--spec", str(MINIMAL_SPEC)])
        assert result.exit_code == 0, result.stdout
        assert "minimal-infra" in result.stdout
        assert "Fichiers" in result.stdout

    def test_n_ecrit_rien(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["validate", "--spec", str(MINIMAL_SPEC)])
        assert list(tmp_path.iterdir()) == []

    def test_signale_une_spec_invalide(self, tmp_path: Path):
        bad = tmp_path / "bad.yml"
        bad.write_text("environments: []\ngroups: []\nproject_name: demo\n", encoding="utf-8")
        result = runner.invoke(app, ["validate", "--spec", str(bad)])
        assert result.exit_code == 1


class TestCommandeCatalog:
    def test_liste_tous_les_roles(self):
        result = runner.invoke(app, ["catalog"])
        assert result.exit_code == 0
        for name in ("common", "users", "ssh_hardening", "firewall", "nginx", "docker"):
            assert name in result.stdout

    def test_detaille_un_role(self):
        result = runner.invoke(app, ["catalog", "common"])
        assert result.exit_code == 0
        assert "common_timezone" in result.stdout
        assert "Valeurs admises" in result.stdout

    def test_role_inconnu(self):
        result = runner.invoke(app, ["catalog", "kubernetes"])
        assert result.exit_code == 1
        assert "Rôle inconnu" in result.stdout + str(result.stderr)


class TestCommandeNew:
    def test_entretien_puis_generation(self, tmp_path: Path, monkeypatch):
        """`new` enchaîne entretien, écriture de forge.yml et génération."""
        from tests.scripted_prompter import BASE_ANSWERS, ScriptedPrompter

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "ansible_forge.cli.QuestionaryPrompter",
            lambda: ScriptedPrompter({**BASE_ANSWERS, "Nom du projet": "demo-cli"}),
        )
        result = runner.invoke(app, ["new"])
        assert result.exit_code == 0, result.stdout
        assert (tmp_path / "forge.yml").is_file()
        assert (tmp_path / "demo-cli" / "ansible.cfg").is_file()

    def test_dry_run_n_ecrit_pas_la_spec(self, tmp_path: Path, monkeypatch):
        from tests.scripted_prompter import BASE_ANSWERS, ScriptedPrompter

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "ansible_forge.cli.QuestionaryPrompter",
            lambda: ScriptedPrompter(BASE_ANSWERS),
        )
        result = runner.invoke(app, ["new", "--dry-run"])
        assert result.exit_code == 0, result.stdout
        assert not (tmp_path / "forge.yml").exists()
        assert list(tmp_path.iterdir()) == []


def test_le_projet_genere_est_rejouable(tmp_path: Path):
    """forge.yml embarqué dans le projet doit reproduire le même projet."""
    first = tmp_path / "premier"
    runner.invoke(app, ["generate", "--spec", str(MINIMAL_SPEC), "--output", str(first)])

    second = tmp_path / "second"
    result = runner.invoke(
        app, ["generate", "--spec", str(first / "forge.yml"), "--output", str(second)]
    )
    assert result.exit_code == 0, result.stdout

    for path in sorted(first.rglob("*")):
        if path.is_file():
            twin = second / path.relative_to(first)
            assert twin.read_bytes() == path.read_bytes(), f"{path} diffère"
