"""Exceptions de l'outil.

Toutes les erreurs prévisibles héritent de :class:`ForgeError` afin que la CLI
puisse les afficher proprement (message court, code de sortie 1) sans exposer
de traceback Python à l'utilisateur.
"""

from __future__ import annotations


class ForgeError(Exception):
    """Erreur fonctionnelle attendue, affichable telle quelle à l'utilisateur."""


class SpecError(ForgeError):
    """La spécification est invalide (champ manquant, valeur hors domaine...)."""


class SpecFileError(SpecError):
    """Le fichier de spécification est absent, illisible ou mal formé."""


class CatalogError(ForgeError):
    """Référence à un rôle ou à une option de rôle inconnus du catalogue."""


class OutputDirError(ForgeError):
    """Le répertoire de sortie est inutilisable (existe déjà, non vide, fichier...)."""


class ToolMissingError(ForgeError):
    """Un outil externe requis (ansible-playbook, ansible-lint) est introuvable."""
