"""Parite du plugin Ansible avec le generateur d'origine.

Le portage de la phase 3 est un portage **a parite** : pour une meme
specification, le plugin doit produire le meme contenu que le generateur legacy,
fige dans `tests/parity/ansible/` avant tout portage.

Les seuls ecarts tolerables sont ceux inscrits dans `MIGRATION.md` §7 et repris
ici sous forme executable, dans `ECARTS` : tout autre ecart fait echouer le test,
avec la liste des fichiers en cause — jamais leur contenu integral (regle
d'economie de contexte de CLAUDE.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from tests.legacy_spec import convertir_fichier
from tests.parity_harness import Ecarts, comparer, generer

#: Module du plugin Ansible, tel que `FORGE_PLUGINS` l'attend.
ANSIBLE_PLUGIN = "forge.plugins.ansible.plugin"

#: Instantane de parite, produit par tests/parity/snapshot_ansible.py.
PARITY_DIR = REPO_ROOT / "tests" / "parity" / "ansible"

#: Specifications legacy correspondantes.
LEGACY_SPECS = REPO_ROOT / "_legacy" / "ansible-forge" / "tests" / "specs"
LEGACY_EXEMPLE = REPO_ROOT / "_legacy" / "ansible-forge" / "examples" / "forge.yml"

#: Ecart de parite 11 : `.copier-answers.yml` est exclu du linter. Ce fichier
#: n'existait pas dans le legacy ; sa mise en forme est celle de copier, et il
#: faisait echouer `ansible-lint` sur 255 violations de style YAML alors que le
#: projet Ansible lui-meme est propre.
_EXCLUDE_LEGACY = "exclude_paths:\n  - .venv/\n  - .github/\n"
_EXCLUDE_FORGE = (
    "exclude_paths:\n  - .venv/\n  - .github/\n"
    "  # Fichier de réponses de copier : c'est la plomberie de la génération, pas du\n"
    "  # code Ansible. Sa mise en forme est celle de copier, pas celle du projet.\n"
    "  - .copier-answers.yml\n"
)

#: Ecarts assumes, tous inscrits dans MIGRATION.md §7.
ECARTS = Ecarts(
    # Ecart 1 : copier exige un fichier de reponses par domaine.
    ajouts=frozenset({".copier-answers.yml"}),
    # Ecart 3 : la specification unifiee vit a la racine du depot cible.
    retraits=frozenset({"forge.yml"}),
    substitutions=(
        # Ecart 7 : l'outil a change de nom.
        ("par ansible-forge à partir de", "par forge à partir de"),
        # Ecart 11.
        (_EXCLUDE_LEGACY, _EXCLUDE_FORGE),
    ),
)


def cas_de_parite() -> list[str]:
    """Noms des cas figes dans l'instantane, tries."""
    if not PARITY_DIR.is_dir():
        return []
    return sorted(p.name for p in PARITY_DIR.iterdir() if p.is_dir())


CAS = cas_de_parite()


def spec_legacy(cas: str) -> Path:
    """Specification legacy correspondant a un cas de l'instantane."""
    return LEGACY_EXEMPLE if cas == "exemple" else LEGACY_SPECS / f"{cas}.yml"


def _generer(cas: str, cible: Path) -> Path:
    return generer(convertir_fichier(spec_legacy(cas)), ANSIBLE_PLUGIN, cible, "ansible")


@pytest.mark.skipif(not CAS, reason="instantane de parite absent")
@pytest.mark.parametrize("cas", CAS, ids=CAS)
def test_les_memes_fichiers_sont_produits(cas, tmp_path):
    """L'arborescence doit correspondre, aux ecarts documentes pres."""
    resultat = comparer(_generer(cas, tmp_path), PARITY_DIR / cas, ECARTS)
    assert not resultat.manquants, (
        f"fichiers manquants ({len(resultat.manquants)}) : "
        f"{', '.join(resultat.manquants)}"
    )
    assert not resultat.en_trop, (
        f"fichiers en trop ({len(resultat.en_trop)}) : {', '.join(resultat.en_trop)}"
    )


@pytest.mark.skipif(not CAS, reason="instantane de parite absent")
@pytest.mark.parametrize("cas", CAS, ids=CAS)
def test_le_contenu_est_identique(cas, tmp_path):
    """Le contenu doit correspondre octet pour octet sur les fichiers communs."""
    resultat = comparer(_generer(cas, tmp_path), PARITY_DIR / cas, ECARTS)
    assert not resultat.differents, (
        f"{len(resultat.differents)} fichier(s) different(s) du generateur "
        f"d'origine : {', '.join(resultat.differents)}"
    )
