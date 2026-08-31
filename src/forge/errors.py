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


# Deux classes ont ete retirees en phase 10, apres verification qu'aucun chemin
# ne les levait :
#
# * `ToolMissingError` — `forge.validate.tools.missing_message()` compose le
#   meme message, et le coeur signale un outil absent par un rapport de
#   validation, jamais par une exception : une commande sautee n'interrompt pas
#   les autres.
# * `ValidationFailed` — `ValidationResult.ok` porte le verdict, et la CLI en
#   deduit son code de sortie. Lever une exception aurait fait perdre le
#   rapport, qui est justement ce que l'utilisateur veut lire.
