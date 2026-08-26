"""Providers Terraform employes par les familles du catalogue.

Une seule table, pour que `required_providers` du module et celui de chaque
racine d'environnement declarent exactement les memes sources et les memes
contraintes de version. Deux declarations divergentes ne produisent pas
d'erreur : Terraform resout l'intersection, et l'ecart ne se voit qu'au jour ou
elle devient vide.

Les contraintes sont en `~>` : elles autorisent les correctifs et les versions
mineures, jamais un changement majeur. Une contrainte sans borne haute laisse
une version majeure future casser le projet sans qu'on ait rien change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """Un provider tel que declare dans un bloc `required_providers`."""

    #: Nom local du provider dans la configuration (`kubernetes`, `random`...).
    name: str

    #: Adresse dans le registre (`hashicorp/kubernetes`).
    source: str

    #: Contrainte de version.
    version: str

    #: Raison de sa presence, reprise en commentaire dans le fichier genere.
    reason: str


#: Table indexee par nom local. L'ordre est alphabetique : c'est celui dans
#: lequel `terraform fmt` laisse les entrees de `required_providers`, et il rend
#: la sortie deterministe quel que soit l'ordre des familles retenues.
PROVIDERS: dict[str, Provider] = {
    "kubernetes": Provider(
        name="kubernetes",
        source="hashicorp/kubernetes",
        version="~> 2.32",
        reason="pose les objets Kubernetes qui accueillent le service",
    ),
    "random": Provider(
        name="random",
        source="hashicorp/random",
        version="~> 3.6",
        reason="engendre les mots de passe, jamais ecrits dans la specification",
    ),
    "tls": Provider(
        name="tls",
        source="hashicorp/tls",
        version="~> 4.0",
        reason="fabrique les certificats auto-signes des environnements de travail",
    ),
}


def resolve(names: set[str]) -> list[Provider]:
    """Providers correspondant a `names`, tries par nom local.

    Leve `KeyError` sur un nom inconnu : une famille qui reclame un provider
    absent de la table est une erreur de programmation du plugin, pas une
    erreur de l'utilisateur.
    """
    return [PROVIDERS[nom] for nom in sorted(names)]
