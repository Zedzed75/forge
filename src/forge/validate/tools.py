"""Detection des outils externes (fusion des deux implementations legacy).

`ansible_forge.verify.require_tools` et `helm_forge.validation.tools.require`
faisaient la meme chose ; une seule version survit ici (MIGRATION.md §5.3). La
nouveaute est le repli WSL : un outil declare `requires_linux` est cherche dans
le PATH Windows **puis** dans la distribution WSL.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from forge.validate import wsl

#: Ou l'outil a ete trouve.
NATIVE = "native"
WSL = "wsl"


@dataclass(frozen=True)
class ToolStatus:
    """Disponibilite d'un outil externe."""

    #: Nom du binaire recherche.
    name: str

    #: `NATIVE`, `WSL`, ou None si introuvable.
    location: str | None

    #: Version rapportee par l'outil, sur une ligne, ou "" si indisponible.
    version: str = ""

    @property
    def available(self) -> bool:
        """Vrai si l'outil est utilisable, quel que soit le mode d'acces."""
        return self.location is not None

    def describe(self) -> str:
        """Ligne d'etat lisible, pour `forge plugins`."""
        if not self.available:
            return f"{self.name} : absent"
        suffix = f" ({self.version})" if self.version else ""
        via = " via WSL" if self.location == WSL else ""
        return f"{self.name} : disponible{via}{suffix}"


def _native_version(name: str, args: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(
            [name, *args], capture_output=True, text=True, timeout=30, errors="replace"
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0] if output else ""


@lru_cache(maxsize=64)
def probe(
    name: str, requires_linux: bool = False, version_args: tuple[str, ...] = ("--version",)
) -> ToolStatus:
    """Cherche `name` nativement, puis dans WSL si l'outil exige Linux."""
    if shutil.which(name):
        return ToolStatus(name=name, location=NATIVE, version=_native_version(name, version_args))
    if requires_linux and wsl.wsl_has_tool(name):
        return ToolStatus(name=name, location=WSL)
    return ToolStatus(name=name, location=None)


def missing_message(name: str, install_hint: str = "", requires_linux: bool = False) -> str:
    """Message d'absence, avec la piste d'installation la plus utile."""
    hint = install_hint
    if not hint and requires_linux:
        hint = wsl.install_hint(name)
    lines = [f"outil introuvable : {name}"]
    if hint:
        lines.append(f"  installation : {hint}")
    return "\n".join(lines)
