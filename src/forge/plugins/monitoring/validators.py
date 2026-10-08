"""Validation commands for the generated monitoring project.

Three checks, and the third one is the one that really counts:

1. `promtool check config` — the collector configuration holds up, and the rule
   files it designates exist and are valid. One per environment: each environment
   has its own configuration.
2. `promtool check rules` — the rules read back: valid PromQL, mandatory fields
   present, annotations that render.
3. `promtool test rules` — **the alerts actually fire**. A synthetic time series
   is given, evaluated at a given instant, and the alert is checked to appear with
   the right labels and the right annotations.

The third is the only one that checks something semantic. A rule can be
syntactically impeccable and never fire — a metric name that does not exist, a
misspelt label, a threshold on the wrong side of the comparison. Neither
`check config` nor `check rules` sees it; it is precisely the defect this domain
can produce, and it is a silent one.

None of these commands reaches a collector: `forge validate` checks files, never a
running infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins.monitoring import tree
from forge.plugins_api.types import Command

#: Maximum time granted to a command, in seconds.
TIMEOUT = 120

#: Installation message.
INSTALL_HINT = (
    "install promtool, shipped with Prometheus "
    "(https://prometheus.io/download/). On Windows, the WSL bridge looks for it "
    "in /opt/forge-tools/bin; a symbolic link is enough."
)

#: Shared environment variables. promtool asks for none: only colour is disabled,
#: so that the report stays comparable from one run to the next.
ENVIRONMENT: tuple[tuple[str, str], ...] = (("NO_COLOR", "1"),)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commands validating the generated monitoring, in execution order."""
    families = spec.monitoring.family_names()
    commands_list: list[Command] = []

    for env in spec.service.environments:
        commands_list.append(
            Command(
                label=f"promtool check config ({env.name})",
                tool="promtool",
                argv=("check", "config", tree.config_file(env.name)),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        commands_list.append(
            Command(
                label=f"promtool check rules ({env.name})",
                tool="promtool",
                argv=(
                    "check",
                    "rules",
                    # The paths are enumerated rather than passed as a glob: the
                    # commands are launched without a shell, and an unexpanded `*`
                    # would make promtool fail on a file it cannot find.
                    *(tree.rule_file(env.name, family) for family in families),
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )

    for env in spec.service.environments:
        commands_list.append(
            Command(
                label=f"promtool test rules ({env.name})",
                tool="promtool",
                argv=(
                    "test",
                    "rules",
                    *(tree.test_file(env.name, family) for family in families),
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    return commands_list
