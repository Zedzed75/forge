"""Tests du rendu : normalisation, fichiers de niveau depot, comparaison."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.errors import RenderError
from forge.plugins_api.types import DomainInfo
from forge.render import scaffold
from forge.render.copier_runner import (
    normalise_text,
    normalise_tree,
    rewrite_src_path,
    template_root,
)
from forge.render.diff import diff_trees

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("a\r\nb\r\n", "a\nb\n"),
        ("a\rb", "a\nb\n"),
        ("a   \nb\t\n", "a\nb\n"),
        ("a\n\n\n\nb\n", "a\n\nb\n"),
        ("a", "a\n"),
        ("a\n\n\n", "a\n"),
        ("", ""),
    ],
)
def test_normalise_text_prend_l_union_des_deux_normalisations_legacy(brut, attendu):
    assert normalise_text(brut) == attendu


def test_normalise_tree_epargne_le_fichier_de_reponses(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("a   \n\n\n\nb\n", encoding="utf-8")
    (tmp_path / "fichier.yml").write_text("a   \n\n\n\nb\n", encoding="utf-8")
    assert normalise_tree(tmp_path) == 1
    assert (tmp_path / ".copier-answers.yml").read_text(encoding="utf-8") == "a   \n\n\n\nb\n"
    assert (tmp_path / "fichier.yml").read_text(encoding="utf-8") == "a\n\nb\n"


def test_normalise_tree_ignore_un_binaire(tmp_path):
    (tmp_path / "image.bin").write_bytes(b"\x00\x01\x02\xff")
    assert normalise_tree(tmp_path) == 0
    assert (tmp_path / "image.bin").read_bytes() == b"\x00\x01\x02\xff"


# ---------------------------------------------------------------------------
# Racine de gabarit
# ---------------------------------------------------------------------------


def test_la_racine_de_gabarit_porte_le_copier_yml():
    assert (template_root() / "copier.yml").is_file()


def test_une_racine_forcee_sans_copier_yml_est_refusee(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(tmp_path))
    with pytest.raises(RenderError, match="copier.yml"):
        template_root()


def test_rewrite_src_path_delie_le_projet_de_son_poste_d_origine(tmp_path):
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(
        "_commit: v1\n_src_path: C:\\ailleurs\\forge\ndomain: {}\n", encoding="utf-8"
    )
    rewrite_src_path(answers, Path("/nouvelle/racine"))
    contenu = answers.read_text(encoding="utf-8")
    assert "_src_path: /nouvelle/racine" in contenu
    assert "_commit: v1" in contenu


def test_rewrite_src_path_ne_touche_a_rien_si_la_racine_est_deja_la_bonne(tmp_path):
    """Recrire une valeur equivalente salirait la cible, et copier refuse un depot sale."""
    answers = tmp_path / ".copier-answers.yml"
    origine = f"_src_path: {tmp_path}\n"
    answers.write_text(origine, encoding="utf-8")
    rewrite_src_path(answers, tmp_path)
    assert answers.read_text(encoding="utf-8") == origine


def test_rewrite_src_path_ignore_un_fichier_absent(tmp_path):
    rewrite_src_path(tmp_path / "absent.yml", Path("/x"))  # ne doit pas lever


# ---------------------------------------------------------------------------
# Fichiers de niveau depot
# ---------------------------------------------------------------------------


def test_le_coeur_ecrit_le_minimum_non_domaine(tmp_path, spec_data):
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
    written = scaffold.write_repo_files(tmp_path, spec_data, infos)
    noms = {path.name for path in written}
    assert noms == {"forge.yml", "README.md", ".gitattributes"}
    assert "eol=lf" in (tmp_path / ".gitattributes").read_text(encoding="utf-8")


def test_le_readme_indexe_les_domaines(tmp_path, spec_data):
    infos = [DomainInfo(name="demo", title="Demo", summary="domaine de demonstration")]
    scaffold.write_repo_files(tmp_path, spec_data, infos)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| Demo | `demo/` | domaine de demonstration |" in readme
    assert "boutique" in readme
    assert "dev, prod" in readme


# ---------------------------------------------------------------------------
# Comparaison d'arborescences
# ---------------------------------------------------------------------------


def _ecrire(root: Path, chemins: dict[str, str]) -> Path:
    for nom, contenu in chemins.items():
        path = root / nom
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contenu, encoding="utf-8", newline="\n")
    return root


def test_deux_arborescences_identiques_ne_montrent_aucun_ecart(tmp_path):
    a = _ecrire(tmp_path / "a", {"x.yml": "1\n"})
    b = _ecrire(tmp_path / "b", {"x.yml": "1\n"})
    ecart = diff_trees("demo", a, b)
    assert ecart.empty
    assert ecart.summary().endswith("a jour")


def test_le_diff_classe_ajouts_suppressions_et_modifications(tmp_path):
    a = _ecrire(tmp_path / "a", {"garde.yml": "1\n", "parti.yml": "x\n"})
    b = _ecrire(tmp_path / "b", {"garde.yml": "2\n", "nouveau.yml": "y\n"})
    ecart = diff_trees("demo", a, b)
    assert ecart.added == ["nouveau.yml"]
    assert ecart.removed == ["parti.yml"]
    assert ecart.modified == [("garde.yml", 1)]
    assert not ecart.empty


def test_le_diff_ignore_le_fichier_de_reponses(tmp_path):
    a = _ecrire(tmp_path / "a", {".copier-answers.yml": "_commit: 1\n"})
    b = _ecrire(tmp_path / "b", {".copier-answers.yml": "_commit: 2\n"})
    assert diff_trees("demo", a, b).empty


def test_le_diff_ne_cite_jamais_le_contenu_des_fichiers(tmp_path):
    a = _ecrire(tmp_path / "a", {"secret.yml": "motdepasse\n"})
    b = _ecrire(tmp_path / "b", {"secret.yml": "autre\n"})
    resume = diff_trees("demo", a, b).summary()
    assert "motdepasse" not in resume and "autre" not in resume
