"""Parite du plugin Ansible avec le generateur d'origine.

Le portage de la phase 3 est un portage **a parite** : pour une meme
specification, le plugin doit produire le meme contenu que le generateur legacy,
fige dans `tests/parity/ansible/` avant tout portage.

Les seuls ecarts tolerables sont ceux inscrits dans `MIGRATION.md` §7 et repris
ici sous forme executable : tout autre ecart fait echouer le test, avec la liste
des fichiers en cause — jamais leur contenu integral (regle d'economie de
contexte de CLAUDE.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from tests.conftest import REPO_ROOT
from tests.legacy_spec import convertir_fichier

#: Module du plugin Ansible, tel que `FORGE_PLUGINS` l'attend.
ANSIBLE_PLUGIN = "forge.plugins.ansible.plugin"

#: Instantane de parite, produit par tests/parity/snapshot_ansible.py.
PARITY_DIR = REPO_ROOT / "tests" / "parity" / "ansible"

#: Specifications legacy correspondantes.
LEGACY_SPECS = REPO_ROOT / "_legacy" / "ansible-forge" / "tests" / "specs"
LEGACY_EXEMPLE = REPO_ROOT / "_legacy" / "ansible-forge" / "examples" / "forge.yml"

#: Ecart de parite 1 (MIGRATION.md §7) : copier exige un fichier de reponses.
AJOUTS_ATTENDUS = frozenset({".copier-answers.yml"})

#: Ecart de parite 3 : la specification unifiee vit a la racine du depot cible,
#: plus dans le sous-repertoire du domaine.
RETRAITS_ATTENDUS = frozenset({"forge.yml"})

#: Ecart de parite 7 : le bandeau d'en-tete nomme l'outil qui a genere le
#: fichier. Il ne peut pas continuer d'annoncer « ansible-forge ». La
#: substitution est appliquee au contenu ATTENDU avant comparaison : sans cela,
#: cet unique changement de mot ferait echouer la quasi-totalite des fichiers et
#: noierait les vraies regressions.
SUBSTITUTIONS = (("par ansible-forge à partir de", "par forge à partir de"),)


def reference(chemin: Path) -> bytes:
    """Contenu attendu, substitutions volontaires appliquees."""
    contenu = chemin.read_bytes()
    try:
        texte = contenu.decode("utf-8")
    except UnicodeDecodeError:  # pragma: no cover - aucun binaire attendu
        return contenu
    for avant, apres in SUBSTITUTIONS:
        texte = texte.replace(avant, apres)
    return texte.encode("utf-8")


def cas_de_parite() -> list[str]:
    """Noms des cas figes dans l'instantane, tries."""
    if not PARITY_DIR.is_dir():
        return []
    return sorted(p.name for p in PARITY_DIR.iterdir() if p.is_dir())


CAS = cas_de_parite()


def spec_legacy(cas: str) -> Path:
    """Specification legacy correspondant a un cas de l'instantane."""
    return LEGACY_EXEMPLE if cas == "exemple" else LEGACY_SPECS / f"{cas}.yml"


def fichiers(racine: Path) -> dict[str, Path]:
    """Chemins relatifs -> chemins absolus, pour toute l'arborescence."""
    return {
        chemin.relative_to(racine).as_posix(): chemin
        for chemin in racine.rglob("*")
        if chemin.is_file()
    }


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(ANSIBLE_PLUGIN)
    return instance


def generer(cas: str, cible: Path) -> Path:
    """Genere le projet Ansible du cas `cas` et retourne son repertoire."""
    manager = _manager()
    data = convertir_fichier(spec_legacy(cas))
    modele = validate_spec(data, manager)
    pipeline.generate(data, modele, manager, cible)
    return cible / "ansible"


@pytest.mark.skipif(not CAS, reason="instantane de parite absent")
@pytest.mark.parametrize("cas", CAS, ids=CAS)
def test_les_memes_fichiers_sont_produits(cas, tmp_path):
    """L'arborescence doit correspondre, aux ecarts documentes pres."""
    produit = fichiers(generer(cas, tmp_path))
    attendu = fichiers(PARITY_DIR / cas)

    manquants = sorted(set(attendu) - set(produit) - RETRAITS_ATTENDUS)
    en_trop = sorted(set(produit) - set(attendu) - AJOUTS_ATTENDUS)
    assert not manquants, f"fichiers manquants ({len(manquants)}) : {', '.join(manquants)}"
    assert not en_trop, f"fichiers en trop ({len(en_trop)}) : {', '.join(en_trop)}"


@pytest.mark.skipif(not CAS, reason="instantane de parite absent")
@pytest.mark.parametrize("cas", CAS, ids=CAS)
def test_le_contenu_est_identique(cas, tmp_path):
    """Le contenu doit correspondre octet pour octet sur les fichiers communs."""
    produit = fichiers(generer(cas, tmp_path))
    attendu = fichiers(PARITY_DIR / cas)

    differents = [
        nom
        for nom in sorted(set(produit) & set(attendu))
        if produit[nom].read_bytes() != reference(attendu[nom])
    ]
    assert not differents, (
        f"{len(differents)} fichier(s) different(s) du generateur d'origine : "
        f"{', '.join(differents)}"
    )
