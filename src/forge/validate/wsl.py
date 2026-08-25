"""Pont WSL : executer un outil externe qui ne tourne pas sous Windows.

Portage generalise de `tests/ansible_tools.py` (MIGRATION.md §3) : le besoin
n'a rien de propre a Ansible — c'est « lancer un binaire Linux sur un projet
genere sous Windows », en recopiant le projet hors des montages Windows, que
Linux voit world-writable (ce qui fait refuser un `ansible.cfg`, et fausserait
d'autres outils de la meme facon).

Variables d'environnement reconnues :
    FORGE_WSL_DISTRO   distribution WSL a utiliser (defaut : Debian)
    FORGE_WSL_PATH     repertoires ajoutes au PATH dans WSL
    FORGE_WSL_USER     utilisateur WSL (defaut : root)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from forge.errors import ForgeError

#: Distribution WSL interrogee.
WSL_DISTRO = os.environ.get("FORGE_WSL_DISTRO", "Debian")

#: Repertoires ajoutes au PATH dans WSL, avant le PATH de la distribution.
#:
#: Convention du projet : les outils de validation vivent sous `/opt`, hors du
#: repertoire personnel d'un utilisateur. Le pont s'execute en effet sous un
#: compte (`root` par defaut) qui n'est pas forcement celui qui a installe les
#: outils — un binaire pose dans `~/.local/bin` d'un autre compte serait
#: invisible. Un lien symbolique vers `/opt/forge-tools/bin` suffit a le rendre
#: joignable, sans deplacer l'installation d'origine.
WSL_PATH = os.environ.get(
    "FORGE_WSL_PATH", "/opt/forge-venv/bin:/opt/forge-tools/bin:/root/.local/bin"
)

#: Utilisateur employe dans WSL.
WSL_USER = os.environ.get("FORGE_WSL_USER", "root")


def quote(value: str) -> str:
    """Protege une valeur pour un shell POSIX."""
    return "'" + str(value).replace("'", "'\\''") + "'"


def to_wsl_path(path: Path) -> str:
    """Traduit un chemin Windows (`Z:\\a\\b`) en chemin WSL (`/mnt/z/a/b`).

    Un chemin UNC (`\\\\serveur\\partage\\...`) n'a pas d'equivalent sous `/mnt`
    tant que le partage n'est pas monte a la main dans la distribution : fabriquer
    un chemin plausible mais faux ferait echouer la copie plus loin, sur un
    `cp: cannot stat` incomprehensible. Mieux vaut le dire tout de suite.
    """
    resolved = Path(path).resolve()
    drive = resolved.drive
    if drive.startswith("\\\\") or drive.startswith("//"):
        raise ForgeError(
            f"chemin UNC non supporte par le pont WSL : {resolved}\n"
            "  generez le projet sur un lecteur local, ou montez le partage dans "
            f"la distribution « {WSL_DISTRO} »."
        )
    letter = drive.rstrip(":").lower()
    rest = resolved.as_posix()[len(drive) :].lstrip("/")
    return f"/mnt/{letter}/{rest}" if letter else resolved.as_posix()


def is_windows() -> bool:
    """Vrai si le processus courant tourne sous Windows."""
    return sys.platform == "win32"


@lru_cache(maxsize=1)
def wsl_available() -> bool:
    """Vrai si `wsl.exe` est present et la distribution configuree repond."""
    if not is_windows() or not shutil.which("wsl.exe"):
        return False
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", WSL_DISTRO, "-u", WSL_USER, "--exec", "true"],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


@lru_cache(maxsize=32)
def wsl_has_tool(tool: str) -> bool:
    """Vrai si `tool` est trouvable dans le PATH de la distribution WSL."""
    if not wsl_available():
        return False
    command = f"PATH={quote(WSL_PATH)}:$PATH command -v {quote(tool)} >/dev/null"
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", WSL_DISTRO, "-u", WSL_USER, "--exec", "bash", "-lc", command],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def build_command(
    tool: str, argv: tuple[str, ...] | list[str], cwd: Path, env: dict[str, str] | None
) -> str:
    """Construit la ligne bash executee dans WSL, copie du projet comprise.

    Le nettoyage passe par un `trap` et non par un `rm` final : sans lui, un
    depassement de delai tue le processus avant la suppression et laisse une
    copie complete du projet dans le `/tmp` de la distribution, a chaque essai.
    """
    arguments = " ".join(quote(arg) for arg in argv)
    assignments = " ".join(
        f"{key}={quote(value)}" for key, value in sorted((env or {}).items())
    )
    return (
        'work="$(mktemp -d /tmp/forge-XXXXXXXX)" || exit 1; '
        "trap 'rm -rf \"$work\"' EXIT HUP INT TERM; "
        f"cp -a {quote(to_wsl_path(cwd))}/. \"$work\"/ && "
        'chmod -R go-w "$work" && cd "$work" && '
        f"PATH={quote(WSL_PATH)}:$PATH {assignments} {quote(tool)} {arguments}"
    )


def run_in_wsl(
    tool: str,
    argv: tuple[str, ...] | list[str],
    cwd: Path,
    *,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Lance `tool` dans WSL sur une copie native de `cwd`."""
    command = build_command(tool, argv, cwd, env)
    return subprocess.run(
        ["wsl.exe", "-d", WSL_DISTRO, "-u", WSL_USER, "--exec", "bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=stdin,
        errors="replace",
    )


def install_hint(tool: str) -> str:
    """Message d'installation adapte a la plateforme courante."""
    if is_windows():
        return (
            f"installez {tool} dans la distribution WSL « {WSL_DISTRO} » "
            f"(PATH utilise : {WSL_PATH}), ou dans le PATH Windows."
        )
    return f"installez {tool} et rendez-le accessible depuis le PATH."
