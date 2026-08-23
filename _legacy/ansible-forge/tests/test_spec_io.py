"""Tests de lecture/écriture de ``forge.yml``."""

from __future__ import annotations

from pathlib import Path

import pytest

from ansible_forge.errors import SpecFileError
from ansible_forge.models.spec import ProjectSpec
from ansible_forge.spec_io import dump_spec, load_spec, parse_spec, save_spec

MINIMAL_YAML = """\
project_name: demo-infra
groups:
  - name: webservers
    roles: [common]
environments:
  - name: dev
    hosts:
      webservers:
        - name: web-dev-01
          ansible_host: 192.168.56.11
"""


def test_round_trip_conserve_la_spec(spec: ProjectSpec, tmp_path: Path):
    path = save_spec(spec, tmp_path / "forge.yml")
    assert load_spec(path) == spec


def test_la_sauvegarde_est_deterministe(spec: ProjectSpec, tmp_path: Path):
    first = save_spec(spec, tmp_path / "a.yml").read_bytes()
    second = save_spec(spec, tmp_path / "b.yml").read_bytes()
    assert first == second


def test_la_sauvegarde_utilise_des_fins_de_ligne_lf(spec: ProjectSpec, tmp_path: Path):
    content = save_spec(spec, tmp_path / "forge.yml").read_bytes()
    assert b"\r\n" not in content


def test_l_entete_est_present_par_defaut(spec: ProjectSpec):
    assert dump_spec(spec).startswith("---\n# ---")


def test_le_marqueur_de_document_precede_l_entete(spec: ProjectSpec):
    """yamllint exige « --- » en première ligne, avant tout commentaire."""
    assert dump_spec(spec).splitlines()[0] == "---"


def test_l_entete_peut_etre_omis(spec: ProjectSpec):
    assert dump_spec(spec, header=False).startswith("spec_version:")


def test_l_ordre_des_cles_suit_le_modele(spec: ProjectSpec):
    body = dump_spec(spec, header=False)
    assert body.index("project_name:") < body.index("environments:")
    assert body.index("environments:") < body.index("groups:")


def test_une_spec_minimale_est_completee(tmp_path: Path):
    """Un forge.yml partiel doit produire la même spec qu'un forge.yml complet."""
    minimal = parse_spec(MINIMAL_YAML)
    complete = parse_spec(dump_spec(minimal, header=False))
    assert minimal == complete
    assert minimal.roles[0].options["timezone"] == "Europe/Paris"


def test_load_spec_signale_un_fichier_absent(tmp_path: Path):
    with pytest.raises(SpecFileError, match="introuvable"):
        load_spec(tmp_path / "absent.yml")


def test_load_spec_signale_un_repertoire(tmp_path: Path):
    with pytest.raises(SpecFileError, match="n'est pas un fichier"):
        load_spec(tmp_path)


def test_parse_spec_signale_un_yaml_invalide():
    with pytest.raises(SpecFileError, match="YAML invalide"):
        parse_spec("project_name: [unclosed\n")


def test_parse_spec_signale_un_fichier_vide():
    with pytest.raises(SpecFileError, match="est vide"):
        parse_spec("")


def test_parse_spec_signale_une_racine_non_dictionnaire():
    with pytest.raises(SpecFileError, match="dictionnaire YAML"):
        parse_spec("- a\n- b\n")


def test_parse_spec_liste_les_erreurs_de_validation():
    with pytest.raises(SpecFileError) as excinfo:
        parse_spec("project_name: Mauvais Nom\ngroups: []\nenvironments: []\n")
    message = str(excinfo.value)
    assert "project_name" in message
    assert "Nom de projet invalide" in message


def test_save_spec_cree_les_repertoires_parents(spec: ProjectSpec, tmp_path: Path):
    path = save_spec(spec, tmp_path / "nested" / "dir" / "forge.yml")
    assert path.is_file()
