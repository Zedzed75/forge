"""Vocabulaire du catalogue de composants Helm.

Le pendant de `plugins/ansible/catalog/definition.py` : le domaine Ansible
catalogue des **roles**, le domaine Helm catalogue des **familles de
ressources** Kubernetes.

Une famille dit ce qu'elle produit (kind, apiVersion), a quelle condition elle
s'applique, quelles cles de `values.yaml` elle expose, et — c'est le point qui
compte — **ce qui casse si on l'ecrit mal**. Ces pieges ne sont pas de la
documentation d'agrement : `kubeconform -strict` refuse un `pathType` absent,
l'API refuse un `roleRef` modifie, et un `policyTypes: [Egress]` sans regle
coupe le DNS. Les consigner ici, une fois, evite de les redecouvrir a chaque
gabarit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Comment forge sait qu'une famille s'applique a un composant.
#:
#: * `kind`  — le composant *est* de ce type (`kind: statefulset`) ;
#: * `addon` — le composant *porte* cet addon (`addons: [ingress]`) ;
#: * `derive`— forge le decide seul (le test de connexion vise le premier
#:   composant expose).
Selection = Literal["kind", "addon", "derive"]


@dataclass(frozen=True)
class ValueKey:
    """Une cle de `values.yaml` exposee a l'utilisateur.

    Chaque cle generee doit porter un commentaire disant a quoi elle sert et
    quelles valeurs elle admet : c'est une regle dure du projet.
    """

    #: Chemin de la cle sous le bloc du composant (`ingress.pathType`).
    name: str

    #: Valeur par defaut, ecrite telle quelle dans le YAML genere.
    default: str

    #: A quoi la cle sert, en une phrase.
    description: str

    #: Valeurs admises, quand elles sont contraintes.
    allowed: str = ""


@dataclass(frozen=True)
class ComponentFamily:
    """Une famille de ressources Kubernetes generable pour un composant."""

    #: Identifiant employe dans forge.yml et dans `domain.component_slots`.
    name: str

    #: Kind Kubernetes produit — jamais invente (regle dure de CLAUDE.md).
    kind: str

    #: apiVersion du kind, pour la fenetre de versions visee par le projet.
    api_version: str

    #: Resume d'une ligne, affiche par `forge catalog helm`.
    summary: str

    #: Comment forge sait que la famille s'applique.
    selection: Selection

    #: Description longue, affichee par `forge catalog helm <famille>`.
    details: str = ""

    #: Cles de `values.yaml` exposees par la famille.
    values: tuple[ValueKey, ...] = ()

    #: Familles dont celle-ci depend pour avoir du sens.
    requires: tuple[str, ...] = ()

    #: Pieges qui font echouer `kubeconform -strict`, `helm lint`, ou
    #: l'application reelle du manifeste. Un par entree, formule comme une
    #: contrainte a respecter.
    traps: tuple[str, ...] = field(default_factory=tuple)

    def option_descriptions(self) -> dict[str, str]:
        """Cles de values et leur description, pour `forge catalog`."""
        return {
            key.name: (
                f"{key.description} (defaut : {key.default}"
                + (f" ; valeurs : {key.allowed}" if key.allowed else "")
                + ")"
            )
            for key in self.values
        }
