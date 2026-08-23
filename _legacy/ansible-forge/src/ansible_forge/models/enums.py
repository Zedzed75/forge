"""Énumérations partagées par le modèle de spécification.

Les valeurs sont des chaînes afin d'être sérialisées telles quelles dans
``forge.yml`` et de rester lisibles dans les fichiers Ansible générés.
"""

from __future__ import annotations

from enum import Enum


class OSFamily(str, Enum):
    """Famille de système d'exploitation ciblée par le projet.

    Détermine les noms de paquets, le gestionnaire de paquets et le backend
    pare-feu par défaut utilisés par les rôles générés.
    """

    DEBIAN = "debian"
    REDHAT = "redhat"
