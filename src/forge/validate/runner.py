"""Execution des commandes de validation declarees par les plugins.

Le plugin declare *quoi* lancer (`forge_validators` -> `list[Command]`) ; le
coeur decide *comment* : sous-processus ou repli WSL, timeout, capture,
chainage de stdin, et rapport. Modele de rapport repris de helm-forge, plus
complet que son equivalent ansible-forge (MIGRATION.md §5.4).

Un outil absent produit un message d'installation, jamais une trace Python.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from forge.errors import PluginError
from forge.plugins_api.types import Command
from forge.validate import tools, wsl

#: Etats possibles d'une verification.
Status = Literal["ok", "failed", "missing", "skipped", "timeout"]

#: Nombre de lignes de sortie conservees par commande en echec.
OUTPUT_LINES = 40


@dataclass
class Check:
    """Resultat d'une commande de validation."""

    #: Libelle declare par le plugin.
    label: str

    #: Binaire invoque.
    tool: str

    #: Etat final.
    status: Status

    #: Code de retour du processus, ou None si rien n'a ete lance.
    returncode: int | None = None

    #: Duree d'execution, en secondes.
    duration: float = 0.0

    #: Sortie standard complete (peut alimenter le stdin d'une autre commande).
    stdout: str = ""

    #: Sortie d'erreur, tronquee a l'affichage.
    stderr: str = ""

    #: Explication lisible en cas d'echec ou d'absence d'outil.
    detail: str = ""

    @property
    def ok(self) -> bool:
        """Vrai si la commande n'est pas un echec (succes ou saut assume)."""
        return self.status in ("ok", "skipped")

    def line(self) -> str:
        """Ligne de rapport, sans la sortie de l'outil."""
        marks = {
            "ok": "OK  ",
            "failed": "ECHEC",
            "missing": "ABSENT",
            "skipped": "SAUTE",
            "timeout": "DELAI",
        }
        return f"[{marks[self.status]}] {self.label} ({self.duration:.1f}s)"


@dataclass
class Report:
    """Ensemble des verifications d'un domaine."""

    domain: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai si aucune verification n'est en echec."""
        return all(check.ok for check in self.checks)

    def failures(self) -> list[Check]:
        """Verifications en echec, dans l'ordre d'execution."""
        return [check for check in self.checks if not check.ok]

    def skipped(self) -> list[Check]:
        """Verifications sautees : elles n'ont rien prouve."""
        return [check for check in self.checks if check.status == "skipped"]

    @property
    def all_skipped(self) -> bool:
        """Vrai si le domaine declarait des verifications et qu'aucune n'a tourne.

        Un rapport « vert » ou rien ne s'est execute est un piege : la CI doit le
        voir, sinon `--skip-missing` transforme une absence d'outil en succes.
        """
        return bool(self.checks) and all(
            check.status == "skipped" for check in self.checks
        )

    def summary(self) -> str:
        """Resume compact : un compte par etat."""
        counts: dict[str, int] = {}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        detail = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        return f"{self.domain} : {detail or 'aucune verification'}"


def _excerpt(text: str, lines: int = OUTPUT_LINES) -> str:
    """Extrait lisible d'une sortie d'outil : debut ET fin, jamais la fin seule.

    Les outils d'infrastructure annoncent la cause en **tete** de sortie
    (`Error: values.yaml:3 unknown key`) puis deroulent du contexte. Ne garder
    que la queue, comme le faisait la premiere version, revenait a effacer
    l'information utile et a n'afficher qu'un marqueur de troncature.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    parts = stripped.splitlines()
    if len(parts) <= lines:
        return "\n".join(parts)
    head = max(lines // 2, 1)
    tail = max(lines - head, 1)
    omitted = len(parts) - head - tail
    return "\n".join(
        [*parts[:head], f"  [... {omitted} ligne(s) omise(s) ...]", *parts[-tail:]]
    )


def run_command(
    command: Command, default_cwd: Path, stdin: str | None = None
) -> Check:
    """Execute une commande, nativement ou via WSL, et retourne son resultat."""
    cwd = Path(command.cwd or default_cwd)
    status = tools.probe(command.tool, command.requires_linux)
    if not status.available:
        return Check(
            label=command.label,
            tool=command.tool,
            status="missing",
            detail=tools.missing_message(
                command.tool, command.install_hint, command.requires_linux
            ),
        )

    started = time.monotonic()
    supplement = dict(command.env)
    try:
        if status.location == tools.WSL:
            completed = wsl.run_in_wsl(
                command.tool,
                command.argv,
                cwd,
                timeout=command.timeout,
                env=supplement,
                stdin=stdin,
            )
        else:
            completed = subprocess.run(
                [command.tool, *command.argv],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=command.timeout,
                env={**os.environ, **supplement} if supplement else None,
                input=stdin,
                errors="replace",
            )
    except subprocess.TimeoutExpired:
        return Check(
            label=command.label,
            tool=command.tool,
            status="timeout",
            duration=time.monotonic() - started,
            detail=f"delai de {command.timeout}s depasse",
        )
    except OSError as exc:
        return Check(
            label=command.label,
            tool=command.tool,
            status="failed",
            duration=time.monotonic() - started,
            detail=str(exc),
        )

    duration = time.monotonic() - started
    return Check(
        label=command.label,
        tool=command.tool,
        status="ok" if completed.returncode == 0 else "failed",
        returncode=completed.returncode,
        duration=duration,
        stdout=completed.stdout or "",
        stderr=_excerpt(completed.stderr or ""),
        detail="" if completed.returncode == 0 else _excerpt(
            completed.stderr or completed.stdout or ""
        ),
    )


def run_commands(
    domain: str,
    commands: list[Command],
    default_cwd: Path,
    *,
    skip_missing: bool = False,
) -> Report:
    """Execute les commandes dans l'ordre, en chainant les stdin demandes.

    `skip_missing` transforme un outil absent en saut assume plutot qu'en echec :
    utile en developpement, jamais en CI.
    """
    report = Report(domain=domain)
    outputs: dict[str, str] = {}
    declared = {command.label for command in commands}
    for command in commands:
        stdin = None
        if command.stdin_from is not None:
            if command.stdin_from not in declared:
                # Libelle source inexistant : c'est une faute dans le plugin, pas
                # un alea d'execution. La signaler comme un simple saut ferait
                # passer `forge validate` au vert sans avoir lance la commande.
                connus = ", ".join(sorted(declared)) or "aucun"
                raise PluginError(
                    f"le domaine '{domain}' chaine la commande « {command.label} » sur "
                    f"« {command.stdin_from} », qui n'est declaree nulle part "
                    f"(libelles connus : {connus})"
                )
            if command.stdin_from not in outputs:
                report.checks.append(
                    Check(
                        label=command.label,
                        tool=command.tool,
                        status="skipped",
                        detail=(
                            f"la commande source « {command.stdin_from} » n'a pas "
                            "produit de sortie exploitable"
                        ),
                    )
                )
                continue
            stdin = outputs[command.stdin_from]
        check = run_command(command, default_cwd, stdin=stdin)
        if check.status == "missing" and skip_missing:
            check.status = "skipped"
        if check.status == "ok":
            outputs[command.label] = check.stdout
        report.checks.append(check)
    return report
