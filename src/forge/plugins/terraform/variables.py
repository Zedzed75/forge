"""Variables d'entree du module Terraform genere.

Une seule declaration sert quatre fichiers : `variables.tf` du module,
`variables.tf` de chaque racine d'environnement, l'appel de module dans son
`main.tf`, et le `terraform.tfvars` de l'environnement. Les redeclarer dans
chaque gabarit les ferait diverger au premier ajout — et Terraform ne signale
pas une variable declaree cote racine mais jamais transmise au module : elle est
simplement sans effet.

Regle absolue : **aucune valeur secrete n'est jamais ecrite**. Une variable
`sensitive` n'a pas de valeur par defaut et n'apparait pas dans
`terraform.tfvars` ; elle se fournit par `TF_VAR_<nom>`, une variable
d'environnement de la CI ou un coffre.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Variable:
    """Une variable d'entree, telle que declaree dans `variables.tf`."""

    #: Nom de la variable (identifiant HCL).
    name: str

    #: Type HCL : `string`, `number`, `bool`, `list(string)`, `map(string)`.
    type: str

    #: Phrase de description, reprise telle quelle dans `description`.
    description: str

    #: Valeur par defaut, ou `_ABSENT` si la variable est obligatoire.
    default: Any = None

    #: Vrai si la variable porte une valeur par defaut (y compris `null`).
    has_default: bool = True

    #: Marque la valeur comme secrete : Terraform la masque dans ses sorties.
    sensitive: bool = False

    #: Vrai si la valeur est transmise par `terraform.tfvars` (donc jamais
    #: secrete, et calculee par environnement).
    per_environment: bool = False


def required(name: str, type_: str, description: str, *, sensitive: bool = False) -> Variable:
    """Variable sans valeur par defaut : Terraform exige qu'elle soit fournie."""
    return Variable(
        name=name,
        type=type_,
        description=description,
        default=None,
        has_default=False,
        sensitive=sensitive,
    )


def optional(
    name: str,
    type_: str,
    description: str,
    default: Any,
    *,
    per_environment: bool = False,
) -> Variable:
    """Variable avec valeur par defaut, eventuellement surchargee par environnement."""
    return Variable(
        name=name,
        type=type_,
        description=description,
        default=default,
        has_default=True,
        per_environment=per_environment,
    )


#: Variables presentes quelles que soient les familles retenues. Elles decrivent
#: *a quoi* le module se rattache ; les familles ajoutent *ce qu'il pose*.
COMMON_VARIABLES: tuple[Variable, ...] = (
    required(
        "service_name",
        "string",
        "Nom du service. Prefixe toutes les ressources creees et alimente le "
        "label app.kubernetes.io/name.",
    ),
    required(
        "environment",
        "string",
        "Nom de l'environnement (dev, staging, prod). Sert de suffixe de "
        "ressource et de valeur du label app.kubernetes.io/instance.",
    ),
    required(
        "namespace",
        "string",
        "Namespace Kubernetes vise. Cree par ce module si la famille "
        "'namespace' est retenue, suppose exister sinon.",
    ),
    optional(
        "labels",
        "map(string)",
        "Labels apposes sur toutes les ressources, en plus des labels "
        "app.kubernetes.io calcules par le module.",
        {},
        per_environment=True,
    ),
    optional(
        "annotations",
        "map(string)",
        "Annotations apposees sur toutes les ressources. Laissez vide si "
        "aucun controleur du cluster n'en attend.",
        {},
    ),
)
