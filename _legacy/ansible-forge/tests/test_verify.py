"""Tests de la commande de vérification d'un projet généré."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ansible_forge import verify
from ansible_forge.cli import app
from ansible_forge.engine.planner import plan
from ansible_forge.engine.writer import write_artifacts
from ansible_forge.errors import ForgeError, ToolMissingError
from ansible_forge.spec_io import load_spec

runner = CliRunner()

MINIMAL_SPEC = Path(__file__).parent / "specs" / "minimal.yml"

#: Les outils Ansible ne tournent pas nativement sous Windows.
TOOLS_AVAILABLE = not verify.missing_tools()


def generated_project(tmp_path: Path) -> Path:
    """Génère le projet minimal et retourne sa racine."""
    project = tmp_path / "projet"
    write_artifacts(plan(load_spec(MINIMAL_SPEC)), project)
    return project


class TestDetectionDesOutils:
    def test_signale_les_outils_manquants(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert verify.missing_tools() == list(verify.REQUIRED_TOOLS)

    def test_leve_une_erreur_explicite(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(ToolMissingError) as excinfo:
            verify.require_tools()
        message = str(excinfo.value)
        assert "ansible-lint" in message
        assert "pip install" in message

    @pytest.mark.skipif(sys.platform != "win32", reason="Message propre à Windows.")
    def test_mentionne_wsl_sous_windows(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(ToolMissingError, match="WSL"):
            verify.require_tools()

    def test_ne_leve_rien_si_les_outils_sont_presents(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
        verify.require_tools()


class TestReconnaissanceDuProjet:
    def test_repertoire_inexistant(self, tmp_path: Path):
        with pytest.raises(ForgeError, match="introuvable"):
            verify.check_project(tmp_path / "absent")

    def test_repertoire_qui_n_est_pas_un_projet(self, tmp_path: Path):
        with pytest.raises(ForgeError, match="ne ressemble pas à un projet"):
            verify.check_project(tmp_path)

    def test_le_projet_est_reconnu_avant_la_recherche_des_outils(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Un répertoire invalide doit être signalé même sans ansible installé."""
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(ForgeError, match="ne ressemble pas à un projet"):
            verify.check_project(tmp_path)

    def test_outils_manquants_sur_un_projet_valide(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        project = generated_project(tmp_path)
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(ToolMissingError):
            verify.check_project(project)

    def test_environnements_detectes(self, tmp_path: Path):
        project = tmp_path / "projet"
        write_artifacts(
            plan(load_spec(Path(__file__).parent / "specs" / "multi_env.yml")), project
        )
        assert verify.environments_of(project) == ["dev", "prod", "staging"]


class TestCommandeCheck:
    def test_signale_un_repertoire_invalide(self, tmp_path: Path):
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1
        assert "ne ressemble pas à un projet" in result.stdout + str(result.stderr)

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="ansible-playbook et ansible-lint requis.")
    def test_projet_genere_conforme(self, tmp_path: Path):
        project = generated_project(tmp_path)
        result = runner.invoke(app, ["check", str(project)])
        assert result.exit_code == 0, result.stdout
        assert "réussie(s)" in result.stdout
