"""Detection of external tools (merge of the two legacy implementations).

`ansible_forge.verify.require_tools` and `helm_forge.validation.tools.require`
did the same thing; a single version survives here (MIGRATION.md §5.3). What is
new is the WSL fallback: a tool declared `requires_linux` is looked up in the
Windows PATH **then** in the WSL distribution.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from forge.validate import wsl

#: Where the tool was found.
NATIVE = "native"
WSL = "wsl"


@dataclass(frozen=True)
class ToolStatus:
    """Availability of an external tool."""

    #: Name of the binary looked for.
    name: str

    #: `NATIVE`, `WSL`, or None if not found.
    location: str | None

    #: Version reported by the tool, on one line, or "" if unavailable.
    version: str = ""

    @property
    def available(self) -> bool:
        """True if the tool is usable, whatever the access mode."""
        return self.location is not None

    def describe(self) -> str:
        """Readable status line, for `forge plugins`."""
        if not self.available:
            return f"{self.name}: missing"
        suffix = f" ({self.version})" if self.version else ""
        via = " via WSL" if self.location == WSL else ""
        return f"{self.name}: available{via}{suffix}"


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
    """Look for `name` natively, then in WSL if the tool requires Linux."""
    if shutil.which(name):
        return ToolStatus(name=name, location=NATIVE, version=_native_version(name, version_args))
    if requires_linux and wsl.wsl_has_tool(name):
        return ToolStatus(name=name, location=WSL)
    return ToolStatus(name=name, location=None)


def missing_message(name: str, install_hint: str = "", requires_linux: bool = False) -> str:
    """Absence message, with the most useful installation lead."""
    hint = install_hint
    if not hint and requires_linux:
        hint = wsl.install_hint(name)
    lines = [f"tool not found: {name}"]
    if hint:
        lines.append(f"  installation: {hint}")
    return "\n".join(lines)
