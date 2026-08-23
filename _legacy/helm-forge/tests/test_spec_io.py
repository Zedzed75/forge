"""Tests de lecture et d'écriture de ``forge.yml``.

L'aller-retour doit être fidèle : c'est ce qui garantit qu'une génération est
rejouable à l'identique des mois plus tard, sans reposer aucune question.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helm_forge.errors import SpecError, SpecNotFoundError
from helm_forge.models import ProjectSpec
from helm_forge.spec_io import dumps, load_spec, loads, save_spec


def test_aller_retour_fidele(full_spec: ProjectSpec) -> None:
    """spec -> YAML -> spec doit redonner exactement le même objet."""
    assert loads(dumps(full_spec)) == full_spec


def test_aller_retour_stable_sur_deux_passes(full_spec: ProjectSpec) -> None:
    """Le second vidage doit être identique au premier, octet pour octet."""
    once = dumps(full_spec)
    twice = dumps(loads(once))
    assert once == twice


def test_vidage_deterministe(minimal_spec: ProjectSpec) -> None:
    assert dumps(minimal_spec) == dumps(minimal_spec)


def test_entete_present_et_ordre_des_cles_preserve(minimal_spec: ProjectSpec) -> None:
    text = dumps(minimal_spec)
    assert text.startswith("# ---")
    assert "forge.yml" in text
    # L'ordre suit la déclaration du modèle, jamais l'ordre alphabétique.
    assert text.index("schema_version") < text.index("app:")
    assert text.index("app:") < text.index("environments:")


def test_ecriture_en_fins_de_ligne_lf(tmp_path: Path, minimal_spec: ProjectSpec) -> None:
    """Le fichier doit être en LF sur toute plateforme, sinon les golden files
    et helm lint divergent entre machines."""
    path = tmp_path / "forge.yml"
    save_spec(minimal_spec, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.startswith(b"# ---")


def test_ecriture_cree_les_repertoires_manquants(
    tmp_path: Path, minimal_spec: ProjectSpec
) -> None:
    path = tmp_path / "a" / "b" / "forge.yml"
    save_spec(minimal_spec, path)
    assert path.is_file()


def test_relecture_depuis_le_disque(tmp_path: Path, full_spec: ProjectSpec) -> None:
    path = tmp_path / "forge.yml"
    save_spec(full_spec, path)
    assert load_spec(path) == full_spec


def test_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(SpecNotFoundError):
        load_spec(tmp_path / "absent.yml")


def test_yaml_invalide() -> None:
    with pytest.raises(SpecError) as exc:
        loads("app: [non ferme")
    assert "illisible" in str(exc.value)


def test_document_vide() -> None:
    with pytest.raises(SpecError) as exc:
        loads("")
    assert "vide" in str(exc.value)


def test_racine_non_objet() -> None:
    with pytest.raises(SpecError) as exc:
        loads("- un\n- deux\n")
    assert "objet YAML" in str(exc.value)


def test_version_de_schema_inconnue() -> None:
    with pytest.raises(SpecError) as exc:
        loads("schema_version: 99\napp:\n  name: a\n  description: x\n")
    assert "schema_version" in str(exc.value)


def test_specification_invalide_donne_une_erreur_claire() -> None:
    with pytest.raises(SpecError) as exc:
        loads("app:\n  name: Majuscules\n  description: x\n")
    assert "invalide" in str(exc.value)


def test_cle_inconnue_dans_le_fichier() -> None:
    """Une faute de frappe ne doit jamais être ignorée silencieusement."""
    text = (
        "app:\n  name: shop\n  description: x\n"
        "environments:\n  - name: dev\n"
        "components:\n  - name: api\n"
        "coucou: 1\n"
    )
    with pytest.raises(SpecError):
        loads(text)
