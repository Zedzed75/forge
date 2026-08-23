"""Hierarchie d'erreurs commune au coeur et aux plugins.

Fusion des deux hierarchies legacy (`ansible_forge.errors` et
`helm_forge.errors`, cf. MIGRATION.md §5.1) : une seule implementation survit.

Toute erreur attendue derive de `ForgeError` : la CLI l'attrape et affiche
`str(e)` sans trace Python. Une exception qui n'en derive pas est un bug.
"""

from __future__ import annotations


class ForgeError(Exception):
    """Erreur attendue, presentable telle quelle a l'utilisateur."""


class SpecFileError(ForgeError):
    """Le fichier de specification est introuvable, illisible ou mal forme."""


class SpecValidationError(ForgeError):
    """Le contenu de la specification viole le modele assemble."""


class PluginError(ForgeError):
    """Un plugin est mal declare, absent, ou viole le contrat de hook."""


class RenderError(ForgeError):
    """Le rendu copier a echoue."""


class ToolMissingError(ForgeError):
    """Un outil externe requis par un validateur est absent du PATH."""

    def __init__(self, tool: str, install_hint: str = "") -> None:
        message = f"outil introuvable : {tool}"
        if install_hint:
            message = f"{message}\n  installation : {install_hint}"
        super().__init__(message)
        self.tool = tool
        self.install_hint = install_hint


class ValidationFailed(ForgeError):
    """Au moins un validateur ou controle inter-domaines a echoue."""
