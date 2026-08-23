"""Exceptions métier de helm-forge.

Chaque exception porte un code de sortie, utilisé par le CLI pour renvoyer un
statut distinct au shell. Cela permet de scripter helm-forge sans analyser les
messages affichés.
"""

from __future__ import annotations


class HelmForgeError(Exception):
    """Erreur métier de helm-forge. Toutes les autres en héritent."""

    #: Code de sortie renvoyé par le CLI lorsque cette erreur remonte.
    exit_code: int = 1


class SpecError(HelmForgeError):
    """La spécification est invalide, illisible ou d'un schéma inconnu."""

    exit_code = 2


class SpecNotFoundError(SpecError):
    """Le fichier forge.yml demandé n'existe pas."""

    exit_code = 3


class TargetExistsError(HelmForgeError):
    """Le répertoire cible existe déjà et n'est pas vide.

    Le générateur refuse d'écraser un projet existant sans --force explicite :
    une génération est destructive par nature (elle réécrit tous les fichiers).
    """

    exit_code = 4


class ToolNotFoundError(HelmForgeError):
    """Un outil externe requis (helm, kubeconform) est introuvable dans le PATH."""

    exit_code = 5


class ValidationFailedError(HelmForgeError):
    """helm lint, helm template ou kubeconform a signalé une erreur."""

    exit_code = 6


class TemplateRenderError(HelmForgeError):
    """Le rendu d'un gabarit Jinja2 a échoué (variable manquante, syntaxe)."""

    exit_code = 7
