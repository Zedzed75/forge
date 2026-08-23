"""Accès aux outils Ansible depuis la suite de tests.

``ansible-core`` ne supporte pas Windows comme nœud de contrôle. Sur Windows,
les tests délèguent donc à une distribution WSL dans laquelle ansible-core et
ansible-lint sont installés ; sur Linux et macOS ils utilisent directement les
binaires du PATH. Si aucun des deux n'est disponible, les tests concernés sont
ignorés plutôt que d'échouer.

Variables d'environnement reconnues :
    ANSIBLE_FORGE_WSL_DISTRO      distribution WSL à utiliser (défaut : Debian)
    ANSIBLE_FORGE_WSL_BIN         répertoire des binaires ansible dans WSL
    ANSIBLE_FORGE_WSL_COLLECTIONS chemin des collections Galaxy dans WSL
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

WSL_DISTRO = os.environ.get("ANSIBLE_FORGE_WSL_DISTRO", "Debian")
WSL_BIN = os.environ.get("ANSIBLE_FORGE_WSL_BIN", "/opt/forge-venv/bin")
WSL_COLLECTIONS = os.environ.get("ANSIBLE_FORGE_WSL_COLLECTIONS", "/opt/forge-collections")

#: Outils dont la suite de tests a besoin.
REQUIRED_TOOLS = ("ansible-playbook", "ansible-lint")

#: Délai maximal d'une commande ansible, en secondes.
TIMEOUT = 300


@dataclass(frozen=True)
class AnsibleRunner:
    """Exécute un outil Ansible, nativement ou à travers WSL."""

    kind: str

    def run(self, tool: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """Lance ``tool`` avec ``args`` depuis le répertoire ``cwd``."""
        if self.kind == "native":
            return subprocess.run(  # noqa: S603 - commande construite par les tests
                [tool, *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                env={**os.environ, "ANSIBLE_FORCE_COLOR": "0"},
            )
        # Les montages Windows sont vus comme « world writable » par Linux :
        # Ansible refuse alors d'y lire ansible.cfg. Le projet est donc recopié
        # dans un répertoire natif WSL, ce qui teste aussi le ansible.cfg généré.
        arguments = " ".join(_quote(arg) for arg in args)
        command = (
            'work="$(mktemp -d /tmp/ansible-forge-XXXXXXXX)" && '
            f"cp -a {_quote(_to_wsl_path(cwd))}/. \"$work\"/ && "
            'chmod -R go-w "$work" && cd "$work" && '
            f"ANSIBLE_COLLECTIONS_PATH={_quote(WSL_COLLECTIONS)} "
            f"ANSIBLE_FORCE_COLOR=0 "
            f"{_quote(f'{WSL_BIN}/{tool}')} {arguments}; "
            'status=$?; rm -rf "$work"; exit $status'
        )
        return subprocess.run(  # noqa: S603 - commande construite par les tests
            ["wsl.exe", "-d", WSL_DISTRO, "-u", "root", "--", "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            errors="replace",
        )


def _quote(value: str) -> str:
    """Protège une valeur pour un shell POSIX."""
    return "'" + str(value).replace("'", "'\\''") + "'"


def _to_wsl_path(path: Path) -> str:
    """Traduit un chemin Windows (``Z:\\a\\b``) en chemin WSL (``/mnt/z/a/b``)."""
    resolved = Path(path).resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix()[len(resolved.drive):].lstrip("/")
    return f"/mnt/{drive}/{rest}" if drive else resolved.as_posix()


@lru_cache(maxsize=1)
def get_runner() -> AnsibleRunner | None:
    """Retourne le lanceur disponible, ou ``None`` si aucun outil n'est installé."""
    if all(shutil.which(tool) for tool in REQUIRED_TOOLS):
        return AnsibleRunner(kind="native")
    if sys.platform == "win32" and _wsl_has_tools():
        return AnsibleRunner(kind="wsl")
    return None


def _wsl_has_tools() -> bool:
    """Indique si la distribution WSL configurée expose les outils attendus."""
    if not shutil.which("wsl.exe"):
        return False
    test = " && ".join(f"test -x {_quote(f'{WSL_BIN}/{tool}')}" for tool in REQUIRED_TOOLS)
    try:
        result = subprocess.run(  # noqa: S603 - commande construite par les tests
            ["wsl.exe", "-d", WSL_DISTRO, "-u", "root", "--", "bash", "-lc", test],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def skip_reason() -> str:
    """Message expliquant pourquoi les tests Ansible sont ignorés."""
    return (
        "ansible-playbook et ansible-lint sont introuvables. "
        "Installez-les (Linux/macOS) ou dans une distribution WSL "
        f"« {WSL_DISTRO} » sous {WSL_BIN} (Windows)."
    )
