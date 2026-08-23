"""Rendu : transforme un plan en fichiers, entièrement en mémoire.

Le rendu n'écrit jamais sur disque. C'est ce qui permet de le tester sans
répertoire temporaire, de comparer deux rendus octet pour octet, et de valider
un projet avant de décider de l'écrire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jinja2 import TemplateError

from ..errors import TemplateRenderError
from ..models import AddonKind, ComponentKind, ProjectSpec
from ..spec_io import dumps as dump_spec
from .environment import build_environment
from .naming import helper_name, values_ref
from .planner import SPEC_SENTINEL, PlannedFile, chart_dir, plan, resource_filename


@dataclass
class FileSet:
    """Ensemble ordonné de fichiers rendus, indexés par chemin relatif."""

    files: dict[str, str] = field(default_factory=dict)

    def __contains__(self, path: str) -> bool:
        return path in self.files

    def __getitem__(self, path: str) -> str:
        return self.files[path]

    def __len__(self) -> int:
        return len(self.files)

    @property
    def paths(self) -> list[str]:
        """Chemins des fichiers, dans l'ordre de génération."""
        return list(self.files)


def render(spec: ProjectSpec) -> FileSet:
    """Rend l'intégralité d'un projet à partir de sa spécification."""
    return render_plan(spec, plan(spec))


def render_plan(spec: ProjectSpec, files: list[PlannedFile]) -> FileSet:
    """Rend un plan déjà construit."""
    env = build_environment()
    base = _base_context(spec)
    rendered = FileSet()

    for planned in files:
        if planned.template == SPEC_SENTINEL:
            rendered.files[planned.path] = dump_spec(spec)
            continue
        try:
            template = env.get_template(planned.template)
            text = template.render(**base, **planned.context)
        except TemplateError as exc:
            raise TemplateRenderError(
                f"échec du rendu de {planned.path} "
                f"(gabarit {planned.template}) : {exc}"
            ) from exc
        rendered.files[planned.path] = _normalise(text)

    return rendered


def _base_context(spec: ProjectSpec) -> dict[str, object]:
    """Contexte commun à tous les gabarits.

    On y expose la spécification, mais aussi quelques raccourcis calculés une
    seule fois, pour éviter de répéter la même logique dans chaque gabarit.
    """
    return {
        "spec": spec,
        "app": spec.app,
        "chart_dir": chart_dir(spec),
        # Préfixe des helpers Helm générés : "<chart>.<suffixe>".
        "helper": spec.app.name,
        "AddonKind": AddonKind,
        "ComponentKind": ComponentKind,
        "resource_filename": resource_filename,
        # Fabriques d'identifiants Helm, qui gèrent notamment les noms de
        # composants contenant un tiret.
        "values_ref": values_ref,
        "helper_name": helper_name,
    }


def _normalise(text: str) -> str:
    """Normalise un rendu : fins de ligne, lignes vides et saut final.

    Trois règles, appliquées à tous les fichiers générés :

    1. fins de ligne en LF, quelle que soit la plateforme de génération ;
    2. au plus une ligne vide consécutive. Un bloc optionnel non retenu laisse
       sinon derrière lui les lignes vides qui l'encadraient ;
    3. exactement un saut de ligne final.

    Sans cette normalisation, la mise en forme d'un fichier dépendrait de la
    combinaison d'options retenue, et les fichiers de référence deviendraient
    illisibles à comparer.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip("\n") + "\n"
