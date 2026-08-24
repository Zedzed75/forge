"""Tests golden : meme specification, meme sortie, octet pour octet.

Harnais repris d'ansible-forge (MIGRATION.md §3) et adapte a une sortie ecrite
par copier. Chaque fichier de `tests/specs/` est rendu puis compare a
`tests/golden/<nom-de-spec>/`.

Re-benediction apres un changement **voulu** de gabarit :

    uv run pytest tests/test_golden.py --regen-golden

Les deux lignes volatiles du fichier de reponses copier (`_commit`, `_src_path`)
sont neutralisees avant comparaison : elles dependent du poste et du clone
temporaire, pas du gabarit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins_api.manager import ForgeManager
from tests.conftest import (
    DEMO_PLUGIN,
    GOLDEN_DIR,
    REPO_ROOT,
    bless,
    load_case,
    spec_files,
    stable_text,
    tree_files,
)

#: Cas de test : un par specification de reference.
CASES = spec_files()

#: Fichier du gabarit demo volontairement stocke en CRLF (cf. .gitattributes).
TEMOIN_CRLF = "fins-de-ligne.txt"


def _render(spec_path: Path, target: Path) -> Path:
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    data, model = load_case(spec_path, manager)
    pipeline.generate(data, model, manager, target)
    return target


@pytest.mark.parametrize("spec_path", CASES, ids=[path.stem for path in CASES])
def test_la_sortie_correspond_a_la_reference(spec_path, tmp_path, regen_golden):
    rendu = _render(spec_path, tmp_path / "rendu")
    reference = GOLDEN_DIR / spec_path.stem

    if regen_golden:
        bless(rendu, reference)
        pytest.skip(f"reference re-benie : {reference.name}")

    assert reference.is_dir(), (
        f"reference absente : {reference}. Lancez pytest --regen-golden apres "
        "avoir verifie que la sortie est correcte."
    )

    attendus = tree_files(reference)
    obtenus = tree_files(rendu)
    assert obtenus == attendus, (
        f"arborescence differente : en trop {sorted(set(obtenus) - set(attendus))}, "
        f"manquants {sorted(set(attendus) - set(obtenus))}"
    )

    # Comparaison sur les octets : `read_text` traduirait les CRLF a la lecture
    # et rendrait le harnais aveugle a une regression de fins de ligne.
    differents = [
        nom
        for nom in attendus
        if stable_text(rendu / nom).encode("utf-8") != (reference / nom).read_bytes()
    ]
    assert not differents, f"contenu different : {', '.join(differents)}"


@pytest.mark.parametrize("spec_path", CASES, ids=[path.stem for path in CASES])
def test_deux_rendus_successifs_sont_identiques(spec_path, tmp_path):
    """Le determinisme ne depend ni de l'ordre des dictionnaires ni de l'horloge."""
    premier = tree_files(_render(spec_path, tmp_path / "un"))
    second = tree_files(_render(spec_path, tmp_path / "deux"))
    assert premier == second
    for nom in premier:
        assert stable_text(tmp_path / "un" / nom) == stable_text(tmp_path / "deux" / nom)


def test_le_filtrage_de_fichier_par_if_supprime_bien_le_fichier(tmp_path):
    """Un segment de chemin rendu vide fait disparaitre le fichier (MIGRATION §2.1)."""
    rendu = _render(next(path for path in CASES if path.stem == "demo-complet"), tmp_path)
    assert (rendu / "demo" / "widgets" / "cpu" / "detail.yml").is_file()
    assert not (rendu / "demo" / "widgets" / "requetes").exists()


def test_les_yields_imbriques_produisent_le_produit_cartesien(tmp_path):
    """Un yield par segment : environnements x widgets, la variable parente restant lue."""
    rendu = _render(next(path for path in CASES if path.stem == "demo-complet"), tmp_path)
    fichiers = tree_files(rendu / "demo" / "environments")
    assert fichiers == [
        "dev/cpu.yml",
        "dev/requetes.yml",
        "prod/cpu.yml",
        "prod/requetes.yml",
    ]


def test_la_normalisation_s_applique_a_un_rendu_copier_reel(tmp_path):
    """Preuve de bout en bout : un gabarit en CRLF ressort en LF.

    Le fichier temoin porte une exception dans le `.gitattributes` du depot ;
    sans elle, git le normaliserait au checkout et le test s'auto-annulerait en
    silence. On verifie donc d'abord qu'il a bien conserve ses CRLF.
    """
    source = REPO_ROOT / "src" / "forge" / "plugins" / "demo" / "template" / TEMOIN_CRLF
    assert source.is_file(), f"fichier temoin absent : {source}"
    if b"\r\n" not in source.read_bytes():
        pytest.fail(
            f"{source} a perdu ses CRLF : l'exception du .gitattributes a saute, "
            "le test ne prouve plus rien."
        )

    rendu = _render(next(path for path in CASES if path.stem == "demo-complet"), tmp_path)
    livre = rendu / "demo" / TEMOIN_CRLF
    assert livre.is_file()
    assert b"\r" not in livre.read_bytes()


def test_un_filtre_de_plugin_est_bien_applique(tmp_path):
    """Preuve que `FORGE_PLUGIN_JINJA` charge bien les filtres du domaine."""
    rendu = _render(next(path for path in CASES if path.stem == "demo-complet"), tmp_path)
    readme = (rendu / "demo" / "README.md").read_text(encoding="utf-8")
    assert "BOUTIQUE" in readme          # filtre shout
    assert "== boutique ==" in readme    # global demo_banner
