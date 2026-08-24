"""Filtres des domaines factices.

Ils reutilisent le gabarit du plugin `demo`, donc ses filtres. Ce module existe
parce que la convention du coeur est **par paquet de plugin** :
`forge.pipeline.plugin_jinja_module` cherche `<paquet-du-plugin>.jinja_ext`.
"""

from __future__ import annotations

from forge.plugins.demo.jinja_ext import FILTERS, GLOBALS

__all__ = ["FILTERS", "GLOBALS"]
