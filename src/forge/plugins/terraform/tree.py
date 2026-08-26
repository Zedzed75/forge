"""Chemins que le domaine Terraform ecrit, et ce que chacun contient.

Meme role — et meme mise en garde — que `plugins/ansible/tree.py` et
`plugins/helm/tree.py` : **c'est le seul endroit du domaine qui duplique la
connaissance de l'arborescence de gabarit**. Un gabarit ajoute, retire ou
renomme sans mise a jour de ce module rend les README generes faux.

L'arbitrage R3 (PLAN.md) a laisse cette liste au plugin plutot que de l'inferer
d'un rendu a blanc, a une condition : qu'un test la confronte a l'arborescence
reellement produite. C'est `test_plugin_terraform.py` qui la tient.

Chaque entree porte sa description : les README generes ne se contentent pas
d'afficher des noms de fichiers, ils disent a quoi chacun sert.
"""

from __future__ import annotations

from typing import Any, Final, NamedTuple

from forge.plugins.terraform.catalog.registry import selected


class Entry(NamedTuple):
    """Un fichier genere et la phrase qui le decrit."""

    #: Chemin relatif a la racine du domaine (`terraform/`).
    path: str

    #: A quoi sert ce fichier, en une phrase.
    purpose: str


#: Repertoire des modules, relatif a la racine du domaine.
MODULES_DIR: Final[str] = "modules"

#: Repertoire des racines d'environnement.
ENVIRONMENTS_DIR: Final[str] = "environments"

#: Fichiers du module, hors ceux des familles retenues. L'ordre est celui de la
#: lecture : ce qu'exige Terraform, puis ce que le module recoit, ce qu'il
#: calcule, ce qu'il rend.
MODULE_BASE: Final[tuple[Entry, ...]] = (
    Entry("versions.tf", "Version de Terraform et providers exiges par le module."),
    Entry("variables.tf", "Toutes les entrees du module, chacune commentee."),
    Entry("locals.tf", "Valeurs calculees : namespace effectif, labels communs."),
    Entry("outputs.tf", "Ce que le module rend a son appelant."),
    Entry("README.md", "Role du module, entrees, sorties et pieges de chaque famille."),
)

#: Fichiers d'une racine d'environnement, dans l'ordre de lecture.
ENVIRONMENT_FILES: Final[tuple[Entry, ...]] = (
    Entry("versions.tf", "Version de Terraform et providers exiges par cette racine."),
    Entry("backend.tf", "Ou l'etat de cet environnement est conserve."),
    Entry("providers.tf", "Configuration des providers : cluster vise, contexte."),
    Entry("variables.tf", "Entrees de la racine, reprises de celles du module."),
    Entry("main.tf", "Appel du module, avec les valeurs de cet environnement."),
    Entry("outputs.tf", "Sorties remontees depuis le module."),
    Entry("terraform.tfvars", "Valeurs de cet environnement. Aucune valeur secrete."),
)


def module_dir(service_name: str) -> str:
    """Chemin du module, relatif a la racine du domaine."""
    return f"{MODULES_DIR}/{service_name}"


def environment_dir(environment: str) -> str:
    """Chemin d'une racine d'environnement, relatif a la racine du domaine."""
    return f"{ENVIRONMENTS_DIR}/{environment}"


def family_file(family: str) -> str:
    """Nom du fichier `.tf` portant une famille de ressources."""
    return f"{family}.tf"


def module_files(spec: Any) -> list[dict[str, str]]:
    """Fichiers du module, base puis familles retenues, dans l'ordre canonique.

    Rendu en dicts et non en `Entry` : le resultat part dans le dict `domain`,
    qui doit rester JSON-serialisable (un `NamedTuple` se serialiserait en
    liste, et les gabarits liraient `f[0]` au lieu de `f.path`).
    """
    entrees = [
        {"path": entree.path, "purpose": entree.purpose} for entree in MODULE_BASE
    ]
    entrees += [
        {
            "path": family_file(famille.name),
            "purpose": f"{famille.summary} ({', '.join(famille.resources)}).",
        }
        for famille in selected(spec.terraform.family_names())
    ]
    return entrees


def environment_files() -> list[dict[str, str]]:
    """Fichiers d'une racine d'environnement, en dicts JSON-serialisables."""
    return [{"path": entree.path, "purpose": entree.purpose} for entree in ENVIRONMENT_FILES]


def root_files(spec: Any) -> list[dict[str, str]]:
    """Fichiers de niveau `terraform/`, hors modules et environnements."""
    entrees = [
        {"path": "README.md", "purpose": "Ce fichier : comment employer le projet."},
        {
            "path": ".gitignore",
            "purpose": (
                "Exclut l'etat, les plans et le cache de providers. L'etat "
                "porte des valeurs en clair : il ne doit jamais etre committe."
            ),
        },
        {
            "path": ".copier-answers.yml",
            "purpose": "Reponses du gabarit, relues par `forge update`. Ne pas editer.",
        },
    ]
    if spec.terraform.extras.tflint_config:
        entrees.append(
            {
                "path": ".tflint.hcl",
                "purpose": "Jeu de regles tflint applique au projet.",
            }
        )
    if spec.terraform.extras.makefile:
        entrees.append(
            {
                "path": "Makefile",
                "purpose": "Raccourcis : `make init ENV=prod`, `make plan ENV=prod`.",
            }
        )
    return sorted(entrees, key=lambda entree: entree["path"])


def expected_paths(spec: Any) -> list[str]:
    """Tous les chemins ecrits par le domaine, tries.

    C'est la liste que le test confronte a l'arborescence reellement rendue.
    """
    chemins = [entree["path"] for entree in root_files(spec)]
    module = module_dir(spec.service.name)
    chemins += [f"{module}/{entree['path']}" for entree in module_files(spec)]
    for env in spec.service.environments:
        racine = environment_dir(env.name)
        chemins += [f"{racine}/{entree['path']}" for entree in environment_files()]
    return sorted(chemins)


def resource_slots(spec: Any) -> dict[str, list[dict[str, str]]]:
    """Emplacements de fichier par famille : `[{...}]` si retenue, `[]` sinon.

    Motif partage avec les deux autres domaines (arbitrage R4, DESIGN.md §5.3) :
    un gabarit propre a une famille existe sans qu'un `[% if %]` ait a figurer
    dans son chemin, et copier decide de l'ecrire ou non par la balise `yield`.
    """
    retenues = set(spec.terraform.family_names())
    from forge.plugins.terraform.catalog.registry import all_families

    return {
        famille.name: (
            [{"name": famille.name, "summary": famille.summary}]
            if famille.name in retenues
            else []
        )
        for famille in all_families()
    }
