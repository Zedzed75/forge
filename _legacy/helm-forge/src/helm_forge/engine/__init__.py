"""Moteur de génération : planification, rendu, écriture.

Les trois responsabilités sont volontairement disjointes :

- ``planner`` décide *quels* fichiers existent, sans rien rendre ;
- ``renderer`` produit leur contenu en mémoire, sans rien écrire ;
- ``writer`` écrit sur disque, sans rien décider.
"""

from __future__ import annotations

from .environment import JINJA_DELIMITERS, build_environment
from .planner import PlannedFile, chart_dir, plan, resource_filename, tree
from .renderer import FileSet, render, render_plan
from .writer import write

__all__ = [
    "FileSet",
    "JINJA_DELIMITERS",
    "PlannedFile",
    "build_environment",
    "chart_dir",
    "plan",
    "render",
    "render_plan",
    "resource_filename",
    "tree",
    "write",
]
