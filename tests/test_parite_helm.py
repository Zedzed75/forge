"""Parite du plugin Helm avec le generateur d'origine.

La phase 4 n'est pas un portage a parite comme la phase 3 : le modele legacy
etait tres en avance sur ses gabarits, et neuf familles de composants sont
**creees** plutot que portees (cf. MIGRATION.md, arbitrages du portage Helm).

La parite se mesure donc sur ce que le legacy produisait reellement : les
32 fichiers de `tests/parity/helm/`. Les neuf nouvelles familles, elles, sont
prouvees autrement — par `helm lint`, `helm template`, `kubeconform -strict` et
des references golden neuves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from tests.legacy_spec import convertir_fichier_helm
from tests.parity_harness import Ecarts, comparer, generer

#: Module du plugin Helm, tel que `FORGE_PLUGINS` l'attend.
HELM_PLUGIN = "forge.plugins.helm.plugin"

#: Instantane de parite, produit par tests/parity/snapshot_helm.py.
PARITY_DIR = REPO_ROOT / "tests" / "parity" / "helm"

#: Specifications legacy correspondantes.
LEGACY_SPECS = REPO_ROOT / "_legacy" / "helm-forge" / "tests" / "specs"

#: Ecarts assumes, tous inscrits dans MIGRATION.md §7.
ECARTS = Ecarts(
    # Ecart 1 : copier exige un fichier de reponses par domaine.
    ajouts=frozenset({".copier-answers.yml"}),
    # Ecart 3 : la specification unifiee vit a la racine du depot cible.
    # Ecart 10 (Helm) : la sentinelle `@spec` du planner disparait.
    retraits=frozenset({"forge.yml"}),
    # Ecart 7 : le bandeau nomme l'outil qui a genere le fichier. Continuer
    # d'annoncer « helm-forge » serait faux.
    substitutions=(
        ("généré par helm-forge", "généré par forge"),
        ("par [helm-forge](https://github.com/)", "par [forge](https://github.com/)"),
        ("helm-forge generate --spec forge.yml --output .", "forge generate"),
    ),
)


def cas_de_parite() -> list[str]:
    """Noms des cas figes dans l'instantane, tries."""
    if not PARITY_DIR.is_dir():
        return []
    return sorted(p.name for p in PARITY_DIR.iterdir() if p.is_dir())


CAS = cas_de_parite()


def _generer(cas: str, cible: Path) -> Path:
    donnees = convertir_fichier_helm(LEGACY_SPECS / f"{cas}.yml")
    return generer(donnees, HELM_PLUGIN, cible, "helm")


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
