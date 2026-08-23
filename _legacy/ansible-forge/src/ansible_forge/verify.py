"""Vérification d'un projet généré par les outils Ansible officiels.

CLAUDE.md exige que tout projet généré passe ``ansible-playbook --syntax-check``
et ``ansible-lint``. Ce module permet de le vérifier depuis la CLI, sur un
projet déjà écrit sur disque.

Aucun de ces outils n'est une dépendance d'ansible-forge : la génération n'en a
pas besoin. Leur absence est donc signalée par un message d'installation, jamais
par une trace Python.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ansible_forge.errors import ForgeError, ToolMissingError

#: Outils requis par la vérification, dans l'ordre d'exécution.
REQUIRED_TOOLS = ("ansible-playbook", "ansible-lint")

#: Délai maximal accordé à une commande, en secondes.
TIMEOUT = 600

#: Fichiers dont la présence identifie un projet généré par ansible-forge.
PROJECT_MARKERS = ("ansible.cfg", "playbooks/site.yml", "inventories")


@dataclass(frozen=True)
class CheckResult:
    """Résultat d'une commande de vérification."""

    label: str
    command: list[str]
    returncode: int
    output: str

    @property
    def ok(self) -> bool:
        """Indique si la commande s'est terminée sans erreur."""
        return self.returncode == 0


def missing_tools() -> list[str]:
    """Retourne les outils requis absents du PATH."""
    return [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]


def require_tools() -> None:
    """Vérifie la présence des outils, sinon lève :class:`ToolMissingError`."""
    missing = missing_tools()
    if not missing:
        return

    message = [
        f"Outil(s) introuvable(s) dans le PATH : {', '.join(missing)}.",
        "Installation : python -m pip install ansible-core ansible-lint",
    ]
    if sys.platform == "win32":
        message.append(
            "ansible-core ne supporte pas Windows comme nœud de contrôle : "
            "installez-le dans WSL et lancez « ansible-forge check » depuis WSL."
        )
    raise ToolMissingError("\n".join(message))


def environments_of(project: Path) -> list[str]:
    """Retourne les environnements du projet, triés par nom."""
    inventories = Path(project) / "inventories"
    return sorted(entry.name for entry in inventories.iterdir() if entry.is_dir())


def check_project(project: Path) -> list[CheckResult]:
    """Vérifie un projet généré et retourne le résultat de chaque commande.

    La syntaxe est contrôlée pour chaque environnement : une erreur dans un
    inventaire de production ne doit pas passer inaperçue parce que celui de
    développement est correct.
    """
    project = Path(project)
    _require_project(project)
    require_tools()

    results = [
        _run(
            f"syntax-check ({env})",
            ["ansible-playbook", "-i", f"inventories/{env}", "playbooks/site.yml", "--syntax-check"],
            project,
        )
        for env in environments_of(project)
    ]
    results.append(_run("ansible-lint", ["ansible-lint", "--offline", "--nocolor"], project))
    return results


def _require_project(project: Path) -> None:
    """Vérifie que le répertoire ressemble à un projet généré."""
    if not project.is_dir():
        raise ForgeError(f"Répertoire de projet introuvable : {project}")
    missing = [marker for marker in PROJECT_MARKERS if not (project / marker).exists()]
    if missing:
        raise ForgeError(
            f"{project} ne ressemble pas à un projet ansible-forge "
            f"(éléments manquants : {', '.join(missing)})."
        )


def _run(label: str, command: list[str], cwd: Path) -> CheckResult:
    """Exécute une commande dans le projet et capture sa sortie."""
    completed = subprocess.run(  # noqa: S603 - commande construite à partir de REQUIRED_TOOLS
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        errors="replace",
    )
    return CheckResult(
        label=label,
        command=command,
        returncode=completed.returncode,
        output=(completed.stdout + completed.stderr).strip(),
    )
