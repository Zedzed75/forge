"""helm-forge — générateur déterministe de projets Kubernetes/Helm commentés.

Le générateur ne fait appel à aucun modèle de langage ni à aucune API externe :
tout est produit par rendu de gabarits Jinja2 à partir d'une spécification.
Deux spécifications identiques produisent deux projets identiques.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
