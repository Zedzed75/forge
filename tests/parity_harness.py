"""Harnais commun aux comparaisons de parite (Ansible, Helm).

Un portage « a parite » se prouve de la meme facon quel que soit le domaine :
generer depuis la specification legacy convertie, puis comparer fichier par
fichier a l'instantane fige avant le portage.

Deux notions y sont explicites, et c'est ce qui rend la comparaison utile :

* les **ecarts d'arborescence assumes** — un fichier que forge ajoute
  (`.copier-answers.yml`) ou ne produit plus (`forge.yml`, remonte a la racine
  de la cible) ;
* les **substitutions volontaires** — un texte que forge change a dessein, par
  exemple le nom de l'outil dans le bandeau d'en-tete. Elles sont appliquees au
  contenu **attendu** : sans cela, un seul mot change ferait echouer la plupart
  des fichiers et noierait les vraies regressions.

Tout ecart hors de ces deux listes fait echouer le test, en nommant les fichiers
en cause — jamais leur contenu integral (regle d'economie de contexte).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge import pipeline
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec


@dataclass(frozen=True)
class Ecarts:
    """Ce qu'un domaine s'autorise a changer par rapport a son instantane."""

    #: Fichiers que forge ajoute et que le legacy ne produisait pas.
    ajouts: frozenset[str] = frozenset()

    #: Fichiers que le legacy produisait et que forge ne produit plus.
    retraits: frozenset[str] = frozenset()

    #: Substitutions appliquees au contenu **attendu** avant comparaison.
    substitutions: tuple[tuple[str, str], ...] = ()

    #: Prefixe des chemins de l'instantane a retirer, quand le legacy ecrivait
    #: a la racine ce que forge ecrit sous un sous-repertoire de domaine.
    racine_legacy: str = ""


@dataclass
class Comparaison:
    """Resultat d'une comparaison, en termes actionnables."""

    manquants: list[str] = field(default_factory=list)
    en_trop: list[str] = field(default_factory=list)
    differents: list[str] = field(default_factory=list)

    @property
    def conforme(self) -> bool:
        return not (self.manquants or self.en_trop or self.differents)


def fichiers(racine: Path) -> dict[str, Path]:
    """Chemins relatifs -> chemins absolus, pour toute l'arborescence."""
    if not racine.is_dir():
        return {}
    return {
        chemin.relative_to(racine).as_posix(): chemin
        for chemin in racine.rglob("*")
        if chemin.is_file()
    }


def manager_du_domaine(module_plugin: str) -> ForgeManager:
    """Gestionnaire ne contenant que le plugin du domaine compare."""
    instance = ForgeManager()
    instance.register_module(module_plugin)
    return instance


def generer(
    donnees: dict[str, Any], module_plugin: str, cible: Path, sous_repertoire: str
) -> Path:
    """Genere le projet et retourne le repertoire du domaine."""
    manager = manager_du_domaine(module_plugin)
    modele = validate_spec(donnees, manager)
    pipeline.generate(donnees, modele, manager, cible)
    return cible / sous_repertoire


def contenu_attendu(chemin: Path, ecarts: Ecarts) -> bytes:
    """Contenu de reference, substitutions volontaires appliquees."""
    brut = chemin.read_bytes()
    if not ecarts.substitutions:
        return brut
    try:
        texte = brut.decode("utf-8")
    except UnicodeDecodeError:  # pragma: no cover - aucun binaire attendu
        return brut
    for avant, apres in ecarts.substitutions:
        texte = texte.replace(avant, apres)
    return texte.encode("utf-8")


def comparer(produit: Path, attendu: Path, ecarts: Ecarts) -> Comparaison:
    """Compare l'arborescence produite a l'instantane, ecarts assumes deduits."""
    fichiers_produits = fichiers(produit)
    fichiers_attendus = fichiers(attendu)
    if ecarts.racine_legacy:
        prefixe = ecarts.racine_legacy.rstrip("/") + "/"
        fichiers_attendus = {
            nom[len(prefixe) :] if nom.startswith(prefixe) else nom: chemin
            for nom, chemin in fichiers_attendus.items()
        }

    resultat = Comparaison(
        manquants=sorted(
            set(fichiers_attendus) - set(fichiers_produits) - ecarts.retraits
        ),
        en_trop=sorted(set(fichiers_produits) - set(fichiers_attendus) - ecarts.ajouts),
    )
    resultat.differents = [
        nom
        for nom in sorted(set(fichiers_produits) & set(fichiers_attendus))
        if fichiers_produits[nom].read_bytes()
        != contenu_attendu(fichiers_attendus[nom], ecarts)
    ]
    return resultat
