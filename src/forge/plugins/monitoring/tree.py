"""Paths the monitoring domain writes, and what each of them contains.

The same role — and the same warning — as in the three other domains: it is the
only place that duplicates the knowledge of the template tree, and a test
confronts it with the real rendering (arbitration R3, PLAN.md).

One peculiarity: **the rules are written per environment, not once and for all**.
Two reasons, and they are independent — the thresholds differ (production
deserves tighter ones than development), and so does the namespace observed. A
rule shared between environments would therefore have to carry wide filters and
average thresholds, that is to say serve neither of the two well.
"""

from __future__ import annotations

from typing import Any, Final, NamedTuple


class Entry(NamedTuple):
    """A generated file and the sentence describing it."""

    path: str
    purpose: str


#: Directory of the collector configuration.
PROMETHEUS_DIR: Final[str] = "prometheus"

#: Directory of the alerting rules. Outside `prometheus/` and symmetrical with
#: `tests/`: the two read side by side, and a rule file has a test file at the
#: same relative path.
RULES_DIR: Final[str] = "rules"

#: Directory of the alert unit tests.
TESTS_DIR: Final[str] = "tests"

#: Directory of the dashboards.
DASHBOARDS_DIR: Final[str] = "grafana/dashboards"


def environment_dir(environment: str) -> str:
    """Configuration directory of an environment."""
    return f"{PROMETHEUS_DIR}/{environment}"


def rules_dir(environment: str) -> str:
    """Rules directory of an environment."""
    return f"{RULES_DIR}/{environment}"


def rule_file(environment: str, family: str) -> str:
    """Rule file of a family, within an environment."""
    return f"{rules_dir(environment)}/{family}.yml"


def test_file(environment: str, family: str) -> str:
    """Unit test file of a family, within an environment."""
    return f"{TESTS_DIR}/{environment}/{family}.yml"


def config_file(environment: str) -> str:
    """Collector configuration for an environment."""
    return f"{environment_dir(environment)}/prometheus.yml"


def dashboard_file(service_name: str) -> str:
    """Grafana dashboard of the service."""
    return f"{DASHBOARDS_DIR}/{service_name}.json"


def root_files(spec: Any) -> list[dict[str, str]]:
    """Files at the `monitoring/` level, configuration and rules aside."""
    entries = [
        {"path": "README.md", "purpose": "This file: what is watched, and how."},
        {
            "path": ".gitignore",
            "purpose": "Excludes the collector data and the local renderings.",
        },
        {
            "path": ".copier-answers.yml",
            "purpose": "Template answers, read back by `forge update`. Do not edit.",
        },
    ]
    if spec.monitoring.extras.makefile:
        entries.append(
            {
                "path": "Makefile",
                "purpose": "Shortcuts: `make check`, `make test`, `make check ENV=prod`.",
            }
        )
    return sorted(entries, key=lambda entry: entry["path"])


def environment_files(spec: Any, environment: str) -> list[dict[str, str]]:
    """Files specific to an environment, in reading order."""
    monitoring = spec.monitoring
    entries = [
        {
            "path": config_file(environment),
            "purpose": (
                "Collector configuration: targets, interval, rule files."
            ),
        }
    ]
    for family in monitoring.family_names():
        entries.append(
            {
                "path": rule_file(environment, family),
                "purpose": f"Alerting rules of the '{family}' family.",
            }
        )
    for family in monitoring.family_names():
        entries.append(
            {
                "path": test_file(environment, family),
                "purpose": (
                    f"Unit test of the '{family}' alerts, run by "
                    "`promtool test rules`."
                ),
            }
        )
    return entries


def expected_paths(spec: Any) -> list[str]:
    """Every path the domain writes, sorted."""
    paths = [entry["path"] for entry in root_files(spec)]
    for env in spec.service.environments:
        paths += [entry["path"] for entry in environment_files(spec, env.name)]
    if spec.monitoring.extras.dashboard:
        paths.append(dashboard_file(spec.service.name))
    return sorted(paths)


def dashboard_slot(spec: Any) -> list[dict[str, str]]:
    """Slot of the dashboard: one entry, or none.

    A pattern shared with the three other domains (arbitration R4, DESIGN.md §5.3).
    """
    return [{"name": spec.service.name}] if spec.monitoring.extras.dashboard else []
