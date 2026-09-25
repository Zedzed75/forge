"""Contraintes de version des collections Galaxy exigées par le catalogue.

Une collection est décrite **ici et nulle part ailleurs**. Un `RoleDefinition`
ne nomme qu'une collection, jamais une version : deux rôles qui dépendent de la
même collection ne peuvent donc pas se contredire sur la version attendue.

Politique retenue (DESIGN.md §8 Q9) : **plancher et plafond de majeure**.

- Le plancher est la plus ancienne version dont on sait qu'elle fournit tout ce
  que les gabarits émettent. Quand personne ne l'a vérifiée, c'est la version
  contre laquelle la CI valide : forge ne prétend pas savoir ce qu'il n'a pas
  testé, et le plancher se descend le jour où quelqu'un fait la vérification.
- Le plafond est la majeure suivant celle contre laquelle la CI valide. Sans
  lui, un projet généré aujourd'hui et installé dans six mois récupère la
  majeure suivante et casse sur un module retiré — exactement ce qui est arrivé
  à la CI de forge avec `community.postgresql` 5.0.0.

Le prix du plafond est assumé : forge doit suivre les majeures des collections
qu'il nomme, sinon les projets générés vieillissent. La procédure de montée est
la même que pour les outils épinglés dans `.github/workflows/ci.yml` : monter la
version validée en CI, monter `max_major` ici, corriger les gabarits si la
majeure a retiré quelque chose, et livrer la montée dans son propre commit.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from forge.errors import SpecValidationError


@dataclass(frozen=True)
class CollectionRequirement:
    """Une collection Galaxy et l'intervalle de versions que forge accepte.

    Attributs :
        name: nom pleinement qualifié de la collection (`namespace.nom`).
        floor: plus ancienne version acceptée, incluse.
        max_major: première majeure **refusée** ; le plafond est exclusif.
        validated: version contre laquelle la CI de forge valide réellement les
            projets générés, citée en commentaire dans ``requirements.yml``.
        reason: justification du plancher, reprise telle quelle en commentaire
            du fichier généré. Une phrase, au présent.
    """

    name: str
    floor: str
    max_major: int
    validated: str
    reason: str

    @property
    def version(self) -> str:
        """Contrainte au format attendu par ``ansible-galaxy``.

        Exemple : ``>=3.13.0,<6.0.0``. Les deux bornes sont toujours écrites :
        une contrainte sans plafond ne protège de rien.
        """
        return f">={self.floor},<{self.max_major}.0.0"


#: Table des collections nommées par le catalogue. Trier par nom : c'est aussi
#: l'ordre d'écriture dans `requirements.yml`.
_REQUIREMENTS: tuple[CollectionRequirement, ...] = (
    CollectionRequirement(
        name="ansible.posix",
        floor="2.2.2",
        max_major=3,
        validated="2.2.2",
        reason=(
            "authorized_key and firewalld have existed since 1.0.0, but no version older "
            "than the one validated in CI has been checked: the floor stays high."
        ),
    ),
    CollectionRequirement(
        name="community.general",
        floor="13.4.0",
        max_major=14,
        validated="13.4.0",
        reason=(
            "timezone and ufw have existed since 1.0.0, but no version older than the "
            "one validated in CI has been checked: the floor stays high."
        ),
    ),
    CollectionRequirement(
        name="community.postgresql",
        floor="3.13.0",
        max_major=6,
        validated="5.0.0",
        reason=(
            "postgresql_alter_system, used by the postgresql role, appeared in 3.13.0; "
            "it replaced postgresql_set, removed in 5.0.0."
        ),
    ),
)

COLLECTION_REQUIREMENTS: dict[str, CollectionRequirement] = {
    requirement.name: requirement for requirement in _REQUIREMENTS
}


def requirement_for(name: str) -> CollectionRequirement:
    """Retourne la contrainte de version d'une collection.

    Lève :class:`SpecValidationError` si la collection n'est pas dans la table :
    forge ne génère jamais une dépendance sans version.
    """
    try:
        return COLLECTION_REQUIREMENTS[name]
    except KeyError:
        known = ", ".join(sorted(COLLECTION_REQUIREMENTS))
        raise SpecValidationError(
            f"Collection Galaxy sans contrainte de version : '{name}'. "
            f"Collections déclarées : {known}."
        ) from None


def requirements_for(names: Iterable[str]) -> list[CollectionRequirement]:
    """Retourne les contraintes des collections données, triées par nom et dédupliquées."""
    return [requirement_for(name) for name in sorted(set(names))]
