"""Classe de base commune à tous les modèles de la spécification."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ForgeModel(BaseModel):
    """Modèle strict : toute clé inconnue est refusée.

    Une faute de frappe dans ``forge.yml`` doit échouer bruyamment plutôt que
    d'être ignorée en silence, sous peine de générer un chart qui ne correspond
    pas à ce que l'utilisateur croit avoir demandé.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
