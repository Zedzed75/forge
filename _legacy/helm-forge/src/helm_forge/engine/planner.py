"""Planification : quels fichiers un projet donné contient-il ?

Le planificateur est volontairement séparé du rendu. Il répond à la seule
question « quels fichiers, dans quel ordre, à partir de quel gabarit », ce qui
permet à ``--dry-run`` d'afficher l'arborescence sans rien rendre ni écrire.

L'ordre du plan est déterministe : il ne dépend que de l'ordre des composants
et des environnements dans la spécification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..constants import SPEC_FILENAME
from ..errors import HelmForgeError
from ..models import AddonKind, ComponentKind, ComponentSpec, Layout, ProjectSpec

#: Gabarit fictif : le contenu vient de spec_io, pas d'un fichier Jinja2.
SPEC_SENTINEL = "@spec"

#: Types de charge de travail sachant être générés à ce stade du projet.
IMPLEMENTED_KINDS: frozenset[ComponentKind] = frozenset({ComponentKind.DEPLOYMENT})

#: Addons sachant être générés à ce stade du projet. Cet ensemble s'étend au
#: fil de l'étape 5, un composant du catalogue à la fois.
IMPLEMENTED_ADDONS: frozenset[AddonKind] = frozenset({AddonKind.SERVICE})


@dataclass(frozen=True)
class PlannedFile:
    """Un fichier à produire : sa destination, son gabarit, son contexte."""

    #: Chemin relatif à la racine du projet, toujours en séparateurs POSIX.
    path: str
    #: Nom du gabarit Jinja2, relatif au répertoire templates du paquet.
    template: str
    #: Variables supplémentaires injectées dans le contexte de rendu.
    context: dict[str, Any] = field(default_factory=dict)


def chart_dir(spec: ProjectSpec) -> str:
    """Répertoire du chart principal, relatif à la racine du projet."""
    return f"charts/{spec.app.name}"


def resource_filename(resource: str, component: ComponentSpec) -> str:
    """Nom de fichier d'une ressource, toujours suffixé par le composant.

    Le suffixe est systématique, y compris pour un chart mono-composant : la
    règle reste ainsi identique quel que soit le projet, et ajouter un second
    composant ne renomme aucun fichier existant.
    """
    return f"{resource}-{component.name}.yaml"


def plan(spec: ProjectSpec) -> list[PlannedFile]:
    """Construit la liste ordonnée des fichiers du projet."""
    _reject_unsupported(spec)

    root = chart_dir(spec)
    files: list[PlannedFile] = [
        PlannedFile(SPEC_FILENAME, SPEC_SENTINEL),
        PlannedFile("README.md", "project/README.md.j2"),
        PlannedFile(".gitignore", "project/gitignore.j2"),
    ]
    if spec.extras.makefile:
        files.append(PlannedFile("Makefile", "project/Makefile.j2"))

    # --- Racine du chart ---------------------------------------------------
    files += [
        PlannedFile(f"{root}/Chart.yaml", "chart/Chart.yaml.j2"),
        PlannedFile(f"{root}/values.yaml", "chart/values.yaml.j2"),
    ]
    for env in spec.environments:
        files.append(
            PlannedFile(
                f"{root}/values-{env.name}.yaml",
                "chart/values-env.yaml.j2",
                {"environment": env},
            )
        )
    files += [
        PlannedFile(f"{root}/.helmignore", "chart/helmignore.j2"),
        PlannedFile(f"{root}/README.md", "chart/README.md.j2"),
    ]

    # --- Gabarits du chart -------------------------------------------------
    templates = f"{root}/templates"
    files += [
        PlannedFile(f"{templates}/_helpers.tpl", "chart/templates/_helpers.tpl.j2"),
        PlannedFile(f"{templates}/NOTES.txt", "chart/templates/NOTES.txt.j2"),
    ]

    for component in spec.components:
        context = {"component": component}
        if component.kind is ComponentKind.DEPLOYMENT:
            files.append(
                PlannedFile(
                    f"{templates}/{resource_filename('deployment', component)}",
                    "chart/templates/deployment.yaml.j2",
                    context,
                )
            )
        if component.has(AddonKind.SERVICE):
            files.append(
                PlannedFile(
                    f"{templates}/{resource_filename('service', component)}",
                    "chart/templates/service.yaml.j2",
                    context,
                )
            )

    target = first_exposed(spec)
    if spec.extras.helm_tests and target is not None:
        files.append(
            PlannedFile(
                f"{templates}/tests/test-connection.yaml",
                "chart/templates/tests/test-connection.yaml.j2",
                {"component": target},
            )
        )

    return files


def tree(files: list[PlannedFile]) -> str:
    """Rend le plan sous forme d'arborescence lisible, pour ``--dry-run``."""
    lines: list[str] = []
    seen: set[str] = set()
    for planned in files:
        parts = planned.path.split("/")
        for depth in range(len(parts) - 1):
            directory = "/".join(parts[: depth + 1])
            if directory not in seen:
                seen.add(directory)
                lines.append(f"{'    ' * depth}{parts[depth]}/")
        lines.append(f"{'    ' * (len(parts) - 1)}{parts[-1]}")
    return "\n".join(lines)


def first_exposed(spec: ProjectSpec) -> ComponentSpec | None:
    """Premier composant joignable par un Service classique, s'il existe.

    Un Service headless est écarté : il n'a pas d'adresse virtuelle, un test de
    connexion basé sur le nom du Service n'y aurait donc aucun sens.
    """
    for component in spec.components:
        if component.has(AddonKind.SERVICE) and not component.service.headless:
            return component
    return None


def _reject_unsupported(spec: ProjectSpec) -> None:
    """Refuse explicitement ce que le générateur ne sait pas encore produire.

    Mieux vaut une erreur nette qu'un chart amputé en silence d'un composant
    que l'utilisateur croyait avoir demandé.
    """
    if spec.layout is not Layout.SINGLE:
        raise HelmForgeError(
            "la disposition « umbrella » n'est pas encore implémentée ; "
            "utilisez layout: single"
        )

    missing_kinds = sorted(
        {c.kind.value for c in spec.components if c.kind not in IMPLEMENTED_KINDS}
    )
    if missing_kinds:
        raise HelmForgeError(
            f"types de composants pas encore implémentés : {missing_kinds}"
        )

    missing_addons = sorted(
        {
            addon.value
            for component in spec.components
            for addon in component.addons
            if addon not in IMPLEMENTED_ADDONS
        }
    )
    if missing_addons:
        raise HelmForgeError(
            f"addons pas encore implémentés : {missing_addons}"
        )
