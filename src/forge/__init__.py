"""forge — generateur deterministe de projets IaC a base de plugins."""

from __future__ import annotations

#: Version du projet, et **seule** source : `pyproject.toml` la lit d'ici
#: (`[tool.hatch.version]`). La dupliquer les avait deja fait diverger.
__version__ = "1.1.0"

__all__ = ["__version__"]
