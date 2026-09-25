"""forge — plugin-based deterministic generator of IaC projects."""

from __future__ import annotations

#: Project version, and the **only** source: `pyproject.toml` reads it from here
#: (`[tool.hatch.version]`). Duplicating it had already made the two diverge.
__version__ = "1.1.0"

__all__ = ["__version__"]
