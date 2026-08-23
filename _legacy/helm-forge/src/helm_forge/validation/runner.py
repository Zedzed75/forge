"""Exécution des contrôles de validation sur un projet généré.

Trois contrôles, dans cet ordre, du moins coûteux au plus exigeant :

1. ``helm lint``      — cohérence du chart et de ses values ;
2. ``helm template``  — le chart se rend réellement, pour chaque environnement ;
3. ``kubeconform``    — les manifestes rendus sont conformes aux schémas de
   l'API Kubernetes ciblée, en mode strict (aucun champ inconnu toléré).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..models import ProjectSpec
from .tools import require

#: Durée maximale accordée à un contrôle, en secondes.
TIMEOUT = 300


@dataclass
class Check:
    """Résultat d'un contrôle unitaire."""

    name: str
    ok: bool
    output: str = ""

    @property
    def status(self) -> str:
        return "OK" if self.ok else "ÉCHEC"


@dataclass
class Report:
    """Résultat complet d'une validation."""

    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai si tous les contrôles sont passés."""
        return all(check.ok for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    def summary(self) -> str:
        """Rend un résumé lisible, une ligne par contrôle."""
        return "\n".join(f"[{check.status}] {check.name}" for check in self.checks)


def validate(project: Path, spec: ProjectSpec) -> Report:
    """Valide un projet généré, environnement par environnement."""
    helm = require("helm")
    kubeconform = require("kubeconform")

    chart = project / "charts" / spec.app.name
    report = Report()

    for env in spec.environments:
        values = _values_args(chart, env.name)

        lint = _run([helm.path, "lint", str(chart), *values])
        report.checks.append(
            Check(f"helm lint ({env.name})", lint.returncode == 0, _output(lint))
        )

        rendered = _run(
            [
                helm.path,
                "template",
                spec.app.name,
                str(chart),
                "--namespace",
                env.namespace or spec.app.name,
                *values,
            ]
        )
        report.checks.append(
            Check(
                f"helm template ({env.name})", rendered.returncode == 0, _output(rendered)
            )
        )
        if rendered.returncode != 0:
            # Sans manifeste rendu, kubeconform n'a rien à valider.
            continue

        conform = _run(
            [
                kubeconform.path,
                "-strict",
                "-summary",
                "-kubernetes-version",
                spec.kubernetes.full_version,
                "-schema-location",
                "default",
                "-",
            ],
            stdin=rendered.stdout,
        )
        report.checks.append(
            Check(
                f"kubeconform -strict ({env.name})",
                conform.returncode == 0,
                _output(conform),
            )
        )

    return report


def _values_args(chart: Path, env_name: str) -> list[str]:
    """Construit les options --values, dans l'ordre de priorité de Helm."""
    args = ["--values", str(chart / "values.yaml")]
    env_values = chart / f"values-{env_name}.yaml"
    if env_values.is_file():
        args += ["--values", str(env_values)]
    return args


def _run(
    command: list[str], stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Exécute une commande externe en capturant sa sortie."""
    return subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    """Concatène sortie standard et sortie d'erreur, sans lignes vides finales."""
    return "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    )
