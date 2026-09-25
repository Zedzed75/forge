"""WSL bridge: running an external tool that does not run under Windows.

Generalised port of `tests/ansible_tools.py` (MIGRATION.md §3): the need has
nothing Ansible-specific about it — it is "run a Linux binary against a project
generated under Windows", copying the project out of the Windows mounts, which
Linux sees as world-writable (which makes an `ansible.cfg` be refused, and would
mislead other tools the same way).

Recognised environment variables:
    FORGE_WSL_DISTRO   WSL distribution to use (default: Debian)
    FORGE_WSL_PATH     directories prepended to the PATH inside WSL
    FORGE_WSL_USER     WSL user (default: root)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PureWindowsPath

from forge.errors import ForgeError

#: WSL distribution queried.
WSL_DISTRO = os.environ.get("FORGE_WSL_DISTRO", "Debian")

#: Directories prepended to the PATH inside WSL, before the distribution's PATH.
#:
#: Project convention: the validation tools live under `/opt`, outside any
#: user's home directory. The bridge runs under an account (`root` by default)
#: which is not necessarily the one that installed the tools — a binary dropped
#: in another account's `~/.local/bin` would be invisible. A symlink into
#: `/opt/forge-tools/bin` is enough to make it reachable, without moving the
#: original installation.
WSL_PATH = os.environ.get(
    "FORGE_WSL_PATH", "/opt/forge-venv/bin:/opt/forge-tools/bin:/root/.local/bin"
)

#: User the bridge runs as inside WSL.
WSL_USER = os.environ.get("FORGE_WSL_USER", "root")


def quote(value: str) -> str:
    """Protect a value for a POSIX shell."""
    return "'" + str(value).replace("'", "'\\''") + "'"


def to_wsl_path(path: str | Path) -> str:
    """Translate a Windows path (`Z:\\a\\b`) into a WSL path (`/mnt/z/a/b`).

    A UNC path (`\\\\server\\share\\...`) has no equivalent under `/mnt` as long
    as the share is not mounted by hand inside the distribution: fabricating a
    plausible but wrong path would make the copy fail further on, with an
    incomprehensible `cp: cannot stat`. Better to say so right away.
    """
    # Two leading separators: a UNC path. The check is made on the **string**,
    # before any interpretation by pathlib. This is not excessive caution: up to
    # Python 3.11, `PureWindowsPath(PosixPath(...))` reuses the components
    # already split according to POSIX rules instead of re-reading the string
    # with the Windows ones, and the UNC prefix disappears. Python 3.12 rewrote
    # pathlib and always re-parses — the CI found the difference between the two.
    raw = str(path).replace("\\", "/")
    if raw.startswith("//"):
        raise ForgeError(
            f"UNC path not supported by the WSL bridge: {path}\n"
            "  generate the project on a local drive, or mount the share in the "
            f"'{WSL_DISTRO}' distribution."
        )

    # `PureWindowsPath(str(...))` and not `Path`: the translation must read a
    # **Windows** path, whatever the host platform. With `Path`, a Linux reads
    # `C:/projects` as an ordinary directory name and returns
    # `/current/directory/C:/projects` — a plausible, wrong path that nothing
    # reports. Going through `str` forces the re-read under Windows rules on
    # every version of Python.
    windows = PureWindowsPath(str(path))
    if not windows.drive and not windows.is_absolute():
        # Relative path: resolve it against the current directory, which
        # legitimately depends on the platform.
        windows = PureWindowsPath(Path(path).resolve())

    drive = windows.drive
    # Second pass, and it is not redundant: resolving a relative path above may
    # land on a network share the initial string did not show.
    if drive.startswith("\\\\") or drive.startswith("//"):
        raise ForgeError(
            f"UNC path not supported by the WSL bridge: {windows}\n"
            "  generate the project on a local drive, or mount the share in the "
            f"'{WSL_DISTRO}' distribution."
        )
    letter = drive.rstrip(":").lower()
    rest = windows.as_posix()[len(drive) :].lstrip("/")
    return f"/mnt/{letter}/{rest}" if letter else windows.as_posix()


def is_windows() -> bool:
    """True if the current process runs under Windows."""
    return sys.platform == "win32"


@lru_cache(maxsize=1)
def wsl_available() -> bool:
    """True if `wsl.exe` is present and the configured distribution answers."""
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
    """True if `tool` can be found in the WSL distribution's PATH."""
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
    """Build the bash line run inside WSL, copy of the project included.

    The cleanup goes through a `trap` rather than a final `rm`: without it, a
    timeout kills the process before the removal and leaves a complete copy of
    the project in the distribution's `/tmp`, on every attempt.
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
    """Run `tool` inside WSL against a native copy of `cwd`."""
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
    """Installation message suited to the current platform."""
    if is_windows():
        return (
            f"install {tool} in the '{WSL_DISTRO}' WSL distribution "
            f"(PATH used: {WSL_PATH}), or in the Windows PATH."
        )
    return f"install {tool} and make it reachable from the PATH."
