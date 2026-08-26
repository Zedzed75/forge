"""Controles croises qu'un plugin sur deux refaisait a l'identique.

Un sous-modele pydantic ne voit que **sa** section : il ne peut pas verifier que
les environnements qu'il cite existent dans `service.environments`, qui vit dans
le bloc partage. Chaque domaine a donc ecrit ce controle, et les quatre versions
etaient les memes a un nom de section pres.

Ce module n'ajoute aucune connaissance de domaine au coeur : il ne parle que de
`service.environments`, qui est du coeur, et de cles fournies par l'appelant.
C'est la difference avec un `forge_consistency` — celui-la porte sur des fichiers
ecrits, celui-ci sur la specification, avant tout rendu.

Un plugin reste libre de ne pas s'en servir : le hook `forge_check_spec` ne
demande rien d'autre qu'une liste d'`Issue`.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from forge.plugins_api.types import Issue


def unknown_environments(
    spec: Any, domain: str, sections: Mapping[str, Iterable[str]]
) -> list[Issue]:
    """Refuse toute cle d'environnement absente de `service.environments`.

    `sections` associe un chemin de section — `helm.environments`,
    `ansible.hosts` — aux noms d'environnement qu'elle cite. Un domaine qui en
    declare plusieurs voit les sections fautives regroupees par environnement :
    citer `dev` dans deux sections produit un seul constat, qui les nomme toutes
    les deux, plutot que deux constats a lire separement.

    L'ordre du resultat est deterministe : il est affiche tel quel.
    """
    connus = {env.name for env in spec.service.environments}
    declares = ", ".join(env.name for env in spec.service.environments)

    citantes: dict[str, list[str]] = {}
    for section, noms in sections.items():
        for nom in noms:
            if nom not in connus:
                citantes.setdefault(nom, []).append(section)

    issues: list[Issue] = []
    for nom in sorted(citantes):
        sujet = " et ".join(citantes[nom])
        verbe = "citent" if len(citantes[nom]) > 1 else "cite"
        issues.append(
            Issue(
                level="error",
                message=(
                    f"{sujet} {verbe} l'environnement '{nom}', absent de "
                    f"service.environments (declares : {declares})."
                ),
                hint=(
                    f"Ajoutez un environnement '{nom}' a service.environments, ou "
                    f"corrigez la cle '{nom}' dans {sujet}."
                ),
                domains=(domain,),
            )
        )
    return issues
